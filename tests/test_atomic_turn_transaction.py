"""Tests verifying that user message, assistant message, and profile updates commit atomically."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.orchestrator import ChatOrchestrator
from app.db.models import Message, User
from app.db.store import get_or_create_user


@pytest.mark.asyncio
async def test_turn_writes_commit_atomically(
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

    psid = "psid_atomic_success"
    await orchestrator.handle_turn(psid, "Tôi cảm thấy rất vui hôm nay!")
    await asyncio.sleep(0.05)

    # Verify user, assistant message, and profile update are all present
    async with session_factory() as verify_session:
        user = await get_or_create_user(verify_session, psid)
        msgs = (
            await verify_session.execute(
                select(Message).where(Message.user_id == user.id).order_by(Message.id.asc())
            )
        ).scalars().all()

        assert len(msgs) == 2
        assert msgs[0].role == "user"
        assert msgs[1].role == "assistant"
        assert user.last_user_msg_at is not None


@pytest.mark.asyncio
async def test_turn_writes_rollback_atomically_on_failure(
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

    psid = "psid_atomic_fail"

    # Pre-create user so user exists
    async with session_factory() as prep_session:
        user = await get_or_create_user(prep_session, psid)
        await prep_session.commit()
        user_id = user.id

    # Simulate an error during profile update (the 3rd write in the transaction)
    with patch("app.chat.orchestrator.update_user_profiles", side_effect=RuntimeError("Simulated DB error")):
        # handle_turn swallows the error and apologises to the user instead of staying silent
        await orchestrator.handle_turn(psid, "Tin nhắn thử lỗi")

    mock_messenger.send_human_like_response.assert_awaited_once()
    assert mock_messenger.send_human_like_response.await_args.args[0] == psid
    assert mock_messenger.send_human_like_response.await_args.args[1] != mock_llm.generate.return_value.content

    # In a new session, verify that neither user message nor assistant message was persisted
    async with session_factory() as verify_session:
        msgs = (
            await verify_session.execute(
                select(Message).where(Message.user_id == user_id)
            )
        ).scalars().all()
        # Full rollback ensures 0 messages persisted
        assert len(msgs) == 0
