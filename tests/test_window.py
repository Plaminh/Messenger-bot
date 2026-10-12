"""Tests for message token estimation and conversational windowing."""

from app.memory.models import Message
from app.memory.window import build_recent_window, estimate_tokens


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") == 1
    # 21 characters -> ~7 tokens
    assert estimate_tokens("hôm nay trời thật đẹp") == 7


def test_build_recent_window_under_budget():
    m1 = Message(id=1, role="user", content="Chào bạn")
    m2 = Message(id=2, role="assistant", content="Chào bạn nhé!")
    window = build_recent_window([m1, m2], token_budget=100)
    assert len(window) == 2
    assert window[0].id == 1
    assert window[1].id == 2


def test_build_recent_window_cuts_older_messages_while_keeping_latest():
    # Construct 10 messages of ~30 tokens each (cost = 4 + 30 = 34 tokens each)
    messages = [
        Message(id=i, role="user" if i % 2 == 1 else "assistant", content="a" * 90)
        for i in range(1, 11)
    ]

    # Budget of 100 tokens should fit at most 2-3 messages
    window = build_recent_window(messages, token_budget=100)

    # Must preserve the newest message (id 10)
    assert len(window) < len(messages)
    assert window[-1].id == 10
    # Must be in chronological order
    for idx in range(len(window) - 1):
        assert window[idx].id < window[idx + 1].id
