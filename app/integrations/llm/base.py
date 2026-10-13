"""Base protocol and data contracts for LLM providers."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResult:
    """Standardized output from an LLM completion."""
    content: str
    usage_tokens: int
    model: str
    tier: str


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol defining the interface for LLM operations."""

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        model_tier: str = "main",  # "main" | "fast"
        json_mode: bool = False,
        max_tokens: int = 300,
        temperature: float = 0.9,
    ) -> LLMResult:
        """Generate response from language model with retry, fallback and token counting."""
        ...
