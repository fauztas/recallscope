"""Session-only image preparation. Uploads are resized in memory and never written to disk."""

import hashlib
import re
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from recallpath.utils.config import JPEG_QUALITY, MAX_EDGE_PX, MAX_PHOTOS

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_TARGET_BYTES = 1_500_000
_MAX_UPLOAD_BYTES = 15 * 1024 * 1024


def _safe_name(filename: str) -> str:
    name = Path(filename or "photo").name
    name = re.sub(r"[^\w.\- ()]", "_", name).strip(" .") or "photo"
    return name[:80]


def unique_filename(filename: str, existing_names: set) -> str:
    name = _safe_name(filename)
    if name not in existing_names:
        return name
    stem = Path(name).stem
    ext = Path(name).suffix or ".jpg"
    number = 2
    while True:
        candidate = f"{stem} ({number}){ext}"
        if candidate not in existing_names:
            return candidate
        number += 1


def prepare_image(filename: str, data: bytes) -> dict:
    """Return resized JPEG bytes, or an error dict. Does not keep the original bytes."""
    name = _safe_name(filename)
    extension = Path(name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        return {
            "ok": False,
            "error": "Use a JPEG, PNG, or WEBP photo.",
        }
    if not data:
        return {"ok": False, "error": "That file was empty."}
    if len(data) > _MAX_UPLOAD_BYTES:
        return {"ok": False, "error": "That photo is too large. Use one under 15 MB."}
    digest = hashlib.sha256(data).hexdigest()
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
            if (image.format or "").upper() not in ALLOWED_FORMATS:
                return {"ok": False, "error": "That file is not a JPEG, PNG, or WEBP photo."}
            prepared = _to_jpeg(image)
    except (UnidentifiedImageError, OSError, ValueError):
        return {"ok": False, "error": "That file could not be read as a photo."}
    return {
        "ok": True,
        "filename": name,
        "mime": "image/jpeg",
        "bytes": prepared,
        "sha256": digest,
    }


def _to_jpeg(image: Image.Image) -> bytes:
    if image.mode in {"RGBA", "LA", "P"}:
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.split()[-1])
        working = background
    elif image.mode != "RGB":
        working = image.convert("RGB")
    else:
        working = image.copy()
    working.thumbnail((MAX_EDGE_PX, MAX_EDGE_PX))
    quality = JPEG_QUALITY
    encoded = _encode(working, quality)
    while len(encoded) > _TARGET_BYTES and quality > 45:
        quality -= 10
        encoded = _encode(working, quality)
    return encoded


def _encode(image: Image.Image, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def add_photos(existing: list, incoming: list) -> list:
    """Add up to the session cap. `incoming` items are `{filename, data}`."""
    notes = []
    names = {photo["filename"] for photo in existing}
    hashes = {photo["sha256"] for photo in existing}
    overflow = False
    for item in incoming:
        filename = item.get("filename") or "photo.jpg"
        if len(existing) >= MAX_PHOTOS:
            overflow = True
            break
        prepared = prepare_image(filename, item.get("data") or b"")
        if not prepared["ok"]:
            notes.append(f"{_safe_name(filename)}: {prepared['error']}")
            continue
        if prepared["sha256"] in hashes:
            notes.append(f"{prepared['filename']} is already in this session.")
            continue
        stored_name = unique_filename(prepared["filename"], names)
        names.add(stored_name)
        hashes.add(prepared["sha256"])
        existing.append({
            "id": prepared["sha256"][:12],
            "filename": stored_name,
            "mime": prepared["mime"],
            "bytes": prepared["bytes"],
            "sha256": prepared["sha256"],
            "analysis": None,
        })
    if overflow:
        notes.append("Only 12 photos can be added in one session. Extra files were left out.")
    return notes
