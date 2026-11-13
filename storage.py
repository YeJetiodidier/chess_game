"""Asset storage for avatars: Vercel Blob in production, local files in dev.

Set ``BLOB_READ_WRITE_TOKEN`` (from the Vercel dashboard) to upload avatars to
Vercel Blob.  Without it, files are written to ``uploads/avatars`` so the app
still works offline.
"""
import io
import os
import uuid
from datetime import datetime, timezone

import requests
from PIL import Image, UnidentifiedImageError

from config import get_secret

BLOB_TOKEN = get_secret("BLOB_READ_WRITE_TOKEN").strip()
BLOB_ACCESS = get_secret("BLOB_ACCESS", "private").strip().lower()
if BLOB_ACCESS not in ("public", "private"):
    BLOB_ACCESS = "private"
BLOB_ENDPOINT = "https://blob.vercel-storage.com"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "avatars")

MAX_AVATAR_BYTES = 2 * 1024 * 1024
MAX_AVATAR_SIDE = 512


def storage_backend() -> str:
    return "Vercel Blob" if BLOB_TOKEN else "Local uploads"


def is_remote(url: str) -> bool:
    return bool(url) and url.startswith(("http://", "https://"))


def local_path(url: str):
    """Resolve a stored local upload path to an absolute path."""
    if not url or is_remote(url):
        return None
    if url.startswith("uploads/avatars/"):
        return os.path.join(LOCAL_UPLOAD_DIR, os.path.basename(url.replace("\\", "/")))
    path = url.replace("/", os.sep)
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def fetch_remote(url: str):
    """Return bytes for a stored Blob URL, including private stores."""
    if not BLOB_TOKEN or not is_remote(url):
        return None
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {BLOB_TOKEN}"},
            timeout=20,
        )
        response.raise_for_status()
        return response.content
    except Exception:
        return None


def _normalise_image(data: bytes) -> bytes:
    """Validate and downscale an uploaded image, returning WebP bytes."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as img:
            img.load()
            if getattr(img, "is_animated", False):
                img.seek(0)
            img = img.convert("RGBA")
            img.thumbnail((MAX_AVATAR_SIDE, MAX_AVATAR_SIDE), Image.LANCZOS)
            out = io.BytesIO()
            img.save(out, format="WEBP", quality=86, method=6)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Please upload a valid PNG, JPG, WEBP or GIF image.") from exc


def upload_avatar(user_id: int, data: bytes):
    """Upload an avatar and return ``(url, error)``."""
    if not data:
        return None, "No image data received."
    if len(data) > MAX_AVATAR_BYTES:
        return None, "Image must be 2 MB or smaller."
    try:
        payload = _normalise_image(data)
    except ValueError as exc:
        return None, str(exc)

    filename = f"{uuid.uuid4().hex}.webp"
    pathname = f"avatars/{int(user_id)}/{filename}"

    if BLOB_TOKEN:
        try:
            response = requests.put(
                f"{BLOB_ENDPOINT}/{pathname}",
                data=payload,
                headers={
                    "Authorization": f"Bearer {BLOB_TOKEN}",
                    "x-content-type": "image/webp",
                    "x-add-random-suffix": "1",
                    "x-vercel-blob-access": BLOB_ACCESS,
                    "x-cache-control-max-age": "31536000",
                },
                timeout=30,
            )
            response.raise_for_status()
            payload_json = response.json()
            return payload_json.get("url") or payload_json.get("downloadUrl"), None
        except Exception:
            return None, "Avatar upload to Vercel Blob failed. Check the token and try again."

    try:
        os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
        absolute = os.path.join(LOCAL_UPLOAD_DIR, filename)
        with open(absolute, "wb") as handle:
            handle.write(payload)
        return f"uploads/avatars/{filename}", None
    except OSError:
        return None, "Could not save the avatar locally."


def delete_avatar(url: str):
    """Best-effort cleanup of a replaced avatar."""
    if not url:
        return
    if BLOB_TOKEN and is_remote(url):
        try:
            requests.post(
                f"{BLOB_ENDPOINT}/delete",
                json={"urls": [url]},
                headers={"Authorization": f"Bearer {BLOB_TOKEN}"},
                timeout=15,
            )
        except Exception:
            pass
        return
    path = local_path(url)
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def new_upload_id() -> str:
    return f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
