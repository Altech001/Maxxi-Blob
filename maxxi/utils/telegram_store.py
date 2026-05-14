# type: ignore

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager


from pydantic import BaseModel
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import DocumentAttributeFilename, Channel
from telethon.tl.functions.channels import CreateChannelRequest, DeleteChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import DeleteMessagesRequest, ForwardMessagesRequest
from telethon.tl import types, functions


from telethon.errors import FloodWaitError
from collections import OrderedDict
import os
import asyncio
import logging
from datetime import datetime
import tempfile
import math
from time import monotonic
from dotenv import load_dotenv

import config


# Load environment variables
load_dotenv()


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await start_client()
    
    yield
    
    # Shutdown logic
    await stop_client()

app = FastAPI(
    title="Telegram Blob Storage API",
    description="API to use Telegram as an infinite blob storage backend.",
    version="1.0.0",
    lifespan=lifespan
)


# Mount static files when the optional demo UI exists.
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    if not os.path.exists("static/index.html"):
        raise HTTPException(status_code=404, detail="Static UI not installed")
    return FileResponse("static/index.html")


def _telegram_session():
    session_string = os.getenv("TELEGRAM_SESSION_STRING", "").strip()
    if session_string:
        return StringSession(session_string)

    session_file = os.getenv("TELEGRAM_SESSION_FILE", "telegram_blob_session")
    if os.getenv("VERCEL") and not os.path.isabs(session_file):
        session_file = os.path.join("/tmp", session_file)
    return session_file


# Telegram API credentials and session file
API_ID = int(os.getenv('TELEGRAM_API_ID', '0')) # Replace with your API ID
API_HASH = os.getenv('TELEGRAM_API_HASH', 'YOUR_API_HASH') # Replace with your API Hash
SESSION_NAME = _telegram_session()

if not API_ID or API_HASH == 'YOUR_API_HASH':
    logger.warning("Please set TELEGRAM_API_ID and TELEGRAM_API_HASH before using Telegram storage endpoints.")
    # In a real application, you might want to exit or handle this more gracefully

client: TelegramClient | None = None
if API_ID and API_HASH != "YOUR_API_HASH":
    client = TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH,
        connection_retries=10,
        retry_delay=2,
        auto_reconnect=True,
        request_retries=10,
    )


def require_configured_client() -> TelegramClient:
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="Telegram client is not configured. Set TELEGRAM_API_ID and TELEGRAM_API_HASH.",
        )
    return client


async def start_client() -> None:
    if client is None:
        logger.warning("Telegram client not started because TELEGRAM_API_ID/TELEGRAM_API_HASH are missing.")
        return
    client_obj = client
    logger.info("Starting up Telegram client...")
    try:
        await client_obj.start()
        if not await client_obj.is_user_authorized():
            logger.warning("Client not authorized. Please run the auth_cli.py script to authorize.")
        else:
            logger.info("Telegram client authorized successfully.")
    except Exception as e:
        logger.error(f"Error during Telegram client startup: {e}")
        if os.getenv("VERCEL"):
            logger.error("On Vercel, set TELEGRAM_SESSION_STRING instead of relying on a .session file.")


async def stop_client() -> None:
    if client is None:
        return
    logger.info("Shutting down Telegram client...")
    await client.disconnect()


class LRUCache:
    def __init__(self, max_items: int, ttl_seconds: int):
        self.max_items = max_items
        self.ttl_seconds = ttl_seconds
        self.items = OrderedDict()

    def get(self, key):
        item = self.items.get(key)
        if not item:
            return None

        created_at, value = item
        if monotonic() - created_at > self.ttl_seconds:
            self.items.pop(key, None)
            return None

        self.items.move_to_end(key)
        return value

    def set(self, key, value):
        self.items[key] = (monotonic(), value)
        self.items.move_to_end(key)
        while len(self.items) > self.max_items:
            self.items.popitem(last=False)

    def pop(self, key):
        self.items.pop(key, None)

    def clear(self):
        self.items.clear()

    def delete_where(self, predicate):
        for key in list(self.items.keys()):
            if predicate(key):
                self.items.pop(key, None)


