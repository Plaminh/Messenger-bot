"""Database connection and session factory management."""

from collections.abc import AsyncGenerator
from functools import lru_cache
from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

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


@lru_cache(maxsize=1)
def get_sync_engine() -> Engine:
    """Return cached sync SQLAlchemy engine."""
    settings = get_settings()
    return create_engine(
        settings.sync_database_url,
        echo=(settings.LOG_LEVEL == "DEBUG"),
        pool_pre_ping=True,
    )


@lru_cache(maxsize=1)
def get_sync_session_maker() -> sessionmaker[Session]:
    """Return cached sync sessionmaker."""
    return sessionmaker(
        bind=get_sync_engine(),
        expire_on_commit=False,
        autoflush=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    session_factory = get_async_session_maker()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
