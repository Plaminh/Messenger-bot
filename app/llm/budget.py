"""Token budgeting and daily quota tracking for LLMs."""

from datetime import date, datetime
from zoneinfo import ZoneInfo
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import get_settings
from app.memory.models import LLMUsage

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def get_current_vn_date() -> date:
    """Return current date in Vietnam timezone (UTC+7)."""
    return datetime.now(VN_TZ).date()


async def record_llm_usage(
    session: AsyncSession,
    model: str,
    tokens: int,
    requests: int = 1,
) -> None:
    """Increment token and request counters atomically for specified model on current date."""
    today = get_current_vn_date()
    update_stmt = (
        update(LLMUsage)
        .where(
            LLMUsage.day == today,
            LLMUsage.model == model,
        )
        .values(
            tokens=LLMUsage.tokens + tokens,
            requests=LLMUsage.requests + requests,
        )
    )
    result = await session.execute(update_stmt)
    if result.rowcount == 0:
        try:
            async with session.begin_nested():
                usage = LLMUsage(
                    day=today,
                    model=model,
                    tokens=tokens,
                    requests=requests,
                )
                session.add(usage)
                await session.flush()
        except IntegrityError:
            await session.execute(update_stmt)

    await session.commit()


async def get_daily_tokens(session: AsyncSession, model: str) -> int:
    """Retrieve total tokens consumed by a model today."""
    today = get_current_vn_date()
    stmt = select(LLMUsage.tokens).where(
        LLMUsage.day == today,
        LLMUsage.model == model,
    )
    result = await session.execute(stmt)
    total = result.scalar_one_or_none()
    return total or 0


async def should_downgrade_to_fast(session: AsyncSession) -> bool:
    """Check if main model has consumed >= 90% of its daily budget."""
    settings = get_settings()
    used_tokens = await get_daily_tokens(session, settings.GROQ_MODEL_MAIN)
    threshold = int(settings.DAILY_TOKEN_BUDGET_MAIN * 0.9)
    return used_tokens >= threshold