FILE_LIST_CACHE_TTL_SECONDS = int(os.getenv("FILE_LIST_CACHE_TTL_SECONDS", "15"))
FOLDER_LIST_CACHE_TTL_SECONDS = int(os.getenv("FOLDER_LIST_CACHE_TTL_SECONDS", "60"))
PREVIEW_CACHE_TTL_SECONDS = int(os.getenv("PREVIEW_CACHE_TTL_SECONDS", "3600"))
MESSAGE_CACHE_TTL_SECONDS = int(os.getenv("MESSAGE_CACHE_TTL_SECONDS", "300"))

file_list_cache = LRUCache(max_items=int(os.getenv("FILE_LIST_CACHE_MAX_ITEMS", "64")), ttl_seconds=FILE_LIST_CACHE_TTL_SECONDS)
folder_list_cache = LRUCache(max_items=1, ttl_seconds=FOLDER_LIST_CACHE_TTL_SECONDS)
preview_cache = LRUCache(max_items=int(os.getenv("PREVIEW_CACHE_MAX_ITEMS", "256")), ttl_seconds=PREVIEW_CACHE_TTL_SECONDS)
message_cache = LRUCache(max_items=int(os.getenv("MESSAGE_CACHE_MAX_ITEMS", "1024")), ttl_seconds=MESSAGE_CACHE_TTL_SECONDS)
preview_tasks = {}


def file_cache_key(folder_id: int | None):
    return folder_id


def message_cache_key(folder_id: int | None, message_id: int):
    return (folder_id, message_id)


def preview_cache_key(folder_id: int | None, message_id: int):
    return (folder_id, message_id)


def invalidate_folder_cache(folder_id: int | None):
    file_list_cache.pop(file_cache_key(folder_id))
    message_cache.delete_where(lambda key: key[0] == folder_id)
    preview_cache.delete_where(lambda key: key[0] == folder_id)


def cache_message(folder_id: int | None, message):
    if message:
        message_cache.set(message_cache_key(folder_id, message.id), message)


def message_to_metadata(message, folder_id: int | None) -> "FileMetadata":
    filename = None
    if message.document and message.document.attributes:
        for attr in message.document.attributes:
            if isinstance(attr, DocumentAttributeFilename):
                filename = attr.file_name
                break

    if not filename:
        filename = message.file.name

    if (not filename or filename.lower() == "unknown") and message.message and "Uploaded to Maxxi: " in message.message:
        filename = message.message.split("Uploaded to Maxxi: ")[-1].strip()

    if not filename or filename.lower() == "unknown":
        filename = f"file_{message.id}"

    return FileMetadata(
        id=message.id,
        folder_id=folder_id,
        name=filename,
        size=message.file.size,
        mime_type=message.file.mime_type,
        file_ext=filename.split(".")[-1] if "." in filename else None,
        created_at=message.date,
        icon_type="file"
    )

# Fast Upload Helper for Parallelism
async def fast_upload(client_obj: TelegramClient, file_path: str, name: str):
    file_size = os.path.getsize(file_path)
    # Determine chunk size: 512KB is optimal for large files
    chunk_size = 512 * 1024
    total_parts = math.ceil(file_size / chunk_size)
    is_big = file_size > 10 * 1024 * 1024
    
    file_id = int.from_bytes(os.urandom(8), 'big', signed=True)
    
    # Increase the number of concurrent uploads
    # Telethon uses a single connection by default, but we can parallelize requests
    semaphore = asyncio.Semaphore(8) # 8 concurrent parts
    
    logger.info(f"FastUpload: Starting parallel upload for {name} ({total_parts} parts)")

    async def upload_part(part_index, chunk):
        async with semaphore:
            if is_big:
                await client_obj(functions.upload.SaveBigFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    file_total_parts=total_parts,
                    bytes=chunk
                ))
            else:
                await client_obj(functions.upload.SaveFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    bytes=chunk
                ))

    with open(file_path, 'rb') as f:
        tasks = []
        for i in range(total_parts):
            chunk = f.read(chunk_size)
            tasks.append(asyncio.create_task(upload_part(i, chunk)))
            if len(tasks) >= 8:
                await asyncio.gather(*tasks)
                tasks = []
        
        if tasks:
            await asyncio.gather(*tasks)
    
    if is_big:
        return types.InputFileBig(id=file_id, parts=total_parts, name=name)
    else:
        # For small files, we can just return a standard InputFile
        # (Though SaveFilePartRequest works too)
        return types.InputFile(id=file_id, parts=total_parts, name=name, md5_checksum='')


