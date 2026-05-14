from __future__ import annotations

import base64
import secrets
import string
import time
from typing import Annotated, Any
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

import config
from auth.jwt import get_current_user
from db_models import User
from utils.cdn_url import folder_for_mime, safe_filename


router = APIRouter(tags=["repo-cdn"])

_rate_limit_hits: dict[str, list[float]] = {}


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else "unknown"


def _rate_limit(request: Request) -> None:
    now = time.monotonic()
    window_start = now - config.RATE_LIMIT_WINDOW_SECONDS
    key = _client_ip(request)
    hits = [hit for hit in _rate_limit_hits.get(key, []) if hit >= window_start]
    if len(hits) >= config.RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Too many upload attempts, please try again later",
        )
    hits.append(now)
    _rate_limit_hits[key] = hits


def _make_id() -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(secrets.randbelow(3) + 2))


def _github_headers() -> dict[str, str]:
    if not config.GITHUB_TOKEN:
        raise HTTPException(status_code=500, detail="GITHUB_TOKEN is not configured")
    return {
        "Authorization": f"token {config.GITHUB_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/vnd.github+json",
    }


def _contents_url(file_path: str) -> str:
    encoded_path = "/".join(quote(part, safe="") for part in file_path.split("/") if part)
    return (
        f"{config.GITHUB_API_URL}/repos/{config.GITHUB_USER}/"
        f"{config.GITHUB_REPO}/contents/{encoded_path}"
    )


def _cdn_url(file_path: str) -> str:
    base = config.CDN_API_URL.rstrip("/")
    return f"{base}/{config.GITHUB_USER}/{config.GITHUB_REPO}@{config.GITHUB_BRANCH}/{file_path}"


async def _verify_turnstile(turnstile_response: str | None) -> None:
    if not turnstile_response:
        raise HTTPException(status_code=400, detail="CAPTCHA response is required")
    if not config.CF_TURNSTILE_SECRET_KEY:
        raise HTTPException(status_code=500, detail="Cloudflare Turnstile is not configured")

    payload = {
        "secret": config.CF_TURNSTILE_SECRET_KEY,
        "response": turnstile_response,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"{config.CF_TURNSTILE_API_URL}/turnstile/v0/siteverify",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    response.raise_for_status()
    data = response.json()
    if not data.get("success"):
        raise HTTPException(
            status_code=400,
            detail="CAPTCHA already used or invalid. Please reload page to continue.",
        )


async def _read_and_validate_file(file: UploadFile) -> bytes:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    mime_type = (file.content_type or "application/octet-stream").lower()
    if mime_type not in {mime.lower() for mime in config.ALLOWED_MIME_TYPES}:
        raise HTTPException(status_code=400, detail=f"File type not allowed: {mime_type}")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="No file uploaded")
    if len(data) > config.GITHUB_UPLOAD_MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds GitHub upload size limit")
    return data


async def _upload_to_github_repo(file: UploadFile) -> dict[str, Any]:
    file_bytes = await _read_and_validate_file(file)
    mime_type = file.content_type or "application/octet-stream"
    folder = folder_for_mime(mime_type)
    filename = safe_filename(f"{_make_id()}_{file.filename or 'upload'}")
    file_path = f"{folder}/{filename}"
    api_url = _contents_url(file_path)
    headers = _github_headers()

    async with httpx.AsyncClient(timeout=30) as client:
        existing = await client.get(api_url, headers=headers)
        if existing.status_code == 200:
            raw_url = _cdn_url(file_path)
            return {
                "success": True,
                "message": "File already exists, returning existing URL",
                "filename": filename,
                "file_path": file_path,
                "folder": folder,
                "mime_type": mime_type,
                "size_bytes": len(file_bytes),
                "rawUrl": raw_url,
                "raw_url": raw_url,
                "cdn_url": raw_url,
                "download_url": raw_url,
            }
        if existing.status_code != 404:
            existing.raise_for_status()

        payload = {
            "message": config.COMMIT_MESSAGE,
            "content": base64.b64encode(file_bytes).decode(),
            "branch": config.GITHUB_BRANCH,
        }
        created = await client.put(api_url, headers=headers, json=payload)
        created.raise_for_status()

    raw_url = _cdn_url(file_path)
    return {
        "success": True,
        "filename": filename,
        "original_filename": file.filename,
        "file_path": file_path,
        "folder": folder,
        "mime_type": mime_type,
        "size_bytes": len(file_bytes),
        "rawUrl": raw_url,
        "raw_url": raw_url,
        "cdn_url": raw_url,
        "download_url": raw_url,
    }


@router.post("/api/v1/repo/files")
async def upload_repo_file(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    _ = current_user
    _rate_limit(request)
    return JSONResponse(await _upload_to_github_repo(file))


@router.post("/api/upload.php", include_in_schema=False)
async def upload_repo_file_compat(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    _rate_limit(request)
    return JSONResponse(await _upload_to_github_repo(file))


@router.post("/giftedUpload.php", include_in_schema=False)
async def upload_repo_file_with_turnstile(
    request: Request,
    file: UploadFile = File(...),
    turnstile_response: Annotated[str | None, Form(alias="turnstileResponse")] = None,
) -> JSONResponse:
    _rate_limit(request)
    await _verify_turnstile(turnstile_response)
    return JSONResponse(await _upload_to_github_repo(file))
