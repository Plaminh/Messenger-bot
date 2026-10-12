"""Tests for privacy commands (/help, /nho, /quen)."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.commands import handle_command, is_command
from app.db.models import Memory, Message, Summary, User
from app.db.store import add_memory, add_message, upsert_summary


def test_is_command_prefix_exact():
    assert is_command("/help") is True
    assert is_command("/nho") is True
    assert is_command("/quen") is True
    assert is_command(" /HELP ") is True
    assert is_command("chào bạn /help") is False
    assert is_command("giúp tôi /quen với") is False


@pytest.mark.asyncio
async def test_quen_wipes_all_user_data_cascade(db_session: AsyncSession):
    # Setup user with message, memory, summary
    user = User(
        fb_psid="psid_wipe_test",
        display_name="An",
        core_profile={"name": "An"},
        style_profile={},
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    await add_message(db_session, user.id, "user", "Tin nhắn bí mật")
    await add_memory(
        db_session,
        user.id,
        "Ký ức nhạy cảm",
        "feeling",
        8,
        [0.1] * 384,
    )
    await upsert_summary(db_session, user.id, "Bản tóm tắt cũ", upto_message_id=1)

    # Verify rows exist
    msgs = (await db_session.execute(select(Message).where(Message.user_id == user.id))).scalars().all()
    assert len(msgs) == 1

    # Execute /quen
    reply = await handle_command(db_session, user, "/quen")
    assert "đã xóa toàn bộ" in reply

    # Verify completely wiped
    users = (await db_session.execute(select(User).where(User.id == user.id))).scalars().all()
    assert len(users) == 0

    msgs_after = (await db_session.execute(select(Message).where(Message.user_id == user.id))).scalars().all()
    assert len(msgs_after) == 0

    mems_after = (await db_session.execute(select(Memory).where(Memory.user_id == user.id))).scalars().all()
    assert len(mems_after) == 0

    sums_after = (await db_session.execute(select(Summary).where(Summary.user_id == user.id))).scalars().all()
    assert len(sums_after) == 0