# Pydantic Models for API responses
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

class SearchRequestModel(BaseModel):
    query: str
    folder_id: int | None = None

# Helper function to check authorization
async def get_authorized_client():
    client_obj = require_configured_client()
    if not client_obj.is_connected():
        try:
            await client_obj.connect()
        except Exception as e:
            logger.error(f"Telegram client connection failed: {e}")
            raise HTTPException(
                status_code=503,
                detail="Telegram client connection failed. On Vercel, set TELEGRAM_SESSION_STRING.",
            ) from e
    if not await client_obj.is_user_authorized():
        raise HTTPException(status_code=401, detail="Telegram client not authorized. Please run auth_cli.py first.")
    return client_obj

# Helper to resolve peer (user, chat, channel)
async def resolve_peer(client_obj, folder_id: int | None):
    if folder_id in (None, 0):
        # Default to 'Saved Messages' (self)
        return await client_obj.get_me()
    
    try:
        # Attempt to get the entity directly by ID
        return await client_obj.get_entity(folder_id)
    except ValueError:
        # If not found in cache, fall back to iterating dialogs (though get_entity is usually sufficient)
        async for dialog in client_obj.iter_dialogs():
            if dialog.entity.id == folder_id:
                return dialog.entity
        raise HTTPException(status_code=404, detail=f"Folder/Chat with ID {folder_id} not found.")
    except Exception as e:
        logger.error(f"Error resolving peer {folder_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error resolving peer: {e}")


FOLDER_ABOUT_TAG = "[maxxi-cdn-folder]"
folder_peer_cache = LRUCache(max_items=32, ttl_seconds=FOLDER_LIST_CACHE_TTL_SECONDS)
folder_locks: dict[str, asyncio.Lock] = {}


def _storage_folder_name(folder_slug: str) -> str:
    label = folder_slug.replace("-", " ").replace("_", " ").title()
    prefix = config.TELEGRAM_FOLDER_PREFIX or "Maxxi"
    return f"{prefix} {label}"


def _storage_folder_title(folder_slug: str) -> str:
    return f"{_storage_folder_name(folder_slug)} [TD]"


def _storage_folder_about(folder_slug: str) -> str:
    return (
        "Maxxi CDN Telegram Storage Folder\n"
        f"{FOLDER_ABOUT_TAG}:{folder_slug}\n"
        "[telegram-drive-folder]"
    )


async def _create_storage_folder(client_obj: TelegramClient, folder_slug: str) -> int:
    title = _storage_folder_title(folder_slug)
    logger.info(f"Creating Telegram storage folder: {title}")
    result = await client_obj(
        CreateChannelRequest(
            title=title,
            about=_storage_folder_about(folder_slug),
            megagroup=False,
            broadcast=True,
        )
    )

    for chat in getattr(result, "chats", []) or []:
        if isinstance(chat, Channel):
            folder_list_cache.clear()
            folder_peer_cache.set(folder_slug, chat.id)
            return chat.id

    for update in getattr(result, "updates", []) or []:
        for chat in getattr(update, "chats", []) or []:
            if isinstance(chat, Channel):
                folder_list_cache.clear()
                folder_peer_cache.set(folder_slug, chat.id)
                return chat.id

    await asyncio.sleep(1)
    created_folder_id = await _find_storage_folder(client_obj, folder_slug)
    if created_folder_id is not None:
        return created_folder_id

    raise HTTPException(status_code=500, detail=f"Failed to create Telegram storage folder: {title}")


