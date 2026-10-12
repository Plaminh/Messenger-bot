"""Tests for message deduplication."""

from app.messenger.dedupe import MessageDeduplicator


def test_deduplicator_basic():
    dedup = MessageDeduplicator(capacity=100)
    assert dedup.is_duplicate("mid.123") is False
    assert dedup.is_duplicate("mid.123") is True
    assert dedup.is_duplicate("mid.456") is False


def test_deduplicator_none_or_empty():
    dedup = MessageDeduplicator()
    assert dedup.is_duplicate(None) is False
    assert dedup.is_duplicate("") is False


def test_deduplicator_capacity_eviction():
    dedup = MessageDeduplicator(capacity=2)
    assert dedup.is_duplicate("mid.1") is False
    assert dedup.is_duplicate("mid.2") is False
    # Evicts mid.1
    assert dedup.is_duplicate("mid.3") is False

    # mid.1 should now be treated as new again because it was evicted
    assert dedup.is_duplicate("mid.1") is False
