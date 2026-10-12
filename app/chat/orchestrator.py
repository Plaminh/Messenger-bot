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

    async def handle_turn(self, psid: str, text: str) -> None:
        """Process one conversational turn for user."""
        clean_text = text.strip()
        if not clean_text:
            return

        async with self._session_factory() as session:
            # Step 1: User lookup / creation
            user = await get_or_create_user(session, psid)

            # Step 2: Command handling
            if is_command(clean_text):
                cmd_reply = await handle_command(session, user, clean_text)
                if cmd_reply:
                    await self._messenger.send_human_like_response(psid, cmd_reply)
                    # For non-destructive commands, record dialog turn
                    if clean_text.split()[0].lower() != "/quen":
                        await add_message(session, user.id, "user", clean_text)
                        await add_message(session, user.id, "assistant", cmd_reply)
                return

            # Step 3: Pronoun detection in early messages
            core = dict(user.core_profile or {})
            if "pronouns" not in core:
                detected_p = detect_pronouns(clean_text)
                if detected_p:
                    core["pronouns"] = detected_p

            # Step 4: Statistical style analysis & EMA update
            updated_style = update_style_profile(user.style_profile or {}, clean_text)

            # Step 5: Safety check (crisis detection)
            crisis_active = is_crisis(clean_text)

            # Step 6: Memory retrieval
            query_vec = await self._embedder.embed_query(clean_text)
            relevant_memories = await retrieve_relevant_memories(
                session,
                user.id,
                query_vec,
                top_k=6,
            )

            # Step 7: Summary & Recent dialog windowing
            summary_record = await get_summary(session, user.id)
            summary_text = summary_record.content if summary_record else None

            recent_history = await get_recent_messages(session, user.id, limit=30)
            window_messages = build_recent_window(recent_history, token_budget=850)

            # Step 8: Prompt assembly
            recent_user_texts = [m.content for m in window_messages if m.role == "user"]
            user_msg_count = await get_user_message_count(session, user.id)
            is_first_interaction = user_msg_count == 0

            system_prompt = assemble_system_prompt(
                core_profile=core,
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

            # Step 9: Determine model tier via daily token budget
            downgrade = await should_downgrade_to_fast(session)
            tier = "fast" if downgrade else "main"

            # Step 10: Call LLM
            llm_result = await self._llm.generate(
                full_messages,
                model_tier=tier,
                temperature=0.9,
                max_tokens=300,
            )

            # Record token consumption
            if llm_result.usage_tokens > 0:
                await record_llm_usage(session, llm_result.model, llm_result.usage_tokens)

            # Step 11: Persist messages & profile updates
            now = datetime.now(timezone.utc)
            await add_message(session, user.id, "user", clean_text)
            await add_message(session, user.id, "assistant", llm_result.content)
            await update_user_profiles(
                session,
                user.id,
                style_profile=updated_style,
                core_profile=core,
                last_user_msg_at=now,
            )

        # Step 12: Deliver response through Messenger client (mark_seen, typing, bubble delay)
        await self._messenger.send_human_like_response(psid, llm_result.content)

        # Step 13: Schedule background tasks asynchronously
        asyncio.create_task(
            self._run_background_tasks(
                user_id=user.id,
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
