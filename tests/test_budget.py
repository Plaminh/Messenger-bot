"""Tests for LLM usage tracking and token budget downgrade threshold."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.llm.budget import (
    get_daily_tokens,
    record_llm_usage,
    should_downgrade_to_fast,
)


@pytest.mark.asyncio
async def test_record_and_query_llm_usage(db_session: AsyncSession):
    model = "llama-3.3-70b-versatile"
    assert await get_daily_tokens(db_session, model) == 0

    await record_llm_usage(db_session, model, tokens=150, requests=1)
    assert await get_daily_tokens(db_session, model) == 150

    await record_llm_usage(db_session, model, tokens=200, requests=1)
    assert await get_daily_tokens(db_session, model) == 350


@pytest.mark.asyncio
async def test_budget_downgrade_threshold_at_90_percent(db_session: AsyncSession):
    settings = get_settings()
    model = settings.GROQ_MODEL_MAIN
    budget = settings.DAILY_TOKEN_BUDGET_MAIN  # default 100,000

    # Under 90% (80,000 tokens) -> should NOT downgrade
    await record_llm_usage(db_session, model, tokens=int(budget * 0.8), requests=1)
    assert await should_downgrade_to_fast(db_session) is False

    # Consumes another 15% (total 95% = 95,000 tokens) -> MUST downgrade to fast tier
    await record_llm_usage(db_session, model, tokens=int(budget * 0.15), requests=1)
    assert await should_downgrade_to_fast(db_session) is True
