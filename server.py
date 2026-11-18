"""HTTP API and static server for the Neural Chess Move Predictor.

Runs either directly (``python server.py``) or through gunicorn
(``gunicorn server:app``).  When ``model.pt`` exists the neural network is
loaded and every named player gets an adaptive head that keeps learning from
their moves (see ``online.py``).

The API is intentionally free of heavyweight web frameworks: ``api_dispatch``
holds the routing logic and both the stdlib handler and the WSGI entry point
call it.
"""
import hashlib
import hmac
import http.client
import http.server
import json
import os
import socketserver
import urllib.parse

import db
from config import get_secret

try:
    PORT = int(os.environ.get("PORT") or 8000)
except ValueError:
    PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
RESULT_SECRET = get_secret("CHESS_RESULT_SECRET", "neural-chess-local-dev")
MAX_BODY_BYTES = 1024 * 1024
STATIC_FILES = {"", "/", "/index.html"}

if RESULT_SECRET == "neural-chess-local-dev":
    print(
        "[Server] WARNING: CHESS_RESULT_SECRET is using the development "
        "default. Set a strong shared secret in production."
    )

try:
    db.init_db()
except Exception as exc:
    print(f"[Server] Database init notice: {exc}")

chess = None
store = None
fallback_model = None
try:
    import chess
    from predict import load_model, predict_moves
    from online import PlayerStore

    model_path = os.path.join(DIRECTORY, "model.pt")
    if os.path.exists(model_path):
        fallback_model = load_model(model_path, device="cpu")
        store = PlayerStore(model_path, device="cpu")
        print("[Server] Neural model loaded. Per-player online learning enabled.")
    else:
        print("[Server] model.pt not found yet. Running in heuristic/python-chess mode.")
except Exception as e:
    print(f"[Server] Model load notice: {e}")


def move_payload(board, move, prob):
    return {
        "san": board.san(move),
        "uci": move.uci(),
        "prob": float(prob),
        "move": {
            "from": (7 - chess.square_rank(move.from_square)) * 8 + chess.square_file(move.from_square),
            "to": (7 - chess.square_rank(move.to_square)) * 8 + chess.square_file(move.to_square),
            "promo": chess.piece_symbol(move.promotion).lower() if move.promotion else None,
            "isCastle": board.is_castling(move),
            "isEP": board.is_en_passant(move),
        },
    }


def verify_result_ticket(user_id, username, ticket):
    message = f"{int(user_id)}:{username}".encode("utf-8")
    expected = hmac.new(
        RESULT_SECRET.encode("utf-8"), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, str(ticket or ""))


def updated_elo(rating, score, opponent_rating=1200, k_factor=24):
    expected = 1.0 / (1.0 + 10 ** ((opponent_rating - rating) / 400.0))
    return max(100, round(rating + k_factor * (score - expected)))


def predict_response(fen, player):
    if chess is None:
        raise RuntimeError("python-chess is required to serve predictions")
    board = chess.Board(fen)
    stats = None
    adaptive = store is not None

    if store is not None:
        predictions = store.predict(player, board)
        stats = store.stats(player)
    elif fallback_model is not None:
        predictions = predict_moves(fallback_model, board, device="cpu")
    else:
        legal = list(board.legal_moves)
        predictions = [(m, 1.0 / max(len(legal), 1)) for m in legal[:5]]

    results = [move_payload(board, move, prob) for move, prob in predictions[:5]]
    return {"model_loaded": fallback_model is not None, "adaptive": adaptive,
            "player": stats, "moves": results}


def api_dispatch(method, path, query, data):
    """Route an API request and return ``(status_code, payload_dict)``."""
    method = (method or "GET").upper()

    if method == "GET":
        if path == "/health":
            return 200, {
                "ok": True,
                "model_loaded": fallback_model is not None,
                "adaptive": store is not None,
            }
        if path == "/api/profiles":
            return 200, {"profiles": store.profiles() if store else []}
        if path == "/api/player":
            name = (query.get("name") or query.get("player") or ["Guest"])[0]
            return 200, {"player": store.stats(name) if store else None,
                         "adaptive": store is not None}
        return 404, {"error": "unknown endpoint"}

    if method != "POST":
        return 405, {"error": "method not allowed"}

    if not hasattr(data, "get"):
        return 400, {"error": "expected a JSON object"}

    if not path.startswith("/api/"):
        return 404, {"error": "unknown endpoint"}

    try:
        if path == "/api/predict":
            fen = data.get("fen") or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
            player = data.get("player") or data.get("name") or "Guest"
            return 200, predict_response(fen, player)

        if path == "/api/game":
            user_id = int(data.get("userId") or 0)
            username = str(data.get("username") or "")
            if not user_id or not verify_result_ticket(
                user_id, username, data.get("ticket")
            ):
                return 403, {"error": "invalid result ticket"}
            user = db.get_user(user_id)
            if not user or user.get("username") != username:
                return 403, {"error": "unknown player"}

            result = str(data.get("result") or "").lower()
            mode = str(data.get("mode") or "ai").lower()
            if result not in ("win", "loss", "draw") or mode not in ("ai", "online"):
                return 400, {"error": "invalid result or mode"}

            external_id = str(data.get("gameId") or "").strip() or None
            existing = db.get_game_by_external_id(external_id) if external_id else None
            if existing:
                return 200, {
                    "ok": True,
                    "recorded": False,
                    "gameId": existing.get("id"),
                    "elo": int(user.get("elo") or 1200),
                }

            game_id = db.record_game(
                user_id,
                result,
                moves=str(data.get("moves") or ""),
                fen_final=str(data.get("fen") or ""),
                mode=mode,
                opponent=str(data.get("opponent") or "Neural AI"),
                user_color=str(data.get("userColor") or ""),
                external_id=external_id,
            )
            if not game_id:
                return 500, {"error": "could not save game"}

            score = {"win": 1.0, "draw": 0.5, "loss": 0.0}[result]
            elo = updated_elo(int(user.get("elo") or 1200), score)
            db.update_elo(user_id, elo)
            return 200, {
                "ok": True,
                "recorded": True,
                "gameId": game_id,
                "elo": elo,
            }

        if store is None:
            return 503, {"error": "adaptive model not loaded", "adaptive": False}

        if path == "/api/move":
            fen = data["fen"]
            uci = data["uci"]
            game = data.get("gameId") or data.get("game") or ""
            color = data.get("color")
            if not color:
                color = "w" if chess.Board(fen).turn == chess.WHITE else "b"
            stats = store.record_move(data.get("player") or "Guest", fen, uci, game, color)
            return 200, {"ok": True, "player": stats}

        if path == "/api/undo":
            stats = store.undo_move(data.get("player") or "Guest",
                                    data.get("gameId") or data.get("game") or "")
            return 200, {"ok": True, "player": stats}

        if path == "/api/result":
            stats = store.record_result(
                data.get("player") or "Guest",
                data.get("gameId") or data.get("game") or "",
                data.get("outcome", "draw"),
                data.get("color"))
            return 200, {"ok": True, "player": stats}

        if path == "/api/player":
            return 200, {"player": store.stats(data.get("player") or "Guest"),
                         "adaptive": True}

        return 404, {"error": "unknown endpoint"}
    except KeyError as ex:
        return 400, {"error": f"missing field: {ex}"}
    except ValueError as ex:
        return 400, {"error": str(ex)}
    except Exception as ex:
        return 500, {"error": str(ex)}


class ChessHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    @staticmethod
    def _static_allowed(path):
        return path in STATIC_FILES

    def _read_json(self):
        try:
            length = int(self.headers.get("Content-Length", 0) or 0)
        except (TypeError, ValueError):
            raise ValueError("invalid Content-Length")
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/health" or parsed.path.startswith("/api/"):
            status, payload = api_dispatch("GET", parsed.path, query, {})
            self._send_json(payload, status)
            return

        if not self._static_allowed(parsed.path):
            self.send_error(404)
            return
        super().do_GET()

    def do_HEAD(self):
        parsed = urllib.parse.urlparse(self.path)
        if not self._static_allowed(parsed.path):
            self.send_error(404)
            return
        super().do_HEAD()

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        try:
            data = self._read_json()
        except Exception as ex:
            self._send_json({"error": f"bad request: {ex}"}, 400)
            return

        status, payload = api_dispatch(
            "POST", parsed.path, urllib.parse.parse_qs(parsed.query), data
        )
        self._send_json(payload, status)


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def _wsgi_json(start_response, status, payload, method="GET"):
    reason = http.client.responses.get(status, "OK")
    if method == "HEAD":
        body = b""
        headers = [("Content-Length", "0")]
    else:
        body = json.dumps(payload).encode("utf-8")
        headers = [("Content-Length", str(len(body)))]
    headers.extend([
        ("Content-Type", "application/json"),
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
        ("X-Content-Type-Options", "nosniff"),
    ])
    start_response(f"{status} {reason}", headers)
    return [body]


def application(environ, start_response):
    """WSGI entry point used by gunicorn (``gunicorn server:app``)."""
    method = (environ.get("REQUEST_METHOD") or "GET").upper()
    path = environ.get("PATH_INFO") or "/"
    query = urllib.parse.parse_qs(environ.get("QUERY_STRING") or "")

    if method == "OPTIONS":
        start_response("204 No Content", [
            ("Access-Control-Allow-Origin", "*"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Content-Length", "0"),
        ])
        return [b""]

    if method in ("GET", "HEAD") and path in STATIC_FILES:
        try:
            with open(os.path.join(DIRECTORY, "index.html"), "rb") as handle:
                body = handle.read()
        except OSError:
            return _wsgi_json(start_response, 404, {"error": "index.html not found"}, method)
        start_response("200 OK", [
            ("Content-Type", "text/html; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("X-Content-Type-Options", "nosniff"),
            ("Access-Control-Allow-Origin", "*"),
        ])
        return [body] if method == "GET" else [b""]

    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    if length < 0 or length > MAX_BODY_BYTES:
        return _wsgi_json(start_response, 413, {"error": "request body too large"}, method)

    data = {}
    if method in ("POST", "PUT", "PATCH"):
        try:
            stream = environ.get("wsgi.input")
            raw = stream.read(length) if stream and length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
        except Exception as ex:
            return _wsgi_json(start_response, 400, {"error": f"bad request: {ex}"}, method)

    status, payload = api_dispatch(method, path, query, data)
    return _wsgi_json(start_response, status, payload, method)


app = application


def run():
    with ThreadingServer(("0.0.0.0", PORT), ChessHandler) as httpd:
        print("\n=======================================================")
        print(f" Neural Chess API running at: http://0.0.0.0:{PORT}")
        print(f" Serving directory: {DIRECTORY}")
        print(" Per-player adaptation + reinforcement learning active.")
        print(" Press Ctrl+C to stop.")
        print("=======================================================\n")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")


if __name__ == "__main__":
    run()
