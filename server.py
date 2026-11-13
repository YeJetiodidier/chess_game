"""Lightweight local server for the Neural Chess Move Predictor.

Uses only the Python standard library for HTTP.  When ``model.pt`` exists the
neural network is loaded and every named player gets an adaptive head that
keeps learning from their moves (see ``online.py``).
"""
import hashlib
import hmac
import http.server
import json
import os
import socketserver
import urllib.parse

import db
from config import get_secret

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))
RESULT_SECRET = get_secret("CHESS_RESULT_SECRET", "neural-chess-local-dev")

try:
    db.init_db()
except Exception as exc:
    print(f"[Server] Database init notice: {exc}")

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
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    # ------------------------------------------------------------------ GET
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/api/profiles":
            self._send_json({"profiles": store.profiles() if store else []})
            return
        if parsed.path == "/api/player":
            name = (query.get("name") or query.get("player") or ["Guest"])[0]
            self._send_json({"player": store.stats(name) if store else None,
                             "adaptive": store is not None})
            return

        super().do_GET()

    # ----------------------------------------------------------------- POST
    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            self.send_response(404)
            self.end_headers()
            return

        try:
            data = self._read_json()
        except Exception as ex:
            self._send_json({"error": f"bad request: {ex}"}, 400)
            return

        try:
            if path == "/api/predict":
                fen = data.get("fen") or "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
                player = data.get("player") or data.get("name") or "Guest"
                self._send_json(predict_response(fen, player))
                return

            if path == "/api/game":
                user_id = int(data.get("userId") or 0)
                username = str(data.get("username") or "")
                if not user_id or not verify_result_ticket(
                    user_id, username, data.get("ticket")
                ):
                    self._send_json({"error": "invalid result ticket"}, 403)
                    return
                user = db.get_user(user_id)
                if not user or user.get("username") != username:
                    self._send_json({"error": "unknown player"}, 403)
                    return

                result = str(data.get("result") or "").lower()
                mode = str(data.get("mode") or "ai").lower()
                if result not in ("win", "loss", "draw") or mode not in ("ai", "online"):
                    self._send_json({"error": "invalid result or mode"}, 400)
                    return

                external_id = str(data.get("gameId") or "").strip() or None
                existing = db.get_game_by_external_id(external_id) if external_id else None
                if existing:
                    self._send_json({
                        "ok": True,
                        "recorded": False,
                        "gameId": existing.get("id"),
                        "elo": int(user.get("elo") or 1200),
                    })
                    return

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
                    self._send_json({"error": "could not save game"}, 500)
                    return

                score = {"win": 1.0, "draw": 0.5, "loss": 0.0}[result]
                elo = updated_elo(int(user.get("elo") or 1200), score)
                db.update_elo(user_id, elo)
                self._send_json({
                    "ok": True,
                    "recorded": True,
                    "gameId": game_id,
                    "elo": elo,
                })
                return

            if store is None:
                self._send_json({"error": "adaptive model not loaded", "adaptive": False}, 503)
                return

            if path == "/api/move":
                fen = data["fen"]
                uci = data["uci"]
                game = data.get("gameId") or data.get("game") or ""
                color = data.get("color")
                if not color:
                    color = "w" if chess.Board(fen).turn == chess.WHITE else "b"
                stats = store.record_move(data.get("player") or "Guest", fen, uci, game, color)
                self._send_json({"ok": True, "player": stats})
                return

            if path == "/api/undo":
                stats = store.undo_move(data.get("player") or "Guest",
                                        data.get("gameId") or data.get("game") or "")
                self._send_json({"ok": True, "player": stats})
                return

            if path == "/api/result":
                stats = store.record_result(
                    data.get("player") or "Guest",
                    data.get("gameId") or data.get("game") or "",
                    data.get("outcome", "draw"),
                    data.get("color"))
                self._send_json({"ok": True, "player": stats})
                return

            if path == "/api/player":
                self._send_json({"player": store.stats(data.get("player") or "Guest"),
                                 "adaptive": True})
                return

            self._send_json({"error": "unknown endpoint"}, 404)
        except KeyError as ex:
            self._send_json({"error": f"missing field: {ex}"}, 400)
        except ValueError as ex:
            self._send_json({"error": str(ex)}, 400)
        except Exception as ex:
            self._send_json({"error": str(ex)}, 500)


class ThreadingServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def run():
    with ThreadingServer(("", PORT), ChessHandler) as httpd:
        print("\n=======================================================")
        print(f" Neural Chess UI running at: http://localhost:{PORT}")
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
