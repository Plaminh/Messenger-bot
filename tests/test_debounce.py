"""Tests for rapid message debouncer."""

import asyncio
import pytest
from app.chat.debounce import MessageDebouncer


@pytest.mark.asyncio
async def test_debounce_groups_rapid_messages():
    delivered = []

    async def callback(psid: str, combined: str) -> None:
        delivered.append((psid, combined))

    debouncer = MessageDebouncer(delay=0.1)

    # User sends 3 messages in rapid succession
    await debouncer.add_message("user_1", "Chào bạn", callback)
    await asyncio.sleep(0.03)
    await debouncer.add_message("user_1", "Hôm nay mình mệt quá", callback)
    await asyncio.sleep(0.03)
    await debouncer.add_message("user_1", "Bạn có rảnh không?", callback)

    # Wait for delay to expire
    await asyncio.sleep(0.15)

    assert len(delivered) == 1
    psid, text = delivered[0]
    assert psid == "user_1"
    assert text == "Chào bạn\nHôm nay mình mệt quá\nBạn có rảnh không?"


@pytest.mark.asyncio
async def test_debounce_isolates_different_users():
    delivered = {}

    async def callback(psid: str, combined: str) -> None:
        delivered[psid] = combined

    debouncer = MessageDebouncer(delay=0.1)

    await debouncer.add_message("user_a", "Tin nhắn từ A", callback)
    await debouncer.add_message("user_b", "Tin nhắn từ B", callback)

    await asyncio.sleep(0.15)

    assert len(delivered) == 2
    assert delivered["user_a"] == "Tin nhắn từ A"
    assert delivered["user_b"] == "Tin nhắn từ B"
