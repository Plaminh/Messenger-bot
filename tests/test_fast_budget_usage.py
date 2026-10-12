"""Tests for fast model usage recording and atomic upsert in budget."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LLMUsage, Message, User
from app.integrations.llm.base import LLMResult
from app.integrations.llm.budget import get_daily_tokens, record_llm_usage
from app.memory.extractor import extract_and_sync_memories
from app.memory.summarizer import maybe_run_rolling_summary


@pytest.mark.asyncio
async def test_record_llm_usage_atomic_accumulation(db_session: AsyncSession):
    model_name = "llama-3.1-8b-instant"

    # Call record_llm_usage multiple times
    await record_llm_usage(db_session, model_name, tokens=100, requests=1)
    await record_llm_usage(db_session, model_name, tokens=250, requests=1)
    await record_llm_usage(db_session, model_name, tokens=50, requests=2)

    total_tokens = await get_daily_tokens(db_session, model_name)
    assert total_tokens == 400

    stmt = select(LLMUsage.requests).where(LLMUsage.model == model_name)
    res = await db_session.execute(stmt)
    reqs = res.scalar_one()
    assert reqs == 4


@pytest.mark.asyncio
async def test_summarizer_and_extractor_record_usage(
    db_session: AsyncSession,
    mock_embedder,
):
    user = User(fb_psid="psid_usage_test", style_profile={}, core_profile={})
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Add 35 unsummarized messages to trigger summarizer
    msgs = [
        Message(user_id=user.id, role="user" if i % 2 == 0 else "assistant", content=f"Tin {i}")
        for i in range(35)
    ]
    db_session.add_all(msgs)
    await db_session.commit()

    fast_model = "llama-3.1-8b-instant"
    mock_llm = MagicMock()
    mock_llm.generate = AsyncMock(
        return_value=LLMResult(
            content=json.dumps({"operations": []}),
            usage_tokens=120,
            model=fast_model,
            tier="fast",
        )
    )

    # 1. Run summarizer
    await maybe_run_rolling_summary(db_session, user.id, mock_llm)

    # Verify usage was recorded
    usage_after_sum = await get_daily_tokens(db_session, fast_model)
    assert usage_after_sum == 120

    # 2. Run extractor
    await extract_and_sync_memories(db_session, user.id, mock_llm, embedder=mock_embedder)

    # Verify extractor also recorded usage
    usage_after_ext = await get_daily_tokens(db_session, fast_model)
    assert usage_after_ext == 240
