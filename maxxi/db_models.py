import datetime
import uuid

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import relationship

import config
from db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    email = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(
        SAEnum("admin", "user", name="user_role", create_constraint=True),
        default="user",
        nullable=False,
    )

    storage_settings = relationship(
        "UserStorageSettings",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    iam_keys = relationship(
        "IamKey",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserStorageSettings(Base):
    __tablename__ = "user_storage_settings"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    storage_backend = Column(
        SAEnum("telegram", "github", name="storage_backend", create_constraint=True),
        default=config.DEFAULT_STORAGE_BACKEND if config.DEFAULT_STORAGE_BACKEND in {"telegram", "github"} else "telegram",
        nullable=False,
    )
    quota_bytes = Column(BigInteger, default=config.USER_STORAGE_LIMIT_BYTES, nullable=False)
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    user = relationship("User", back_populates="storage_settings")


class IamKey(Base):
    __tablename__ = "iam_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    access_key_id = Column(String, unique=True, nullable=False, index=True)
    hashed_secret_key = Column(String, nullable=False)
    status = Column(
        SAEnum("active", "disabled", name="iam_key_status", create_constraint=True),
        default="active",
        nullable=False,
    )
    created_date = Column(DateTime, default=datetime.datetime.utcnow)
    last_used_date = Column(DateTime, nullable=True)
    deleted = Column(Boolean, default=False, nullable=False)

    user = relationship("User", back_populates="iam_keys")
