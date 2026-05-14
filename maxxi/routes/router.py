# type: ignore
import base64
from collections.abc import AsyncIterator
from datetime import datetime, timezone
import os
from secrets import token_urlsafe
import tempfile
from typing import Annotated, Any, cast
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from sqlalchemy.orm import Session
from telethon.helpers import TotalList
from telethon.tl.custom.message import Message
from telethon.tl.types import DocumentAttributeFilename

import config
from auth.jwt import get_current_user
from db import get_db
from db_models import User, UserStorageSettings
from models import CDNFileRecord, DeleteResponse
from utils import github_store, metadata
from utils.cdn_url import attach_urls, build_file_urls, folder_for_mime, safe_filename
from utils.telegram_store import (
    delete_telegram_file,
    get_authorized_client,
    get_file_message,
    message_to_metadata,
    upload_path_to_telegram,
)


router = APIRouter(
    prefix="/api/v1",
    tags=["api"],
)
public_router = APIRouter(tags=["cdn"])


def _validate_upload(file: UploadFile, file_size: int) -> None:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    if file_size > config.MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds configured size limit")

    mime_type = (file.content_type or "application/octet-stream").lower()
    if mime_type not in {mime.lower() for mime in config.ALLOWED_MIME_TYPES}:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {mime_type}")


def _folder_id(value: int | None) -> int | None:
    if value in (None, 0):
        if config.TELEGRAM_AUTO_CREATE_FOLDERS:
            return None
        return config.TELEGRAM_STORAGE_FOLDER_ID
    return value


def _filename_from_message(message: Message) -> str:
    if message.document and message.document.attributes:
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                return attr.file_name
    if message.file and message.file.name:
        return message.file.name
    return f"file_{message.id}"


def _ensure_message(message) -> Message:
    if isinstance(message, TotalList):
        if not message:
            raise HTTPException(status_code=404, detail="File message not found")
        message = message[0]

    if message is None or getattr(message, "media", None) is None:
        raise HTTPException(status_code=404, detail="File message not found")

    return cast(Message, message)


def _content_disposition(filename: str, disposition: str) -> str:
    if disposition not in {"inline", "attachment"}:
        disposition = "attachment"
    escaped = filename.replace('"', "")
    return f'{disposition}; filename="{escaped}"'


def _is_owner(record: dict[str, Any], user: User) -> bool:
    if getattr(user, "role", "user") == "admin":
        return True
    return str(record.get("owner_user_id") or "") == user.id


def _user_records(records: list[dict[str, Any]], user: User) -> list[dict[str, Any]]:
    return [record for record in records if _is_owner(record, user)]


