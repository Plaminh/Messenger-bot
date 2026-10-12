"""Tests for per-user inactivity timer triggering memory extractor."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.orchestrator import ChatOrchestrator
from app.llm.base import LLMResult


@pytest.mark.asyncio
async def test_inactivity_timer_triggers_extractor(
    db_session: AsyncSession,
    mock_messenger,
    mock_embedder,
):
    session_factory = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            content='{"operations": []}',
            usage_tokens=15,
            model="llama-3.1-8b-instant",
            tier="fast",
        )
    )

    with patch("app.chat.orchestrator.extract_and_sync_memories", new_callable=AsyncMock) as mock_extract:
        orchestrator = ChatOrchestrator(
            session_factory=session_factory,
            messenger_client=mock_messenger,
            llm_provider=mock_llm,
            embedder=mock_embedder,
            inactivity_delay=0.04,
        )

        await orchestrator.handle_turn("psid_inactivity_1", "Chào bạn, hôm nay tôi vui lắm")

        # Initially, inactivity timer hasn't fired yet
        assert mock_extract.call_count == 0

        # Wait for inactivity delay to expire
        await asyncio.sleep(0.08)

        # After delay, extractor must be triggered
        assert mock_extract.call_count == 1


@pytest.mark.asyncio
async def test_inactivity_timer_resets_on_new_message(
    db_session: AsyncSession,
    mock_messenger,
    mock_embedder,
):
    session_factory = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            content='{"operations": []}',
            usage_tokens=15,
            model="llama-3.1-8b-instant",
            tier="fast",
        )
    )

    with patch("app.chat.orchestrator.extract_and_sync_memories", new_callable=AsyncMock) as mock_extract:
        orchestrator = ChatOrchestrator(
            session_factory=session_factory,
            messenger_client=mock_messenger,
            llm_provider=mock_llm,
            embedder=mock_embedder,
            inactivity_delay=0.12,
        )

        # Message 1
        await orchestrator.handle_turn("psid_inactivity_2", "Tin nhắn 1")
        await asyncio.sleep(0.04)

        # Message 2 arrives before timer 1 expires -> resets timer
        await orchestrator.handle_turn("psid_inactivity_2", "Tin nhắn 2")
        await asyncio.sleep(0.05)  # From msg 1 = 0.09s (would have fired without reset), from msg 2 = 0.05s (< 0.12s)

        assert mock_extract.call_count == 0

        # Now wait for timer 2 to lapse (> 0.12s from msg 2)
        await asyncio.sleep(0.09)
        assert mock_extract.call_count == 1
