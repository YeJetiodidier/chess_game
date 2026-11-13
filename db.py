"""Database layer for Vercel Postgres (Neon) with a SQLite fallback.

Vercel Postgres exposes a standard PostgreSQL connection string through
``POSTGRES_URL`` / ``DATABASE_URL``.  When no such URL is configured the app
transparently uses a local SQLite file so development works out of the box.

Passwords are stored as PBKDF2-HMAC-SHA256 digests with a per-user salt.
Legacy SHA-256 hashes from earlier builds are still accepted and are upgraded
on the next successful sign-in.
"""
import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager

from config import get_secret

POSTGRES_URL = (
    get_secret("POSTGRES_URL")
    or get_secret("DATABASE_URL")
    or get_secret("POSTGRES_URL_NON_POOLING")
).strip()
USE_POSTGRES = POSTGRES_URL.startswith(("postgres://", "postgresql://"))

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_chess.db")

PBKDF2_ITERATIONS = 240_000
_LEGACY_SALT = "chess_salt_"
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------
@contextmanager
def get_connection():
    """Yield ``(connection, cursor)`` for Postgres or SQLite and clean up."""
    if USE_POSTGRES:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(POSTGRES_URL, connect_timeout=15)
        try:
            yield conn, conn.cursor(cursor_factory=RealDictCursor)
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn, conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def _sql(query: str) -> str:
    """Translate ``?`` placeholders for Postgres."""
    if USE_POSTGRES:
        return query.replace("?", "%s")
    return query


def _columns(cursor, table: str):
    if USE_POSTGRES:
        cursor.execute(
            _sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = ?"
            ),
            (table,),
        )
        return {row["column_name"] for row in cursor.fetchall()}
    cursor.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cursor.fetchall()}


