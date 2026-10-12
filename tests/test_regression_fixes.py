"""Regression tests for the bugs found in the review (ownership, summary, debounce, ...)."""

import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from groq import RateLimitError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.chat.debounce import MessageDebouncer
from app.chat.orchestrator import ERROR_REPLY_TEXT, ChatOrchestrator
from app.core.settings import Settings
from app.db.models import Memory, Message, Summary, User
from app.db.store import get_all_memories, upsert_summary
from app.integrations.embedder import EmbedderUnavailableError, TextEmbedder
from app.integrations.llm.base import LLMResult
from app.integrations.llm.groq_provider import MAX_RETRY_AFTER_SECONDS, GroqProvider
from app.memory.extractor import extract_and_sync_memories
from app.memory.summarizer import maybe_run_rolling_summary


def _llm(content: str, tier: str = "fast", tokens: int = 10) -> MagicMock:
    mock = MagicMock()
    mock.generate = AsyncMock(
        return_value=LLMResult(content=content, usage_tokens=tokens, model="llama-3.1-8b-instant", tier=tier)
    )
    return mock


async def _make_user(session: AsyncSession, psid: str) -> User:
    user = User(fb_psid=psid, style_profile={}, core_profile={})
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


# ---------------------------------------------------------------- #1 settings
def test_asyncpg_url_is_converted_to_psycopg():
    s = Settings(DATABASE_URL="postgresql+asyncpg://u:p@db:5432/x")
    assert s.async_database_url == "postgresql+psycopg://u:p@db:5432/x"
    assert s.sync_database_url == "postgresql+psycopg://u:p@db:5432/x"


# ---------------------------------------------------------------- #2 memory ownership
@pytest.mark.asyncio
async def test_extractor_cannot_update_or_delete_other_users_memories(db_session, mock_embedder):
    victim = await _make_user(db_session, "victim")
    attacker = await _make_user(db_session, "attacker")

    victim_mem = Memory(user_id=victim.id, content="Victim fact", category="other", importance=5, embedding=[0.05] * 384)
    victim_mem2 = Memory(user_id=victim.id, content="Victim fact 2", category="other", importance=5, embedding=[0.05] * 384)
    db_session.add_all([victim_mem, victim_mem2])
    db_session.add_all(
        [
            Message(user_id=attacker.id, role="user", content="hello"),
            Message(user_id=attacker.id, role="assistant", content="hi"),
        ]
    )
    await db_session.commit()
    await db_session.refresh(victim_mem)
    await db_session.refresh(victim_mem2)

    payload = {
        "operations": [
            {"op": "delete", "id": victim_mem.id},
            {"op": "update", "id": victim_mem2.id, "fact": "HACKED", "category": "other", "importance": 9},
        ]
    }
    await extract_and_sync_memories(db_session, attacker.id, _llm(json.dumps(payload)), embedder=mock_embedder)

    memories = {m.id: m.content for m in await get_all_memories(db_session, victim.id)}
    assert memories == {victim_mem.id: "Victim fact", victim_mem2.id: "Victim fact 2"}


# ---------------------------------------------------------------- #3 summary overwrite
@pytest.mark.asyncio
async def test_summary_not_overwritten_when_llm_falls_back(db_session):
    user = await _make_user(db_session, "sum_fallback")
    db_session.add_all(
        [Message(user_id=user.id, role="user" if i % 2 == 0 else "assistant", content=f"Tin {i}") for i in range(40)]
    )
    await db_session.commit()
    await upsert_summary(db_session, user.id, "Tóm tắt cũ", upto_message_id=0)
    await db_session.commit()

    fallback = _llm("mình hơi đơ xíu, lát nói tiếp nhé 🥺", tier="fallback", tokens=0)
    assert await maybe_run_rolling_summary(db_session, user.id, fallback) is False

    summary = (await db_session.execute(select(Summary).where(Summary.user_id == user.id))).scalar_one()
    assert summary.content == "Tóm tắt cũ"
    assert summary.upto_message_id == 0


