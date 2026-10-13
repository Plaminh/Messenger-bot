"""Sensitive user text is never learned as a voice sample."""

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.orchestrator import ChatOrchestrator
from app.db.models import User
from app.db.store import add_message
from app.persona.prompt import assemble_system_prompt


@pytest.mark.asyncio
async def test_sensitive_history_is_excluded_from_voice_examples(
    db_session, mock_messenger, mock_llm
):
    user = User(
        fb_psid="safe-style",
        style_profile={},
        core_profile={"name_lookup_done": True},
    )
    db_session.add(user)
    await db_session.flush()
    await add_message(db_session, user.id, "user", "một câu bình thường")
    await add_message(db_session, user.id, "assistant", "mình nghe đây")
    await add_message(db_session, user.id, "user", "đụ má")
    await add_message(db_session, user.id, "user", "mình muốn chết")
    await db_session.commit()

    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    mock_messenger.fetch_first_name = AsyncMock(return_value=(None, True))
    orchestrator = ChatOrchestrator(
        messenger_client=mock_messenger,
        session_factory=factory,
        llm_provider=mock_llm,
    )
    ctx = await orchestrator.prepare_context(user.fb_psid, "hôm nay ổn")
    system_prompt = ctx.full_messages[0]["content"]
    assert "một câu bình thường" in system_prompt
    assert "đụ má" not in system_prompt
    assert "mình muốn chết" not in system_prompt


def test_toxic_guidance_is_present_except_during_crisis():
    common = dict(
        display_name=None,
        core_profile={},
        style_profile={},
        relevant_memories=[],
        summary_content=None,
        recent_user_messages=[],
    )
    toxic = assemble_system_prompt(is_toxic_active=True, **common)
    crisis = assemble_system_prompt(
        is_toxic_active=True,
        is_crisis_active=True,
        **common,
    )
    assert "NGÔN TỪ THÔ TỤC" in toxic
    assert "không chửi lại" in toxic.lower()
    assert "NGÔN TỪ THÔ TỤC" not in crisis
