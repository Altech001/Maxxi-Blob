from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from fastapi import Request

import config


def public_base_url(request: Request | None = None) -> str:
    if config.PUBLIC_BASE_URL:
        return config.PUBLIC_BASE_URL.rstrip("/")
    if request:
        return str(request.base_url).rstrip("/")
    return ""


def cdn_base_url(request: Request | None = None) -> str:
    if config.CDN_BASE_URL:
        return config.CDN_BASE_URL.rstrip("/")
    return public_base_url(request)


def safe_filename(filename: str) -> str:
    cleaned = filename.strip().replace(" ", "-")
    cleaned = re.sub(r"[^a-zA-Z0-9._-]", "", cleaned)
    return cleaned or "file"


def safe_folder(folder: str | None) -> str:
    cleaned = (folder or "documents").strip().lower().replace(" ", "-")
    cleaned = re.sub(r"[^a-z0-9_-]", "", cleaned)
    return cleaned or "documents"


def folder_for_mime(mime_type: str | None, category: str | None = None) -> str:
    mime = (mime_type or "").lower()
    for folder, types in config.CDN_FOLDER_MAP.items():
        if mime in {item.lower() for item in types}:
            return folder

    category_map = {
        "image": "images",
        "video": "videos",
        "audio": "audio",
        "docs": "documents",
        "document": "documents",
    }
    return category_map.get((category or "").lower(), "documents")


def jsdelivr_like_path(file_id: str | int, filename: str, folder: str | None = None) -> str:
    file_id_str = quote(str(file_id), safe="")
    name = quote(safe_filename(filename), safe="")
    folder_slug = quote(safe_folder(folder), safe="")
    return (
        f"/gh/{config.GITHUB_USER}/{config.GITHUB_REPO}@"
        f"{config.GITHUB_BRANCH}/telegram/{folder_slug}/{file_id_str}/{name}"
    )


def build_file_urls(
    file_id: str | int,
    filename: str,
    request: Request | None = None,
    cdn_url: str | None = None,
    folder: str | None = None,
) -> dict[str, str]:
    base = public_base_url(request)
    cdn_base = cdn_base_url(request)
    file_id_str = quote(str(file_id), safe="")
    name = quote(safe_filename(filename), safe="")
    cdn_path = jsdelivr_like_path(file_id_str, name, folder)
    api_path = f"/api/v1/files/{file_id_str}"
    api_download_url = f"{base}{api_path}/download"
    file_url = cdn_url or f"{cdn_base}{cdn_path}"

    return {
        "cdn_url": file_url,
        "rawUrl": file_url,
        "raw_url": file_url,
        "download_url": file_url,
        "inline_url": file_url,
        "metadata_url": f"{base}{api_path}/metadata",
        "preview_url": file_url,
        "api_download_url": api_download_url,
        "api_inline_url": f"{api_download_url}?disposition=inline",
        "api_attachment_url": f"{api_download_url}?disposition=attachment",
        "api_preview_url": f"{base}{api_path}/preview",
        "cdn_path": cdn_path,
    }


def attach_urls(record: dict[str, Any], request: Request | None = None) -> dict[str, Any]:
    filename = str(record.get("filename") or record.get("name") or "file")
    file_id = record.get("id") or record.get("message_id")
    if file_id is None:
        return record
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    folder = record.get("cdn_folder") or folder_for_mime(
        str(record.get("mime_type") or metadata.get("mime_type") or ""),
        str(record.get("category") or metadata.get("category") or ""),
    )
    direct_cdn_url = str(record.get("cdn_url") or "") if record.get("storage_backend") == "github" else ""
    return {
        **record,
        **build_file_urls(
            file_id,
            filename,
            request,
            cdn_url=direct_cdn_url or None,
            folder=str(folder),
        ),
    }
