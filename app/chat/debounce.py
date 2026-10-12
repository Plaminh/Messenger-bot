"""Debounce incoming rapid messages per user.

If a user sends multiple messages within a short window (~2.5s), they are combined
into a single turn. Ensures per-user sequential processing using per-user asyncio.Lock.
Assumes single-worker deployment.
"""

import asyncio
import inspect
from collections.abc import Callable, Coroutine
from typing import Any, Optional
from app.core.logging import get_logger
from app.core.tasks import create_background_task

logger = get_logger(__name__)

DEFAULT_DEBOUNCE_DELAY = 2.5


class MessageDebouncer:
    """Manages debouncing timers and per-user sequential execution locks."""

    def __init__(self, delay: float = DEFAULT_DEBOUNCE_DELAY) -> None:
        self.delay = delay
        self._buffers: dict[str, list[tuple[str, Optional[str]]]] = {}
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
        callback: Callable[..., Coroutine[Any, Any, None]],
        mid: Optional[str] = None,
    ) -> None:
        """Enqueue message for debouncing and reset user's timer."""
        if psid not in self._buffers:
            self._buffers[psid] = []
        self._buffers[psid].append((text, mid))

        # Cancel existing timer if active
        if psid in self._timers:
            self._timers[psid].cancel()

        # Start new countdown timer tracked with strong reference
        self._timers[psid] = create_background_task(
            self._debounce_worker(psid, callback),
            name=f"debounce_{psid}",
        )

    async def _debounce_worker(
        self,
        psid: str,
        callback: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Wait for delay window to lapse without interruption, then trigger callback."""
        try:
            await asyncio.sleep(self.delay)
        except asyncio.CancelledError:
            # Timer was reset by a new incoming message
            return

        # Timer expired without new messages
        items = self._buffers.pop(psid, [])
        self._timers.pop(psid, None)

        if not items:
            if psid not in self._buffers and psid not in self._timers:
                self._user_locks.pop(psid, None)
            return

        texts = [item[0] for item in items]
        mids = [item[1] for item in items if item[1]]
        last_mid = mids[-1] if mids else None

        combined_text = "\n".join(texts)
        lock = self._get_lock(psid)

        # Process sequentially for this user
        async with lock:
            try:
                sig = inspect.signature(callback)
                if "mid" in sig.parameters or any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
                    await callback(psid, combined_text, mid=last_mid)
                elif len(sig.parameters) >= 3:
                    await callback(psid, combined_text, last_mid)
                else:
                    await callback(psid, combined_text)
            except Exception as exc:
                logger.error("Error executing callback for psid %s: %s", psid, exc, exc_info=True)
            finally:
                # Cleanup per-user lock if no new messages queued or timers running
                if psid not in self._buffers and psid not in self._timers:
                    self._user_locks.pop(psid, None)


# Default global debouncer instance
debouncer = MessageDebouncer()