async def _find_storage_folder(client_obj: TelegramClient, folder_slug: str) -> int | None:
    cached = folder_peer_cache.get(folder_slug)
    if cached is not None:
        return cached

    expected_title = _storage_folder_title(folder_slug).lower()
    legacy_title = f"{folder_slug} [td]".lower()

    async for dialog in client_obj.iter_dialogs():
        if not isinstance(dialog.entity, Channel):
            continue

        title = (dialog.title or "").lower()
        if title in {expected_title, legacy_title}:
            folder_peer_cache.set(folder_slug, dialog.entity.id)
            return dialog.entity.id

        try:
            full_channel = await client_obj(GetFullChannelRequest(channel=dialog.entity))
            about = getattr(full_channel.full_chat, "about", "") or ""
            if f"{FOLDER_ABOUT_TAG}:{folder_slug}" in about:
                folder_peer_cache.set(folder_slug, dialog.entity.id)
                return dialog.entity.id
        except Exception as e:
            logger.debug(f"Could not inspect Telegram folder {dialog.title}: {e}")

    return None


async def ensure_storage_folder(client_obj: TelegramClient, folder_slug: str) -> int:
    lock = folder_locks.setdefault(folder_slug, asyncio.Lock())
    async with lock:
        existing_folder_id = await _find_storage_folder(client_obj, folder_slug)
        if existing_folder_id is not None:
            return existing_folder_id
        return await _create_storage_folder(client_obj, folder_slug)


async def resolve_upload_folder_id(
    folder_id: int | None,
    folder_slug: str | None = None,
    client_obj: TelegramClient | None = None,
) -> int | None:
    if folder_id not in (None, 0):
        return folder_id
    if not config.TELEGRAM_AUTO_CREATE_FOLDERS or not folder_slug:
        return config.TELEGRAM_STORAGE_FOLDER_ID
    client_obj = client_obj or await get_authorized_client()
    return await ensure_storage_folder(client_obj, folder_slug)


async def upload_bytes_to_telegram(
    file_bytes: bytes,
    filename: str,
    mime_type: str | None = None,
    folder_id: int | None = None,
    folder_slug: str | None = None,
    client_obj: TelegramClient | None = None,
) -> UploadResponse:
    client_obj = client_obj or await get_authorized_client()
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(file_bytes)

        target_folder_id = await resolve_upload_folder_id(folder_id, folder_slug, client_obj)
        target_peer = await resolve_peer(client_obj, target_folder_id)
        input_file = await fast_upload(client_obj, temp_file_path, filename)
        message = await client_obj.send_file(
            target_peer,
            input_file,
            caption=f"Uploaded to Maxxi: {filename}",
            force_document=True,
            attributes=[DocumentAttributeFilename(filename)],
        )
        cache_message(target_folder_id, message)
        invalidate_folder_cache(target_folder_id)

        return UploadResponse(filename=filename, message_id=message.id, size=len(file_bytes), folder_id=target_folder_id)
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


async def upload_path_to_telegram(
    file_path: str,
    filename: str,
    mime_type: str | None = None,
    folder_id: int | None = None,
    folder_slug: str | None = None,
    client_obj: TelegramClient | None = None,
) -> UploadResponse:
    client_obj = client_obj or await get_authorized_client()
    try:
        target_folder_id = await resolve_upload_folder_id(folder_id, folder_slug, client_obj)
        target_peer = await resolve_peer(client_obj, target_folder_id)
        input_file = await fast_upload(client_obj, file_path, filename)
        message = await client_obj.send_file(
            target_peer,
            input_file,
            caption=f"Uploaded to Maxxi: {filename}",
            force_document=True,
            attributes=[DocumentAttributeFilename(filename)],
        )
        cache_message(target_folder_id, message)
        invalidate_folder_cache(target_folder_id)

        return UploadResponse(
            filename=filename,
            message_id=message.id,
            size=os.path.getsize(file_path),
            folder_id=target_folder_id,
        )
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")


async def get_file_message(
    message_id: int,
    folder_id: int | None = None,
    client_obj: TelegramClient | None = None,
):
    client_obj = client_obj or await get_authorized_client()
    target_peer = await resolve_peer(client_obj, folder_id)
    message = message_cache.get(message_cache_key(folder_id, message_id))
    if not message:
        message = await client_obj.get_messages(target_peer, ids=message_id)
        cache_message(folder_id, message)
    if not message or not message.media or not message.file:
        raise HTTPException(status_code=404, detail="File not found")
    return message


