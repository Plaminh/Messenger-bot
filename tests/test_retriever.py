"""Tests for composite memory retriever and re-ranking."""

from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Memory, User
from app.memory.retriever import compute_python_cosine, retrieve_relevant_memories


def test_compute_python_cosine():
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]

    assert abs(compute_python_cosine(v1, v2) - 1.0) < 1e-5
    assert abs(compute_python_cosine(v1, v3) - 0.0) < 1e-5


@pytest.mark.asyncio
async def test_retriever_ranking_with_composite_score(db_session: AsyncSession):
    # Create test user
    user = User(fb_psid="psid_retriever_test", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    now = datetime.now(timezone.utc)
    # Memory 1: High cosine similarity (aligned vector), recent, high importance
    m1 = Memory(
        user_id=user.id,
        content="User thích uống cà phê đen không đường",
        category="preference",
        importance=9,
        embedding=[1.0] + [0.0] * 383,
        created_at=now,
        last_accessed_at=now,
    )
    # Memory 2: Low cosine similarity (orthogonal vector), low importance
    m2 = Memory(
        user_id=user.id,
        content="User từng đi công tác Hà Nội năm ngoái",
        category="event",
        importance=3,
        embedding=[0.0, 1.0] + [0.0] * 382,
        created_at=now - timedelta(days=30),
        last_accessed_at=now - timedelta(days=30),
    )
    # Memory 3: Moderate cosine similarity, high importance
    m3 = Memory(
        user_id=user.id,
        content="User dị ứng với hải sản",
        category="preference",
        importance=10,
        embedding=[0.7, 0.7] + [0.0] * 382,
        created_at=now,
        last_accessed_at=now,
    )

    db_session.add_all([m1, m2, m3])
    await db_session.commit()

    # Query vector aligned with Memory 1
    query_vector = [1.0] + [0.0] * 383

    results = await retrieve_relevant_memories(
        db_session,
        user.id,
        query_vector,
        candidate_limit=10,
        top_k=2,
    )

    assert len(results) == 2
    # Memory 1 should be ranked highest due to high cosine + high importance + recent
    assert results[0].id == m1.id
    # Memory 3 should be ranked 2nd
    assert results[1].id == m3.id