def _ensure_storage_settings(db: Session, user: User) -> UserStorageSettings:
    settings = db.query(UserStorageSettings).filter(UserStorageSettings.user_id == user.id).first()
    if settings:
        return settings
    settings = UserStorageSettings(user_id=user.id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


async def _user_used_bytes(user: User) -> int:
    records = await github_store.list_records()
    return sum(int(record.get("size_bytes") or 0) for record in _user_records(records, user))


async def _enforce_user_quota(user: User, db: Session, next_file_size: int) -> UserStorageSettings:
    settings = _ensure_storage_settings(db, user)
    used_bytes = await _user_used_bytes(user)
    quota_bytes = int(settings.quota_bytes or config.USER_STORAGE_LIMIT_BYTES)
    if used_bytes + next_file_size > quota_bytes:
        raise HTTPException(
            status_code=413,
            detail="User storage quota exceeded. Limit is 20GB.",
        )
    return settings


def _github_headers() -> dict[str, str]:
    if not config.GITHUB_TOKEN:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN is not configured")
    return {
        "Authorization": f"token {config.GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    }


def _github_contents_url(file_path: str) -> str:
    encoded_path = "/".join(quote(part, safe="") for part in file_path.split("/") if part)
    return (
        f"{config.GITHUB_API_URL}/repos/{config.GITHUB_USER}/"
        f"{config.GITHUB_REPO}/contents/{encoded_path}"
    )


def _github_cdn_url(file_path: str) -> str:
    base = config.CDN_API_URL.rstrip("/")
    return f"{base}/{config.GITHUB_USER}/{config.GITHUB_REPO}@{config.GITHUB_BRANCH}/{file_path}"


async def _github_cdn_redirect(
    record: dict[str, Any],
    disposition: str,
) -> StreamingResponse:
    file_path = str(record.get("file_path") or "")
    if not file_path:
        github = record.get("github") if isinstance(record.get("github"), dict) else {}
        file_path = str(github.get("file_path") or "")
    if not file_path:
        raise HTTPException(status_code=404, detail="GitHub file path not found")

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(_github_contents_url(file_path), headers=_github_headers())
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="GitHub file not found")
        response.raise_for_status()

    payload = response.json()
    content = str(payload.get("content") or "")
    encoding = str(payload.get("encoding") or "")
    if encoding != "base64" or not content:
        raise HTTPException(status_code=404, detail="GitHub file content not found")

    file_bytes = base64.b64decode(content)
    filename = str(record.get("filename") or os.path.basename(file_path) or "file")
    metadata_dict = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    media_type = str(
        record.get("mime_type")
        or metadata_dict.get("mime_type")
        or "application/octet-stream"
    )
    return StreamingResponse(
        iter([file_bytes]),
        media_type=media_type,
        headers={"Content-Disposition": _content_disposition(filename, disposition)},
    )


async def _upload_temp_to_github(
    temp_file_path: str,
    original_filename: str,
    mime_type: str,
    cdn_folder: str,
    owner: User,
) -> dict[str, Any]:
    file_size = os.path.getsize(temp_file_path)
    if file_size > config.GITHUB_UPLOAD_MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds GitHub upload size limit")

    cdn_filename = safe_filename(original_filename)
    object_id = f"gh_{token_urlsafe(10)}"
    file_path = f"users/{owner.id}/{cdn_folder}/{object_id}_{cdn_filename}"
    with open(temp_file_path, "rb") as temp_file:
        encoded = base64.b64encode(temp_file.read()).decode()

    payload = {
        "message": config.COMMIT_MESSAGE,
        "content": encoded,
        "branch": config.GITHUB_BRANCH,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        created = await client.put(_github_contents_url(file_path), headers=_github_headers(), json=payload)
        created.raise_for_status()

    return {
        "id": object_id,
        "filename": cdn_filename,
        "file_path": file_path,
        "cdn_url": _github_cdn_url(file_path),
    }


async def _delete_github_file(file_path: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        existing = await client.get(_github_contents_url(file_path), headers=_github_headers())
        if existing.status_code == 404:
            return
        existing.raise_for_status()
        sha = existing.json().get("sha")
        if not sha:
            return
        payload = {
            "message": f"Maxxi CDN: delete {file_path}",
            "sha": sha,
            "branch": config.GITHUB_BRANCH,
        }
        deleted = await client.request(
            "DELETE",
            _github_contents_url(file_path),
            headers=_github_headers(),
            json=payload,
        )
        deleted.raise_for_status()


async def _save_upload_to_temp(file: UploadFile) -> tuple[str, int]:
    temp_file_path = ""
    file_size = 0
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            while chunk := await file.read(1024 * 1024):
                file_size += len(chunk)
                if file_size > config.MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="File exceeds configured size limit")
                temp_file.write(chunk)
        return temp_file_path, file_size
    except Exception:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise


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
        "metadata_note": "Rich metadata parsing skipped for large file.",
    }


def _folder_totals(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    totals: dict[str, dict[str, int]] = {}
    for record in records:
        folder = str(record.get("cdn_folder") or record.get("category") or "documents")
        folder_total = totals.setdefault(folder, {"count": 0, "size_bytes": 0})
        folder_total["count"] += 1
        folder_total["size_bytes"] += int(record.get("size_bytes") or 0)
    return totals


def _listing_response(records: list[dict[str, Any]], request: Request) -> dict[str, Any]:
    attached_records = [attach_urls(record, request) for record in records]
    total_size = sum(int(record.get("size_bytes") or 0) for record in attached_records)
    return {
        "success": True,
        "total_files": len(attached_records),
        "total_size_bytes": total_size,
        "folders": _folder_totals(attached_records),
        "files": attached_records,
    }


async def _record_for_message(
    message_id: int,
    folder_id: int | None,
    request: Request,
) -> dict[str, Any]:
    records = await github_store.list_records()
    record = next((item for item in records if str(item.get("id")) == str(message_id)), None)
    if record:
        return attach_urls(record, request)

    message = _ensure_message(await get_file_message(message_id, folder_id))
    basic = message_to_metadata(message, folder_id)
    filename = basic.name
    category = metadata.get_category(basic.mime_type or "application/octet-stream")
    cdn_folder = folder_for_mime(basic.mime_type, category)
    record = {
        "id": str(message_id),
        "filename": filename,
        "message_id": message_id,
        "folder_id": folder_id,
        "size_bytes": basic.size,
        "mime_type": basic.mime_type,
        "category": category,
        "cdn_folder": cdn_folder,
        "extension": basic.file_ext or "",
        "telegram": {
            "message_id": message_id,
            "folder_id": folder_id,
        },
        "metadata": basic.model_dump(mode="json"),
        "uploaded_at": basic.created_at.isoformat(),
    }
    return attach_urls(record, request)


async def _stored_folder_id(file_id: int, provided_folder_id: int | None = None) -> int | None:
    if provided_folder_id not in (None, 0):
        return provided_folder_id

    record = await github_store.get_record(str(file_id))
    if record:
        telegram = record.get("telegram") if isinstance(record.get("telegram"), dict) else {}
        stored_folder_id = telegram.get("folder_id") or record.get("folder_id")
        if stored_folder_id not in (None, 0):
            return int(stored_folder_id)

    return _folder_id(provided_folder_id)


def _public_file_id(message_id: int, folder_id: int | None) -> str:
    if folder_id not in (None, 0):
        return f"{folder_id}_{message_id}"
    return str(message_id)


async def _telegram_location(file_id: str | int, provided_folder_id: int | None = None) -> tuple[int, int | None]:
    record = await github_store.get_record(str(file_id))
    if record:
        telegram = record.get("telegram") if isinstance(record.get("telegram"), dict) else {}
        message_id = int(record.get("message_id") or telegram.get("message_id"))
        stored_folder_id = telegram.get("folder_id") or record.get("folder_id")
        return message_id, int(stored_folder_id) if stored_folder_id not in (None, 0) else None

    try:
        return int(file_id), await _stored_folder_id(int(file_id), provided_folder_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail="File metadata not found") from e


@router.post("/files", response_model=CDNFileRecord)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    folder_id: Annotated[int | None, Form()] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CDNFileRecord:
    original_filename = file.filename or "upload"
    mime_type = file.content_type or "application/octet-stream"
    category = metadata.get_category(mime_type)
    cdn_folder = folder_for_mime(mime_type, category)
    target_folder_id = _folder_id(folder_id)
    temp_file_path, file_size = await _save_upload_to_temp(file)
    _validate_upload(file, file_size)
    storage_settings = await _enforce_user_quota(current_user, db, file_size)

    try:
        cdn_filename = safe_filename(original_filename)
        if file_size <= config.METADATA_PARSE_MAX_BYTES:
            with open(temp_file_path, "rb") as temp_file:
                parsed = metadata.extract(temp_file.read(), cdn_filename, mime_type)
        else:
            parsed = _basic_metadata(cdn_filename, mime_type, file_size)

        category = str(parsed.get("category") or category or "docs")
        cdn_folder = folder_for_mime(mime_type, category)

        if storage_settings.storage_backend == "github":
            github_upload = await _upload_temp_to_github(
                temp_file_path=temp_file_path,
                original_filename=original_filename,
                mime_type=mime_type,
                cdn_folder=cdn_folder,
                owner=current_user,
            )
            public_file_id = github_upload["id"]
            cdn_filename = github_upload["filename"]
            github_url = github_upload["cdn_url"]
            virtual_file_path = github_upload["file_path"]
            urls = build_file_urls(
                public_file_id,
                cdn_filename,
                request,
                cdn_url=github_url,
                folder=cdn_folder,
            )
            record = {
                "success": True,
                "id": public_file_id,
                "filename": cdn_filename,
                "original_filename": original_filename,
                "file_path": virtual_file_path,
                "message_id": None,
                "folder_id": None,
                "size_bytes": file_size,
                "mime_type": mime_type,
                "category": category,
                "cdn_folder": cdn_folder,
                "extension": parsed.get("extension", ""),
                "storage_backend": "github",
                "owner_user_id": current_user.id,
                "owner_email": current_user.email,
                "telegram": {},
                "github": {
                    "storage": "bytes",
                    "repo": f"{config.GITHUB_USER}/{config.GITHUB_REPO}",
                    "branch": config.GITHUB_BRANCH,
                    "file_path": virtual_file_path,
                    "metadata_file": f"{config.METADATA_ROOT}/{cdn_folder}/{public_file_id}.json",
                },
                "metadata": parsed,
                "uploaded_at": parsed["uploaded_at"],
                **urls,
                "cdn_path": virtual_file_path,
            }
            await github_store.upsert_file_record(record)
            return CDNFileRecord(**record)

        telegram_upload = await upload_path_to_telegram(
            file_path=temp_file_path,
            filename=original_filename,
            mime_type=mime_type,
            folder_id=target_folder_id,
            folder_slug=cdn_folder,
        )
        target_folder_id = telegram_upload.folder_id
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    public_file_id = _public_file_id(telegram_upload.message_id, target_folder_id)
    urls = build_file_urls(
        public_file_id,
        cdn_filename,
        request,
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
        "mime_type": mime_type,
        "category": category,
        "cdn_folder": cdn_folder,
        "extension": parsed.get("extension", ""),
        "telegram": {
            "message_id": telegram_upload.message_id,
            "folder_id": target_folder_id,
            "storage": "telegram",
            "folder": cdn_folder,
            "file_path": virtual_file_path,
            "filename": original_filename,
        },
        "github": {
            "storage": "metadata",
            "repo": f"{config.GITHUB_USER}/{config.GITHUB_REPO}",
            "branch": config.GITHUB_BRANCH,
            "metadata_file": f"{config.METADATA_ROOT}/{cdn_folder}/{public_file_id}.json",
        },
        "metadata": parsed,
        "storage_backend": "telegram",
        "owner_user_id": current_user.id,
        "owner_email": current_user.email,
        "uploaded_at": parsed["uploaded_at"],
        **urls,
    }

    await github_store.upsert_file_record(record)
    return CDNFileRecord(**record)


@router.get("/files")
async def list_files(
    request: Request,
    folder: str | None = None,
    category: str | None = None,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    records = await github_store.list_records()
    records = _user_records(records, current_user)
    if folder:
        records = [record for record in records if str(record.get("cdn_folder")) == folder]
    if category:
        records = [record for record in records if str(record.get("category")) == category]
    return JSONResponse(_listing_response(records, request))


@router.get("/files/{file_id}/metadata")
async def file_metadata(
    file_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    record = await github_store.get_record(file_id)
    if not record:
        raise HTTPException(status_code=404, detail="File metadata not found")
    if not _is_owner(record, current_user):
        raise HTTPException(status_code=403, detail="You do not have access to this file")
    return JSONResponse(attach_urls(record, request))


@router.get("/files/{file_id}/download", response_model=None)
async def download_file(
    file_id: str,
    disposition: Annotated[str, Query(pattern="^(inline|attachment)$")] = "inline",
    folder_id: int | None = None,
) -> StreamingResponse | RedirectResponse:
    # Check if this is a GitHub-stored file first
    record = await github_store.get_record(str(file_id))
    if record and record.get("storage_backend") == "github":
        return await _github_cdn_redirect(record, disposition)

    # Telegram-stored file — stream from Telegram
    message_id, target_folder_id = await _telegram_location(file_id, folder_id)
    message = _ensure_message(await get_file_message(message_id, target_folder_id))
    filename = _filename_from_message(message)

    client_obj = await get_authorized_client()

    async def stream() -> AsyncIterator[bytes]:
        async for chunk in client_obj.iter_download(message.media): # type: ignore
            yield chunk

    return StreamingResponse(
        stream(),
        media_type=message.file.mime_type or "application/octet-stream",
        headers={"Content-Disposition": _content_disposition(filename, disposition)},
    )


@router.get("/files/{file_id}/preview", response_model=None)
async def preview_file(file_id: str, folder_id: int | None = None) -> StreamingResponse | RedirectResponse:
    # Check if this is a GitHub-stored file first
    record = await github_store.get_record(str(file_id))
    if record and record.get("storage_backend") == "github":
        return await _github_cdn_redirect(record, "inline")

    # Telegram-stored file — get thumbnail
    message_id, target_folder_id = await _telegram_location(file_id, folder_id)
    message = _ensure_message(await get_file_message(message_id, target_folder_id))
    thumb = -1 if getattr(message.media, "document", None) or getattr(message.media, "photo", None) else None
    client_obj = await get_authorized_client()
    preview_bytes = await client_obj.download_media(message, file=bytes, thumb=thumb)
    if not preview_bytes:
        raise HTTPException(status_code=404, detail="Preview not available")
    return StreamingResponse(iter([preview_bytes]), media_type="image/jpeg")


@router.delete("/files/{file_id}", response_model=DeleteResponse)
async def delete_file(
    file_id: str,
    folder_id: int | None = None,
    current_user: User = Depends(get_current_user),
) -> DeleteResponse:
    record = await github_store.get_record(str(file_id))
    if record and not _is_owner(record, current_user):
        raise HTTPException(status_code=403, detail="You do not have access to this file")
    if record and record.get("storage_backend") == "github":
        file_path = str(record.get("file_path") or "")
        if file_path:
            await _delete_github_file(file_path)
        await github_store.delete_file_record(str(file_id))
        return DeleteResponse(message=f"File {file_id} deleted")
    message_id, target_folder_id = await _telegram_location(file_id, folder_id)
    await delete_telegram_file(message_id, target_folder_id)
    await github_store.delete_file_record(str(file_id))
    return DeleteResponse(message=f"File {file_id} deleted")


@router.get("/cdn/{file_id}/{filename:path}", include_in_schema=False)
async def cdn_file(file_id: str, filename: str) -> RedirectResponse:
    return RedirectResponse(url=f"/api/v1/files/{file_id}/download?disposition=inline")


@public_router.get(
    "/gh/{owner}/{repo_ref}/telegram/{cdn_folder}/{file_id}/{filename:path}",
    include_in_schema=False,
)
async def jsdelivr_like_file_with_folder(
    owner: str,
    repo_ref: str,
    cdn_folder: str,
    file_id: str,
    filename: str,
) -> StreamingResponse:
    repo, _, branch = repo_ref.partition("@")
    if owner != config.GITHUB_USER or repo != config.GITHUB_REPO:
        raise HTTPException(status_code=404, detail="CDN namespace not found")
    if branch and branch != config.GITHUB_BRANCH:
        raise HTTPException(status_code=404, detail="CDN branch not found")
    return await download_file(file_id=file_id, disposition="inline")


@public_router.get(
    "/gh/{owner}/{repo_ref}/telegram/{file_id}/{filename:path}",
    include_in_schema=False,
)
async def jsdelivr_like_file(
    owner: str,
    repo_ref: str,
    file_id: str,
    filename: str,
) -> StreamingResponse:
    repo, _, branch = repo_ref.partition("@")
    if owner != config.GITHUB_USER or repo != config.GITHUB_REPO:
        raise HTTPException(status_code=404, detail="CDN namespace not found")
    if branch and branch != config.GITHUB_BRANCH:
        raise HTTPException(status_code=404, detail="CDN branch not found")
    return await download_file(file_id=file_id, disposition="inline")
