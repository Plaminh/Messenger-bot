"""Groq chat completions with safe diagnostics, retries, and usage accounting."""

import asyncio
import json
import math
import random
from typing import Any, Optional
from groq import APIStatusError, APITimeoutError, AsyncGroq, RateLimitError

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.integrations.llm.base import LLMBilledAttempt, LLMProvider, LLMResult

logger = get_logger(__name__)
FRIENDLY_FALLBACK_TEXT = "mình hơi đơ xíu, lát nói tiếp nhé 🥺"
MAX_RETRY_AFTER_SECONDS = 8.0
GPT_OSS_MODELS = {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}


class ProviderCallError(Exception):
    def __init__(self, category: str, billed_attempts: list[LLMBilledAttempt]) -> None:
        super().__init__(category)
        self.category = category
        self.billed_attempts = list(billed_attempts)


def _error_category(exc: Exception) -> str:
    if isinstance(exc, ProviderCallError):
        return exc.category
    if isinstance(exc, RateLimitError):
        return "rate_limit"
    if isinstance(exc, APITimeoutError):
        return "timeout"
    if isinstance(exc, APIStatusError):
        status = getattr(exc, "status_code", None)
        return f"http_{status // 100}xx" if isinstance(status, int) else "api_status"
    if isinstance(exc, (IndexError, AttributeError, TypeError, ValueError)):
        return "invalid_response"
    return "unexpected"


