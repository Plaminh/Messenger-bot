"""Dialogue orchestrator.

Coordinates full conversational turn execution in strict order:
1. Command checking (/help, /nho, /quen)
2. Style profiling (statistical heuristics, EMA)
3. Safety & crisis detection
4. Long-term memory retrieval
5. Context windowing by token budget
6. Prompt assembly
7. LLM invocation with budget check and fallback
8. Message persistence
9. Human-like multi-bubble delivery
10. Background tasks (rolling summary, memory extractor)
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_async_session_maker
from app.core.logging import get_logger
from app.chat.commands import handle_command, is_command
from app.llm.base import LLMProvider
from app.llm.budget import record_llm_usage, should_downgrade_to_fast
from app.llm.groq_provider import GroqProvider
from app.memory.embedder import TextEmbedder, get_embedder
from app.memory.extractor import extract_and_sync_memories, should_trigger_extraction
from app.memory.retriever import retrieve_relevant_memories
from app.memory.store import (
    add_message,
    get_or_create_user,
    get_recent_messages,
    get_summary,
    get_user_message_count,
    is_message_mid_exists,
    update_user_profiles,
)
from app.memory.summarizer import maybe_run_rolling_summary
from app.memory.window import build_recent_window
from app.messenger.client import MessengerClient, get_messenger_client
from app.persona.prompt import assemble_system_prompt, build_chat_messages
from app.persona.safety import is_crisis
from app.persona.style import detect_pronouns, update_style_profile

logger = get_logger(__name__)


class ChatOrchestrator:
    """Coordinates pipeline execution for user conversational turns."""

    def __init__(
        self,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        messenger_client: Optional[MessengerClient] = None,
        llm_provider: Optional[LLMProvider] = None,
        embedder: Optional[TextEmbedder] = None,
    ) -> None:
        self._session_factory = session_factory or get_async_session_maker()
        self._messenger = messenger_client or get_messenger_client()
        self._llm = llm_provider or GroqProvider()
        self._embedder = embedder or get_embedder()

    async def _run_background_tasks(
        self,
        user_id: int,
        user_msg_count: int,
        last_user_msg_at: Optional[datetime],
    ) -> None:
        """Execute rolling summarizer and memory extractor in background."""
        try:
            async with self._session_factory() as session:
                # 1. Rolling summarizer check
                await maybe_run_rolling_summary(session, user_id, self._llm)

                # 2. Long-term memory extraction check
                if should_trigger_extraction(user_msg_count, last_user_msg_at):
                    await extract_and_sync_memories(session, user_id, self._llm, self._embedder)
        except Exception as exc:
            logger.error("Error executing background tasks for user_id=%d: %s", user_id, exc)

    async def handle_turn(self, psid: str, text: str, mid: Optional[str] = None) -> None:
        """Process one conversational turn for user."""
        clean_text = text.strip()
        if not clean_text:
            return

        # ---------------- Phase 1: DB Read Session ----------------
        async with self._session_factory() as read_session:
            # Step 0: Deduplicate via DB if mid provided
            if mid and await is_message_mid_exists(read_session, mid):
                logger.info("Ignoring duplicate message mid via DB: %s", mid)
                return

            # Step 1: User lookup / creation
            user = await get_or_create_user(read_session, psid)

            # Step 2: Command handling
            if is_command(clean_text):
                cmd_reply = await handle_command(read_session, user, clean_text)
                if cmd_reply:
                    await self._messenger.send_human_like_response(psid, cmd_reply)
                    # For non-destructive commands, record dialog turn
                    if clean_text.split()[0].lower() != "/quen":
                        try:
                            await add_message(read_session, user.id, "user", clean_text, mid=mid)
                        except IntegrityError:
                            await read_session.rollback()
                            return
                        await add_message(read_session, user.id, "assistant", cmd_reply)
                await read_session.commit()
                return

            user_id = user.id
            core_profile = dict(user.core_profile or {})
            raw_style = dict(user.style_profile or {})

            # Step 6: Memory retrieval
            query_vec = await self._embedder.embed_query(clean_text)
            relevant_memories = await retrieve_relevant_memories(
                read_session,
                user_id,
                query_vec,
                top_k=6,
            )

            # Step 7: Summary & Recent dialog windowing
            summary_record = await get_summary(read_session, user_id)
            summary_text = summary_record.content if summary_record else None

            recent_history = await get_recent_messages(read_session, user_id, limit=30)
            window_messages = build_recent_window(recent_history, token_budget=850)
            user_msg_count = await get_user_message_count(read_session, user_id)

            # Step 9: Determine model tier via daily token budget
            downgrade = await should_downgrade_to_fast(read_session)
            tier = "fast" if downgrade else "main"
            await read_session.commit()

        # ---------------- Phase 2: In-Memory Prep & LLM Call (No DB Session Held) ----------------
        # Step 3: Pronoun detection in early messages
        if "pronouns" not in core_profile:
            detected_p = detect_pronouns(clean_text)
            if detected_p:
                core_profile["pronouns"] = detected_p

        # Step 4: Statistical style analysis & EMA update
        updated_style = update_style_profile(raw_style, clean_text)

        # Step 5: Safety check (crisis detection)
        crisis_active = is_crisis(clean_text)

        # Step 8: Prompt assembly
        recent_user_texts = [m.content for m in window_messages if m.role == "user"]
        is_first_interaction = user_msg_count == 0

        system_prompt = assemble_system_prompt(
            core_profile=core_profile,
            style_profile=updated_style,
            relevant_memories=relevant_memories,
            summary_content=summary_text,
            recent_user_messages=recent_user_texts,
            is_crisis_active=crisis_active,
            is_first_interaction=is_first_interaction,
        )

        full_messages = build_chat_messages(
            system_prompt=system_prompt,
            window_messages=window_messages,
            current_user_text=clean_text,
        )

        # Step 10: Call LLM without holding any database connection/session
        llm_result = await self._llm.generate(
            full_messages,
            model_tier=tier,
            temperature=0.9,
            max_tokens=300,
        )

        # ---------------- Phase 3: DB Write Session ----------------
        now = datetime.now(timezone.utc)
        async with self._session_factory() as write_session:
            try:
                # Record token consumption
                if llm_result.usage_tokens > 0:
                    await record_llm_usage(write_session, llm_result.model, llm_result.usage_tokens)

                # Step 11: Persist messages & profile updates in a single atomic transaction
                await add_message(write_session, user_id, "user", clean_text, mid=mid)
                await add_message(write_session, user_id, "assistant", llm_result.content)
                await update_user_profiles(
                    write_session,
                    user_id,
                    style_profile=updated_style,
                    core_profile=core_profile,
                    last_user_msg_at=now,
                )
                await write_session.commit()
            except IntegrityError:
                await write_session.rollback()
                logger.warning("Duplicate message mid prevented by unique constraint: %s", mid)
                return
            except Exception:
                await write_session.rollback()
                raise

        # ---------------- Phase 4: Delivery & Async Background Tasks ----------------
        # Step 12: Deliver response through Messenger client (mark_seen, typing, bubble delay)
        await self._messenger.send_human_like_response(psid, llm_result.content)

        # Step 13: Schedule background tasks asynchronously
        asyncio.create_task(
            self._run_background_tasks(
                user_id=user_id,
                user_msg_count=user_msg_count + 1,
                last_user_msg_at=now,
            )
        )


# Global orchestrator singleton
_orchestrator: Optional[ChatOrchestrator] = None


def get_orchestrator() -> ChatOrchestrator:
    """Return shared ChatOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = ChatOrchestrator()
    return _orchestrator