def _row_to_dict(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    return {key: row[key] for key in row.keys()}


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
def init_db():
    """Create tables/indexes and apply lightweight additive migrations."""
    with get_connection() as (conn, cur):
        if USE_POSTGRES:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(160) UNIQUE NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    elo INTEGER NOT NULL DEFAULT 1200,
                    avatar_url TEXT,
                    bio TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id SERIAL PRIMARY KEY,
                    external_id VARCHAR(80),
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    result VARCHAR(20),
                    moves TEXT,
                    fen_final TEXT,
                    pgn TEXT,
                    mode VARCHAR(40),
                    opponent VARCHAR(80),
                    user_color VARCHAR(8),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            for column, ddl in (
                ("avatar_url", "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT"),
                ("bio", "ALTER TABLE users ADD COLUMN IF NOT EXISTS bio TEXT"),
                ("last_seen", "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("external_id", "ALTER TABLE games ADD COLUMN IF NOT EXISTS external_id VARCHAR(80)"),
                ("pgn", "ALTER TABLE games ADD COLUMN IF NOT EXISTS pgn TEXT"),
                ("mode", "ALTER TABLE games ADD COLUMN IF NOT EXISTS mode VARCHAR(40)"),
                ("opponent", "ALTER TABLE games ADD COLUMN IF NOT EXISTS opponent VARCHAR(80)"),
                ("user_color", "ALTER TABLE games ADD COLUMN IF NOT EXISTS user_color VARCHAR(8)"),
            ):
                cur.execute(ddl)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_games_created ON games(created_at DESC)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_games_external ON games(external_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_elo ON users(elo DESC)")
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    elo INTEGER NOT NULL DEFAULT 1200,
                    avatar_url TEXT,
                    bio TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    external_id TEXT,
                    user_id INTEGER,
                    result TEXT,
                    moves TEXT,
                    fen_final TEXT,
                    pgn TEXT,
                    mode TEXT,
                    opponent TEXT,
                    user_color TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
            user_cols = _columns(cur, "users")
            if "avatar_url" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
            if "bio" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN bio TEXT")
            if "last_seen" not in user_cols:
                cur.execute("ALTER TABLE users ADD COLUMN last_seen TIMESTAMP")
            game_cols = _columns(cur, "games")
            if "external_id" not in game_cols:
                cur.execute("ALTER TABLE games ADD COLUMN external_id TEXT")
            if "pgn" not in game_cols:
                cur.execute("ALTER TABLE games ADD COLUMN pgn TEXT")
            if "mode" not in game_cols:
                cur.execute("ALTER TABLE games ADD COLUMN mode TEXT")
            if "opponent" not in game_cols:
                cur.execute("ALTER TABLE games ADD COLUMN opponent TEXT")
            if "user_color" not in game_cols:
                cur.execute("ALTER TABLE games ADD COLUMN user_color TEXT")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_games_created ON games(created_at DESC)")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_games_external ON games(external_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_elo ON users(elo DESC)")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    """Return a salted PBKDF2-HMAC-SHA256 digest string."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def _legacy_hash(password: str) -> str:
    return hashlib.sha256((_LEGACY_SALT + password).encode("utf-8")).hexdigest()


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a PBKDF2 or legacy SHA-256 hash."""
    if not stored_hash:
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        try:
            _, iterations, salt, expected = stored_hash.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
            )
            return hmac.compare_digest(digest.hex(), expected)
        except (ValueError, TypeError):
            return False
    return hmac.compare_digest(_legacy_hash(password), stored_hash)


def _needs_rehash(stored_hash: str) -> bool:
    return not (stored_hash or "").startswith("pbkdf2_sha256$")


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def create_user(username, email, password):
    """Create a user. Returns ``(success: bool, message: str)``."""
    username = (username or "").strip()
    email = (email or "").strip().lower()
    password = password or ""

    if not _USERNAME_RE.match(username):
        return False, "Username must be 3-30 characters (letters, numbers, _ . -)."
    if not _EMAIL_RE.match(email):
        return False, "Please enter a valid email address."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    try:
        with get_connection() as (conn, cur):
            cur.execute(
                _sql(
                    "INSERT INTO users (username, email, password_hash) "
                    "VALUES (?, ?, ?)"
                ),
                (username, email, hash_password(password)),
            )
        return True, "Account created successfully!"
    except Exception:
        return False, "Username or email already exists."


def verify_user(username_or_email, password):
    """Verify credentials and return the user dict, or ``None``."""
    identity = (username_or_email or "").strip()
    if not identity or not password:
        return None

    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT id, username, email, password_hash, elo, avatar_url, bio "
                "FROM users WHERE username = ? OR email = ?"
            ),
            (identity, identity.lower()),
        )
        row = _row_to_dict(cur.fetchone())
        if not row or not verify_password(password, row.get("password_hash")):
            return None

        if _needs_rehash(row.get("password_hash")):
            cur.execute(
                _sql("UPDATE users SET password_hash = ? WHERE id = ?"),
                (hash_password(password), row["id"]),
            )
        cur.execute(
            _sql("UPDATE users SET last_seen = CURRENT_TIMESTAMP WHERE id = ?"),
            (row["id"],),
        )
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"],
            "elo": row["elo"] if row["elo"] is not None else 1200,
            "avatar_url": row.get("avatar_url"),
            "bio": row.get("bio") or "",
        }


def get_user(user_id):
    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT id, username, email, elo, avatar_url, bio, created_at "
                "FROM users WHERE id = ?"
            ),
            (user_id,),
        )
        return _row_to_dict(cur.fetchone())


def get_user_by_username(username):
    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT id, username, email, elo, avatar_url, bio, created_at "
                "FROM users WHERE username = ?"
            ),
            ((username or "").strip(),),
        )
        return _row_to_dict(cur.fetchone())


def update_profile(user_id, bio=None, avatar_url=None):
    """Update optional profile fields; only provided values are changed."""
    fields, params = [], []
    if bio is not None:
        fields.append("bio = ?")
        params.append(bio.strip()[:280])
    if avatar_url is not None:
        fields.append("avatar_url = ?")
        params.append(avatar_url)
    if not fields:
        return
    params.append(user_id)
    with get_connection() as (conn, cur):
        cur.execute(_sql(f"UPDATE users SET {', '.join(fields)} WHERE id = ?"), tuple(params))


def update_password(user_id, new_password):
    if len(new_password or "") < 6:
        return False, "Password must be at least 6 characters."
    with get_connection() as (conn, cur):
        cur.execute(
            _sql("UPDATE users SET password_hash = ? WHERE id = ?"),
            (hash_password(new_password), user_id),
        )
    return True, "Password updated."


