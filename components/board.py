"""Streamlit chessboard component with live move prediction."""
import hashlib
import hmac
import json
import os

import streamlit.components.v1 as components

from config import get_secret

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_BASE = get_secret("CHESS_API_BASE", "http://localhost:8000").rstrip("/")
RESULT_SECRET = get_secret("CHESS_RESULT_SECRET", "neural-chess-local-dev")


def _json_for_script(payload) -> str:
    return json.dumps(payload, ensure_ascii=True).replace("<", "\\u003c")


def _result_ticket(user_id, username: str) -> str:
    message = f"{int(user_id)}:{username}".encode("utf-8")
    return hmac.new(RESULT_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def render_interactive_board(
    fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
    height=580,
    player_name=None,
    opponent_name=None,
    white_name=None,
    black_name=None,
    ai_side="b",
    ai_auto=False,
    ai_level="top",
    mode="ai",
    user_id=None,
    username=None,
    user_color=None,
):
    """Render the interactive board with an injected runtime configuration."""
    with open(os.path.join(BASE_DIR, "index.html"), "r", encoding="utf-8") as handle:
        html_content = handle.read()

    config = {
        "apiBase": API_BASE,
        "startFen": fen,
        "playerName": player_name,
        "opponentName": opponent_name,
        "whiteName": white_name,
        "blackName": black_name,
        "aiSide": ai_side if ai_side in ("w", "b", "both") else "",
        "aiAuto": bool(ai_auto),
        "aiLevel": ai_level if ai_level in ("top", "mixed", "random") else "top",
        "mode": mode,
        "userColor": user_color,
    }

    if user_id and username:
        config["user"] = {
            "id": int(user_id),
            "name": str(username),
            "ticket": _result_ticket(user_id, str(username)),
        }

    injection = (
        "<head><script>window.CHESS_API_BASE = "
        + _json_for_script(API_BASE)
        + "; window.CHESS_CONFIG = "
        + _json_for_script(config)
        + ";</script>"
    )
    html_content = html_content.replace("<head>", injection, 1)

    components.html(html_content, height=height, scrolling=False)
