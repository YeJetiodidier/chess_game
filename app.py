"""Neural Chess — complete Streamlit application.

Screens
-------
* Login / Sign-up / Guest access
* Lobby with live challenges and progress
* Tournaments, Play Online, Play a Friend, vs Computer
* Puzzles, Lessons, Leaderboard
* Profile, history, avatar upload, and settings

Data lives in Vercel Postgres (Neon) when ``POSTGRES_URL`` is configured,
otherwise a local SQLite file is used. Avatars use Vercel Blob when
``BLOB_READ_WRITE_TOKEN`` is present, otherwise local ``uploads/avatars``.
"""
import os

import chess
import streamlit as st

import db
import storage
from components import ui
from components.board import API_BASE, render_interactive_board
from components.styles import THEME_CSS
from config import get_secret

_st_markdown = st.markdown


def _markdown(body, *args, **kwargs):
    if kwargs.get("unsafe_allow_html") and not args:
        kwargs.pop("unsafe_allow_html", None)
        return st.html(body, **kwargs)
    return _st_markdown(body, *args, **kwargs)


st.markdown = _markdown

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

NAV_PAGES = [
    "Lobby",
    "Tournaments",
    "Play Online",
    "Play a Friend",
    "Puzzles",
    "vs Computer",
    "Lessons",
    "Leaderboard",
    "Profile",
    "Settings",
]

DEMO_TOURNAMENTS = [
    {
        "name": "Midnight Blitz",
        "format": "3 + 0 · Arena",
        "time": "Tonight · 23:00",
        "prize": "500 credits",
        "desc": "Fast, unforgiving, and open to every rating.",
        "status": "Open",
    },
    {
        "name": "Brass Rapid Cup",
        "format": "10 + 5 · Swiss",
        "time": "Saturday · 18:00",
        "prize": "1,200 credits",
        "desc": "Seven rounds of classical rapid with increment.",
        "status": "Open",
    },
    {
        "name": "Weekend Arena",
        "format": "5 + 3 · Arena",
        "time": "Sunday · 15:00",
        "prize": "800 credits",
        "desc": "A relaxed arena to test your new opening ideas.",
        "status": "Soon",
    },
]

LESSONS = [
    {
        "title": "The Italian Game",
        "duration": "10 min",
        "level": "Beginner",
        "summary": "Build a healthy centre and develop every piece with purpose.",
        "points": [
            "Start with 1.e4 e5 2.Nf3 Nc6 3.Bc4.",
            "Aim for castling before move ten.",
            "Watch the f7 square — it is the weakest point in Black's camp.",
        ],
    },
    {
        "title": "Tactics: pins and skewers",
        "duration": "12 min",
        "level": "Intermediate",
        "summary": "Learn to spot the two most common line tactics in real games.",
        "points": [
            "A pin freezes a piece in front of something more valuable.",
            "Skewers attack the more valuable piece first.",
            "Look for aligned king, queen, and rook on a line.",
        ],
    },
    {
        "title": "Rook endgame essentials",
        "duration": "15 min",
        "level": "Advanced",
        "summary": "Convert small advantages with the Lucena and Philidor positions.",
        "points": [
            "Put your rook behind the passed pawn.",
            "The defending king belongs in front of the pawn.",
            "Know the Lucena bridge and the Philidor draw.",
        ],
    },
]

PUZZLES = [
    {
        "title": "Back-rank finish",
        "rating": 900,
        "fen": "6k1/5ppp/8/8/8/8/5PPP/R5K1 w - - 0 1",
        "uci": "a1a8",
        "san": "Ra8#",
        "prompt": "White to move. Find mate in one.",
        "explanation": "The rook slides to the eighth rank. Black's own pawns trap the king.",
    },
    {
        "title": "The open file",
        "rating": 1100,
        "fen": "6k1/5ppp/8/8/8/8/5PPP/3Q2K1 w - - 0 1",
        "uci": "d1d8",
        "san": "Qd8#",
        "prompt": "White to move. Find mate in one.",
        "explanation": "The queen uses the empty d-file and covers every escape square.",
    },
    {
        "title": "Smothered mate",
        "rating": 1300,
        "fen": "6rk/6pp/8/6N1/8/8/8/6K1 w - - 0 1",
        "uci": "g5f7",
        "san": "Nf7#",
        "prompt": "White to move. Find mate in one.",
        "explanation": "The knight jumps to f7 and Black's own pieces smother the king.",
    },
]


# ---------------------------------------------------------------------------
# Session & routing helpers
# ---------------------------------------------------------------------------
def _init_state():
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("nav", "Lobby")
    st.session_state.setdefault("nav_history", [])
    st.session_state.setdefault("_last_nav", st.session_state.get("nav", "Lobby"))
    st.session_state.setdefault("board_cfg", None)
    st.session_state.setdefault("ai_started", False)
    st.session_state.setdefault("online_started", False)
    st.session_state.setdefault("local_started", False)


def _set_nav(page: str):
    """Set the current page and remember it so history is not double-counted."""
    st.session_state.nav = page
    st.session_state["_last_nav"] = page