async def delete_telegram_file(
    message_id: int,
    folder_id: int | None = None,
    client_obj: TelegramClient | None = None,
) -> None:
    client_obj = client_obj or await get_authorized_client()
    target_peer = await resolve_peer(client_obj, folder_id)
    await client_obj.delete_messages(target_peer, [message_id])
    invalidate_folder_cache(folder_id)




@app.get("/health", response_model=HealthCheckResponse)
async def health_check():
    if client is None:
        connected = False
        authorized = False
    else:
        connected = client.is_connected()
        authorized = await client.is_user_authorized()
    return HealthCheckResponse(
        status="ok" if connected and authorized else "degraded",
        telegram_connected=connected,
        telegram_authorized=authorized
    )


@app.post("/upload", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...), folder_id: int | None = None, client_obj: TelegramClient = Depends(get_authorized_client)):
    temp_file_path = None
    try:
        # Create a temporary file to store the incoming chunks
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            logger.info(f"Receiving file chunks into temporary file: {temp_file_path}")
            file_size = 0
            while contents := await file.read(1024 * 1024): # Read in 1MB chunks
                temp_file.write(contents)
                file_size += len(contents)
                logger.debug(f"Received {file_size} bytes for {file.filename}")
        
        target_peer = await resolve_peer(client_obj, folder_id)

        logger.info(f"Uploading file: {file.filename} ({file_size} bytes) to folder_id: {folder_id}")
        
        # Perform high-speed parallel upload
        input_file = await fast_upload(client_obj, temp_file_path, file.filename)
        
        # Send the uploaded file as a document
        message = await client_obj.send_file(
            target_peer, 
            input_file, 
            caption=f"Uploaded to Maxxi: {file.filename}",
            force_document=True
        )
        logger.info(f"File uploaded. Message ID: {message.id}")
        invalidate_folder_cache(folder_id)


        return UploadResponse(filename=file.filename, message_id=message.id, size=file_size)
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {e}")
    finally:
        # Clean up the temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Cleaned up temporary file: {temp_file_path}")


@app.get("/download/{message_id}")
async def download_file(message_id: int, folder_id: int | None = None, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        target_peer = await resolve_peer(client_obj, folder_id)
        
        message = message_cache.get(message_cache_key(folder_id, message_id))
        if not message:
            message = await client_obj.get_messages(target_peer, ids=message_id)
            cache_message(folder_id, message)
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="File not found or no media in message.")

        if not message.file:
            raise HTTPException(status_code=404, detail="No file attached to this message.")


        filename = "downloaded_file"
        if message.document and message.document.attributes:
            for attr in message.document.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    filename = attr.file_name
                    break
        
        logger.info(f"Downloading file for message ID: {message_id} from folder_id: {folder_id} (filename: {filename})")
        
        async def file_iterator():
            downloaded_bytes = 0
            total_size = message.file.size
            async for chunk in client_obj.iter_download(message.media):
                downloaded_bytes += len(chunk)
                if downloaded_bytes % (10 * 1024 * 1024) == 0: # Log every 10MB
                    logger.info(f"Downloaded {downloaded_bytes}/{total_size} bytes for {filename}")
                yield chunk


        return StreamingResponse(file_iterator(), media_type=message.file.mime_type, headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\""
        })
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {e}")

