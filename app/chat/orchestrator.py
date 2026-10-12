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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_async_session_maker
from app.core.logging import get_logger
from app.core.tasks import create_background_task
from app.chat.commands import handle_command, is_command
from app.db.store import (
    add_message,
    get_or_create_user,
    get_recent_messages,
    get_summary,
    get_user_message_count,
    is_message_mid_exists,
    update_user_profiles,
)
from app.integrations.embedder import TextEmbedder, get_embedder
from app.integrations.llm.base import LLMProvider, LLMResult
from app.integrations.llm.budget import record_llm_usage, should_downgrade_to_fast
from app.integrations.llm.groq_provider import GroqProvider
from app.integrations.messenger.client import MessengerClient, get_messenger_client
from app.memory.extractor import extract_and_sync_memories, should_trigger_extraction
from app.memory.retriever import retrieve_relevant_memories
from app.memory.summarizer import maybe_run_rolling_summary
from app.memory.window import (
    RECENT_WINDOW_MESSAGE_LIMIT,
    RECENT_WINDOW_TOKEN_BUDGET,
    build_recent_window,
)
from app.persona.prompt import assemble_system_prompt, build_chat_messages
from app.persona.safety import is_crisis
from app.persona.style import detect_pronouns, update_style_profile

logger = get_logger(__name__)

ERROR_REPLY_TEXT = "ui mình gặp trục trặc xíu, bạn nhắn lại giúp mình sau nha 🥺"


@dataclass
class TurnContext:
    """Encapsulates context prepared for a conversational turn."""

    psid: str
    user_id: int
    clean_text: str
    mid: Optional[str] = None
    core_profile: dict[str, Any] = field(default_factory=dict)
    updated_style: dict[str, Any] = field(default_factory=dict)
    full_messages: list[dict[str, str]] = field(default_factory=list)
    tier: str = "main"
    user_msg_count: int = 0


