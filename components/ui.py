"""Reusable HTML building blocks for the Neural Chess interface."""
import base64
import html
import io
import os
import re
from functools import lru_cache

from PIL import Image

import storage


def esc(value) -> str:
    return html.escape(str(value if value is not None else ""))


def initials(name: str) -> str:
    parts = [part for part in re.split(r"[\s_.-]+", (name or "").strip()) if part]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def crown_svg(size: int = 22) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        '<path d="M3.2 7.4l4.3 3.7L12 4.6l4.5 6.5 4.3-3.7-1.7 10.2a1.2 1.2 0 0 1-1.2 1H6.1a1.2 1.2 0 0 1-1.2-1L3.2 7.4z" '
        'fill="currentColor"/>'
        '<circle cx="12" cy="18.6" r="1.25" fill="#141311"/>'
        "</svg>"
    )


@lru_cache(maxsize=128)
def _local_avatar_uri(path: str, mtime: float, size: int):
    try:
        with Image.open(path) as img:
            img.load()
            img = img.convert("RGBA")
            img.thumbnail((size * 2, size * 2), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=88, method=6)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/webp;base64,{encoded}"
    except Exception:
        return None


def avatar_src(username: str, avatar_url: str, size: int = 44):
    if avatar_url:
        if storage.is_remote(avatar_url):
            return avatar_url
        path = storage.local_path(avatar_url)
        if path and os.path.isfile(path):
            return _local_avatar_uri(path, os.path.getmtime(path), size)
    return None


def avatar_html(username: str, avatar_url: str = None, size: int = 44, extra_class: str = "") -> str:
    src = avatar_src(username, avatar_url, size)
    classes = f"avatar {extra_class}".strip()
    if src:
        inner = f'<img src="{esc(src)}" alt="{esc(username)} avatar">'
    else:
        inner = f'<span>{esc(initials(username))}</span>'
    return (
        f'<div class="{classes}" style="width:{size}px;height:{size}px;'
        f'font-size:{max(11, int(size * 0.34))}px">{inner}</div>'
    )


def brand_html(tagline: str = "Play. Learn. Dominate.") -> str:
    return f"""
    <div class="brand">
        <div class="brand-mark">{crown_svg(24)}</div>
        <div class="brand-copy">
            <div class="brand-name">NEURAL CHESS</div>
            <div class="brand-tag">{esc(tagline)}</div>
        </div>
    </div>
    """


def stat_card(label: str, value, hint: str = "", tone: str = "") -> str:
    tone_class = f" stat-{tone}" if tone else ""
    return f"""
    <div class="stat-card{tone_class}">
        <div class="stat-label">{esc(label)}</div>
        <div class="stat-value">{esc(value)}</div>
        <div class="stat-hint">{esc(hint)}</div>
    </div>
    """


def section_header(kicker: str, title: str, sub: str = "") -> str:
    sub_html = f'<div class="section-sub">{esc(sub)}</div>' if sub else ""
    return f"""
    <div class="section-head">
        <div>
            <div class="section-kicker">{esc(kicker)}</div>
            <div class="section-title">{esc(title)}</div>
            {sub_html}
        </div>
    </div>
    """


def pill(text: str, tone: str = "gold") -> str:
    return f'<span class="pill pill-{esc(tone)}">{esc(text)}</span>'


def result_pill(result: str) -> str:
    mapping = {
        "win": ("Win", "green"),
        "loss": ("Loss", "red"),
        "draw": ("Draw", "muted"),
    }
    label, tone = mapping.get((result or "").lower(), (result or "—", "muted"))
    return pill(label, tone)


def challenge_rows(items) -> str:
    if not items:
        return ""
    rows = []
    for item in items:
        rows.append(
            f"""
            <div class="challenge-row">
                {avatar_html(item.get("name", "?"), item.get("avatar_url"), 40)}
                <div class="challenge-info">
                    <div class="challenge-name">{esc(item.get("name"))}</div>
                    <div class="challenge-meta">{esc(item.get("meta", "Rated game"))}</div>
                </div>
                <div class="challenge-time">{esc(item.get("time", "10:00"))}</div>
                <div class="challenge-side">{esc(item.get("tag", "Blitz"))}</div>
            </div>
            """
        )
    return f'<div class="challenge-list">{"".join(rows)}</div>'


def demo_challenges():
    return [
        {"name": "ELON MUSK", "meta": "Rated · 1842", "time": "9:40", "tag": "Blitz"},
        {"name": "VINAY_P", "meta": "Rated · 1675", "time": "9:56", "tag": "Blitz"},
        {"name": "ELON MUSK", "meta": "Rated · 1842", "time": "10:00", "tag": "Rapid"},
        {"name": "VINAY_P", "meta": "Rated · 1675", "time": "9:45", "tag": "Rapid"},
        {"name": "ELON MUSK", "meta": "Rated · 1842", "time": "9:54", "tag": "Blitz"},
        {"name": "VINAY_P", "meta": "Rated · 1675", "time": "9:38", "tag": "Bullet"},
    ]


def leaderboard_table(rows, current_user_id=None) -> str:
    if not rows:
        return ""
    body = []
    for index, row in enumerate(rows, start=1):
        me = " is-me" if current_user_id and row.get("id") == current_user_id else ""
        games = row.get("games") or 0
        wins = row.get("wins") or 0
        body.append(
            f"""
            <div class="board-row{me}">
                <div class="board-rank">{index:02d}</div>
                {avatar_html(row.get("username", "?"), row.get("avatar_url"), 38)}
                <div class="board-name">
                    <div>{esc(row.get("username"))}</div>
                    <div class="board-sub">{int(games)} games · {int(wins)} wins</div>
                </div>
                <div class="board-rating">{int(row.get("elo") or 1200)}</div>
            </div>
            """
        )
    return f'<div class="board-table">{"".join(body)}</div>'


def game_history_table(games) -> str:
    if not games:
        return ""
    rows = []
    for game in games:
        when = game.get("created_at")
        if hasattr(when, "strftime"):
            when = when.strftime("%b %d, %Y")
        elif when:
            when = str(when)[:10]
        rows.append(
            f"""
            <div class="board-row">
                <div class="board-rank">{esc((game.get("mode") or "AI")[:1].upper())}</div>
                <div class="board-name">
                    <div>vs {esc(game.get("opponent") or "Neural AI")}</div>
                    <div class="board-sub">{esc(game.get("mode") or "Rated")} · {esc(when)}</div>
                </div>
                <div class="board-side">{result_pill(game.get("result"))}</div>
            </div>
            """
        )
    return f'<div class="board-table">{"".join(rows)}</div>'


def empty_state(title: str, text: str) -> str:
    return f"""
    <div class="empty-state">
        <div class="empty-crown">{crown_svg(30)}</div>
        <div class="empty-title">{esc(title)}</div>
        <div class="empty-text">{esc(text)}</div>
    </div>
    """
