"""
Image storage: local disk in development, Vercel Blob in production.

Vercel Functions have an ephemeral filesystem, so anything written to disk is
gone by the next request. When BLOB_READ_WRITE_TOKEN is present we upload to
Vercel Blob and store the absolute URL it returns; otherwise we keep the
simple local-disk behaviour so `uvicorn main:app --reload` still works with
no cloud account.

Callers get back a URL string and never touch a path.
"""
import json
import os
import urllib.request
import uuid
from pathlib import Path

from config import IMAGE_DIR

BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN")
BLOB_API = "https://blob.vercel-storage.com"
BLOB_API_VERSION = "7"


def using_blob() -> bool:
    return bool(BLOB_TOKEN)


def backend_name() -> str:
    return "vercel-blob" if using_blob() else "local-disk"


def save_image(data: bytes, filename: str, content_type: str = "image/jpeg") -> str:
    """Store an image and return a URL that a browser can load."""
    safe_name = Path(filename).name.replace(" ", "_") or "upload.jpg"
    key = f"{uuid.uuid4().hex[:8]}_{safe_name}"

    if using_blob():
        return _put_blob(key, data, content_type)

    (IMAGE_DIR / key).write_bytes(data)
    return f"/images/{key}"


def _put_blob(key: str, data: bytes, content_type: str) -> str:
    request = urllib.request.Request(
        f"{BLOB_API}/{key}",
        data=data,
        method="PUT",
        headers={
            "authorization": f"Bearer {BLOB_TOKEN}",
            "x-api-version": BLOB_API_VERSION,
            "x-content-type": content_type,
            "x-add-random-suffix": "1",
            "content-type": content_type,
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())["url"]


def clear_local_images() -> int:
    """Delete locally stored images. Blob objects are left alone."""
    if using_blob():
        return 0
    removed = 0
    for path in Path(IMAGE_DIR).glob("*"):
        if path.is_file() and path.name != ".gitkeep":
            path.unlink()
            removed += 1
    return removed
