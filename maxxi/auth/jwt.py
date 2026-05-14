# type: ignore

import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy.orm import Session

import config
from db import get_db
from db_models import User


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


def get_current_user(
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
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/google", auto_error=False)),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None
    token_data = decode_token(token)
    return db.query(User).filter(User.email == token_data.email).first()
