from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory, User
from app.memory.retriever import MAX_MEMORY_CHARS, normalize_memory_text, retrieve_relevant_memories


def test_memory_normalization_matches_accented_and_unaccented_text():
    assert normalize_memory_text("  Cà-phê!!!  đen ") == "ca phe den"
    assert normalize_memory_text("CA PHE den") == "ca phe den"


@pytest.mark.asyncio
async def test_retriever_ranks_keyword_recency_and_importance_with_isolation(db_session: AsyncSession):
    user = User(fb_psid="psid_retriever_test", style_profile={}, core_profile={})
    other = User(fb_psid="psid_retriever_other", style_profile={}, core_profile={})
    db_session.add_all([user, other])
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(other)
    now = datetime.now(timezone.utc)

    relevant = Memory(user_id=user.id, content="User thích uống cà phê đen không đường", category="preference", importance=9, created_at=now, last_accessed_at=now)
    stale = Memory(user_id=user.id, content="User từng uống cà phê ở Hà Nội", category="event", importance=2, created_at=now - timedelta(days=30), last_accessed_at=now - timedelta(days=30))
    foreign = Memory(user_id=other.id, content="User thích cà phê đen", category="preference", importance=10, created_at=now, last_accessed_at=now)
    db_session.add_all([relevant, stale, foreign])
    await db_session.commit()

    results = await retrieve_relevant_memories(db_session, user.id, "CA PHE den", top_k=2)
    assert [memory.id for memory in results] == [relevant.id, stale.id]
    assert all(memory.user_id == user.id for memory in results)


@pytest.mark.asyncio
async def test_retriever_limits_result_count_and_total_length(db_session: AsyncSession):
    user = User(fb_psid="psid_retriever_limit", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    db_session.add_all([
        Memory(user_id=user.id, content=f"mèo {index} " + ("x" * 1000), category="other", importance=10)
        for index in range(10)
    ])
    await db_session.commit()

    results = await retrieve_relevant_memories(db_session, user.id, "mèo", top_k=10, candidate_limit=100)
    assert len(results) <= 10
    assert sum(len(memory.content) for memory in results) <= MAX_MEMORY_CHARS