def update_elo(user_id, elo):
    with get_connection() as (conn, cur):
        cur.execute(
            _sql("UPDATE users SET elo = ? WHERE id = ?"),
            (max(100, int(elo)), user_id),
        )


def count_users():
    with get_connection() as (conn, cur):
        cur.execute("SELECT COUNT(*) AS n FROM users")
        row = _row_to_dict(cur.fetchone())
        return int(row["n"]) if row else 0


# ---------------------------------------------------------------------------
# Games & stats
# ---------------------------------------------------------------------------
def record_game(
    user_id,
    result,
    moves="",
    fen_final="",
    pgn=None,
    mode=None,
    opponent=None,
    user_color=None,
    external_id=None,
):
    """Persist a finished game and return its id (or ``None``)."""
    try:
        with get_connection() as (conn, cur):
            if external_id:
                cur.execute(
                    _sql("SELECT id FROM games WHERE external_id = ?"),
                    (external_id,),
                )
                existing = _row_to_dict(cur.fetchone())
                if existing:
                    return existing.get("id")
            cur.execute(
                _sql(
                    "INSERT INTO games "
                    "(external_id, user_id, result, moves, fen_final, pgn, mode, opponent, user_color) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
                ),
                (
                    external_id,
                    user_id,
                    result,
                    moves,
                    fen_final,
                    pgn,
                    mode,
                    opponent,
                    user_color,
                ),
            )
            if USE_POSTGRES:
                cur.execute("SELECT LASTVAL() AS id")
                row = _row_to_dict(cur.fetchone())
            else:
                row = {"id": cur.lastrowid}
            return row.get("id") if row else None
    except Exception:
        return None


def get_game_by_external_id(external_id):
    if not external_id:
        return None
    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT id, user_id, result, mode, external_id "
                "FROM games WHERE external_id = ?"
            ),
            (external_id,),
        )
        return _row_to_dict(cur.fetchone())


def get_user_games(user_id, limit=20):
    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT id, result, moves, fen_final, mode, opponent, user_color, created_at "
                "FROM games WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT ?"
            ),
            (user_id, int(limit)),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_recent_games(limit=10):
    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT g.id, g.result, g.mode, g.opponent, g.user_color, g.created_at, "
                "u.username FROM games g JOIN users u ON u.id = g.user_id "
                "ORDER BY g.created_at DESC, g.id DESC LIMIT ?"
            ),
            (int(limit),),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_user_stats(user_id):
    stats = {"games": 0, "wins": 0, "losses": 0, "draws": 0, "win_rate": 0.0}
    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT COUNT(*) AS games, "
                "SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) AS wins, "
                "SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) AS losses, "
                "SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) AS draws "
                "FROM games WHERE user_id = ?"
            ),
            (user_id,),
        )
        row = _row_to_dict(cur.fetchone())
    if row:
        stats["games"] = int(row.get("games") or 0)
        stats["wins"] = int(row.get("wins") or 0)
        stats["losses"] = int(row.get("losses") or 0)
        stats["draws"] = int(row.get("draws") or 0)
    if stats["games"]:
        stats["win_rate"] = round(100.0 * stats["wins"] / stats["games"], 1)
    return stats


def get_leaderboard(limit=10):
    with get_connection() as (conn, cur):
        cur.execute(
            _sql(
                "SELECT u.id, u.username, u.elo, u.avatar_url, "
                "COUNT(g.id) AS games, "
                "COALESCE(SUM(CASE WHEN g.result = 'win' THEN 1 ELSE 0 END), 0) AS wins "
                "FROM users u LEFT JOIN games g ON g.user_id = u.id "
                "GROUP BY u.id, u.username, u.elo, u.avatar_url "
                "ORDER BY u.elo DESC, u.username ASC LIMIT ?"
            ),
            (int(limit),),
        )
        return [_row_to_dict(r) for r in cur.fetchall()]


def get_user_rank(user_id):
    """Return the 1-based leaderboard position for a user."""
    rows = get_leaderboard(10000)
    for index, row in enumerate(rows, start=1):
        if row.get("id") == user_id:
            return index
    return None
