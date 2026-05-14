from __future__ import annotations

import argparse
import asyncio
import json
import mimetypes
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from utils import github_store, metadata  # noqa: E402
from utils.cdn_url import build_file_urls, folder_for_mime, safe_filename  # noqa: E402
from utils.telegram_store import stop_client, upload_path_to_telegram  # noqa: E402


def _folder_id(value: int | None) -> int | None:
    if value in (None, 0):
        return config.TELEGRAM_STORAGE_FOLDER_ID
    return value


def _detect_mime_type(file_path: Path, mime_type: str | None) -> str:
    if mime_type:
        return mime_type
    guessed, _ = mimetypes.guess_type(file_path.name)
    return guessed or "application/octet-stream"


def _validate_file(file_path: Path, mime_type: str, file_size: int) -> None:
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")
    if file_size > config.MAX_FILE_SIZE:
        raise ValueError(f"File exceeds MAX_FILE_SIZE: {file_size} > {config.MAX_FILE_SIZE}")
    if mime_type.lower() not in {mime.lower() for mime in config.ALLOWED_MIME_TYPES}:
        raise ValueError(f"File type not allowed: {mime_type}")


def _basic_metadata(filename: str, mime_type: str, file_size: int) -> dict[str, Any]:
    extension = os.path.splitext(filename)[1].lower().lstrip(".")
    return {
        "filename": filename,
        "extension": extension,
        "mime_type": mime_type,
        "category": metadata.get_category(mime_type),
        "size_bytes": file_size,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "metadata_limited": True,
        "metadata_note": "Rich metadata parsing skipped for large direct upload.",
    }


async def upload_direct(
    file_path: Path,
    folder_id: int | None,
    mime_type: str | None,
) -> dict[str, Any]:
    file_size = file_path.stat().st_size
    upload_mime_type = _detect_mime_type(file_path, mime_type)
    _validate_file(file_path, upload_mime_type, file_size)

    original_filename = file_path.name
    cdn_filename = safe_filename(original_filename)
    target_folder_id = _folder_id(folder_id)

    try:
        telegram_upload = await upload_path_to_telegram(
            file_path=str(file_path),
            filename=original_filename,
            mime_type=upload_mime_type,
            folder_id=target_folder_id,
            folder_slug=folder_for_mime(upload_mime_type),
        )
        target_folder_id = telegram_upload.folder_id

        if file_size <= config.METADATA_PARSE_MAX_BYTES:
            parsed = metadata.extract(file_path.read_bytes(), cdn_filename, upload_mime_type)
        else:
            parsed = _basic_metadata(cdn_filename, upload_mime_type, file_size)

        category = str(parsed.get("category") or "docs")
        cdn_folder = folder_for_mime(upload_mime_type, category)
        public_file_id = (
            f"{target_folder_id}_{telegram_upload.message_id}"
            if target_folder_id not in (None, 0)
            else str(telegram_upload.message_id)
        )
        urls = build_file_urls(
            public_file_id,
            cdn_filename,
            folder=cdn_folder,
        )
        virtual_file_path = f"telegram/{cdn_folder}/{telegram_upload.message_id}/{cdn_filename}"
        record = {
            "success": True,
            "id": public_file_id,
            "filename": cdn_filename,
            "original_filename": original_filename,
            "file_path": virtual_file_path,
            "message_id": telegram_upload.message_id,
            "folder_id": target_folder_id,
            "size_bytes": file_size,
            "mime_type": upload_mime_type,
            "category": category,
            "cdn_folder": cdn_folder,
            "extension": parsed.get("extension", ""),
            "telegram": {
                "message_id": telegram_upload.message_id,
                "folder_id": target_folder_id,
                "storage": "telegram",
                "file_path": virtual_file_path,
                "filename": original_filename,
                "folder": cdn_folder,
                "uploaded_by": "direct_client",
            },
            "github": {
                "storage": "metadata",
                "repo": f"{config.GITHUB_USER}/{config.GITHUB_REPO}",
                "branch": config.GITHUB_BRANCH,
                "metadata_file": f"{config.METADATA_ROOT}/{cdn_folder}/{public_file_id}.json",
            },
            "metadata": parsed,
            "uploaded_at": parsed["uploaded_at"],
            **urls,
        }

        await github_store.upsert_file_record(record)
        return record
    finally:
        await stop_client()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload a local file directly to Telegram, bypassing Vercel upload limits.",
    )
    parser.add_argument("file", type=Path, help="Path to the file to upload")
    parser.add_argument("--folder-id", type=int, default=0, help="Telegram folder/chat id. Defaults to Saved Messages/configured storage.")
    parser.add_argument("--mime-type", help="Override detected MIME type")
    args = parser.parse_args()

    record = asyncio.run(upload_direct(args.file, args.folder_id, args.mime_type))
    print(json.dumps(record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
