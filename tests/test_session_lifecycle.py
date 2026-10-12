"""Tests verifying that database sessions are not held during LLM generation."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.orchestrator import ChatOrchestrator
from app.llm.base import LLMResult


@pytest.mark.asyncio
async def test_db_session_closed_during_llm_invocation(
    db_session: AsyncSession,
    mock_messenger,
    mock_embedder,
):
    real_session_maker = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    open_sessions_count = 0
    sessions_opened_total = 0
    open_sessions_during_llm = None

    @asynccontextmanager
    async def tracking_session_factory():
        nonlocal open_sessions_count, sessions_opened_total
        sessions_opened_total += 1
        open_sessions_count += 1
        async with real_session_maker() as s:
            try:
                yield s
            finally:
                open_sessions_count -= 1

    async def mock_generate(*args, **kwargs):
        nonlocal open_sessions_during_llm
        open_sessions_during_llm = open_sessions_count
        return LLMResult(
            content="Phản hồi thử nghiệm",
            usage_tokens=20,
            model="llama-3.3-70b-versatile",
            tier="main",
        )

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(side_effect=mock_generate)

    orchestrator = ChatOrchestrator(
        session_factory=tracking_session_factory,
        messenger_client=mock_messenger,
        llm_provider=mock_llm,
        embedder=mock_embedder,
    )

    await orchestrator.handle_turn("psid_session_test", "Chào bạn!")

    # Verify LLM was actually called
    assert mock_llm.generate.call_count == 1
    # Verify NO db session was open during LLM invocation
    assert open_sessions_during_llm == 0
    # Verify exactly 2 distinct sessions were used: one for read, one for write
    assert sessions_opened_total == 2
