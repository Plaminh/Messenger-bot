"""Long-term memory extraction and reconciliation module.

Distills persistent facts about the user every ~6 messages or after inactivity.
Calls tier 'fast' in JSON mode and applies add/update/delete operations directly.
"""

from datetime import datetime, timezone
import json
from typing import Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.llm.base import LLMProvider
from app.llm.budget import record_llm_usage
from app.memory.embedder import TextEmbedder, get_embedder
from app.memory.retriever import retrieve_relevant_memories
from app.memory.store import (
    add_memory,
    delete_memory,
    get_recent_messages,
    update_memory,
)

logger = get_logger(__name__)

EXTRACTION_MESSAGE_INTERVAL = 6
EXTRACTION_INACTIVITY_SECONDS = 300  # 5 minutes


def should_trigger_extraction(
    user_msg_count: int,
    last_user_msg_at: Optional[datetime],
) -> bool:
    """Check if memory extraction conditions are satisfied."""
    if user_msg_count > 0 and user_msg_count % EXTRACTION_MESSAGE_INTERVAL == 0:
        return True

    if last_user_msg_at:
        now = datetime.now(timezone.utc)
        if last_user_msg_at.tzinfo is None:
            last_user_msg_at = last_user_msg_at.replace(tzinfo=timezone.utc)
        if (now - last_user_msg_at).total_seconds() >= EXTRACTION_INACTIVITY_SECONDS:
            return True

    return False


async def extract_and_sync_memories(
    session: AsyncSession,
    user_id: int,
    llm: LLMProvider,
    embedder: Optional[TextEmbedder] = None,
) -> None:
    """Extract durable facts from recent dialogue and synchronize memory store."""
    recent_msgs = await get_recent_messages(session, user_id, limit=10)
    if len(recent_msgs) < 2:
        return

    embedder_instance = embedder or get_embedder()

    # Form conversational snippet
    snippet_lines = []
    for msg in recent_msgs:
        speaker = "Bạn (bot)" if msg.role == "assistant" else "User"
        snippet_lines.append(f"{speaker}: {msg.content}")
    dialogue_snippet = "\n".join(snippet_lines)

    # Find up to 3 existing memories for context
    query_vec = await embedder_instance.embed_query(dialogue_snippet[-200:])
    existing_memories = await retrieve_relevant_memories(
        session,
        user_id,
        query_vec,
        candidate_limit=10,
        top_k=3,
    )

    existing_context = "\n".join(
        [
            f"[ID {m.id}] ({m.category}, quan trọng {m.importance}/10): {m.content}"
            for m in existing_memories
        ]
    )
    if not existing_context:
        existing_context = "(Chưa có ký ức nào liên quan)"

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
        "6. Định dạng JSON bắt buộc: {\"operations\": [{\"op\": \"add|update|delete\", \"id\": null|int, \"fact\": \"...\", \"category\": \"...\", \"importance\": 1-10}]}"
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
        if res.usage_tokens > 0:
            await record_llm_usage(session, res.model, res.usage_tokens)

        data = json.loads(res.content)
        ops = []
        if isinstance(data, list):
            ops = data
        elif isinstance(data, dict):
            ops = data.get("operations", []) or data.get("memories", [])

        if not isinstance(ops, list):
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
                vec = await embedder_instance.embed_passage(fact)
                await add_memory(
                    session,
                    user_id=user_id,
                    content=fact,
                    category=category,
                    importance=importance,
                    embedding=vec,
                    source_message_ids=source_msg_ids,
                )
                logger.info("Added memory for user_id=%d: %s", user_id, category)

            elif op == "update" and fact and mem_id:
                vec = await embedder_instance.embed_passage(fact)
                await update_memory(
                    session,
                    memory_id=int(mem_id),
                    content=fact,
                    category=category,
                    importance=importance,
                    embedding=vec,
                )
                logger.info("Updated memory id=%s for user_id=%d", mem_id, user_id)

            elif op == "delete" and mem_id:
                await delete_memory(session, memory_id=int(mem_id))
                logger.info("Deleted memory id=%s for user_id=%d", mem_id, user_id)

        await session.commit()

    except Exception as exc:
        logger.error("Failed extracting memories for user_id=%d: %s", user_id, exc)
