"""Tests for debouncer lock and buffer cleanup."""

import asyncio
import pytest

from app.chat.debounce import MessageDebouncer


@pytest.mark.asyncio
async def test_debounce_cleans_up_locks_and_buffers_after_processing():
    debouncer = MessageDebouncer(delay=0.03)
    user_psid = "cleanup_user_1"
    delivered = []

    async def callback(psid: str, text: str) -> None:
        delivered.append((psid, text))

    await debouncer.add_message(user_psid, "Xin chào", callback)
    # While debouncing, buffer and lock exist
    assert user_psid in debouncer._buffers
    assert user_psid in debouncer._timers

    # Wait for execution to finish completely
    await asyncio.sleep(0.08)

    assert len(delivered) == 1
    # After turn is finished, buffers and locks must be cleaned up
    assert user_psid not in debouncer._buffers
    assert user_psid not in debouncer._timers
    assert user_psid not in debouncer._user_locks


@pytest.mark.asyncio
async def test_debounce_preserves_lock_if_new_message_arrives_during_callback():
    debouncer = MessageDebouncer(delay=0.02)
    user_psid = "cleanup_user_2"
    delivered = []

    async def slow_callback(psid: str, text: str) -> None:
        delivered.append(text)
        await asyncio.sleep(0.05)

    await debouncer.add_message(user_psid, "Tin 1", slow_callback)
    await asyncio.sleep(0.03)  # Slow callback starts executing

    # Incoming message while callback is still running
    await debouncer.add_message(user_psid, "Tin 2", slow_callback)

    # Wait until all callbacks finish
    await asyncio.sleep(0.12)

    assert len(delivered) == 2
    assert delivered == ["Tin 1", "Tin 2"]
    # Ultimately cleaned up after both finish
    assert user_psid not in debouncer._user_locks
