"""Pytest test configuration and fixtures."""

import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

# Set required environment variables before app imports
os.environ["META_VERIFY_TOKEN"] = "test_verify_token"
os.environ["META_PAGE_ACCESS_TOKEN"] = "test_page_token"
os.environ["META_APP_SECRET"] = "test_app_secret_12345"
os.environ["META_API_VERSION"] = "v21.0"
os.environ["GROQ_API_KEY"] = "gsk_test_groq_key"
os.environ["GROQ_MODEL_MAIN"] = "llama-3.3-70b-versatile"
os.environ["GROQ_MODEL_FAST"] = "llama-3.1-8b-instant"
os.environ["DAILY_TOKEN_BUDGET_MAIN"] = "100000"
os.environ["DAILY_TOKEN_BUDGET_FAST"] = "500000"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["LOG_LEVEL"] = "DEBUG"

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.db import Base
from app.core.settings import get_settings
from app.integrations.llm.base import LLMResult


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide isolated in-memory SQLite async database session."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def mock_messenger():
    """Mock MessengerClient."""
    mock = MagicMock()
    mock.send_action = AsyncMock(return_value=True)
    mock.send_text = AsyncMock(return_value=True)
    mock.send_human_like_response = AsyncMock(return_value=None)
    mock.split_into_bubbles = MagicMock(side_effect=lambda text, max_bubbles=3: [text])
    return mock


@pytest.fixture
def mock_llm():
    """Mock LLMProvider."""
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=LLMResult(
            content="Mình luôn ở đây lắng nghe bạn nè! 🌸",
            usage_tokens=45,
            model="llama-3.3-70b-versatile",
            tier="main",
        )
    )
    return mock
