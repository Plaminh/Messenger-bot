"""Focused contracts for advice, corrections, and rapid-message batching."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ChatOrchestrator
from app.db.models import User
from app.db.store import add_message, get_recent_messages
from app.persona.prompt import assemble_system_prompt


def _system_prompt() -> str:
    return assemble_system_prompt(
        display_name=None,
        core_profile={},
        style_profile={},
        relevant_memories=[],
        summary_content=None,
        recent_user_messages=[],
    )


def test_prompt_prioritizes_practical_advice_without_forced_question():
    prompt = _system_prompt()

    assert "trả lời trực tiếp bằng gợi ý thực tế" in prompt
    assert "câu hỏi đó là tùy chọn, không bắt buộc" in prompt
    assert "không ép mọi câu trả lời phải phản chiếu cảm xúc" in prompt
    assert "được dùng vài bước ngắn, cụ thể" in prompt


def test_prompt_disambiguates_users_friend_and_preserves_corrections():
    prompt = _system_prompt()

    assert "'bạn của t/mình/tao' chỉ bạn của người dùng, không phải bot" in prompt
    assert "lời sửa mới nhất được ưu tiên nhưng không làm mất yêu cầu ban đầu" in prompt


@pytest.mark.asyncio
async def test_correction_then_fear_remain_ordered_user_messages(
    db_session, mock_messenger, mock_llm
):
    user = User(
        fb_psid="correction-sequence",
        style_profile={},
        core_profile={"name_lookup_done": True},
    )
    db_session.add(user)
    await db_session.flush()
    await add_message(db_session, user.id, "user", "chỉ t cách cua đổ bạn", mid="m1")
    await add_message(db_session, user.id, "assistant", "Bạn đang nói về mình à?")
    await add_message(db_session, user.id, "user", "thích bạn của t, không phải m", mid="m2")
    await db_session.commit()

    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    mock_messenger.fetch_first_name = AsyncMock(return_value=(None, True))
    orchestrator = ChatOrchestrator(
        messenger_client=mock_messenger,
        session_factory=factory,
        llm_provider=mock_llm,
    )

    ctx = await orchestrator.prepare_context(user.fb_psid, "sợ", mid="m3")
    dialog = ctx.full_messages[1:]

    assert [(item["role"], item["content"]) for item in dialog] == [
        ("user", "chỉ t cách cua đổ bạn"),
        ("assistant", "Bạn đang nói về mình à?"),
        ("user", "thích bạn của t, không phải m"),
        ("user", "sợ"),
    ]


@pytest.mark.asyncio
async def test_debounce_keeps_advice_request_when_followed_by_complaint():
    debouncer = MessageDebouncer(delay=0.01)
    callback = AsyncMock()

    await debouncer.add_message("u", "chỉ t cách cua đổ bạn", callback, mid="m1")
    await debouncer.add_message("u", "sao m cứ hỏi hoài vậy", callback, mid="m2")
    await asyncio.sleep(0.04)

    callback.assert_awaited_once_with(
        "u",
        "chỉ t cách cua đổ bạn\nsao m cứ hỏi hoài vậy",
        mid="m2",
        source_messages=[
            ("chỉ t cách cua đổ bạn", "m1"),
            ("sao m cứ hỏi hoài vậy", "m2"),
        ],
    )


@pytest.mark.asyncio
async def test_batched_messages_are_persisted_individually_with_their_mids(
    db_session, mock_messenger, mock_llm
):
    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    mock_messenger.fetch_first_name = AsyncMock(return_value=(None, True))
    orchestrator = ChatOrchestrator(
        messenger_client=mock_messenger,
        session_factory=factory,
        llm_provider=mock_llm,
    )
    source = [("chỉ t cách cua đổ bạn", "m1"), ("sao m cứ hỏi hoài vậy", "m2")]

    ctx = await orchestrator.prepare_context(
        "batch-persist",
        "\n".join(text for text, _ in source),
        mid="m2",
        source_messages=source,
    )
    assert [item["content"] for item in ctx.full_messages[-2:]] == [text for text, _ in source]
    assert await orchestrator.persist_turn(ctx, await orchestrator.generate_reply(ctx))

    stored = await get_recent_messages(db_session, ctx.user_id)
    assert [(item.role, item.content, item.mid) for item in stored] == [
        ("user", "chỉ t cách cua đổ bạn", "m1"),
        ("user", "sao m cứ hỏi hoài vậy", "m2"),
    ]


@pytest.mark.asyncio
async def test_mixed_duplicate_batch_keeps_and_persists_only_new_message(
    db_session, mock_messenger, mock_llm
):
    user = User(
        fb_psid="mixed-batch",
        style_profile={},
        core_profile={"name_lookup_done": True},
    )
    db_session.add(user)
    await db_session.flush()
    await add_message(db_session, user.id, "user", "tin đã lưu", mid="duplicate-mid")
    await db_session.commit()

    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    orchestrator = ChatOrchestrator(
        messenger_client=mock_messenger,
        session_factory=factory,
        llm_provider=mock_llm,
    )
    source = [("tin đã lưu", "duplicate-mid"), ("tin mới cần trả lời", "new-mid")]

    ctx = await orchestrator.prepare_context(
        user.fb_psid,
        "\n".join(text for text, _ in source),
        mid="new-mid",
        source_messages=source,
    )

    assert ctx is not None
    assert ctx.clean_text == "tin mới cần trả lời"
    assert ctx.mid == "new-mid"
    assert ctx.source_messages == [("tin mới cần trả lời", "new-mid")]
    assert ctx.full_messages[-1] == {"role": "user", "content": "tin mới cần trả lời"}
    assert all(item["content"] != "tin đã lưu" for item in ctx.full_messages[-1:])

    reply = await orchestrator.generate_reply(ctx)
    mock_llm.generate.assert_awaited_once()
    sent_payload = mock_llm.generate.await_args.args[0]
    assert sent_payload[-1] == {"role": "user", "content": "tin mới cần trả lời"}
    assert await orchestrator.persist_turn(ctx, reply)

    stored = await get_recent_messages(db_session, user.id)
    assert [(item.content, item.mid) for item in stored] == [
        ("tin đã lưu", "duplicate-mid"),
        ("tin mới cần trả lời", "new-mid"),
    ]
