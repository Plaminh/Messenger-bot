"""Groq LLM provider implementation.

Implements AsyncGroq integration with 2 tiers (main / fast), exponential backoff
with jitter on 429/5xx, fallback chain (main -> fast -> friendly message),
and token budget recording.
"""

import asyncio
import json
import random
from typing import Any, Optional
from groq import AsyncGroq, APIStatusError, RateLimitError, APITimeoutError

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.llm.base import LLMProvider, LLMResult

logger = get_logger(__name__)

FRIENDLY_FALLBACK_TEXT = "mình hơi đơ xíu, lát nói tiếp nhé 🥺"


class GroqProvider(LLMProvider):
    """Production LLM provider utilizing Groq API."""

    def __init__(
        self,
        client: Optional[AsyncGroq] = None,
        api_key: Optional[str] = None,
        main_model: Optional[str] = None,
        fast_model: Optional[str] = None,
    ) -> None:
        if api_key is None or main_model is None or fast_model is None:
            settings = get_settings()
            self.api_key = api_key or settings.GROQ_API_KEY
            self.main_model = main_model or settings.GROQ_MODEL_MAIN
            self.fast_model = fast_model or settings.GROQ_MODEL_FAST
        else:
            self.api_key = api_key
            self.main_model = main_model
            self.fast_model = fast_model
        self._client = client or AsyncGroq(api_key=self.api_key, timeout=25.0)

    def _get_model_for_tier(self, tier: str) -> str:
        """Resolve model name for specified tier."""
        return self.fast_model if tier == "fast" else self.main_model

    async def _call_model_with_retries(
        self,
        model_name: str,
        messages: list[dict[str, str]],
        *,
        json_mode: bool = False,
        max_tokens: int = 300,
        temperature: float = 0.9,
        max_retries: int = 3,
    ) -> LLMResult:
        """Execute chat completion with exponential backoff and jitter on 429/5xx."""
        kwargs: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        last_error: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                response = await self._client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content or ""
                usage_tokens = 0
                if response.usage:
                    usage_tokens = response.usage.total_tokens

                return LLMResult(
                    content=content,
                    usage_tokens=usage_tokens,
                    model=model_name,
                    tier="fast" if model_name == self.fast_model else "main",
                )
            except RateLimitError as exc:
                last_error = exc
                retry_after_header = None
                if hasattr(exc, "response") and exc.response:
                    retry_after_header = exc.response.headers.get("retry-after")

                if retry_after_header:
                    try:
                        wait_seconds = float(retry_after_header)
                    except ValueError:
                        wait_seconds = (2**attempt) + random.uniform(0.1, 0.5)
                else:
                    wait_seconds = (2**attempt) + random.uniform(0.1, 0.5)

                logger.warning(
                    "Rate limit (429) on %s. Attempt %d/%d, retrying in %.2fs",
                    model_name,
                    attempt + 1,
                    max_retries,
                    wait_seconds,
                )
                await asyncio.sleep(wait_seconds)

            except (APIStatusError, APITimeoutError) as exc:
                last_error = exc
                status_code = getattr(exc, "status_code", 500)
                # Retry on 5xx server errors
                if status_code >= 500 or isinstance(exc, APITimeoutError):
                    wait_seconds = (2**attempt) + random.uniform(0.1, 0.5)
                    logger.warning(
                        "Groq error %s on %s. Attempt %d/%d, retrying in %.2fs",
                        status_code,
                        model_name,
                        attempt + 1,
                        max_retries,
                        wait_seconds,
                    )
                    await asyncio.sleep(wait_seconds)
                else:
                    # Don't retry client 4xx errors other than 429
                    raise exc

            except Exception as exc:
                last_error = exc
                logger.error("Unexpected error invoking model %s: %s", model_name, exc)
                raise exc

        raise last_error or RuntimeError(f"Failed calling model {model_name} after {max_retries} retries")

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model_tier: str = "main",
        json_mode: bool = False,
        max_tokens: int = 300,
        temperature: float = 0.9,
    ) -> LLMResult:
        """Generate response with fallback chain (main -> fast -> friendly message)."""
        target_model = self._get_model_for_tier(model_tier)

        try:
            result = await self._call_model_with_retries(
                target_model,
                messages,
                json_mode=json_mode,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            # If json_mode requested, validate JSON format with 1 retry on corrupted JSON
            if json_mode:
                try:
                    json.loads(result.content)
                except Exception:
                    logger.warning("Corrupted JSON from %s, attempting 1 recovery retry", target_model)
                    retry_messages = list(messages) + [
                        {"role": "assistant", "content": result.content},
                        {
                            "role": "user",
                            "content": "Output was invalid JSON. Return ONLY a valid JSON object.",
                        },
                    ]
                    result = await self._call_model_with_retries(
                        target_model,
                        retry_messages,
                        json_mode=True,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )

            return result

        except Exception as exc:
            logger.warning(
                "Model %s failed: %s. Initiating fallback chain.",
                target_model,
                exc,
            )

            # Fallback step 1: If main model failed, try fast model
            if model_tier == "main":
                try:
                    logger.info("Falling back from main to fast model (%s)", self.fast_model)
                    return await self._call_model_with_retries(
                        self.fast_model,
                        messages,
                        json_mode=json_mode,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                except Exception as fast_exc:
                    logger.error("Fast fallback model also failed: %s", fast_exc)

            # Fallback step 2: If everything fails and not json_mode, return warm friendly message
            if not json_mode:
                return LLMResult(
                    content=FRIENDLY_FALLBACK_TEXT,
                    usage_tokens=0,
                    model="fallback",
                    tier="fallback",
                )

            # For json_mode failure, return empty valid json
            return LLMResult(
                content="{}",
                usage_tokens=0,
                model="fallback",
                tier="fallback",
            )
