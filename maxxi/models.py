from pydantic import BaseModel
from datetime import datetime
from typing import Any


class FileMetadata(BaseModel):
    id: int
    folder_id: int | None = None
    name: str
    size: int
    mime_type: str | None = None
    file_ext: str | None = None
    created_at: datetime
    icon_type: str = "file"


class FolderMetadata(BaseModel):
    id: int
    parent_id: int | None = None
    name: str


class HealthCheckResponse(BaseModel):
    status: str
    telegram_connected: bool
    telegram_authorized: bool


class UploadResponse(BaseModel):
    filename: str
    message_id: int
    size: int
    folder_id: int | None = None


class CDNFileRecord(BaseModel):
    success: bool = True
    id: str
    filename: str
    original_filename: str
    file_path: str
    message_id: int | None = None
    folder_id: int | None = None
    size_bytes: int
    mime_type: str | None = None
    category: str
    cdn_folder: str
    extension: str
    telegram: dict[str, Any] = {}
    metadata: dict[str, Any]
    github: dict[str, Any] = {}
    cdn_url: str
    rawUrl: str
    raw_url: str
    download_url: str
    inline_url: str
    metadata_url: str
    preview_url: str
    api_download_url: str
    api_inline_url: str
    api_attachment_url: str
    api_preview_url: str
    cdn_path: str
    uploaded_at: str


class DeleteResponse(BaseModel):
    message: str


class CreateFolderRequest(BaseModel):
    name: str


class CreateFolderResponse(BaseModel):
    id: int
    name: str


class MoveFilesRequest(BaseModel):
    message_ids: list[int]
    source_folder_id: int | None = None
    target_folder_id: int | None = None


# class SearchRequestModel(BaseModel):
#     query: str
#     folder_id: int | None = None
