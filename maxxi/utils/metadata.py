"""
metadata.py – extract rich metadata from an uploaded file's raw bytes.

Handles:
  • All files   → name, size, mime_type, category, extension
  • Images      → width, height, mode (via Pillow)
  • Audio/Video → duration, bitrate, codec, sample_rate, channels (via mutagen)
  • Documents   → page_count for PDFs (via pypdf)
"""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from typing import Any

from PIL import Image, UnidentifiedImageError

import config


# ── Category helper ──────────────────────────────────────────────────────────


def get_category(mime: str) -> str:
    mime = mime.lower()
    for category, types in config.FOLDER_MAP.items():
        if mime in [t.lower() for t in types]:
            return category
    return "docs"


# ── Core extractor ───────────────────────────────────────────────────────────


def extract(
    file_bytes: bytes,
    filename: str,
    mime_type: str,
) -> dict[str, Any]:
    """Return a metadata dict for the given file bytes."""

    ext = os.path.splitext(filename)[1].lower().lstrip(".")
    category = get_category(mime_type)
    now = datetime.now(timezone.utc).isoformat()

    meta: dict[str, Any] = {
        "filename": filename,
        "extension": ext,
        "mime_type": mime_type,
        "category": category,
        "size_bytes": len(file_bytes),
        "size_human": _human_size(len(file_bytes)),
        "uploaded_at": now,
    }

    if category == "image":
        meta.update(_image_meta(file_bytes))
    elif category in ("audio", "video"):
        meta.update(_av_meta(file_bytes, filename, mime_type))
    elif category == "docs" and mime_type == "application/pdf":
        meta.update(_pdf_meta(file_bytes))

    return meta


# ── Image metadata ────────────────────────────────────────────────────────────


def _image_meta(data: bytes) -> dict[str, Any]:
    try:
        img = Image.open(io.BytesIO(data))
        return {
            "width": img.width,
            "height": img.height,
            "mode": img.mode,
            "format": img.format,
        }
    except UnidentifiedImageError:
        return {}
    except Exception:
        return {}


# ── Audio / Video metadata ───────────────────────────────────────────────────


def _av_meta(data: bytes, filename: str, mime: str) -> dict[str, Any]:
    try:
        from mutagen import File as MutagenFile # type: ignore

        audio = MutagenFile(io.BytesIO(data), filename=filename) # type: ignore
        if audio is None:
            return {}

        result: dict[str, Any] = {}

        if hasattr(audio, "info"):
            info = audio.info
            if hasattr(info, "length"):
                secs = info.length
                result["duration_seconds"] = round(secs, 2)
                result["duration_human"] = _human_duration(secs)
            if hasattr(info, "bitrate"):
                result["bitrate_kbps"] = info.bitrate // 1000 if info.bitrate else None
            if hasattr(info, "sample_rate"):
                result["sample_rate_hz"] = info.sample_rate
            if hasattr(info, "channels"):
                result["channels"] = info.channels
            # video dimensions
            if hasattr(info, "fps"):
                result["fps"] = getattr(info, "fps", None)

        # common tags
        tags: dict[str, Any] = {}
        for key in ("title", "artist", "album", "date", "genre"):
            val = audio.get(key) or audio.get(key.upper())
            if val:
                tags[key] = str(val[0]) if isinstance(val, list) else str(val)
        if tags:
            result["tags"] = tags

        return result
    except Exception:
        return {}


# ── PDF metadata ─────────────────────────────────────────────────────────────


def _pdf_meta(data: bytes) -> dict[str, Any]:
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        info = reader.metadata or {}
        result: dict[str, Any] = {"page_count": len(reader.pages)}
        for key in ("/Title", "/Author", "/Subject", "/Creator"):
            val = info.get(key)
            if val:
                result[key.lstrip("/").lower()] = str(val)
        return result
    except Exception:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024 # type: ignore
    return f"{n:.1f} TB"


def _human_duration(secs: float) -> str:
    secs = int(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