@app.get("/preview/{message_id}")
async def get_preview(message_id: int, folder_id: int | None = None, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        cache_key = preview_cache_key(folder_id, message_id)
        cached_preview = preview_cache.get(cache_key)
        if cached_preview:
            logger.debug(f"Preview cache hit for message ID: {message_id} in folder_id: {folder_id}")
            return Response(
                content=cached_preview,
                media_type="image/jpeg",
                headers={"Cache-Control": f"public, max-age={PREVIEW_CACHE_TTL_SECONDS}"}
            )

        existing_task = preview_tasks.get(cache_key)
        if existing_task:
            preview_bytes = await existing_task
            if not preview_bytes:
                raise HTTPException(status_code=404, detail="Preview not available")
            return Response(
                content=preview_bytes,
                media_type="image/jpeg",
                headers={"Cache-Control": f"public, max-age={PREVIEW_CACHE_TTL_SECONDS}"}
            )

        target_peer = await resolve_peer(client_obj, folder_id)
        message = message_cache.get(message_cache_key(folder_id, message_id))
        if not message:
            message = await client_obj.get_messages(target_peer, ids=message_id)
            cache_message(folder_id, message)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="No media found")

        # Determine if we should download the thumb or the whole file (for small images)
        thumb = None
        if hasattr(message.media, 'document') and message.media.document.thumbs:
            thumb = -1 # Get the last (usually largest) thumbnail
        elif hasattr(message.media, 'photo'):
            thumb = -1

        task = asyncio.create_task(client_obj.download_media(message, file=bytes, thumb=thumb))
        preview_tasks[cache_key] = task
        try:
            preview_bytes = await task
        finally:
            preview_tasks.pop(cache_key, None)

        if not preview_bytes:
            raise HTTPException(status_code=404, detail="Preview not available")

        preview_cache.set(cache_key, preview_bytes)

        # Return as JPEG for previews
        return Response(
            content=preview_bytes,
            media_type="image/jpeg",
            headers={"Cache-Control": f"public, max-age={PREVIEW_CACHE_TTL_SECONDS}"}
        )
    except Exception as e:
        logger.error(f"Error generating preview for {message_id}: {e}")
        raise HTTPException(status_code=404, detail="Preview not available")


