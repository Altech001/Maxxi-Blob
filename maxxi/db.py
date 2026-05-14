from collections.abc import Generator
import logging

from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import declarative_base, Session, sessionmaker

import config
Base = declarative_base()
logger = logging.getLogger(__name__)

engine_kwargs = {"pool_pre_ping": True}
if config.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(config.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
def create_db_tables() -> None:
    import db_models  # noqa: F401

    try:
        Base.metadata.create_all(bind=engine)  # type: ignore
    except SQLAlchemyError:
        logger.exception("Failed to create database tables")
        raise


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
