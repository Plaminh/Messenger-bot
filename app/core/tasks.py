"""Asyncio background task tracking and error management."""

import asyncio
from collections.abc import Coroutine
from typing import Any, Optional
from app.core.logging import get_logger

logger = get_logger(__name__)

# Strong references to running background tasks to prevent premature GC
_active_tasks: set[asyncio.Task] = set()


def create_background_task(
    coro: Coroutine[Any, Any, Any],
    name: Optional[str] = None,
) -> asyncio.Task:
    """Create and track an asyncio task with strong reference and error logging.

    Ensures tasks are not garbage collected mid-execution by the event loop,
    and logs any unhandled exceptions when tasks complete.
    """
    task = asyncio.create_task(coro, name=name)
    _active_tasks.add(task)

    def _on_done(t: asyncio.Task) -> None:
        _active_tasks.discard(t)
        if not t.cancelled():
            exc = t.exception()
            if exc:
                task_name = t.get_name() or "unnamed"
                logger.error(
                    "Background task '%s' failed with exception: %s",
                    task_name,
                    exc,
                    exc_info=exc,
                )

    task.add_done_callback(_on_done)
    return task


def get_active_tasks() -> set[asyncio.Task]:
    """Return currently tracked active background tasks."""
    return _active_tasks