# ---------------------------------------------------------------- #7 summary vs window blind spot
@pytest.mark.asyncio
async def test_summarizer_covers_messages_that_fell_out_of_token_window(db_session):
    user = await _make_user(db_session, "sum_window")
    long_text = "x" * 300  # ~100 tokens each => only ~6 fit the token window
    db_session.add_all([Message(user_id=user.id, role="user", content=long_text) for _ in range(20)])
    await db_session.commit()

    assert await maybe_run_rolling_summary(db_session, user.id, _llm("Tóm tắt mới")) is True
    summary = (await db_session.execute(select(Summary).where(Summary.user_id == user.id))).scalar_one()
    assert summary.upto_message_id is not None and summary.upto_message_id >= 10


@pytest.mark.asyncio
async def test_summarizer_waits_while_everything_is_still_in_window(db_session):
    user = await _make_user(db_session, "sum_small")
    db_session.add_all([Message(user_id=user.id, role="user", content=f"Tin {i}") for i in range(10)])
    await db_session.commit()
    llm = _llm("Tóm tắt")
    assert await maybe_run_rolling_summary(db_session, user.id, llm) is False
    llm.generate.assert_not_awaited()


# ---------------------------------------------------------------- C extractor watermark
@pytest.mark.asyncio
async def test_extractor_does_not_reprocess_same_messages(db_session, mock_embedder):
    user = await _make_user(db_session, "extract_twice")
    db_session.add_all(
        [
            Message(user_id=user.id, role="user", content="Mình nuôi một con mèo tên Mun"),
            Message(user_id=user.id, role="assistant", content="Dễ thương quá"),
        ]
    )
    await db_session.commit()

    payload = json.dumps({"operations": [{"op": "add", "id": None, "fact": "User nuôi mèo tên Mun", "category": "person", "importance": 6}]})
    llm = _llm(payload)

    await extract_and_sync_memories(db_session, user.id, llm, embedder=mock_embedder)
    await extract_and_sync_memories(db_session, user.id, llm, embedder=mock_embedder)  # e.g. inactivity timer

    assert llm.generate.await_count == 1
    assert len(await get_all_memories(db_session, user.id)) == 1

    db_session.add_all(
        [
            Message(user_id=user.id, role="user", content="Hôm nay Mun đi tiêm phòng"),
            Message(user_id=user.id, role="assistant", content="Ổn không bạn"),
        ]
    )
    await db_session.commit()
    await extract_and_sync_memories(db_session, user.id, _llm('{"operations": []}'), embedder=mock_embedder)


@pytest.mark.asyncio
async def test_extractor_second_run_only_sees_new_messages(db_session, mock_embedder):
    user = await _make_user(db_session, "extract_new_only")
    db_session.add_all(
        [
            Message(user_id=user.id, role="user", content="CU_TIN_CU"),
            Message(user_id=user.id, role="assistant", content="ok"),
        ]
    )
    await db_session.commit()
    await extract_and_sync_memories(db_session, user.id, _llm('{"operations": []}'), embedder=mock_embedder)

    db_session.add_all(
        [
            Message(user_id=user.id, role="user", content="TIN_MOI"),
            Message(user_id=user.id, role="assistant", content="ok2"),
        ]
    )
    await db_session.commit()
    llm = _llm('{"operations": []}')
    await extract_and_sync_memories(db_session, user.id, llm, embedder=mock_embedder)

    prompt = llm.generate.await_args.args[0][1]["content"]
    assert "TIN_MOI" in prompt and "CU_TIN_CU" not in prompt


@pytest.mark.asyncio
async def test_extractor_keeps_watermark_when_llm_unavailable(db_session, mock_embedder):
    user = await _make_user(db_session, "extract_fallback")
    db_session.add_all(
        [
            Message(user_id=user.id, role="user", content="Mình mới đổi việc"),
            Message(user_id=user.id, role="assistant", content="Wow"),
        ]
    )
    await db_session.commit()

    await extract_and_sync_memories(db_session, user.id, _llm("{}", tier="fallback", tokens=0), embedder=mock_embedder)
    llm = _llm('{"operations": []}')
    await extract_and_sync_memories(db_session, user.id, llm, embedder=mock_embedder)
    llm.generate.assert_awaited_once()  # same messages were retried


