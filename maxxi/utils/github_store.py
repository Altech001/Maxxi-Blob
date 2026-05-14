"""
github_store.py - read and write file metadata in the GitHub repo.

New records are stored as one JSON file per upload:

metadata/
  images/
    5791.json
  videos/
    5802.json
  documents/
    5803.json

The old single metadata.json store is still read as a fallback so existing
records remain visible while the app moves to the foldered layout.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

import config
from utils.cdn_url import folder_for_mime, safe_folder


HEADERS = {
    "Authorization": f"token {config.GITHUB_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/vnd.github+json",
}
CONTENTS_API_ROOT = (
    f"{config.GITHUB_API_URL}/repos/{config.GITHUB_USER}/"
    f"{config.GITHUB_REPO}/contents"
)


def _contents_url(path: str) -> str:
    encoded_path = "/".join(quote(part, safe="") for part in path.strip("/").split("/") if part)
    return f"{CONTENTS_API_ROOT}/{encoded_path}"


def _empty_store() -> dict[str, Any]:
    return {"files": []}


def metadata_folder_for_record(record: dict[str, Any]) -> str:
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
    return safe_folder(
        str(record.get("cdn_folder") or "")
        or folder_for_mime(
            str(record.get("mime_type") or metadata.get("mime_type") or ""),
            str(record.get("category") or metadata.get("category") or ""),
        )
    )


def record_metadata_path(record: dict[str, Any]) -> str:
    record_id = record.get("id") or record.get("message_id")
    if record_id is None:
        raise ValueError("Metadata record requires an id or message_id")
    folder = metadata_folder_for_record(record)
    return f"{config.METADATA_ROOT}/{folder}/{record_id}.json"


def bucket_policy_path(bucket: str) -> str:
    return f"{config.METADATA_ROOT}/bucket-policies/{safe_folder(bucket)}.json"


async def _fetch_json_file(path: str) -> tuple[Any | None, str | None]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_contents_url(path), headers=HEADERS)

    if resp.status_code == 404:
        return None, None

    resp.raise_for_status()
    data = resp.json()
    content = base64.b64decode(data["content"]).decode()
    return json.loads(content), data["sha"]


async def _save_json_file(
    path: str,
    data: Any,
    sha: str | None,
    commit_msg: str,
) -> None:
    encoded = base64.b64encode(json.dumps(data, indent=2, ensure_ascii=False).encode()).decode()
    payload: dict[str, Any] = {
        "message": commit_msg,
        "content": encoded,
        "branch": config.GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.put(_contents_url(path), headers=HEADERS, json=payload)

    resp.raise_for_status()


async def _delete_json_file(path: str, sha: str, commit_msg: str) -> None:
    payload = {
        "message": commit_msg,
        "sha": sha,
        "branch": config.GITHUB_BRANCH,
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.request("DELETE", _contents_url(path), headers=HEADERS, json=payload)

    resp.raise_for_status()


async def _list_directory(path: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_contents_url(path), headers=HEADERS)

    if resp.status_code == 404:
        return []

    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else []


async def _fetch_legacy_store() -> dict[str, Any]:
    data, _ = await _fetch_json_file(config.METADATA_FILE)
    return data if isinstance(data, dict) else _empty_store()


async def _fetch_legacy_record(file_id: str) -> dict[str, Any] | None:
    legacy_store = await _fetch_legacy_store()
    return next((item for item in legacy_store.get("files", []) if str(item.get("id")) == file_id), None)


async def _delete_legacy_record(file_id: str) -> bool:
    legacy_store, sha = await _fetch_json_file(config.METADATA_FILE)
    if not isinstance(legacy_store, dict) or not sha:
        return False

    files = legacy_store.get("files")
    if not isinstance(files, list):
        return False

    kept_files = [item for item in files if str(item.get("id")) != file_id]
    if len(kept_files) == len(files):
        return False

    legacy_store["files"] = kept_files
    await _save_json_file(
        config.METADATA_FILE,
        legacy_store,
        sha,
        commit_msg=f"Maxxi CDN: delete legacy {file_id}",
    )
    return True


async def _find_record_path(file_id: str) -> tuple[str, dict[str, Any], str] | None:
    for folder in config.CDN_FOLDER_MAP:
        path = f"{config.METADATA_ROOT}/{safe_folder(folder)}/{file_id}.json"
        data, sha = await _fetch_json_file(path)
        if isinstance(data, dict) and sha:
            return path, data, sha
    return None


async def append_file_record(record: dict[str, Any]) -> None:
    """Add a new file record to its type-specific metadata folder."""
    await upsert_file_record(record)


async def upsert_file_record(record: dict[str, Any]) -> None:
    """Create or replace a file record by id in its type-specific folder."""
    path = record_metadata_path(record)
    existing, sha = await _fetch_json_file(path)
    replaced = isinstance(existing, dict)
    github = record.get("github") if isinstance(record.get("github"), dict) else {}
    github_storage = github.get("storage") or (
        "bytes" if record.get("storage_backend") == "github" else "metadata"
    )
    saved_record = {
        **(existing if isinstance(existing, dict) else {}),
        **record,
        "github": {
            **github,
            "storage": github_storage,
            "repo": f"{config.GITHUB_USER}/{config.GITHUB_REPO}",
            "branch": config.GITHUB_BRANCH,
            "metadata_file": path,
        },
    }
    if replaced:
        saved_record["updated_at"] = datetime.now(timezone.utc).isoformat()

    await _save_json_file(
        path,
        saved_record,
        sha,
        commit_msg=f"Maxxi CDN: {'update' if replaced else 'add'} {record.get('filename', 'file')}",
    )


async def delete_file_record(file_id: str) -> bool:
    """Remove a record by id from whichever metadata folder contains it."""
    found = await _find_record_path(file_id)
    if not found:
        return await _delete_legacy_record(file_id)

    path, _, sha = found
    await _delete_json_file(path, sha, commit_msg=f"Maxxi CDN: delete {file_id}")
    return True


async def list_records() -> list[dict[str, Any]]:
    """Return records from all type-specific metadata folders, plus legacy records."""
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for folder in config.CDN_FOLDER_MAP:
        folder_path = f"{config.METADATA_ROOT}/{safe_folder(folder)}"
        entries = await _list_directory(folder_path)
        for entry in entries:
            if entry.get("type") != "file" or not str(entry.get("name", "")).endswith(".json"):
                continue
            data, _ = await _fetch_json_file(str(entry["path"]))
            if not isinstance(data, dict):
                continue
            record_id = str(data.get("id") or data.get("message_id") or "")
            if record_id:
                seen_ids.add(record_id)
            records.append(data)

    legacy_store = await _fetch_legacy_store()
    for record in legacy_store.get("files", []):
        record_id = str(record.get("id") or record.get("message_id") or "")
        if record_id and record_id in seen_ids:
            continue
        records.append(record)

    return records


async def get_record(file_id: str) -> dict[str, Any] | None:
    """Return a single record by id from foldered metadata, then legacy metadata."""
    found = await _find_record_path(file_id)
    if found:
        _, record, _ = found
        return record
    return await _fetch_legacy_record(file_id)


async def upsert_bucket_policy(bucket: str, policy: dict[str, Any]) -> dict[str, Any]:
    path = bucket_policy_path(bucket)
    existing, sha = await _fetch_json_file(path)
    now = datetime.now(timezone.utc).isoformat()
    saved_policy = {
        **(existing if isinstance(existing, dict) else {}),
        **policy,
        "bucket": bucket,
        "updated_at": now,
    }
    if not isinstance(existing, dict):
        saved_policy["created_at"] = now

    await _save_json_file(
        path,
        saved_policy,
        sha,
        commit_msg=f"Maxxi CDN: {'update' if sha else 'add'} bucket policy {bucket}",
    )
    return saved_policy


async def get_bucket_policy(bucket: str) -> dict[str, Any] | None:
    data, _ = await _fetch_json_file(bucket_policy_path(bucket))
    return data if isinstance(data, dict) else None


async def list_bucket_policies() -> list[dict[str, Any]]:
    policies: list[dict[str, Any]] = []
    entries = await _list_directory(f"{config.METADATA_ROOT}/bucket-policies")
    for entry in entries:
        if entry.get("type") != "file" or not str(entry.get("name", "")).endswith(".json"):
            continue
        data, _ = await _fetch_json_file(str(entry["path"]))
        if isinstance(data, dict):
            policies.append(data)
    return policies


async def delete_bucket_policy(bucket: str) -> bool:
    path = bucket_policy_path(bucket)
    _, sha = await _fetch_json_file(path)
    if not sha:
        return False
    await _delete_json_file(path, sha, commit_msg=f"Maxxi CDN: delete bucket policy {bucket}")
    return True
