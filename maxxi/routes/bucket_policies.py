from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth.jwt import get_current_user
from db_models import User
from utils import github_store


router = APIRouter(prefix="/api/v1/bucket-policies", tags=["bucket-policies"])


class BucketPolicy(BaseModel):
    bucket: str
    access: Literal["public", "private"] = "public"
    object_acl: bool = False
    disable_directory_listing: bool = True
    allowed_actions: list[str] = Field(default_factory=lambda: ["files:read", "files:list"])
    allowed_origins: list[str] = Field(default_factory=list)
    custom_domain: str | None = None
    additional_headers: dict[str, str] = Field(
        default_factory=lambda: {"X-Content-Type-Options": "nosniff"}
    )
    cors_rules: list[dict[str, Any]] = Field(default_factory=list)
    iam_key_ids: list[str] = Field(default_factory=list)


class BucketPolicyUpdate(BaseModel):
    access: Literal["public", "private"] = "public"
    object_acl: bool = False
    disable_directory_listing: bool = True
    allowed_actions: list[str] = Field(default_factory=lambda: ["files:read", "files:list"])
    allowed_origins: list[str] = Field(default_factory=list)
    custom_domain: str | None = None
    additional_headers: dict[str, str] = Field(
        default_factory=lambda: {"X-Content-Type-Options": "nosniff"}
    )
    cors_rules: list[dict[str, Any]] = Field(default_factory=list)
    iam_key_ids: list[str] = Field(default_factory=list)


def default_policy(bucket: str) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "bucket": bucket,
        "access": "public",
        "object_acl": False,
        "disable_directory_listing": True,
        "allowed_actions": ["files:read", "files:list"],
        "allowed_origins": [],
        "custom_domain": None,
        "additional_headers": {"X-Content-Type-Options": "nosniff"},
        "cors_rules": [],
        "iam_key_ids": [],
        "created_at": now,
        "updated_at": now,
    }


@router.get("", response_model=list[BucketPolicy])
async def list_policies() -> list[dict[str, Any]]:
    """Return all saved bucket policies."""
    return await github_store.list_bucket_policies()


@router.get("/{bucket}", response_model=BucketPolicy)
async def get_policy(bucket: str) -> dict[str, Any]:
    """Return a saved bucket policy, or the required default policy for the bucket."""
    return await github_store.get_bucket_policy(bucket) or default_policy(bucket)


@router.put("/{bucket}", response_model=BucketPolicy)
async def upsert_policy(
    bucket: str,
    policy: BucketPolicyUpdate,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create or replace the required policy for a bucket."""
    saved_policy = policy.model_dump()
    saved_policy["updated_by"] = current_user.email
    return await github_store.upsert_bucket_policy(bucket, saved_policy)


@router.post("/{bucket}", response_model=BucketPolicy)
async def create_policy(
    bucket: str,
    policy: BucketPolicyUpdate,
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a bucket policy. Use PUT for idempotent updates."""
    existing = await github_store.get_bucket_policy(bucket)
    if existing:
        raise HTTPException(status_code=409, detail="Bucket policy already exists")
    saved_policy = policy.model_dump()
    saved_policy["updated_by"] = current_user.email
    return await github_store.upsert_bucket_policy(bucket, saved_policy)


@router.delete("/{bucket}")
async def delete_policy(
    bucket: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    _ = current_user
    deleted = await github_store.delete_bucket_policy(bucket)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bucket policy not found")
    return {"message": f"Bucket policy {bucket} deleted"}