# ---------------------------------------------------------------- #4 + B orchestrator
def _orchestrator(db_session, mock_messenger, mock_llm, embedder) -> ChatOrchestrator:
    factory = async_sessionmaker(bind=db_session.bind, class_=AsyncSession, expire_on_commit=False)
    return ChatOrchestrator(
        session_factory=factory,
        messenger_client=mock_messenger,
        llm_provider=mock_llm,
        embedder=embedder,
        inactivity_delay=60.0,
    )


@pytest.mark.asyncio
async def test_fallback_reply_is_not_saved_as_assistant_message(db_session, mock_messenger, mock_embedder):
    fallback_text = "mình hơi đơ xíu, lát nói tiếp nhé 🥺"
    llm = _llm(fallback_text, tier="fallback", tokens=0)
    orch = _orchestrator(db_session, mock_messenger, llm, mock_embedder)

    await orch.handle_turn("psid_fallback", "Chào bạn", mid="mid.fb.1")

    mock_messenger.send_human_like_response.assert_awaited_with("psid_fallback", fallback_text)
    rows = (await db_session.execute(select(Message.role, Message.content))).all()
    assert [r.role for r in rows] == ["user"]


@pytest.mark.asyncio
async def test_pipeline_failure_sends_apology_instead_of_silence(db_session, mock_messenger):
    broken_embedder = MagicMock()
    broken_embedder.embed_query = AsyncMock(side_effect=RuntimeError("model gone"))
    orch = _orchestrator(db_session, mock_messenger, _llm("unused", tier="main"), broken_embedder)

    await orch.handle_turn("psid_broken", "Alo")  # must not raise

    mock_messenger.send_human_like_response.assert_awaited_once_with("psid_broken", ERROR_REPLY_TEXT)


# ---------------------------------------------------------------- A debouncer
@pytest.mark.asyncio
async def test_debouncer_never_runs_two_turns_of_same_user_in_parallel():
    debouncer = MessageDebouncer(delay=0.02)
    running = 0
    peak = 0
    order: list[str] = []

    async def slow(psid: str, text: str) -> None:
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        order.append(text)
        await asyncio.sleep(0.2)
        running -= 1

    await debouncer.add_message("u", "m1", slow)
    await asyncio.sleep(0.05)  # m1 running
    await debouncer.add_message("u", "m2", slow)  # waits for lock
    await asyncio.sleep(0.20)  # m1 finished, m2 running
    await debouncer.add_message("u", "m3", slow)  # used to get a brand-new lock
    await asyncio.sleep(0.75)

    assert order == ["m1", "m2", "m3"]
    assert peak == 1
    assert "u" not in debouncer._user_locks
    assert "u" not in debouncer._pending


# ---------------------------------------------------------------- #5 retry-after cap
@pytest.mark.asyncio
async def test_huge_retry_after_falls_back_without_sleeping_for_hours():
    response = httpx.Response(429, headers={"retry-after": "3600"}, request=httpx.Request("POST", "http://x"))
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=RateLimitError("rate limited", response=response, body=None))
    provider = GroqProvider(client=client, api_key="k", main_model="main", fast_model="fast")

    sleep_mock = AsyncMock()
    with patch("asyncio.sleep", sleep_mock):
        result = await provider.generate([{"role": "user", "content": "hi"}], model_tier="main")

    assert result.tier == "fallback"
    for call in sleep_mock.await_args_list:
        assert call.args[0] <= MAX_RETRY_AFTER_SECONDS


# ---------------------------------------------------------------- #6 embedder
@pytest.mark.asyncio
async def test_embedder_raises_when_model_missing_and_dummy_not_allowed():
    embedder = TextEmbedder(model_name="nonexistent/model", allow_dummy=False)
    with patch.dict(sys.modules, {"sentence_transformers": None}):
        with pytest.raises(EmbedderUnavailableError):
            await embedder.preload()
        with pytest.raises(EmbedderUnavailableError):
            await embedder.embed_query("xin chào")


@pytest.mark.asyncio
async def test_dummy_vectors_differ_per_text_when_explicitly_allowed():
    embedder = TextEmbedder(model_name="nonexistent/model", allow_dummy=True)
    with patch.dict(sys.modules, {"sentence_transformers": None}):
        a = await embedder.embed_query("mèo")
        b = await embedder.embed_query("chó")
        a2 = await embedder.embed_query("mèo")
    assert a == a2
    cosine = sum(x * y for x, y in zip(a, b))
    assert cosine < 0.9