def _safe_int(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def _usage_metadata(response: Any) -> tuple[int, int, int]:
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    reasoning = details.get("reasoning_tokens", 0) if isinstance(details, dict) else getattr(details, "reasoning_tokens", 0)
    return (
        _safe_int(getattr(usage, "total_tokens", 0)),
        _safe_int(getattr(usage, "completion_tokens", 0)),
        _safe_int(reasoning),
    )


class GroqProvider(LLMProvider):
    def __init__(
        self,
        client: Optional[AsyncGroq] = None,
        api_key: Optional[str] = None,
        main_model: Optional[str] = None,
        fast_model: Optional[str] = None,
        max_completion_tokens: Optional[int] = None,
        length_retry_max_completion_tokens: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.GROQ_API_KEY
        self.main_model = main_model or settings.GROQ_MODEL_MAIN
        self.fast_model = fast_model or settings.GROQ_MODEL_FAST
        self.max_completion_tokens = max_completion_tokens or settings.GROQ_MAX_COMPLETION_TOKENS
        self.length_retry_max_completion_tokens = length_retry_max_completion_tokens or settings.GROQ_LENGTH_RETRY_MAX_COMPLETION_TOKENS
        if self.length_retry_max_completion_tokens <= self.max_completion_tokens:
            raise ValueError("length retry completion budget must exceed the initial budget")
        self._client = client or AsyncGroq(api_key=self.api_key, timeout=25.0)

    def _get_model_for_tier(self, tier: str) -> str:
        return self.fast_model if tier == "fast" else self.main_model

    async def _call_model_with_retries(
        self, model_name: str, messages: list[dict[str, str]], *,
        json_mode: bool = False, max_tokens: int = 300,
        temperature: float = 0.9, max_retries: int = 3,
    ) -> LLMResult:
        kwargs: dict[str, Any] = {"model": model_name, "messages": messages, "temperature": temperature}
        is_gpt_oss = model_name in GPT_OSS_MODELS
        if is_gpt_oss:
            kwargs.update(reasoning_effort="low", max_completion_tokens=self.max_completion_tokens)
        else:
            kwargs["max_tokens"] = max_tokens
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        billed: list[LLMBilledAttempt] = []
        last_error: Optional[Exception] = None
        length_retry_used = False
        transport_attempt = 0
        logger.info("LLM call model=%s", model_name)

        while transport_attempt < max_retries:
            try:
                response = await self._client.chat.completions.create(**kwargs)
                total, completion, reasoning = _usage_metadata(response)
                billed.append(LLMBilledAttempt(model_name, total))
                choices = getattr(response, "choices", None)
                count = len(choices) if isinstance(choices, (list, tuple)) else 0
                finish_reason = None
                content = ""
                parse_error: Optional[Exception] = None
                try:
                    choice = choices[0]
                    finish_reason = getattr(choice, "finish_reason", None)
                    raw = getattr(getattr(choice, "message", None), "content", None)
                    if raw is not None and not isinstance(raw, str):
                        raise TypeError("completion content is not text")
                    content = raw or ""
                except (IndexError, TypeError, AttributeError) as exc:
                    parse_error = exc

                logger.info(
                    "LLM response metadata model=%s exception_class=%s choices_count=%d finish_reason=%s "
                    "content_length=%d completion_tokens=%d reasoning_tokens=%d",
                    model_name, type(parse_error).__name__ if parse_error else "None", count,
                    finish_reason, len(content), completion, reasoning,
                )
                if parse_error:
                    raise ProviderCallError("invalid_response", billed) from parse_error
                if not content.strip():
                    if finish_reason == "length" and is_gpt_oss and not length_retry_used:
                        length_retry_used = True
                        retry_budget = min(self.length_retry_max_completion_tokens, max(self.max_completion_tokens + 1, self.max_completion_tokens * 2))
                        kwargs["max_completion_tokens"] = retry_budget
                        logger.warning("LLM empty length completion retry model=%s retry_budget=%d", model_name, retry_budget)
                        continue
                    raise ProviderCallError("invalid_response", billed)
                return LLMResult(content, sum(x.tokens for x in billed), model_name,
                                 "fast" if model_name == self.fast_model else "main", billed)

            except RateLimitError as exc:
                last_error = exc
                headers = getattr(getattr(exc, "response", None), "headers", {})
                retry_after = headers.get("retry-after") if headers else None
                backoff = (2**transport_attempt) + random.uniform(0.1, 0.5)
                try:
                    wait = float(retry_after) if retry_after else backoff
                except ValueError:
                    wait = backoff
                if not math.isfinite(wait) or wait < 0:
                    wait = backoff
                transport_attempt += 1
                if wait > MAX_RETRY_AFTER_SECONDS or transport_attempt >= max_retries:
                    break
                logger.warning("LLM retry model=%s error_category=rate_limit attempt=%d wait_seconds=%.2f", model_name, transport_attempt, wait)
                await asyncio.sleep(wait)
            except (APIStatusError, APITimeoutError) as exc:
                last_error = exc
                status = getattr(exc, "status_code", 500)
                transport_attempt += 1
                if not (status >= 500 or isinstance(exc, APITimeoutError)) or transport_attempt >= max_retries:
                    break
                wait = (2 ** (transport_attempt - 1)) + random.uniform(0.1, 0.5)
                logger.warning("LLM retry model=%s error_category=%s attempt=%d wait_seconds=%.2f", model_name, _error_category(exc), transport_attempt, wait)
                await asyncio.sleep(wait)
            except ProviderCallError:
                raise
            except Exception as exc:
                logger.error("LLM request failed model=%s exception_class=%s error_category=%s", model_name, type(exc).__name__, _error_category(exc))
                raise ProviderCallError(_error_category(exc), billed) from exc

        category = _error_category(last_error) if last_error else "unexpected"
        raise ProviderCallError(category, billed) from last_error

    async def generate(
        self, messages: list[dict[str, str]], *, model_tier: str = "main",
        json_mode: bool = False, max_tokens: int = 300, temperature: float = 0.9,
    ) -> LLMResult:
        target = self._get_model_for_tier(model_tier)
        billed: list[LLMBilledAttempt] = []
        logger.info("LLM selected_model=%s fallback_used=false", target)
        try:
            result = await self._call_model_with_retries(target, messages, json_mode=json_mode, max_tokens=max_tokens, temperature=temperature)
            billed.extend(result.billed_attempts)
            if json_mode:
                try:
                    json.loads(result.content)
                except Exception:
                    logger.warning("LLM JSON recovery model=%s", target)
                    retry_messages = list(messages) + [
                        {"role": "assistant", "content": result.content},
                        {"role": "user", "content": "Output was invalid JSON. Return ONLY a valid JSON object."},
                    ]
                    result = await self._call_model_with_retries(target, retry_messages, json_mode=True, max_tokens=max_tokens, temperature=temperature)
                    billed.extend(result.billed_attempts)
                    try:
                        json.loads(result.content)
                    except Exception as recovery_exc:
                        logger.warning("LLM JSON recovery invalid model=%s", target)
                        raise ProviderCallError("invalid_json", []) from recovery_exc
            result.billed_attempts = billed
            result.usage_tokens = sum(x.tokens for x in billed)
            return result
        except Exception as exc:
            billed.extend(getattr(exc, "billed_attempts", []))
            logger.warning("LLM primary failed model=%s exception_class=%s error_category=%s fallback_used=%s", target, type(exc).__name__, _error_category(exc), model_tier == "main")
            if model_tier == "main":
                try:
                    logger.info("LLM fallback selected_model=%s fallback_used=true", self.fast_model)
                    result = await self._call_model_with_retries(self.fast_model, messages, json_mode=json_mode, max_tokens=max_tokens, temperature=temperature)
                    billed.extend(result.billed_attempts)
                    if json_mode:
                        try:
                            json.loads(result.content)
                        except Exception as fallback_json_exc:
                            logger.warning("LLM fallback JSON invalid model=%s", self.fast_model)
                            raise ProviderCallError("invalid_json", []) from fallback_json_exc
                    result.billed_attempts = billed
                    result.usage_tokens = sum(x.tokens for x in billed)
                    return result
                except Exception as fast_exc:
                    billed.extend(getattr(fast_exc, "billed_attempts", []))
                    logger.error("LLM fallback failed model=%s exception_class=%s error_category=%s fallback_used=true", self.fast_model, type(fast_exc).__name__, _error_category(fast_exc))
            logger.warning("LLM static fallback used fallback_used=true error_category=provider_unavailable")
            return LLMResult(FRIENDLY_FALLBACK_TEXT if not json_mode else "{}", sum(x.tokens for x in billed), "fallback", "fallback", billed)
