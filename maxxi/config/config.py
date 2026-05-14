# type: ignore
import os
from dotenv import load_dotenv

load_dotenv(override=False)

# Server
PORT: int = int(os.getenv("PORT", "8000"))
PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
CDN_BASE_URL: str = os.getenv("CDN_BASE_URL", "").rstrip("/")

# Database / auth
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./maxxi.db")
JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))
USER_STORAGE_LIMIT_BYTES: int = int(os.getenv("USER_STORAGE_LIMIT_BYTES", str(20 * 1024 * 1024 * 1024)))
DEFAULT_STORAGE_BACKEND: str = os.getenv("DEFAULT_STORAGE_BACKEND", "telegram").lower()

# # Telegram
# TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
# TELEGRAM_CHAT_ID: str   = os.getenv("TELEGRAM_CHAT_ID", "")   # channel/group/user chat id
# TELEGRAM_API_URL: str   = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
# TELEGRAM_FILE_URL: str  = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"


# Telegram API credentials and session file
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))  # Replace with your API ID
API_HASH = os.getenv("TELEGRAM_API_HASH", "YOUR_API_HASH")  # Replace with your API Hash
SESSION_NAME = "maxxi_session"
TELEGRAM_SESSION_STRING: str = os.getenv("TELEGRAM_SESSION_STRING", "")
TELEGRAM_SESSION_FILE: str = os.getenv("TELEGRAM_SESSION_FILE", "telegram_blob_session")
TELEGRAM_AUTO_CREATE_FOLDERS: bool = os.getenv("TELEGRAM_AUTO_CREATE_FOLDERS", "true").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
TELEGRAM_FOLDER_PREFIX: str = os.getenv("TELEGRAM_FOLDER_PREFIX", "Maxxi").strip()
_telegram_storage_folder_id = os.getenv("TELEGRAM_STORAGE_FOLDER_ID")
TELEGRAM_STORAGE_FOLDER_ID: int | None = (
    int(_telegram_storage_folder_id) if _telegram_storage_folder_id else None
)


# GitHub (metadata store)
REPO_BRANCH: str = os.getenv("REPO_BRANCH", "main")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
GITHUB_USER: str = os.getenv("GITHUB_USERNAME", "Altech001")
GITHUB_REPO: str = os.getenv("GITHUB_REPO", "maxxi")
GITHUB_BRANCH: str = os.getenv("REPO_BRANCH", "main")
GITHUB_API_URL: str = os.getenv("GITHUB_API_URL", "https://api.github.com")
METADATA_FILE: str = os.getenv("METADATA_FILE", "metadata.json")  # path inside repo
METADATA_ROOT: str = os.getenv("METADATA_ROOT", "metadata").strip("/")
COMMIT_MESSAGE: str = os.getenv("COMMIT_MESSAGE", "Github Cdn:Upload")
CDN_API_URL: str = os.getenv("CDN_API_URL", "https://cdn.jsdelivr.net/gh")
GITHUB_UPLOAD_MAX_FILE_SIZE: int = int(
    os.getenv("GITHUB_UPLOAD_MAX_FILE_SIZE", str(50 * 1024 * 1024))
)
CF_TURNSTILE_API_URL: str = os.getenv(
    "CF_TURNSTILE_API_URL",
    "https://challenges.cloudflare.com",
).rstrip("/")
CF_TURNSTILE_SECRET_KEY: str = os.getenv("CF_TURNSTILE_SECRET_KEY", "")


# Upload limits
MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(5 * 1024 * 1024 * 1024)))
METADATA_PARSE_MAX_BYTES: int = int(os.getenv("METADATA_PARSE_MAX_BYTES", str(50 * 1024 * 1024)))
RATE_LIMIT_REQUESTS: int = 10
RATE_LIMIT_WINDOW_SECONDS: int = 5 * 60


# Allowed MIME types
IMAGE_MIMETYPES = [
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/avif",
    "image/heif",
    "image/heic",
    "image/x-icon",
    "image/tiff",
]
AUDIO_MIMETYPES = [
    "audio/mp3",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "audio/aac",
    "audio/x-m4a",
]
VIDEO_MIMETYPES = [
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "video/x-msvideo",
    "video/avi",
    "video/mpeg",
    "video/x-matroska",
    "video/ogg",
    "video/3gpp",
]
DOC_MIMETYPES = [
    "text/plain",
    "text/html",
    "text/css",
    "text/javascript",
    "text/csv",
    "text/markdown",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/octet-stream",
    "font/ttf",
    "font/otf",
    "font/woff",
    "font/woff2",
]

ALLOWED_MIME_TYPES: set[str] = set(
    IMAGE_MIMETYPES + AUDIO_MIMETYPES + VIDEO_MIMETYPES + DOC_MIMETYPES
)

FOLDER_MAP: dict[str, list[str]] = {
    "image": IMAGE_MIMETYPES,
    "video": VIDEO_MIMETYPES,
    "audio": AUDIO_MIMETYPES,
    "docs": DOC_MIMETYPES,
}

CDN_FOLDER_MAP: dict[str, list[str]] = {
    "images": IMAGE_MIMETYPES,
    "videos": VIDEO_MIMETYPES,
    "audio": AUDIO_MIMETYPES,
    "archives": [
        "application/zip",
        "application/x-zip-compressed",
        "application/x-tar",
        "application/gzip",
        "application/x-7z-compressed",
        "application/vnd.rar",
    ],
    "code": [
        "text/html",
        "text/css",
        "text/javascript",
        "text/csv",
        "text/markdown",
        "application/json",
        "application/xml",
        "application/javascript",
    ],
    "fonts": [
        "font/ttf",
        "font/otf",
        "font/woff",
        "font/woff2",
    ],
    "documents": DOC_MIMETYPES,
}

# Google OAuth2 for Drive / Sheets integrations
GOOGLE_OAUTH_CLIENT_ID: str = os.getenv(
    "GOOGLE_OAUTH_CLIENT_ID",
    "607016949081-pu5rdrdaobgtvgiq8q6omf05thl3avpa.apps.googleusercontent.com",
)
GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", GOOGLE_OAUTH_CLIENT_ID)
GOOGLE_OAUTH_CLIENT_SECRET: str = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
GOOGLE_OAUTH_REDIRECT_URI: str = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "http://localhost:5173/integrations/google/callback",
)
