"""Rolling conversation summarizer.

Compresses conversational turns that are about to leave the recent-message window into a
concise running summary (<= 300 tokens), so there is no blind spot between the window and
the summary. Always runs in background using tier 'fast'.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.store import get_summary, get_unsummarized_messages, upsert_summary
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.budget import record_llm_usage
from app.memory.window import (
    RECENT_WINDOW_MESSAGE_LIMIT,
    RECENT_WINDOW_TOKEN_BUDGET,
    SUMMARY_LEAD_MESSAGES,
    SUMMARY_LEAD_TOKENS,
    build_recent_window,
    estimate_tokens,
)

logger = get_logger(__name__)

MIN_CHUNK_TO_SUMMARIZE = 4
CHUNK_TO_SUMMARIZE = 20
MAX_SUMMARY_TOKENS = 300


async def maybe_run_rolling_summary(
    session: AsyncSession,
    user_id: int,
    llm: LLMProvider,
) -> bool:
    """Check if threshold is reached and trigger rolling summary in background.

    Returns True if a summary was generated, False otherwise.
    """
    summary = await get_summary(session, user_id)
    upto_id = summary.upto_message_id if summary else None

    unsummarized = await get_unsummarized_messages(session, user_id, upto_message_id=upto_id)

    # Messages the prompt window still shows verbatim (slightly smaller than the real
    # window so the summary is always ready before a message drops out of it).
    window_candidates = unsummarized[-max(RECENT_WINDOW_MESSAGE_LIMIT - SUMMARY_LEAD_MESSAGES, 1):]
    visible = build_recent_window(
        window_candidates,
        token_budget=max(RECENT_WINDOW_TOKEN_BUDGET - SUMMARY_LEAD_TOKENS, 1),
    )
    outside_count = len(unsummarized) - len(visible)
    if outside_count < MIN_CHUNK_TO_SUMMARIZE:
        return False

    # Summarize the oldest messages that are no longer (or almost no longer) in the window
    chunk = unsummarized[: min(outside_count, CHUNK_TO_SUMMARIZE)]
    new_upto_id = chunk[-1].id

    # Format transcript
    lines = []
    for msg in chunk:
        speaker = "Bạn (bot)" if msg.role == "assistant" else "User"
        lines.append(f"{speaker}: {msg.content}")
    transcript = "\n".join(lines)

    previous_summary = summary.content if summary else "Chưa có tóm tắt trước đó."

    prompt_messages = [
        {
            "role": "system",
            "content": (
                "Bạn là trợ lý tóm tắt hội thoại thân mật. "
                "Nhiệm vụ: Cập nhật tóm tắt dòng chảy cuộc trò chuyện giữa User và Bạn thân. "
                "Yêu cầu: Viết súc tích, dưới 250 token, nêu các chủ đề, sự kiện và cảm xúc chính đã diễn ra. "
                "Không dùng danh sách gạch đầu dòng dài dòng."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Tóm tắt trước đó:\n{previous_summary}\n\n"
                f"Đoạn hội thoại mới cần tích hợp:\n{transcript}\n\n"
                "Hãy viết tóm tắt cập nhật hoàn chỉnh:"
            ),
        },
    ]

    try:
        res = await llm.generate(
            prompt_messages,
            model_tier="fast",
            max_tokens=MAX_SUMMARY_TOKENS,
            temperature=0.3,
        )
        if res.usage_tokens > 0:
            await record_llm_usage(session, res.model, res.usage_tokens)
        updated_content = res.content.strip()

        # Never overwrite the stored summary with the friendly error text / empty output
        if res.tier == "fallback" or not updated_content:
            await session.commit()  # keep usage accounting, leave summary untouched
            logger.warning("Skipped rolling summary for user_id=%d: LLM unavailable or empty", user_id)
            return False

        # Condense if too long
        if estimate_tokens(updated_content) > MAX_SUMMARY_TOKENS:
            condense_messages = [
                {
                    "role": "system",
                    "content": "Hãy cô đọng đoạn văn sau xuống dưới 200 token mà không làm mất thông tin cảm xúc và sự kiện chính:",
                },
                {"role": "user", "content": updated_content},
            ]
            condensed_res = await llm.generate(
                condense_messages,
                model_tier="fast",
                max_tokens=MAX_SUMMARY_TOKENS,
                temperature=0.3,
            )
            if condensed_res.usage_tokens > 0:
                await record_llm_usage(session, condensed_res.model, condensed_res.usage_tokens)
            condensed_content = condensed_res.content.strip()
            if condensed_res.tier == "fallback" or not condensed_content:
                await session.commit()
                logger.warning("Skipped rolling summary for user_id=%d: condensing failed", user_id)
                return False
            updated_content = condensed_content

        await upsert_summary(session, user_id, updated_content, upto_message_id=new_upto_id)
        await session.commit()
        logger.info("Updated rolling summary for user_id=%d upto_message_id=%d", user_id, new_upto_id)
        return True

    except Exception as exc:
        logger.error("Failed to run rolling summary for user_id=%d: %s", user_id, exc)
        return False
