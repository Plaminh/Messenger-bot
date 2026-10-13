"""Database connection and session factory management."""

from functools import lru_cache
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.settings import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""
    pass


@lru_cache(maxsize=1)
def get_async_engine() -> AsyncEngine:
    """Return cached async SQLAlchemy engine."""
    settings = get_settings()
    return create_async_engine(
        settings.async_database_url,
        echo=(settings.LOG_LEVEL == "DEBUG"),
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Return cached async sessionmaker."""
    return async_sessionmaker(
        bind=get_async_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
