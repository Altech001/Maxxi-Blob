# type: ignore

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict

import config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/google")


class GoogleLoginParams(BaseModel):
    token: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str


def _missing_auth_dependency(exc: ModuleNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Auth dependency is not installed: {exc.name}",
    )


def get_db_session():
    try:
        from db import get_db
    except ModuleNotFoundError as exc:
        raise _missing_auth_dependency(exc) from exc

    yield from get_db()


@router.post("/google", response_model=Token)
def google_login(data: GoogleLoginParams, db: Any = Depends(get_db_session)) -> Token:
    """Authenticate via Google and return a JWT access token."""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        from auth.jwt import create_access_token, hash_password
        from db_models import User, UserStorageSettings
    except ModuleNotFoundError as exc:
        logger.error("Missing auth dependency: %s", exc.name)
        raise _missing_auth_dependency(exc) from exc

    # ── Verify the Google credential ──────────────────────────────────────
    try:
        idinfo = id_token.verify_oauth2_token(
            data.token,
            google_requests.Request(),
            config.GOOGLE_CLIENT_ID,
        )
        email = idinfo.get("email")
        name = idinfo.get("name", "Google User")
        if not email:
            raise ValueError("No email in token")
    except ValueError as exc:
        logger.warning("Google token verification failed (ValueError): %s", exc)
        raise HTTPException(status_code=401, detail=f"Invalid Google token: {exc}") from exc
    except Exception as exc:
        logger.exception("Google token verification failed (unexpected): %s", exc)
        raise HTTPException(status_code=401, detail=f"Token verification error: {exc}") from exc

    # ── Upsert user in database ───────────────────────────────────────────
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                full_name=name,
                hashed_password=hash_password("google_oauth_fallback_" + email),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.add(UserStorageSettings(user_id=user.id))
            db.commit()
        elif not getattr(user, "storage_settings", None):
            db.add(UserStorageSettings(user_id=user.id))
            db.commit()
    except Exception as exc:
        logger.exception("Database error during Google sign-in for %s: %s", email, exc)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc

    access_token = create_access_token(data={"sub": user.email})
    return Token(access_token=access_token)


@router.get("/me", response_model=UserOut)
def me(
    token: str = Depends(oauth2_scheme),
    db: Any = Depends(get_db_session),
) -> Any:
    """Return the currently authenticated user."""
    try:
        from auth.jwt import decode_token
        from db_models import User
    except ModuleNotFoundError as exc:
        raise _missing_auth_dependency(exc) from exc

    token_data = decode_token(token)
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
