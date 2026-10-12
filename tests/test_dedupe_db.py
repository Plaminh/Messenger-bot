"""Tests for database-level deduplication and mid persistence."""

import asyncio
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ChatOrchestrator
from app.db.models import Message


@pytest.mark.asyncio
async def test_orchestrator_persists_mid_and_deduplicates_via_db(
    db_session: AsyncSession,
    mock_messenger,
    mock_llm,
    mock_embedder,
):
    session_factory = async_sessionmaker(
        bind=db_session.bind,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    orchestrator = ChatOrchestrator(
        session_factory=session_factory,
        messenger_client=mock_messenger,
        llm_provider=mock_llm,
        embedder=mock_embedder,
    )

    mid = "mid.persistent_test_100"
    # First turn should process normally
    await orchestrator.handle_turn("psid_db_dedupe", "Xin chào bạn thân", mid=mid)

    # Verify user message in DB contains the mid
    stmt = select(Message).where(Message.mid == mid)
    res = await db_session.execute(stmt)
    msg = res.scalar_one_or_none()
    assert msg is not None
    assert msg.role == "user"
    assert msg.mid == mid

    # Check messenger was called once
    assert mock_messenger.send_human_like_response.call_count == 1

    # Second turn with the SAME mid should be ignored by DB deduplication
    await orchestrator.handle_turn("psid_db_dedupe", "Tin nhắn gửi lại", mid=mid)
    assert mock_messenger.send_human_like_response.call_count == 1


@pytest.mark.asyncio
async def test_debounce_passes_last_mid():
    delivered = []

    async def callback(psid: str, combined: str, mid: str | None = None) -> None:
        delivered.append((psid, combined, mid))

    debouncer = MessageDebouncer(delay=0.05)
    await debouncer.add_message("user_multi_mid", "Câu thứ nhất", callback, mid="mid.first")
    await asyncio.sleep(0.01)
    await debouncer.add_message("user_multi_mid", "Câu thứ hai", callback, mid="mid.second")

    await asyncio.sleep(0.1)

    assert len(delivered) == 1
    psid, combined, mid = delivered[0]
    assert psid == "user_multi_mid"
    assert combined == "Câu thứ nhất\nCâu thứ hai"
    assert mid == "mid.second"
