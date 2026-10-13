"""Inactivity extraction timers survive commands, failures, duplicates and restarts."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.orchestrator import ChatOrchestrator
from app.db.models import User
from app.db.store import add_message
from app.memory.extractor import should_trigger_extraction


def _orchestrator(db_session, mock_messenger, mock_llm):
    mock_messenger.fetch_first_name = AsyncMock(return_value=(None, True))
    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return ChatOrchestrator(
        messenger_client=mock_messenger,
        session_factory=factory,
        llm_provider=mock_llm,
        inactivity_delay=60,
    )


def test_message_count_trigger_has_no_time_branch():
    assert should_trigger_extraction(6)
    assert should_trigger_extraction(12)
    assert not should_trigger_extraction(0)
    assert not should_trigger_extraction(7)


@pytest.mark.asyncio
async def test_help_restores_timer_and_duplicate_mid_keeps_existing_timer(
    db_session, mock_messenger, mock_llm
):
    orchestrator = _orchestrator(db_session, mock_messenger, mock_llm)
    user = User(fb_psid="timer-user", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.flush()
    await add_message(db_session, user.id, "user", "old", mid="duplicate-mid")
    await db_session.commit()

    orchestrator._schedule_inactivity_timer(user.fb_psid, user.id)
    original = orchestrator._inactivity_timers[user.fb_psid]
    assert await orchestrator.prepare_context(user.fb_psid, "again", mid="duplicate-mid") is None
    assert orchestrator._inactivity_timers[user.fb_psid] is original
    assert not original.cancelled()

    assert await orchestrator.prepare_context(user.fb_psid, "/help", mid="help-mid") is None
    replacement = orchestrator._inactivity_timers[user.fb_psid]
    assert replacement is not original and not replacement.done()
    await orchestrator.aclose()


@pytest.mark.asyncio
async def test_quen_removes_timer_and_extraction_lock(db_session, mock_messenger, mock_llm):
    orchestrator = _orchestrator(db_session, mock_messenger, mock_llm)
    user = User(fb_psid="forget-timer", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.commit()
    orchestrator._schedule_inactivity_timer(user.fb_psid, user.id)
    lock = orchestrator._extraction_locks.setdefault(user.id, asyncio.Lock())

    assert await orchestrator.prepare_context(user.fb_psid, "/quen") is None
    assert user.fb_psid not in orchestrator._inactivity_timers
    assert user.id not in orchestrator._extraction_locks
    assert lock is not None


@pytest.mark.asyncio
async def test_failed_turn_restores_inactivity_timer(db_session, mock_messenger, mock_llm):
    orchestrator = _orchestrator(db_session, mock_messenger, mock_llm)
    orchestrator.generate_reply = AsyncMock(side_effect=RuntimeError("LLM failed"))

    await orchestrator.handle_turn("failed-turn", "xin chào")
    assert "failed-turn" in orchestrator._inactivity_timers
    await orchestrator.aclose()


@pytest.mark.asyncio
async def test_recovery_schedules_only_users_with_pending_messages(
    db_session, mock_messenger, mock_llm
):
    pending = User(fb_psid="pending", style_profile={}, core_profile={})
    complete = User(fb_psid="complete", style_profile={}, core_profile={})
    db_session.add_all([pending, complete])
    await db_session.flush()
    pending_message = await add_message(db_session, pending.id, "user", "new")
    complete_message = await add_message(db_session, complete.id, "user", "done")
    complete.last_extracted_message_id = complete_message.id
    await db_session.commit()

    orchestrator = _orchestrator(db_session, mock_messenger, mock_llm)
    assert await orchestrator.recover_pending_extractions() == 1
    assert set(orchestrator._inactivity_timers) == {pending.fb_psid}
    assert pending_message.id > 0
    await orchestrator.aclose()
