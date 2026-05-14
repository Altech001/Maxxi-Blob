# type: ignore

import base64
import binascii
import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from db import get_db
from db_models import IamKey, User


class TokenData(BaseModel):
    email: str


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/google")


def hash_password(password: str) -> str:
    """Hash a password with a random salt using SHA-256.

    Note: This app uses Google OAuth exclusively — passwords are placeholder
    values that are never used for authentication.  Using hashlib avoids the
    passlib + bcrypt ≥ 4.1 incompatibility on Vercel's serverless runtime.
    """
    salt = os.urandom(16).hex()
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"sha256${salt}${digest}"


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against a sha256$salt$digest hash."""
    try:
        _, salt, digest = hashed.split("$", 2)
    except ValueError:
        return False
    expected = hashlib.sha256((salt + plain).encode()).hexdigest()
    return hmac.compare_digest(expected, digest)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        return TokenData(email=email)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


def _credentials_from_basic_auth(header: str) -> tuple[str, str] | None:
    try:
        decoded = base64.b64decode(header.removeprefix("Basic ").strip()).decode()
        access_key_id, secret_access_key = decoded.split(":", 1)
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if not access_key_id or not secret_access_key:
        return None
    return access_key_id, secret_access_key


def _credentials_from_api_key_header(header: str) -> tuple[str, str] | None:
    for separator in (":", "."):
        if separator in header:
            access_key_id, secret_access_key = header.split(separator, 1)
            if access_key_id and secret_access_key:
                return access_key_id, secret_access_key
    return None


def _user_from_api_key(access_key_id: str, secret_access_key: str, db: Session) -> User:
    key = (
        db.query(IamKey)
        .filter(
            IamKey.access_key_id == access_key_id,
            IamKey.status == "active",
            IamKey.deleted.is_(False),
        )
        .first()
    )
    if key is None or not verify_password(secret_access_key, key.hashed_secret_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    user = db.query(User).filter(User.id == key.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner not found",
        )

    key.last_used_date = datetime.utcnow()
    db.add(key)
    db.commit()
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    authorization = request.headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        token_data = decode_token(token)
        user = db.query(User).filter(User.email == token_data.email).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return user

    if authorization.lower().startswith("basic "):
        basic_credentials = _credentials_from_basic_auth(authorization)
        if basic_credentials:
            return _user_from_api_key(*basic_credentials, db)

    access_key_id = request.headers.get("x-maxxi-access-key")
    secret_access_key = request.headers.get("x-maxxi-secret-key")
    if access_key_id and secret_access_key:
        return _user_from_api_key(access_key_id, secret_access_key, db)

    api_key = request.headers.get("x-api-key")
    if api_key:
        api_key_credentials = _credentials_from_api_key_header(api_key)
        if api_key_credentials:
            return _user_from_api_key(*api_key_credentials, db)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing Authorization bearer token or Maxxi API key",
    )


def get_jwt_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    token_data = decode_token(token)
    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_optional_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User | None:
    authorization = request.headers.get("authorization", "")
    if not authorization:
        access_key_id = request.headers.get("x-maxxi-access-key")
        secret_access_key = request.headers.get("x-maxxi-secret-key")
        if access_key_id and secret_access_key:
            return _user_from_api_key(access_key_id, secret_access_key, db)
        return None

    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        token_data = decode_token(token)
        return db.query(User).filter(User.email == token_data.email).first()
    if authorization.lower().startswith("basic "):
        basic_credentials = _credentials_from_basic_auth(authorization)
        if basic_credentials:
            return _user_from_api_key(*basic_credentials, db)
    return None