class ChatOrchestrator:
    """Coordinates pipeline execution for user conversational turns."""

    def __init__(
        self,
        session_factory: Optional[async_sessionmaker[AsyncSession]] = None,
        messenger_client: Optional[MessengerClient] = None,
        llm_provider: Optional[LLMProvider] = None,
        embedder: Optional[TextEmbedder] = None,
        inactivity_delay: float = 300.0,
    ) -> None:
        self._session_factory = session_factory or get_async_session_maker()
        self._messenger = messenger_client or get_messenger_client()
        self._llm = llm_provider or GroqProvider()
        self._embedder = embedder or get_embedder()
        self._inactivity_delay = inactivity_delay
        self._inactivity_timers: dict[str, asyncio.Task] = {}
        self._extraction_locks: dict[int, asyncio.Lock] = {}

    async def _extract_memories(self, user_id: int) -> None:
        """Run memory extraction with a fresh session, never concurrently for one user."""
        lock = self._extraction_locks.setdefault(user_id, asyncio.Lock())
        async with lock:
            async with self._session_factory() as session:
                await extract_and_sync_memories(session, user_id, self._llm, self._embedder)

    def _schedule_inactivity_timer(self, psid: str, user_id: int) -> None:
        """Reset and schedule per-user inactivity timer for memory extraction."""
        existing_timer = self._inactivity_timers.pop(psid, None)
        if existing_timer:
            existing_timer.cancel()

        async def _inactivity_worker(uid: int, user_psid: str) -> None:
            try:
                await asyncio.sleep(self._inactivity_delay)
            except asyncio.CancelledError:
                return

            self._inactivity_timers.pop(user_psid, None)
            try:
                await self._extract_memories(uid)
            except Exception as exc:
                logger.error("Error executing inactivity extraction for user_id=%d: %s", uid, exc)

        self._inactivity_timers[psid] = create_background_task(
            _inactivity_worker(user_id, psid),
            name=f"inactivity_extractor_{psid}",
        )

    async def _run_background_tasks(
        self,
        user_id: int,
        user_msg_count: int,
        last_user_msg_at: Optional[datetime],
    ) -> None:
        """Execute rolling summarizer and memory extractor in background."""
        try:
            # 1. Rolling summarizer check
            async with self._session_factory() as session:
                await maybe_run_rolling_summary(session, user_id, self._llm)

            # 2. Long-term memory extraction check (per-user lock + watermark => no duplicates)
            if should_trigger_extraction(user_msg_count, last_user_msg_at):
                await self._extract_memories(user_id)
        except Exception as exc:
            logger.error("Error executing background tasks for user_id=%d: %s", user_id, exc)

    async def prepare_context(
        self,
        psid: str,
        text: str,
        mid: Optional[str] = None,
    ) -> Optional[TurnContext]:
        """Prepare conversational context, checking deduplication and building prompt messages."""
        clean_text = text.strip()
        if not clean_text:
            return None

        # Cancel any pending inactivity timer for this user immediately upon new activity
        pending_timer = self._inactivity_timers.pop(psid, None)
        if pending_timer:
            pending_timer.cancel()

        # ---------------- Phase 1: DB Read Session ----------------
        async with self._session_factory() as read_session:
            # Step 0: Deduplicate via DB if mid provided
            if mid and await is_message_mid_exists(read_session, mid):
                logger.info("Ignoring duplicate message mid via DB: %s", mid)
                return None

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
                            return None
                        await add_message(read_session, user.id, "assistant", cmd_reply)
                await read_session.commit()
                return None

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

            recent_history = await get_recent_messages(
                read_session,
                user_id,
                limit=RECENT_WINDOW_MESSAGE_LIMIT,
            )
            window_messages = build_recent_window(recent_history, token_budget=RECENT_WINDOW_TOKEN_BUDGET)
            user_msg_count = await get_user_message_count(read_session, user_id)

            # Step 9: Determine model tier via daily token budget
            downgrade = await should_downgrade_to_fast(read_session)
            tier = "fast" if downgrade else "main"
            await read_session.commit()

        # ---------------- Phase 2: In-Memory Prep (No DB Session Held) ----------------
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

        return TurnContext(
            psid=psid,
            user_id=user_id,
            clean_text=clean_text,
            mid=mid,
            core_profile=core_profile,
            updated_style=updated_style,
            full_messages=full_messages,
            tier=tier,
            user_msg_count=user_msg_count,
        )

    async def generate_reply(self, ctx: TurnContext) -> LLMResult:
        """Call LLM without holding any database connection/session."""
        return await self._llm.generate(
            ctx.full_messages,
            model_tier=ctx.tier,
            temperature=0.9,
            max_tokens=300,
        )

    async def persist_turn(
        self,
        ctx: TurnContext,
        reply: LLMResult,
        now: Optional[datetime] = None,
    ) -> bool:
        """Persist messages, token usage, and user profiles in a single atomic transaction."""
        write_time = now or datetime.now(timezone.utc)
        async with self._session_factory() as write_session:
            try:
                # Record token consumption
                if reply.usage_tokens > 0:
                    await record_llm_usage(write_session, reply.model, reply.usage_tokens)

                # Persist messages & profile updates in a single atomic transaction
                await add_message(write_session, ctx.user_id, "user", ctx.clean_text, mid=ctx.mid)
                # The friendly "I'm laggy" text is an error notice, not part of the conversation
                if reply.tier != "fallback":
                    await add_message(write_session, ctx.user_id, "assistant", reply.content)
                await update_user_profiles(
                    write_session,
                    ctx.user_id,
                    style_profile=ctx.updated_style,
                    core_profile=ctx.core_profile,
                    last_user_msg_at=write_time,
                )
                await write_session.commit()
                return True
            except IntegrityError:
                await write_session.rollback()
                logger.warning("Duplicate message mid prevented by unique constraint: %s", ctx.mid)
                return False
            except Exception:
                await write_session.rollback()
                raise

    def schedule_background(
        self,
        ctx: TurnContext,
        now: Optional[datetime] = None,
    ) -> None:
        """Schedule asynchronous rolling summarization and inactivity extraction."""
        bg_time = now or datetime.now(timezone.utc)
        create_background_task(
            self._run_background_tasks(
                user_id=ctx.user_id,
                user_msg_count=ctx.user_msg_count + 1,
                last_user_msg_at=bg_time,
            ),
            name=f"bg_tasks_user_{ctx.user_id}",
        )
        self._schedule_inactivity_timer(ctx.psid, ctx.user_id)

    async def handle_turn(self, psid: str, text: str, mid: Optional[str] = None) -> None:
        """Process one conversational turn for user.

        Any failure before the reply is delivered results in a short apology message
        instead of silence.
        """
        delivered = False
        try:
            ctx = await self.prepare_context(psid, text, mid)
            if ctx is None:
                return

            reply = await self.generate_reply(ctx)

            now = datetime.now(timezone.utc)
            persisted = await self.persist_turn(ctx, reply, now)
            if not persisted:
                return

            # Deliver response through Messenger client (mark_seen, typing, bubble delay)
            await self._messenger.send_human_like_response(ctx.psid, reply.content)
            delivered = True

            # Schedule background tasks asynchronously with strong reference tracking
            self.schedule_background(ctx, now)
        except Exception as exc:
            logger.error("Turn failed for psid=%s: %s", psid, exc, exc_info=True)
            if not delivered:
                await self._send_error_reply(psid)

    async def _send_error_reply(self, psid: str) -> None:
        """Best-effort apology when the pipeline failed; never raises."""
        try:
            await self._messenger.send_human_like_response(psid, ERROR_REPLY_TEXT)
        except Exception as exc:
            logger.error("Could not deliver error reply to psid=%s: %s", psid, exc)
