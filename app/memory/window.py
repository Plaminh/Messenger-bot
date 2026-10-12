"""Token budget estimation and conversational window management."""

from typing import Sequence
from app.db.models import Message


# Shared by the orchestrator (prompt window) and the summarizer (what must be summarized)
RECENT_WINDOW_TOKEN_BUDGET = 850
RECENT_WINDOW_MESSAGE_LIMIT = 30
# Summarizer works "ahead" of the real window so no message falls between window and summary
SUMMARY_LEAD_TOKENS = 200
SUMMARY_LEAD_MESSAGES = 6


def estimate_tokens(text: str) -> int:
    """Estimate token count for Vietnamese and multilingual text.

    Uses heuristic: approx 1 token per 3 characters for Vietnamese syllables.
    """
    if not text:
        return 0
    return max(1, len(text.strip()) // 3)


def estimate_messages_tokens(messages: Sequence[dict[str, str]]) -> int:
    """Calculate aggregate tokens across formatted message dictionaries."""
    total = 0
    for msg in messages:
        # 4 overhead tokens for role/formatting + content tokens
        total += 4 + estimate_tokens(msg.get("content", ""))
    return total


def build_recent_window(
    messages: Sequence[Message],
    token_budget: int = 850,
) -> list[Message]:
    """Select the most recent messages fitting within the allocated token budget.

    Guarantees that the window always ends at the latest message.
    Messages are returned in ascending chronological order (oldest to newest).

    Args:
        messages: List of Message models in chronological order.
        token_budget: Maximum tokens allowed for the recent dialog window.

    Returns:
        Sublist of messages fitting within the budget.
    """
    if not messages:
        return []

    accumulated_tokens = 0
    selected_indices: list[int] = []

    # Iterate backwards from the newest message
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        cost = 4 + estimate_tokens(msg.content)
        if accumulated_tokens + cost > token_budget and selected_indices:
            # Exceeded budget; cannot include this older message
            break
        accumulated_tokens += cost
        selected_indices.append(i)

    # Reverse back to chronological order (oldest to newest)
    selected_indices.reverse()
    return [messages[i] for i in selected_indices]
