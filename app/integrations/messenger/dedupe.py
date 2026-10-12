"""Message deduplication module.

Maintains an in-memory cache of recent message IDs (mid) to deduplicate Meta webhook retries.
"""

from collections import OrderedDict
from threading import Lock


class MessageDeduplicator:
    """Thread-safe LRU set for message ID deduplication."""

    def __init__(self, capacity: int = 10_000) -> None:
        self.capacity = capacity
        self._cache: OrderedDict[str, None] = OrderedDict()
        self._lock = Lock()

    def is_duplicate(self, mid: str | None) -> bool:
        """Check if message id has already been seen; records it if not seen.

        Args:
            mid: Message ID from Facebook Messenger.

        Returns:
            True if mid was already present, False if it is new.
        """
        if not mid:
            return False

        with self._lock:
            if mid in self._cache:
                return True

            self._cache[mid] = None
            if len(self._cache) > self.capacity:
                self._cache.popitem(last=False)
            return False

    def clear(self) -> None:
        """Clear cache (primarily for tests)."""
        with self._lock:
            self._cache.clear()


# Default singleton instance
deduplicator = MessageDeduplicator()
