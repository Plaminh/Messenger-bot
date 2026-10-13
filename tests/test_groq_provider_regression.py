"""Groq response parsing, GPT-OSS budgets, and billed-attempt accounting."""

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.db.models import LLMUsage
from app.integrations.llm.budget import record_llm_result_usage
from app.integrations.llm.groq_provider import FRIENDLY_FALLBACK_TEXT, GroqProvider


def _response(content, *, finish="stop", total=20, completion=8, reasoning=3, choices=True):
    usage = SimpleNamespace(
        total_tokens=total,
        completion_tokens=completion,
        completion_tokens_details=SimpleNamespace(reasoning_tokens=reasoning),
    )
    choice_list = [] if choices is False else [
        SimpleNamespace(
            finish_reason=finish,
            message=SimpleNamespace(content=content, reasoning="never expose this"),
        )
    ]
    return SimpleNamespace(choices=choice_list, usage=usage)


def _provider(*responses, fast_model="openai/gpt-oss-20b"):
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=list(responses))
    provider = GroqProvider(
        client=client,
        api_key="test",
        main_model="openai/gpt-oss-120b",
        fast_model=fast_model,
        max_completion_tokens=2048,
        length_retry_max_completion_tokens=4096,
    )
    return provider, client.chat.completions.create


@pytest.mark.asyncio
async def test_gpt_oss_normal_content_uses_reasoning_and_completion_budget(caplog):
    caplog.set_level(logging.INFO, logger="app.integrations.llm.groq_provider")
    provider, create = _provider(_response("câu trả lời ngắn"))

    result = await provider.generate([{"role": "user", "content": "xin lời khuyên"}])

    assert result.content == "câu trả lời ngắn"
    assert result.usage_tokens == 20
    kwargs = create.await_args.kwargs
    assert kwargs["reasoning_effort"] == "low"
    assert kwargs["max_completion_tokens"] == 2048
    assert "max_tokens" not in kwargs
    assert "never expose this" not in result.content
    assert "never expose this" not in caplog.text
    assert "xin lời khuyên" not in caplog.text
    assert "choices_count=1" in caplog.text
    assert "finish_reason=stop" in caplog.text


@pytest.mark.asyncio
async def test_empty_length_retries_once_and_accounts_for_both_attempts(db_session):
    provider, create = _provider(
        _response("", finish="length", total=2100, completion=2048, reasoning=2048),
        _response("trả lời sau retry", total=120, completion=40, reasoning=20),
    )

    result = await provider.generate([{"role": "user", "content": "giúp mình"}])

    assert result.content == "trả lời sau retry"
    assert result.usage_tokens == 2220
    assert [attempt.tokens for attempt in result.billed_attempts] == [2100, 120]
    assert create.await_count == 2
    assert create.await_args_list[0].kwargs["max_completion_tokens"] == 2048
    assert create.await_args_list[1].kwargs["max_completion_tokens"] == 4096

    await record_llm_result_usage(db_session, result)
    await db_session.commit()
    rows = list((await db_session.execute(select(LLMUsage))).scalars())
    assert [(row.model, row.tokens, row.requests) for row in rows] == [
        ("openai/gpt-oss-120b", 2220, 2)
    ]


@pytest.mark.asyncio
async def test_malformed_fast_response_returns_static_fallback_and_keeps_usage(caplog):
    caplog.set_level(logging.INFO, logger="app.integrations.llm.groq_provider")
    provider, _ = _provider(_response(None, total=17, choices=False))

    result = await provider.generate(
        [{"role": "user", "content": "hello"}],
        model_tier="fast",
    )

    assert result.content == FRIENDLY_FALLBACK_TEXT
    assert result.tier == "fallback"
    assert result.usage_tokens == 17
    assert len(result.billed_attempts) == 1
    assert "exception_class=IndexError" in caplog.text
    assert "choices_count=0" in caplog.text


@pytest.mark.asyncio
async def test_malformed_main_response_falls_back_and_accounts_both_models():
    provider, create = _provider(
        _response(None, total=11, choices=False),
        _response("fallback hợp lệ", total=13),
    )

    result = await provider.generate([{"role": "user", "content": "hello"}])

    assert result.content == "fallback hợp lệ"
    assert result.model == "openai/gpt-oss-20b"
    assert result.usage_tokens == 24
    assert [(item.model, item.tokens) for item in result.billed_attempts] == [
        ("openai/gpt-oss-120b", 11),
        ("openai/gpt-oss-20b", 13),
    ]
    assert create.await_count == 2


@pytest.mark.asyncio
async def test_invalid_json_after_recovery_is_rejected_with_usage_preserved():
    provider, create = _provider(
        _response("not-json", total=10),
        _response("still-not-json", total=12),
    )

    result = await provider.generate(
        [{"role": "user", "content": "extract"}],
        model_tier="fast",
        json_mode=True,
    )

    assert result.content == "{}"
    assert result.tier == "fallback"
    assert result.usage_tokens == 22
    assert [item.tokens for item in result.billed_attempts] == [10, 12]
    assert create.await_count == 2


@pytest.mark.asyncio
async def test_invalid_json_from_model_fallback_is_rejected_with_all_usage():
    provider, create = _provider(
        _response("bad-main-json", total=7),
        _response("bad-main-recovery", total=9),
        _response("bad-fallback-json", total=11),
    )

    result = await provider.generate(
        [{"role": "user", "content": "extract"}],
        json_mode=True,
    )

    assert result.content == "{}"
    assert result.tier == "fallback"
    assert result.usage_tokens == 27
    assert [(item.model, item.tokens) for item in result.billed_attempts] == [
        ("openai/gpt-oss-120b", 7),
        ("openai/gpt-oss-120b", 9),
        ("openai/gpt-oss-20b", 11),
    ]
    assert create.await_count == 3


def test_length_retry_budget_must_exceed_initial_budget():
    with pytest.raises(ValueError, match="must exceed"):
        GroqProvider(
            client=MagicMock(),
            api_key="test",
            main_model="openai/gpt-oss-120b",
            fast_model="openai/gpt-oss-20b",
            max_completion_tokens=2048,
            length_retry_max_completion_tokens=2048,
        )