def _push_history(previous: str):
    history = st.session_state.setdefault("nav_history", [])
    if previous and (not history or history[-1] != previous):
        history.append(previous)
    # keep a short, sane history
    st.session_state.nav_history = history[-20:]


def _go(page: str):
    current = st.session_state.get("nav", "Lobby")
    if page and page != current:
        _push_history(current)
    _set_nav(page)


def _go_back():
    history = st.session_state.get("nav_history") or []
    target = history.pop() if history else "Lobby"
    st.session_state.nav_history = history
    _set_nav(target)


def _sync_nav_history():
    """Record navigation that bypasses _go, such as the sidebar radio."""
    current = st.session_state.get("nav", "Lobby")
    last = st.session_state.get("_last_nav", current)
    if current != last:
        _push_history(last)
        st.session_state["_last_nav"] = current


def _sign_out():
    st.session_state.authenticated = False
    st.session_state.user = None
    _set_nav("Lobby")
    st.session_state.nav_history = []
    st.session_state.board_cfg = None
    for key in ("ai_started", "online_started", "local_started", "tournament_joined"):
        st.session_state.pop(key, None)
    st.rerun()


def _sign_in(user):
    st.session_state.authenticated = True
    st.session_state.user = user
    _set_nav("Lobby")
    st.session_state.nav_history = []
    st.session_state.board_cfg = None
    st.rerun()


def _refresh_user():
    user = st.session_state.get("user")
    if not user or not user.get("id"):
        return
    fresh = db.get_user(user["id"])
    if fresh:
        # preserve credentials already loaded (e.g. email) if the lookup omits them
        st.session_state.user = {**user, **fresh}
    else:
        _sign_out()


def _user_name() -> str:
    user = st.session_state.get("user") or {}
    return user.get("username") or "Player"


def _user_id():
    user = st.session_state.get("user") or {}
    return user.get("id") or 0


def _fmt_date(value) -> str:
    if hasattr(value, "strftime"):
        return value.strftime("%b %Y")
    if value:
        return str(value)[:10]
    return "—"


def _ai_cfg(side: str, level: str, time_control: str, fen: str = START_FEN):
    name = _user_name()
    if side == "w":
        white, black = "Neural AI", name
    elif side == "both":
        white, black = "Neural AI (White)", "Neural AI (Black)"
    else:
        white, black = name, "Neural AI"
    return {
        "fen": fen,
        "white_name": white,
        "black_name": black,
        "player_name": name,
        "opponent_name": "Neural AI",
        "ai_side": side,
        "ai_auto": True,
        "ai_level": level,
        "mode": "ai",
        "user_color": {"w": "b", "b": "w"}.get(side),
        "title": "Rated game · Neural engine",
        "time": time_control,
    }


def _start_default_ai():
    st.session_state.board_cfg = _ai_cfg("b", "mixed", "10 + 0")
    st.session_state.ai_started = True
    st.session_state.nav = "vs Computer"


# ---------------------------------------------------------------------------
# Shared layout
# ---------------------------------------------------------------------------
def _sidebar():
    user = st.session_state.get("user") or {}
    with st.sidebar:
        st.markdown(ui.brand_html(), unsafe_allow_html=True)
        st.button(
            "New Game",
            type="primary",
            use_container_width=True,
            key="side_new_game",
            on_click=_start_default_ai,
        )

        st.markdown('<div class="side-label">Arena</div>', unsafe_allow_html=True)
        st.radio(
            "Navigation",
            NAV_PAGES,
            key="nav",
            label_visibility="collapsed",
        )

        st.markdown('<div class="side-label">Account</div>', unsafe_allow_html=True)
        meta = f"{int(user.get('elo') or 1200)} Elo" if user.get("id") else "Guest mode"
        st.markdown(
            f"""
            <div class="user-chip">
                {ui.avatar_html(user.get("username", "Guest"), user.get("avatar_url"), 40)}
                <div>
                    <div class="name">{ui.esc(user.get("username", "Guest"))}</div>
                    <div class="meta">{ui.esc(meta)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown('<div class="side-label">System</div>', unsafe_allow_html=True)
        db_label = "Vercel Postgres" if db.USE_POSTGRES else "Local SQLite"
        api_dot = "gold" if API_BASE else "off"
        st.markdown(
            f"""
            <div class="side-card">
                <div class="statusline"><span class="status-dot"></span>{ui.esc(db_label)}</div>
                <div class="statusline"><span class="status-dot"></span>{ui.esc(storage.storage_backend())}</div>
                <div class="statusline"><span class="status-dot {api_dot}"></span>Prediction API</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Sign out",
            use_container_width=True,
            key="side_sign_out",
            on_click=_sign_out,
        )