@app.delete("/delete/{message_id}", response_model=DeleteResponse)
async def delete_file(message_id: int, folder_id: int | None = None, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        target_peer = await resolve_peer(client_obj, folder_id)

        logger.info(f"Attempting to delete message ID: {message_id} from folder_id: {folder_id}")
        await client_obj.delete_messages(target_peer, [message_id])
        invalidate_folder_cache(folder_id)
        logger.info(f"Message ID {message_id} deleted successfully.")
        return DeleteResponse(message=f"File with message ID {message_id} deleted successfully.")
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")

@app.post("/create_folder", response_model=CreateFolderResponse)
async def create_folder(request: CreateFolderRequest, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        # Telegram-Drive creates a private channel as a folder
        # Telethon equivalent: client(CreateChannelRequest(title, about, ...))
        title = f"{request.name} [TD]"
        about = "Telegram Drive Storage Folder\n[telegram-drive-folder]"
        
        logger.info(f"Creating Telegram channel: {title}")
        result = await client_obj(CreateChannelRequest(
            title=title,
            about=about,
            megagroup=False, # Not a megagroup
            broadcast=True, # Channel
        ))

        # The result contains an Update object, we need to extract the channel ID
        # This part can be a bit tricky as the structure might vary.
        # Assuming the channel is in the updates.chats
        channel_id = None
        if hasattr(result, 'updates'):
            for update in result.updates:
                if hasattr(update, 'chats'):
                    for chat in update.chats:
                        if isinstance(chat, Channel):
                            channel_id = chat.id
                            break
                if channel_id:
                    break
        
        if channel_id is None:
            raise HTTPException(status_code=500, detail="Failed to retrieve channel ID after creation.")

        folder_list_cache.clear()
        logger.info(f"Folder (channel) '{request.name}' created with ID: {channel_id}")
        return CreateFolderResponse(id=channel_id, name=request.name)
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {e}")

@app.delete("/delete_folder/{folder_id}", response_model=DeleteResponse)
async def delete_folder(folder_id: int, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        # Resolve the peer to ensure it's a channel before attempting to delete
        entity = await client_obj.get_entity(folder_id)
        if not isinstance(entity, Channel):
            raise HTTPException(status_code=400, detail="Only channels can be deleted as folders.")

        logger.info(f"Attempting to delete folder (channel) with ID: {folder_id}")
        await client_obj(DeleteChannelRequest(channel=entity))
        folder_list_cache.clear()
        invalidate_folder_cache(folder_id)
        logger.info(f"Folder (channel) {folder_id} deleted successfully.")
        return DeleteResponse(message=f"Folder with ID {folder_id} deleted successfully.")
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting folder: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete folder: {e}")

@app.post("/move_files", response_model=dict)
async def move_files(request: MoveFilesRequest, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        source_peer = await resolve_peer(client_obj, request.source_folder_id)
        target_peer = await resolve_peer(client_obj, request.target_folder_id)

        if source_peer.id == target_peer.id:
            return {"message": "Source and target folders are the same, no action taken."}

        logger.info(f"Moving messages {request.message_ids} from {source_peer.id} to {target_peer.id}")
        # Forward messages to the target peer
        await client_obj(ForwardMessagesRequest(
            from_peer=source_peer,
            id=request.message_ids,
            to_peer=target_peer
        ))
        
        # Delete original messages from the source peer
        await client_obj(DeleteMessagesRequest(
            peer=source_peer,
            id=request.message_ids
        ))
        invalidate_folder_cache(request.source_folder_id)
        invalidate_folder_cache(request.target_folder_id)
        logger.info(f"Messages {request.message_ids} moved successfully.")
        return {"message": f"Messages {request.message_ids} moved from {source_peer.id} to {target_peer.id}."}
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error moving files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to move files: {e}")

@app.get("/list_files", response_model=list[FileMetadata])
async def list_files(folder_id: int | None = None, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        cache_key = file_cache_key(folder_id)
        cached_files = file_list_cache.get(cache_key)
        if cached_files is not None:
            logger.info(f"File list cache hit for folder_id: {folder_id} ({len(cached_files)} files)")
            return cached_files

        target_peer = await resolve_peer(client_obj, folder_id)
        
        files = []
        logger.info(f"Listing files in folder_id: {folder_id}")
        async for message in client_obj.iter_messages(target_peer, reverse=True):
            if message.file:
                cache_message(folder_id, message)
                files.append(message_to_metadata(message, folder_id))
        logger.info(f"Found {len(files)} files in folder_id: {folder_id}")
        file_list_cache.set(cache_key, files)
        return files
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")

@app.get("/list_folders", response_model=list[FolderMetadata])
async def list_folders(client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        cached_folders = folder_list_cache.get("folders")
        if cached_folders is not None:
            logger.info(f"Folder list cache hit ({len(cached_folders)} folders)")
            return cached_folders

        folders = []
        logger.info("Scanning for folders (channels) in dialogs...")
        async for dialog in client_obj.iter_dialogs():
            if isinstance(dialog.entity, Channel):
                # Check for the [TD] tag in title or about to identify Telegram Drive folders
                is_td_folder = False
                folder_name = dialog.title
                if "[TD]" in dialog.title.upper():
                    is_td_folder = True
                    folder_name = dialog.title.replace(" [TD]", "").replace(" [td]", "").strip()
                else:
                    # Also check 'about' field, similar to Rust implementation
                    try:
                        full_channel = await client_obj(GetFullChannelRequest(channel=dialog.entity))
                        if hasattr(full_channel.full_chat, 'about') and "[telegram-drive-folder]" in full_channel.full_chat.about:
                            is_td_folder = True
                    except Exception as e:
                        logger.warning(f"Could not get full channel info for {dialog.title}: {e}")

                if is_td_folder:
                    folders.append(FolderMetadata(
                        id=dialog.entity.id,
                        name=folder_name,
                        parent_id=None # Telegram channels don't have a direct parent in this context
                    ))
        logger.info(f"Found {len(folders)} Telegram Drive folders.")
        folder_list_cache.set("folders", folders)
        return folders
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except Exception as e:
        logger.error(f"Error listing folders: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list folders: {e}")

@app.get("/search", response_model=list[FileMetadata])
async def search_files(query: str, folder_id: int | None = None, client_obj: TelegramClient = Depends(get_authorized_client)):
    try:
        target_peer = await resolve_peer(client_obj, folder_id)
        
        files = []
        logger.info(f"Searching for '{query}' in folder_id: {folder_id}")
        # Telethon's search_messages can search within a peer
        async for message in client_obj.iter_messages(target_peer, search=query, reverse=True):
            if message.file:
                cache_message(folder_id, message)
                files.append(message_to_metadata(message, folder_id))
        logger.info(f"Found {len(files)} files matching query '{query}' in folder_id: {folder_id}")
        return files
    except FloodWaitError as e:
        raise HTTPException(status_code=429, detail=f"Telegram flood wait. Please try again in {e.seconds} seconds.")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error searching files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search files: {e}")
