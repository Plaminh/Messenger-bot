"""Long-term memory extraction and reconciliation module.

Distills persistent facts about the user every ~6 messages or after inactivity.
Calls tier 'fast' in JSON mode and applies add/update/delete operations directly.
"""

import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.store import (
    add_memory,
    delete_memory,
    get_last_extracted_message_id,
    get_messages_after,
    get_recent_messages,
    set_last_extracted_message_id,
    update_memory,
)
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.budget import record_llm_result_usage
from app.memory.retriever import retrieve_relevant_memories
from app.persona.safety import sanitize_turns

logger = get_logger(__name__)

EXTRACTION_MESSAGE_INTERVAL = 6
EXTRACTION_INACTIVITY_SECONDS = 300  # 5 minutes
EXTRACTION_FIRST_RUN_MESSAGES = 12  # no watermark yet: look at the latest N messages
EXTRACTION_MAX_BATCH_MESSAGES = 30  # per run, messages after the watermark


def should_trigger_extraction(user_msg_count: int) -> bool:
    """Check if memory extraction conditions are satisfied."""
    return user_msg_count > 0 and user_msg_count % EXTRACTION_MESSAGE_INTERVAL == 0


async def extract_and_sync_memories(
    session: AsyncSession,
    user_id: int,
    llm: LLMProvider,
) -> None:
    """Extract durable facts from recent dialogue and synchronize memory store."""
    # Only look at messages newer than the last extraction watermark so the same
    # dialogue is never extracted twice (message-count trigger + inactivity timer).
    last_extracted_id = await get_last_extracted_message_id(session, user_id)
    if last_extracted_id is None:
        recent_msgs = await get_recent_messages(session, user_id, limit=EXTRACTION_FIRST_RUN_MESSAGES)
    else:
        recent_msgs = await get_messages_after(
            session,
            user_id,
            last_extracted_id,
            limit=EXTRACTION_MAX_BATCH_MESSAGES,
        )
    if len(recent_msgs) < 2:
        return

    sanitized_messages = sanitize_turns(recent_msgs)
    if len(sanitized_messages) < 2:
        await set_last_extracted_message_id(session, user_id, recent_msgs[-1].id)
        await session.commit()
        return

    # Form conversational snippet
    snippet_lines = []
    for role, content in sanitized_messages:
        speaker = "Bạn (bot)" if role == "assistant" else "User"
        snippet_lines.append(f"{speaker}: {content}")
    dialogue_snippet = "\n".join(snippet_lines)

    existing_memories = await retrieve_relevant_memories(
        session, user_id, dialogue_snippet[-500:], candidate_limit=20, top_k=5
    )
    existing_context = "\n".join(
        f"[ID {memory.id}] ({memory.category}, {memory.importance}/10): {memory.content}"
        for memory in existing_memories
    ) or "(Chưa có ký ức liên quan)"

    system_prompt = (
        "Bạn là module trích xuất ký ức dài hạn cho chatbot người bạn thân.\n"
        "Nhiệm vụ: Phân tích đoạn hội thoại gần nhất và trích xuất các thông tin/sự kiện bền vững về USER.\n"
        "Quy tắc nghiêm ngặt:\n"
        "1. Chỉ lưu sự kiện về User (thói quen, công việc, sở thích, người thân, sự kiện quan trọng, mục tiêu, cảm xúc sâu sắc).\n"
        "2. TUYỆT ĐỐI KHÔNG lưu nguyên văn tin nhắn, không lưu lời của bot, không lưu câu chào hỏi xã giao.\n"
        "3. Sử dụng các op sau:\n"
        "   - 'add': thông tin mới về user (id: null).\n"
        "   - 'update': cập nhật thông tin đã có nếu có chi tiết mới hoặc thay đổi (id: số ID hiện tại).\n"
        "   - 'delete': xóa thông tin nếu user đã sửa đổi hoặc thông tin không còn đúng (id: số ID hiện tại).\n"
        "4. Category hợp lệ: 'person', 'event', 'preference', 'feeling', 'goal', 'other'.\n"
        "5. Importance: số nguyên từ 1 đến 10.\n"
        "6. Tuyệt đối không lưu nội dung tự hại, tự sát, chửi thề hay xúc phạm.\n"
        "7. Định dạng JSON bắt buộc: {\"operations\": [{\"op\": \"add|update|delete\", \"id\": null|int, \"fact\": \"...\", \"category\": \"...\", \"importance\": 1-10}]}"
    )

    user_prompt = (
        f"Ký ức hiện có:\n{existing_context}\n\n"
        f"Đoạn hội thoại gần đây:\n{dialogue_snippet}\n\n"
        "Hãy xuất JSON chứa các thao tác cập nhật ký ức (nếu không có gì đáng nhớ thì mảng rỗng):"
    )

    try:
        res = await llm.generate(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model_tier="fast",
            json_mode=True,
            max_tokens=500,
            temperature=0.2,
        )
        await record_llm_result_usage(session, res)

        if res.tier == "fallback":
            # LLM unavailable: keep the watermark so these messages are retried later
            await session.commit()
            return

        data = json.loads(res.content)
        ops = []
        if isinstance(data, list):
            ops = data
        elif isinstance(data, dict):
            ops = data.get("operations", []) or data.get("memories", [])

        if not isinstance(ops, list):
            await set_last_extracted_message_id(session, user_id, recent_msgs[-1].id)
            await session.commit()
            return

        source_msg_ids = [m.id for m in recent_msgs[-3:]]

        for op_item in ops:
            if not isinstance(op_item, dict):
                continue
            op = op_item.get("op", "add")
            fact = op_item.get("fact", "").strip()
            category = op_item.get("category", "other")
            importance = int(op_item.get("importance", 5))
            mem_id = op_item.get("id")

            if op == "add" and fact:
                await add_memory(
                    session,
                    user_id=user_id,
                    content=fact,
                    category=category,
                    importance=importance,
                    source_message_ids=source_msg_ids,
                )
                logger.info("Added memory for user_id=%d: %s", user_id, category)

            elif op == "update" and fact and mem_id:
                updated = await update_memory(
                    session,
                    memory_id=int(mem_id),
                    content=fact,
                    category=category,
                    importance=importance,
                    user_id=user_id,
                )
                if updated:
                    logger.info("Updated memory id=%s for user_id=%d", mem_id, user_id)
                else:
                    logger.warning("Ignored update of memory id=%s not owned by user_id=%d", mem_id, user_id)

            elif op == "delete" and mem_id:
                deleted = await delete_memory(session, memory_id=int(mem_id), user_id=user_id)
                if deleted:
                    logger.info("Deleted memory id=%s for user_id=%d", mem_id, user_id)
                else:
                    logger.warning("Ignored delete of memory id=%s not owned by user_id=%d", mem_id, user_id)

        await set_last_extracted_message_id(session, user_id, recent_msgs[-1].id)
        await session.commit()

    except Exception as exc:
        await session.rollback()
        logger.error("Failed extracting memories for user_id=%d: %s", user_id, exc)
