"""Tests for decomposed ChatOrchestrator turn lifecycle methods."""

from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.orchestrator import ChatOrchestrator, TurnContext
from app.db.models import Message
from app.integrations.llm.base import LLMResult


@pytest.mark.asyncio
async def test_decomposed_turn_lifecycle_steps(
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

    psid = "psid_lifecycle_test"
    text = "Hôm nay mình vừa được thăng chức!"
    mid = "mid.lifecycle_1"

    # 1. prepare_context
    ctx = await orchestrator.prepare_context(psid, text, mid=mid)
    assert ctx is not None
    assert isinstance(ctx, TurnContext)
    assert ctx.psid == psid
    assert ctx.clean_text == text
    assert ctx.mid == mid
    assert ctx.user_id > 0
    assert ctx.tier in ("main", "fast")
    assert len(ctx.full_messages) > 0

    # 2. generate_reply
    reply = await orchestrator.generate_reply(ctx)
    assert isinstance(reply, LLMResult)
    assert reply.content != ""
    assert mock_llm.generate.call_count == 1

    # 3. persist_turn
    now = datetime.now(timezone.utc)
    persisted = await orchestrator.persist_turn(ctx, reply, now)
    assert persisted is True

    # Verify messages in DB
    async with session_factory() as verify_session:
        msgs = (
            await verify_session.execute(
                select(Message).where(Message.user_id == ctx.user_id).order_by(Message.id.asc())
            )
        ).scalars().all()
        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[0].mid == mid
        assert msgs[1].role == "assistant"

    # 4. schedule_background
    orchestrator.schedule_background(ctx, now)
    assert psid in orchestrator._inactivity_timers

    # Clean up timer
    timer = orchestrator._inactivity_timers.pop(psid, None)
    if timer:
        timer.cancel()


@pytest.mark.asyncio
async def test_prepare_context_empty_text_or_duplicate_mid(
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

    # Empty text returns None
    assert await orchestrator.prepare_context("psid_1", "   ") is None

    # First message succeeds
    ctx1 = await orchestrator.prepare_context("psid_dup", "Xin chào", mid="mid.dup_check")
    assert ctx1 is not None
    reply = await orchestrator.generate_reply(ctx1)
    await orchestrator.persist_turn(ctx1, reply)

    # Duplicate mid returns None
    ctx2 = await orchestrator.prepare_context("psid_dup", "Xin chào lần 2", mid="mid.dup_check")
    assert ctx2 is None
