import datetime
import secrets
import string
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

import config
from auth.jwt import get_current_user, hash_password
from db import get_db
from db_models import IamKey, User, UserStorageSettings
from utils import github_store


router = APIRouter(prefix="/api/v1/me", tags=["user-storage"])


class StorageSettingsOut(BaseModel):
    storage_backend: Literal["telegram", "github"]
    quota_bytes: int
    used_bytes: int
    remaining_bytes: int


class StorageSettingsUpdate(BaseModel):
    storage_backend: Literal["telegram", "github"]


class IamKeyCreate(BaseModel):
    name: str


class IamKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    access_key_id: str
    status: str
    created_date: datetime.datetime
    last_used_date: datetime.datetime | None = None


class IamKeyCreated(IamKeyOut):
    secret_access_key: str


def _ensure_settings(db: Session, user: User) -> UserStorageSettings:
    settings = db.query(UserStorageSettings).filter(UserStorageSettings.user_id == user.id).first()
    if settings:
        return settings

    settings = UserStorageSettings(user_id=user.id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
    return settings


async def _used_bytes(user: User) -> int:
    records = await github_store.list_records()
    return sum(
        int(record.get("size_bytes") or 0)
        for record in records
        if str(record.get("owner_user_id") or "") == user.id
    )


def _token(prefix: str, length: int) -> str:
    alphabet = string.ascii_letters + string.digits
    return f"{prefix}_{''.join(secrets.choice(alphabet) for _ in range(length))}"


@router.get("/storage", response_model=StorageSettingsOut)
async def get_storage_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StorageSettingsOut:
    settings = _ensure_settings(db, current_user)
    used = await _used_bytes(current_user)
    quota = int(settings.quota_bytes or config.USER_STORAGE_LIMIT_BYTES)
    return StorageSettingsOut(
        storage_backend=settings.storage_backend,
        quota_bytes=quota,
        used_bytes=used,
        remaining_bytes=max(quota - used, 0),
    )


@router.put("/storage", response_model=StorageSettingsOut)
async def update_storage_settings(
    data: StorageSettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StorageSettingsOut:
    settings = _ensure_settings(db, current_user)
    settings.storage_backend = data.storage_backend
    db.add(settings)
    db.commit()
    db.refresh(settings)
    used = await _used_bytes(current_user)
    quota = int(settings.quota_bytes or config.USER_STORAGE_LIMIT_BYTES)
    return StorageSettingsOut(
        storage_backend=settings.storage_backend,
        quota_bytes=quota,
        used_bytes=used,
        remaining_bytes=max(quota - used, 0),
    )


@router.get("/iam-keys", response_model=list[IamKeyOut])
def list_iam_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IamKey]:
    return (
        db.query(IamKey)
        .filter(IamKey.user_id == current_user.id, IamKey.deleted.is_(False))
        .order_by(IamKey.created_date.desc())
        .all()
    )


@router.post("/iam-keys", response_model=IamKeyCreated)
def create_iam_key(
    data: IamKeyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IamKeyCreated:
    name = data.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Key name is required")

    secret_key = _token("tsec", 48)
    key = IamKey(
        user_id=current_user.id,
        name=name,
        access_key_id=_token("tid", 36),
        hashed_secret_key=hash_password(secret_key),
    )
    db.add(key)
    db.commit()
    db.refresh(key)
    return IamKeyCreated(
        id=key.id,
        name=key.name,
        access_key_id=key.access_key_id,
        secret_access_key=secret_key,
        status=key.status,
        created_date=key.created_date,
        last_used_date=key.last_used_date,
    )


@router.delete("/iam-keys/{key_id}")
def delete_iam_key(
    key_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    key = (
        db.query(IamKey)
        .filter(IamKey.id == key_id, IamKey.user_id == current_user.id, IamKey.deleted.is_(False))
        .first()
    )
    if not key:
        raise HTTPException(status_code=404, detail="IAM key not found")

    key.deleted = True
    key.status = "disabled"
    db.add(key)
    db.commit()
    return {"message": "IAM key deleted"}
