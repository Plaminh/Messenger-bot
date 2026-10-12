"""Tests for Groq provider retries, backoff, fallback chain, and JSON mode recovery."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from groq import RateLimitError

from app.llm.groq_provider import FRIENDLY_FALLBACK_TEXT, GroqProvider


@pytest.mark.asyncio
async def test_groq_provider_fallback_to_fast_when_main_fails():
    mock_client = MagicMock()

    # Main model fails, fast model succeeds
    def mock_create(*args, **kwargs):
        model = kwargs.get("model")
        if model == "main-model":
            raise Exception("Main model 500 error")
        resp = MagicMock()
        resp.choices = [MagicMock(message=MagicMock(content="Fast model reply"))]
        resp.usage = MagicMock(total_tokens=25)
        return resp

    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

    provider = GroqProvider(
        client=mock_client,
        api_key="key",
        main_model="main-model",
        fast_model="fast-model",
    )

    with patch("asyncio.sleep", AsyncMock()):
        result = await provider.generate(
            [{"role": "user", "content": "hi"}],
            model_tier="main",
        )

    assert result.content == "Fast model reply"
    assert result.model == "fast-model"


@pytest.mark.asyncio
async def test_groq_provider_friendly_fallback_when_all_fail():
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=Exception("Total outage"))

    provider = GroqProvider(
        client=mock_client,
        api_key="key",
        main_model="main-model",
        fast_model="fast-model",
    )

    with patch("asyncio.sleep", AsyncMock()):
        result = await provider.generate(
            [{"role": "user", "content": "hi"}],
            model_tier="main",
        )

    assert result.content == FRIENDLY_FALLBACK_TEXT
    assert result.tier == "fallback"


@pytest.mark.asyncio
async def test_groq_provider_json_recovery_retry():
    mock_client = MagicMock()

    call_count = 0

    def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        resp = MagicMock()
        resp.usage = MagicMock(total_tokens=30)
        if call_count == 1:
            # First response is invalid JSON
            resp.choices = [MagicMock(message=MagicMock(content="Not a JSON string!"))]
        else:
            # Second response recovers with valid JSON
            resp.choices = [MagicMock(message=MagicMock(content='{"status": "recovered"}'))]
        return resp

    mock_client.chat.completions.create = AsyncMock(side_effect=mock_create)

    provider = GroqProvider(
        client=mock_client,
        api_key="key",
        main_model="main-model",
        fast_model="fast-model",
    )

    result = await provider.generate(
        [{"role": "user", "content": "extract json"}],
        model_tier="fast",
        json_mode=True,
    )

    assert call_count == 2
    assert '{"status": "recovered"}' in result.content
