# type: ignore

from contextlib import asynccontextmanager
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db import create_db_tables
from routes.auth import router as auth_router
from routes.bucket_policies import router as bucket_policies_router
from routes.repo_cdn import router as repo_cdn_router
from routes.router import public_router, router
from routes.user_storage import router as user_storage_router
from utils.telegram_store import start_client, stop_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        create_db_tables()
    except Exception:
        logger.exception("Database initialization failed; auth routes may be unavailable")
    await start_client()
    yield
    await stop_client()


app = FastAPI(
    title="Maxxi CDN",
    description="Store file bytes in Telegram, store parsed metadata in GitHub, and serve CDN-style URLs.",
    version="1.0.0",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Content-Type", "X-Requested-With", "Authorization"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all so unhandled 500s still get CORS headers from the middleware."""
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    logger.debug(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


app.include_router(router)
app.include_router(repo_cdn_router)
app.include_router(bucket_policies_router)
app.include_router(auth_router)
app.include_router(user_storage_router)
app.include_router(public_router)
app.get("/")(lambda: {"message": "Hello World!"})
