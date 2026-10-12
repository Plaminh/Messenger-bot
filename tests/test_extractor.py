"""Tests for long-term memory extractor and JSON error recovery."""

import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory, Message, User
from app.db.store import get_all_memories
from app.integrations.llm.base import LLMResult
from app.memory.extractor import (
    extract_and_sync_memories,
    should_trigger_extraction,
)


def test_should_trigger_extraction():
    assert should_trigger_extraction(6, None) is True
    assert should_trigger_extraction(12, None) is True
    assert should_trigger_extraction(5, None) is False
    assert should_trigger_extraction(0, None) is False


@pytest.mark.asyncio
async def test_extractor_executes_add_and_delete_operations(
    db_session: AsyncSession,
    mock_embedder,
):
    user = User(fb_psid="psid_extractor_test", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add existing memory to be deleted
    existing_mem = Memory(
        user_id=user.id,
        content="User đang làm việc ở công ty cũ",
        category="event",
        importance=5,
        embedding=[0.05] * 384,
    )
    db_session.add(existing_mem)

    # Add recent messages
    m1 = Message(user_id=user.id, role="user", content="Mình vừa chuyển sang công ty mới rồi")
    m2 = Message(user_id=user.id, role="assistant", content="Chúc mừng bạn nhé!")
    db_session.add_all([m1, m2])
    await db_session.commit()
    await db_session.refresh(existing_mem)

    # Mock LLM returning operations to add new job fact and delete old job fact
    llm_payload = {
        "operations": [
            {
                "op": "add",
                "id": None,
                "fact": "User vừa chuyển sang công ty mới",
                "category": "event",
                "importance": 8,
            },
            {
                "op": "delete",
                "id": existing_mem.id,
                "fact": "",
                "category": "event",
                "importance": 1,
            },
        ]
    }

    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            content=json.dumps(llm_payload),
            usage_tokens=80,
            model="llama-3.1-8b-instant",
            tier="fast",
        )
    )

    await extract_and_sync_memories(
        db_session,
        user.id,
        mock_llm,
        embedder=mock_embedder,
    )

    memories = await get_all_memories(db_session, user.id)
    assert len(memories) == 1
    assert "công ty mới" in memories[0].content