def _page_top(eyebrow: str, title: str, sub: str = "", action_label: str = None, action_page: str = None, key: str = None):
    left, right = st.columns([4.4, 1])
    with left:
        st.markdown(
            f"""
            <div class="page-top">
                <div>
                    <div class="eyebrow">{ui.esc(eyebrow)}</div>
                    <div class="title">{ui.esc(title)}</div>
                    <div class="sub">{ui.esc(sub)}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        if action_label and action_page:
            st.button(
                action_label,
                type="primary",
                use_container_width=True,
                key=key or f"top_{action_page.lower().replace(' ', '_')}",
                on_click=_go,
                args=(action_page,),
            )


def _back_bar():
    history = st.session_state.get("nav_history") or []
    if not history:
        return
    prev = history[-1]
    st.button(
        f"← Back to {prev}",
        key=f"back_{st.session_state.get('nav', 'page')}",
        on_click=_go_back,
    )


def _render_board(cfg):
    st.markdown(
        f"""
        <div class="board-caption">
            <span class="label">{ui.esc(cfg.get("title", "Interactive board"))}</span>
            <span class="value">{ui.esc(cfg.get("time", ""))}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_interactive_board(
        fen=cfg.get("fen") or START_FEN,
        height=680,
        player_name=cfg.get("player_name"),
        opponent_name=cfg.get("opponent_name"),
        white_name=cfg.get("white_name"),
        black_name=cfg.get("black_name"),
        ai_side=cfg.get("ai_side", "b"),
        ai_auto=cfg.get("ai_auto", True),
        ai_level=cfg.get("ai_level", "top"),
        mode=cfg.get("mode", "ai"),
        user_id=_user_id(),
        username=_user_name(),
        user_color=cfg.get("user_color"),
    )


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def _auth_page():
    st.markdown(
        """
        <style>
            [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none !important; }
            .block-container { padding-top: 2.4rem !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.12, 0.88], gap="large")
    with left:
        st.markdown(
            ui.brand_html("The thinking player's arena")
            + """
            <div class="auth-hero">
                <div class="hero-kicker">Est. for the patient</div>
                <h1 class="auth-hero-title">Every move<br><span class="accent">has a reason.</span></h1>
                <p class="auth-hero-sub">
                    Play, study, and train against a neural engine that learns how you
                    think. Your games, rating, and progress stay with you.
                </p>
                <div class="auth-points">
                    <div class="auth-point">
                        <div class="auth-point-icon">&#9823;</div>
                        <div><b>Adaptive opponent</b><div class="muted tiny">A model that adjusts to your style.</div></div>
                    </div>
                    <div class="auth-point">
                        <div class="auth-point-icon">&#9822;</div>
                        <div><b>Live analysis</b><div class="muted tiny">Top predictions on every position.</div></div>
                    </div>
                    <div class="auth-point">
                        <div class="auth-point-icon">&#9819;</div>
                        <div><b>Your arena</b><div class="muted tiny">Profiles, history, and a global ladder.</div></div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with right:
        with st.container(border=True):
            st.markdown('<div class="auth-card-title">Welcome</div>', unsafe_allow_html=True)
            st.markdown(
                '<div class="auth-card-sub">Sign in to continue, or create a free account.</div>',
                unsafe_allow_html=True,
            )

            login_tab, signup_tab = st.tabs(["Login", "Sign Up"])

            with login_tab:
                with st.form("login_form"):
                    identity = st.text_input(
                        "Username or Email",
                        key="login_identity",
                        placeholder="e.g. grandmaster",
                    )
                    password = st.text_input(
                        "Password",
                        type="password",
                        key="login_password",
                        placeholder="Your password",
                    )
                    login_submit = st.form_submit_button(
                        "Login", type="primary", use_container_width=True
                    )
                if login_submit:
                    if not identity or not password:
                        st.error("Enter your username (or email) and password.")
                    else:
                        with st.spinner("Checking your credentials…"):
                            user = db.verify_user(identity, password)
                        if user:
                            _sign_in(user)
                        else:
                            st.error("Those credentials do not match our records.")

                if st.button("Continue as Guest", use_container_width=True, key="guest_login"):
                    _sign_in(
                        {
                            "id": 0,
                            "username": "Guest Player",
                            "email": "guest@local",
                            "elo": 1200,
                            "avatar_url": None,
                            "bio": "",
                        }
                    )

                st.markdown(
                    '<div class="auth-switch">New here? <b>Create an account</b> above.</div>',
                    unsafe_allow_html=True,
                )

            with signup_tab:
                with st.form("signup_form"):
                    username = st.text_input(
                        "Username", key="signup_username", placeholder="e.g. magnus2026"
                    )
                    email = st.text_input(
                        "Email", key="signup_email", placeholder="you@domain.com"
                    )
                    new_password = st.text_input(
                        "Password",
                        type="password",
                        key="signup_password",
                        placeholder="At least 6 characters",
                    )
                    confirm_password = st.text_input(
                        "Re-enter Password",
                        type="password",
                        key="signup_confirm",
                        placeholder="Repeat your password",
                    )
                    signup_submit = st.form_submit_button(
                        "Sign Up", type="primary", use_container_width=True
                    )
                if signup_submit:
                    if not username or not email or not new_password:
                        st.error("All fields are required.")
                    elif new_password != confirm_password:
                        st.error("Passwords do not match.")
                    else:
                        with st.spinner("Creating your account…"):
                            ok, message = db.create_user(username, email, new_password)
                        if not ok:
                            st.error(message)
                        else:
                            with st.spinner("Setting up your profile…"):
                                user = db.verify_user(username, new_password)
                            if user:
                                _sign_in(user)
                            else:
                                st.success(message + " You can now log in.")

                st.markdown(
                    '<div class="auth-switch">Already have an account? <b>Log in</b> above.</div>',
                    unsafe_allow_html=True,
                )


# ---------------------------------------------------------------------------
# Lobby
# ---------------------------------------------------------------------------
def _lobby():
    _back_bar()
    user = st.session_state.get("user") or {}
    uid = _user_id()
    stats = db.get_user_stats(uid) if uid else {"games": 0, "wins": 0, "losses": 0, "draws": 0, "win_rate": 0}
    rank = db.get_user_rank(uid) if uid else None
    total_players = db.count_users()

    st.markdown(
        f"""
        <div class="hero">
            <div class="hero-kicker">New Game</div>
            <h1 class="hero-title">Find your next <span class="accent">challenge.</span></h1>
            <div class="hero-sub">
                Play someone at your level, sharpen your tactics, or study a lesson.
                The arena is open. Choose how you want to grow today.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    b1, b2, _ = st.columns([1, 1, 2])
    with b1:
        st.button(
            "Play Online",
            type="primary",
            use_container_width=True,
            key="lobby_play_online",
            on_click=_go,
            args=("Play Online",),
        )
    with b2:
        st.button(
            "vs Computer",
            use_container_width=True,
            key="lobby_vs_computer",
            on_click=_go,
            args=("vs Computer",),
        )

    st.markdown('<div class="section-head"><div class="section-kicker">Overview</div><div class="section-title">Your arena at a glance</div></div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(ui.stat_card("Rating", int(user.get("elo") or 1200), "Current Elo", "gold"), unsafe_allow_html=True)
    with c2:
        st.markdown(ui.stat_card("Games", stats["games"], f'{stats["wins"]}W · {stats["losses"]}L · {stats["draws"]}D'), unsafe_allow_html=True)
    with c3:
        st.markdown(ui.stat_card("Win rate", f'{stats["win_rate"]}%', "Across all games", "green"), unsafe_allow_html=True)
    with c4:
        rank_text = f"#{rank}" if rank else "—"
        st.markdown(ui.stat_card("Global rank", rank_text, f"{total_players} players", "gold"), unsafe_allow_html=True)

    recent = db.get_recent_games(6)
    if recent:
        items = [
            {
                "name": game.get("opponent") or game.get("username") or "Neural AI",
                "meta": f"{game.get('mode') or 'Rated'} · {game.get('result', '—').title()}",
                "time": "10:00",
                "tag": "Recent",
            }
            for game in recent
        ]
        caption = "Recent games across the arena."
    else:
        items = ui.demo_challenges()
        caption = "Practice lobby — sample opponents while the arena fills up."

    left, right = st.columns([1.55, 1])
    with left:
        st.markdown('<div class="section-head"><div class="section-kicker">Play Online</div><div class="section-title">Open challenges</div><div class="section-sub">Play someone at your level.</div></div>', unsafe_allow_html=True)
        st.markdown(ui.challenge_rows(items), unsafe_allow_html=True)
        st.caption(caption)
    with right:
        st.markdown('<div class="section-head"><div class="section-kicker">Your profile</div><div class="section-title">Progress</div></div>', unsafe_allow_html=True)
        next_rank = f"#{rank - 1}" if rank and rank > 1 else "Top board"
        st.markdown(
            f"""
            <div class="side-card">
                {ui.avatar_html(user.get("username", "Guest"), user.get("avatar_url"), 54)}
                <div style="height:10px"></div>
                <div class="statusline"><span class="status-dot gold"></span><b>{int(user.get("elo") or 1200)}</b>&nbsp;Elo</div>
                <div class="statusline"><span class="status-dot"></span>{stats["games"]} games completed</div>
                <div class="statusline"><span class="status-dot off"></span>Next target: {ui.esc(next_rank)}</div>
                <div class="divider"></div>
                <div class="muted tiny">Keep playing rated games to climb the ladder.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Open profile",
            use_container_width=True,
            key="lobby_profile",
            on_click=_go,
            args=("Profile",),
        )

    st.markdown('<div class="section-head"><div class="section-kicker">Improve</div><div class="section-title">Keep the edge</div></div>', unsafe_allow_html=True)
    f1, f2, f3 = st.columns(3)
    features = [
        (f1, "Tournaments", "Compete on a schedule.", "Arena and Swiss events.", "Tournaments", "lobby_tournaments"),
        (f2, "Solve Puzzles", "Find the right move.", "Short tactical tests.", "Puzzles", "lobby_puzzles"),
        (f3, "Lesson", "Improve yourself.", "10 minutes at a time.", "Lessons", "lobby_lessons"),
    ]
    for column, title, text, meta, page, key in features:
        with column:
            st.markdown(
                f"""
                <div class="feature-card">
                    <div class="feature-kicker">{ui.esc(page)}</div>
                    <div class="feature-title">{ui.esc(title)}</div>
                    <div class="feature-text">{ui.esc(text)}</div>
                    <div class="feature-meta">{ui.esc(meta)}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                f"Open {page}",
                use_container_width=True,
                key=key,
                on_click=_go,
                args=(page,),
            )


# ---------------------------------------------------------------------------
# Tournaments
# ---------------------------------------------------------------------------
def _tournaments():
    _back_bar()
    _page_top("Compete", "Tournaments", "Arena and Swiss events for every time control.")
    joined = st.session_state.get("tournament_joined")
    if joined:
        st.success(f"You are registered for {joined}. We will remind you before the first round.")

    columns = st.columns(3)
    for index, tournament in enumerate(DEMO_TOURNAMENTS):
        with columns[index % 3]:
            st.markdown(
                f"""
                <div class="feature-card">
                    <div class="feature-kicker">{ui.esc(tournament["status"])}</div>
                    <div class="feature-title">{ui.esc(tournament["name"])}</div>
                    <div class="feature-text">{ui.esc(tournament["desc"])}</div>
                    <div class="divider"></div>
                    <div class="statusline"><span class="status-dot gold"></span>{ui.esc(tournament["format"])}</div>
                    <div class="statusline"><span class="status-dot off"></span>{ui.esc(tournament["time"])}</div>
                    <div class="feature-meta">Prize pool: {ui.esc(tournament["prize"])}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.button(
                "Join tournament",
                use_container_width=True,
                key=f"join_tournament_{index}",
                on_click=lambda name=tournament["name"]: st.session_state.update(tournament_joined=name),
            )


# ---------------------------------------------------------------------------
# Play Online
# ---------------------------------------------------------------------------
def _reset_online():
    st.session_state.online_started = False


def _start_online():
    time_control = st.session_state.get("online_time", "10 + 0")
    level_choice = st.session_state.get("online_level", "Intermediate")
    level = {"Beginner": "random", "Intermediate": "mixed", "Advanced": "top", "Master": "top"}.get(level_choice, "top")
    st.session_state.board_cfg = _ai_cfg("b", level, time_control)
    st.session_state.board_cfg["mode"] = "online"
    st.session_state.board_cfg["title"] = f"Matchmaking · {level_choice}"
    st.session_state.online_started = True


def _play_online():
    _back_bar()
    _page_top("Play Online", "Play someone at your level", "Matched against the neural ladder in seconds.")
    cfg = st.session_state.get("board_cfg") or {}
    if st.session_state.get("online_started") and cfg.get("mode") == "online":
        top_left, top_right = st.columns([3, 1])
        with top_left:
            st.caption(f"Opponent strength: {st.session_state.get('online_level', 'Intermediate')}")
        with top_right:
            st.button("New search", use_container_width=True, key="online_new_search", on_click=_reset_online)
        _render_board(cfg)
        return

    left, right = st.columns([1.1, 1])
    with left:
        with st.container(border=True):
            st.markdown('<div class="section-kicker">Matchmaking</div>', unsafe_allow_html=True)
            st.markdown('<div class="section-title">Choose your table</div>', unsafe_allow_html=True)
            st.radio(
                "Time control",
                ["3 + 0", "5 + 3", "10 + 0", "15 + 10"],
                index=2,
                horizontal=True,
                key="online_time",
            )
            st.radio(
                "Opponent strength",
                ["Beginner", "Intermediate", "Advanced", "Master"],
                index=1,
                horizontal=True,
                key="online_level",
            )
            st.button(
                "Find opponent",
                type="primary",
                use_container_width=True,
                key="online_find",
                on_click=_start_online,
            )
            st.caption("The neural engine plays the opponent side automatically.")
    with right:
        st.markdown('<div class="section-head"><div class="section-kicker">Near you</div><div class="section-title">Players in the arena</div></div>', unsafe_allow_html=True)
        rows = db.get_leaderboard(8)
        if rows:
            items = [
                {
                    "name": row.get("username"),
                    "meta": f'{int(row.get("elo") or 1200)} Elo · {int(row.get("games") or 0)} games',
                    "time": "10:00",
                    "tag": "Rated",
                    "avatar_url": row.get("avatar_url"),
                }
                for row in rows
            ]
            st.markdown(ui.challenge_rows(items), unsafe_allow_html=True)
        else:
            st.markdown(ui.empty_state("The arena is quiet", "Be the first player to join the ladder."), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Play a Friend
# ---------------------------------------------------------------------------
def _reset_local():
    st.session_state.local_started = False


def _start_local():
    user = _user_name()
    st.session_state.board_cfg = {
        "fen": START_FEN,
        "white_name": st.session_state.get("friend_white") or user,
        "black_name": st.session_state.get("friend_black") or "Friend",
        "player_name": st.session_state.get("friend_white") or user,
        "opponent_name": st.session_state.get("friend_black") or "Friend",
        "ai_side": "",
        "ai_auto": False,
        "ai_level": "top",
        "mode": "local",
        "title": "Local game · Pass and play",
        "time": st.session_state.get("friend_time", "10 + 0"),
    }
    st.session_state.local_started = True


def _play_friend():
    _back_bar()
    _page_top("Play a Friend", "Two players, one board", "Pass the device and play a relaxed local game.")
    cfg = st.session_state.get("board_cfg") or {}
    if st.session_state.get("local_started") and cfg.get("mode") == "local":
        left, right = st.columns([3, 1])
        with left:
            st.caption(f'{cfg.get("white_name")} (White) vs {cfg.get("black_name")} (Black)')
        with right:
            st.button("End game", use_container_width=True, key="local_end", on_click=_reset_local)
        _render_board(cfg)
        return

    with st.container(border=True):
        st.markdown('<div class="section-kicker">Local table</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Set the players</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.text_input("White player", value=_user_name(), key="friend_white")
        with c2:
            st.text_input("Black player", value="Friend", key="friend_black")
        st.radio(
            "Time control",
            ["3 + 0", "5 + 3", "10 + 0", "15 + 10"],
            index=2,
            horizontal=True,
            key="friend_time",
        )
        st.button(
            "Start local game",
            type="primary",
            use_container_width=True,
            key="friend_start",
            on_click=_start_local,
        )
        st.caption("AI auto-play is off. Both sides are controlled by the players.")


# ---------------------------------------------------------------------------
# vs Computer
# ---------------------------------------------------------------------------
def _reset_ai():
    st.session_state.ai_started = False


def _start_ai():
    side = st.session_state.get("ai_side_choice", "Black")
    side_value = {"Black": "b", "White": "w", "Both": "both"}.get(side, "b")
    level_choice = st.session_state.get("ai_level_choice", "Balanced")
    level = {"Focused": "top", "Balanced": "mixed", "Surprise": "random"}.get(level_choice, "mixed")
    time_control = st.session_state.get("ai_time", "10 + 0")
    st.session_state.board_cfg = _ai_cfg(side_value, level, time_control)
    st.session_state.ai_started = True


def _vs_computer():
    _back_bar()
    _page_top("vs Computer", "Train against the neural engine", "Choose a side and a temperament. The board does the rest.")
    cfg = st.session_state.get("board_cfg") or {}
    if st.session_state.get("ai_started") and cfg.get("mode") == "ai":
        left, right = st.columns([3, 1])
        with left:
            st.caption(f'{cfg.get("white_name")} (White) vs {cfg.get("black_name")} (Black)')
        with right:
            st.button("New game", use_container_width=True, key="ai_new_game", on_click=_reset_ai)
        _render_board(cfg)
        return

    with st.container(border=True):
        st.markdown('<div class="section-kicker">Engine setup</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Choose your opponent</div>', unsafe_allow_html=True)
        st.radio(
            "AI side",
            ["Black", "White", "Both"],
            index=0,
            horizontal=True,
            key="ai_side_choice",
        )
        st.radio(
            "Temperament",
            ["Focused", "Balanced", "Surprise"],
            index=1,
            horizontal=True,
            key="ai_level_choice",
        )
        st.radio(
            "Time control",
            ["3 + 0", "5 + 3", "10 + 0", "15 + 10"],
            index=2,
            horizontal=True,
            key="ai_time",
        )
        st.button(
            "Start game",
            type="primary",
            use_container_width=True,
            key="ai_start",
            on_click=_start_ai,
        )
        st.caption("Focused always plays the top prediction. Balanced mixes the top three. Surprise samples the list.")


# ---------------------------------------------------------------------------
# Puzzles
# ---------------------------------------------------------------------------
def _puzzles():
    _back_bar()
    _page_top("Solve Puzzles", "Find the right move", "Short positions with one clean finish.")
    titles = [f'{puzzle["title"]} · {puzzle["rating"]}' for puzzle in PUZZLES]
    choice = st.selectbox("Puzzle", titles, key="puzzle_choice")
    puzzle = PUZZLES[titles.index(choice)]

    left, right = st.columns([1.55, 1])
    with left:
        _render_board(
            {
                "fen": puzzle["fen"],
                "player_name": "You",
                "opponent_name": "Puzzle",
                "white_name": "White",
                "black_name": "Black",
                "ai_side": "",
                "ai_auto": False,
                "ai_level": "top",
                "mode": "puzzle",
                "title": puzzle["title"],
                "time": f'Rating {puzzle["rating"]}',
            }
        )
    with right:
        st.markdown(
            f"""
            <div class="feature-card">
                <div class="feature-kicker">Puzzle</div>
                <div class="feature-title">{ui.esc(puzzle["title"])}</div>
                <div class="feature-text">{ui.esc(puzzle["prompt"])}</div>
                <div class="feature-meta">Rating {puzzle["rating"]}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        reveal_key = f'revealed_{puzzle["uci"]}'
        if st.button("Reveal solution", type="primary", use_container_width=True, key="reveal_puzzle"):
            st.session_state[reveal_key] = True
        if st.session_state.get(reveal_key):
            st.success(f'Solution: {puzzle["san"]}')
            st.caption(puzzle["explanation"])
        st.caption("Try the move on the board first, then reveal the answer.")


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------
def _lessons():
    _back_bar()
    _page_top("Lesson", "Improve yourself", "Ten focused minutes is enough to move the needle.")
    for lesson in LESSONS:
        with st.expander(f'{lesson["title"]} · {lesson["duration"]}'):
            st.markdown(f'**{lesson["level"]}** · {lesson["summary"]}')
            for point in lesson["points"]:
                st.markdown(f"- {point}")


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------
def _leaderboard():
    _back_bar()
    _page_top("Arena", "Leaderboard", "The sharpest players on the Neural Chess ladder.")
    rows = db.get_leaderboard(25)
    uid = _user_id()
    top_rating = rows[0]["elo"] if rows else 1200
    rank = db.get_user_rank(uid) if uid else None

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(ui.stat_card("Players", len(rows), "On the ladder"), unsafe_allow_html=True)
    with c2:
        st.markdown(ui.stat_card("Top rating", int(top_rating), "Current leader", "gold"), unsafe_allow_html=True)
    with c3:
        st.markdown(ui.stat_card("Your rank", f"#{rank}" if rank else "—", "Keep climbing", "green"), unsafe_allow_html=True)

    if not rows:
        st.markdown(ui.empty_state("No rated games yet", "Finish a game to put the first name on the board."), unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-head"><div class="section-kicker">Top 25</div><div class="section-title">Global standings</div></div>', unsafe_allow_html=True)
        st.markdown(ui.leaderboard_table(rows, uid), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
def _profile():
    _back_bar()
    user = st.session_state.get("user") or {}
    uid = _user_id()
    _page_top("Account", "Your profile", "A record of the games you have played and the player you are becoming.")

    if not uid:
        st.markdown(
            ui.empty_state("You are browsing as a guest", "Create an account to save games, upload an avatar, and join the leaderboard."),
            unsafe_allow_html=True,
        )
        st.button(
            "Create an account",
            type="primary",
            key="guest_create_account",
            on_click=_sign_out,
        )
        return

    stats = db.get_user_stats(uid)
    rank = db.get_user_rank(uid)
    st.markdown(
        f"""
        <div class="hero" style="padding:26px 30px">
            <div style="display:flex; gap:18px; align-items:center; flex-wrap:wrap">
                {ui.avatar_html(user.get("username"), user.get("avatar_url"), 82)}
                <div>
                    <div class="hero-kicker">Member since {ui.esc(_fmt_date(user.get("created_at")))} · {ui.esc(user.get("email") or "No email on file")}</div>
                    <div class="hero-title" style="font-size:2rem">{ui.esc(user.get("username"))}</div>
                    <div class="hero-sub" style="margin-top:6px">{ui.esc(user.get("bio") or "No bio yet. Tell the arena who you are.")}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(ui.stat_card("Rating", int(user.get("elo") or 1200), "Elo", "gold"), unsafe_allow_html=True)
    with c2:
        st.markdown(ui.stat_card("Games", stats["games"], f'{stats["wins"]} wins'), unsafe_allow_html=True)
    with c3:
        st.markdown(ui.stat_card("Win rate", f'{stats["win_rate"]}%', "Lifetime", "green"), unsafe_allow_html=True)
    with c4:
        st.markdown(ui.stat_card("Rank", f"#{rank}" if rank else "—", "Global", "gold"), unsafe_allow_html=True)

    left, right = st.columns([1, 1])
    with left:
        st.markdown('<div class="section-head"><div class="section-kicker">Identity</div><div class="section-title">Avatar</div></div>', unsafe_allow_html=True)
        uploaded = st.file_uploader(
            "Upload a new avatar",
            type=["png", "jpg", "jpeg", "webp", "gif"],
            key="avatar_upload",
        )
        if uploaded is not None:
            st.image(uploaded, width=110)
            if st.button("Save avatar", type="primary", key="save_avatar"):
                with st.spinner("Uploading your avatar…"):
                    url, error = storage.upload_avatar(uid, uploaded.getvalue())
                if url:
                    old = user.get("avatar_url")
                    db.update_profile(uid, avatar_url=url)
                    if old:
                        storage.delete_avatar(old)
                    st.success("Avatar updated.")
                    st.rerun()
                else:
                    st.error(error)
        st.caption("PNG, JPG, WEBP, or GIF. Maximum 2 MB. Stored in Vercel Blob in production.")

    with right:
        st.markdown('<div class="section-head"><div class="section-kicker">Profile</div><div class="section-title">About you</div></div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="side-card" style="margin-bottom:14px">
                <div class="statusline"><span class="status-dot gold"></span>Email</div>
                <div class="muted tiny" style="margin-top:6px; word-break:break-word">{ui.esc(user.get("email") or "Not set")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("bio_form"):
            bio = st.text_area("Bio", value=user.get("bio") or "", max_chars=280, key="bio_text")
            save_bio = st.form_submit_button("Save profile", type="primary", use_container_width=True)
        if save_bio:
            db.update_profile(uid, bio=bio)
            st.success("Profile saved.")
            st.rerun()

    st.markdown('<div class="section-head"><div class="section-kicker">History</div><div class="section-title">Recent games</div></div>', unsafe_allow_html=True)
    games = db.get_user_games(uid, 15)
    if games:
        st.markdown(ui.game_history_table(games), unsafe_allow_html=True)
    else:
        st.markdown(ui.empty_state("No games yet", "Play a rated game and it will appear here."), unsafe_allow_html=True)

    with st.expander("Change password"):
        with st.form("password_form"):
            current = st.text_input("Current password", type="password", key="password_current")
            new = st.text_input("New password", type="password", key="password_new")
            confirm = st.text_input("Confirm new password", type="password", key="password_confirm")
            change = st.form_submit_button("Update password", type="primary")
        if change:
            if not current or not new:
                st.error("Fill in both password fields.")
            elif new != confirm:
                st.error("New passwords do not match.")
            elif db.verify_user(user.get("username"), current):
                ok, message = db.update_password(uid, new)
                if ok:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("Current password is incorrect.")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
def _settings():
    _back_bar()
    _page_top("System", "Settings", "Connection, storage, and account controls.")
    user = st.session_state.get("user") or {}
    model_path = os.path.join(BASE_DIR, "model.pt")
    profiles_dir = os.path.join(BASE_DIR, "profiles")
    profile_count = len(os.listdir(profiles_dir)) if os.path.isdir(profiles_dir) else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(ui.stat_card("Database", "Vercel" if db.USE_POSTGRES else "SQLite", "Postgres / Neon" if db.USE_POSTGRES else "Local fallback", "gold"), unsafe_allow_html=True)
    with c2:
        st.markdown(ui.stat_card("Storage", "Vercel Blob" if storage.storage_backend() == "Vercel Blob" else "Local", "Avatar uploads", "gold"), unsafe_allow_html=True)
    with c3:
        st.markdown(ui.stat_card("Model", "Loaded" if os.path.exists(model_path) else "Missing", "ResNet predictor", "green"), unsafe_allow_html=True)
    with c4:
        st.markdown(ui.stat_card("Profiles", profile_count, "Learned players", "green"), unsafe_allow_html=True)

    left, right = st.columns([1.2, 1])
    with left:
        st.markdown('<div class="section-head"><div class="section-kicker">Environment</div><div class="section-title">Vercel configuration</div></div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="feature-card">
                <div class="feature-text">
                    The Streamlit app runs on a long-lived host (Streamlit Cloud or Render).
                    Data and assets live in Vercel.
                </div>
                <div class="divider"></div>
                <div class="statusline"><span class="status-dot"></span><b>POSTGRES_URL</b>&nbsp;users and games</div>
                <div class="statusline"><span class="status-dot"></span><b>BLOB_READ_WRITE_TOKEN</b>&nbsp;avatar storage</div>
                <div class="statusline"><span class="status-dot gold"></span><b>CHESS_API_BASE</b>&nbsp;{ui.esc(API_BASE)}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.caption("Local development reads the same values from .env. Never commit secrets.")
    with right:
        st.markdown('<div class="section-head"><div class="section-kicker">Account</div><div class="section-title">Session</div></div>', unsafe_allow_html=True)
        st.markdown(
            f"""
            <div class="side-card">
                {ui.avatar_html(user.get("username", "Guest"), user.get("avatar_url"), 46)}
                <div style="height:10px"></div>
                <div class="statusline"><span class="status-dot gold"></span>{ui.esc(user.get("username", "Guest"))}</div>
                <div class="statusline"><span class="status-dot off"></span>{ui.esc(user.get("email", ""))}</div>
                <div class="statusline"><span class="status-dot"></span>{int(user.get("elo") or 1200)} Elo</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            "Sign out",
            use_container_width=True,
            key="settings_sign_out",
            on_click=_sign_out,
        )
        st.caption("Streamlit sessions are per browser tab. Signing out clears this session.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Neural Chess",
    page_icon="♟",
    layout="wide",
    initial_sidebar_state="auto",
)

db.init_db()
st.markdown(THEME_CSS, unsafe_allow_html=True)
_init_state()

# First-run branded boot screen. It self-dismisses via CSS after the initial
# render so it never blocks interaction and never returns on later reruns.
# A cached deployment can pair a new app.py with a stale components/ui.py, so
# reload the module once and fall back to inline markup if boot_splash is gone.
def _boot_splash_html():
    splash = getattr(ui, "boot_splash", None)
    if not callable(splash):
        try:
            import importlib

            importlib.reload(ui)
            splash = getattr(ui, "boot_splash", None)
        except Exception:
            splash = None
    if callable(splash):
        try:
            return splash()
        except Exception:
            pass
    return (
        '<div class="nc-splash" role="status" aria-live="polite">'
        '<div class="nc-splash-title">Neural Chess</div>'
        '<div class="nc-splash-sub">Preparing the arena...</div>'
        "</div>"
    )


if not st.session_state.get("_boot_splash_shown"):
    st.markdown(_boot_splash_html(), unsafe_allow_html=True)
    st.session_state["_boot_splash_shown"] = True

if not st.session_state.authenticated:
    _auth_page()
    st.stop()

_refresh_user()
_sidebar()
_sync_nav_history()

page = st.session_state.get("nav", "Lobby")
if page not in NAV_PAGES:
    page = "Lobby"

if page == "Lobby":
    _lobby()
elif page == "Tournaments":
    _tournaments()
elif page == "Play Online":
    _play_online()
elif page == "Play a Friend":
    _play_friend()
elif page == "Puzzles":
    _puzzles()
elif page == "vs Computer":
    _vs_computer()
elif page == "Lessons":
    _lessons()
elif page == "Leaderboard":
    _leaderboard()
elif page == "Profile":
    _profile()
elif page == "Settings":
    _settings()
