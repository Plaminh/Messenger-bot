"""Bounded deterministic memory retrieval remains isolated per user."""

from datetime import datetime, timedelta, timezone

import pytest

from app.db.models import Memory, User
from app.memory.retriever import MAX_MEMORY_CHARS, normalize_memory_text, retrieve_relevant_memories


@pytest.mark.asyncio
async def test_accent_normalization_ranking_isolation_and_limits(db_session):
    assert normalize_memory_text(" Cà-phê đen! ") == "ca phe den"

    owner = User(fb_psid="owner", style_profile={}, core_profile={})
    other = User(fb_psid="other", style_profile={}, core_profile={})
    db_session.add_all([owner, other])
    await db_session.commit()
    now = datetime.now(timezone.utc)
    recent = Memory(user_id=owner.id, content="Thích cà phê đen", category="preference", importance=9,
                    created_at=now, last_accessed_at=now)
    old = Memory(user_id=owner.id, content="Từng uống ca phe ở Huế", category="event", importance=2,
                 created_at=now - timedelta(days=30), last_accessed_at=now - timedelta(days=30))
    foreign = Memory(user_id=other.id, content="Thích cà phê đen", category="preference", importance=10)
    oversized = Memory(user_id=owner.id, content="ca phe " + "x" * MAX_MEMORY_CHARS,
                       category="other", importance=10)
    db_session.add_all([recent, old, foreign, oversized])
    await db_session.commit()

    found = await retrieve_relevant_memories(db_session, owner.id, "CA PHE", top_k=10)
    assert [memory.id for memory in found] == [recent.id, old.id]
    assert all(memory.user_id == owner.id for memory in found)
    assert sum(len(memory.content) for memory in found) <= MAX_MEMORY_CHARS


@pytest.mark.asyncio
async def test_retrieval_is_read_only_and_order_is_stable(db_session):
    user = User(fb_psid="read-only", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.flush()
    timestamp = datetime(2025, 1, 1, tzinfo=timezone.utc)
    memories = [
        Memory(
            user_id=user.id,
            content="thích cà phê sáng",
            category="preference",
            importance=8,
            created_at=timestamp,
            last_accessed_at=timestamp,
        ),
        Memory(
            user_id=user.id,
            content="thích cà phê tối",
            category="preference",
            importance=6,
            created_at=timestamp,
            last_accessed_at=timestamp,
        ),
    ]
    db_session.add_all(memories)
    await db_session.commit()

    first = await retrieve_relevant_memories(db_session, user.id, "cà phê", top_k=10)
    second = await retrieve_relevant_memories(db_session, user.id, "cà phê", top_k=10)

    assert [item.id for item in first] == [item.id for item in second]
    for memory in memories:
        await db_session.refresh(memory)
        stored = memory.last_accessed_at
        if stored.tzinfo is None:
            stored = stored.replace(tzinfo=timezone.utc)
        assert stored == timestamp
