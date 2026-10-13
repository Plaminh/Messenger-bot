"""Sensitive exchanges never enter memory extraction or rolling summaries."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import User
from app.db.store import (
    add_message,
    get_last_extracted_message_id,
    get_summary,
)
from app.integrations.llm.base import LLMResult
from app.memory.extractor import extract_and_sync_memories
from app.memory.summarizer import maybe_run_rolling_summary
from app.persona.safety import sanitize_turns


def test_sanitize_turns_removes_sensitive_pair_and_can_insert_placeholder():
    messages = [
        SimpleNamespace(role="user", content="mình muốn chết"),
        SimpleNamespace(role="assistant", content="phản hồi an toàn"),
        SimpleNamespace(role="user", content="mình thích cà phê"),
    ]
    assert sanitize_turns(messages) == [("user", "mình thích cà phê")]
    assert sanitize_turns(messages, placeholder="[đã lược bỏ]") == [
        ("user", "[đã lược bỏ]"),
        ("user", "mình thích cà phê"),
    ]


@pytest.mark.asyncio
async def test_extractor_omits_sensitive_pair_from_llm(db_session):
    user = User(fb_psid="extract-safe", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.flush()
    await add_message(db_session, user.id, "user", "mình thích trà")
    await add_message(db_session, user.id, "assistant", "mình nhớ rồi")
    await add_message(db_session, user.id, "user", "đụ má")
    await add_message(db_session, user.id, "assistant", "bạn đang rất bực")
    await db_session.commit()
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=LLMResult('{"operations": []}', 0, "test", "fast"))

    await extract_and_sync_memories(db_session, user.id, llm)

    payload = llm.generate.await_args.args[0]
    sent_text = "\n".join(item["content"] for item in payload)
    assert "mình thích trà" in sent_text
    assert "đụ má" not in sent_text
    assert "bạn đang rất bực" not in sent_text


@pytest.mark.asyncio
async def test_extractor_advances_watermark_when_everything_is_filtered(db_session):
    user = User(fb_psid="extract-watermark", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.flush()
    await add_message(db_session, user.id, "user", "mình muốn chết")
    last = await add_message(db_session, user.id, "assistant", "phản hồi an toàn")
    await db_session.commit()
    llm = MagicMock(generate=AsyncMock())

    await extract_and_sync_memories(db_session, user.id, llm)

    assert await get_last_extracted_message_id(db_session, user.id) == last.id
    llm.generate.assert_not_awaited()


@pytest.mark.asyncio
async def test_summary_uses_placeholder_and_original_upto_id(db_session, monkeypatch):
    user = User(fb_psid="summary-safe", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.flush()
    await add_message(db_session, user.id, "user", "mình muốn chết")
    await add_message(db_session, user.id, "assistant", "phản hồi an toàn")
    await add_message(db_session, user.id, "user", "chuyện bình thường")
    last = await add_message(db_session, user.id, "assistant", "ừ mình nghe")
    await db_session.commit()
    monkeypatch.setattr("app.memory.summarizer.build_recent_window", lambda *args, **kwargs: [])
    llm = MagicMock()
    llm.generate = AsyncMock(return_value=LLMResult("tóm tắt sạch", 0, "test", "fast"))

    assert await maybe_run_rolling_summary(db_session, user.id, llm)

    sent_text = llm.generate.await_args.args[0][1]["content"]
    assert "[một đoạn trao đổi nhạy cảm đã được lược bỏ]" in sent_text
    assert "mình muốn chết" not in sent_text
    assert "phản hồi an toàn" not in sent_text
    summary = await get_summary(db_session, user.id)
    assert summary.upto_message_id == last.id
