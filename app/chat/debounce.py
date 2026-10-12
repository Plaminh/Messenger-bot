"""Debounce incoming rapid messages per user.

If a user sends multiple messages within a short window (~2.5s), they are combined
into a single turn. Ensures per-user sequential processing using per-user asyncio.Lock.
Assumes single-worker deployment.
"""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DEBOUNCE_DELAY = 2.5


class MessageDebouncer:
    """Manages debouncing timers and per-user sequential execution locks."""

    def __init__(self, delay: float = DEFAULT_DEBOUNCE_DELAY) -> None:
        self.delay = delay
        self._buffers: dict[str, list[str]] = {}
        self._timers: dict[str, asyncio.Task] = {}
        self._user_locks: dict[str, asyncio.Lock] = {}

    def _get_lock(self, psid: str) -> asyncio.Lock:
        """Get or create per-user asyncio.Lock."""
        if psid not in self._user_locks:
            self._user_locks[psid] = asyncio.Lock()
        return self._user_locks[psid]

    async def add_message(
        self,
        psid: str,
        text: str,
        callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        """Enqueue message for debouncing and reset user's timer."""
        if psid not in self._buffers:
            self._buffers[psid] = []
        self._buffers[psid].append(text)

        # Cancel existing timer if active
        if psid in self._timers:
            self._timers[psid].cancel()

        # Start new countdown timer
        self._timers[psid] = asyncio.create_task(
            self._debounce_worker(psid, callback)
        )

    async def _debounce_worker(
        self,
        psid: str,
        callback: Callable[[str, str], Coroutine[Any, Any, None]],
    ) -> None:
        """Wait for delay window to lapse without interruption, then trigger callback."""
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            # Timer was reset by a new incoming message
            return

        # Timer expired without new messages
        texts = self._buffers.pop(psid, [])
        self._timers.pop(psid, None)

        if not texts:
            return

        combined_text = "\n".join(texts)
        lock = self._get_lock(psid)

        # Process sequentially for this user
        async with lock:
            try:
                await callback(psid, combined_text)
            except Exception as exc:
                logger.error("Error executing callback for psid %s: %s", psid, exc, exc_info=True)


# Default global debouncer instance
debouncer = MessageDebouncer()
