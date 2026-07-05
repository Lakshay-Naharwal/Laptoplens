"""
scraper/cache.py
Thread-safe, in-memory TTL cache with a Redis-compatible interface.

To switch to actual Redis in production:
    from redis import Redis
    cache = Redis(host='localhost', port=6379, db=0)
    cache.setex(key, ttl, json.dumps(value))
    value = json.loads(cache.get(key))

This implementation mirrors that interface so a swap is trivial.
"""

import time
import threading
import json
from collections import OrderedDict
from typing import Any, Optional

DEFAULT_TTL = 3 * 60 * 60  # 3 hours — keeps IP ban risk low
MAX_CACHE_SIZE = 1000


class TTLCache:
    """
    A thread-safe in-memory cache where every entry has a TTL (time-to-live).
    Expired entries are cleaned up lazily on each access. Uses LRU eviction
    when MAX_CACHE_SIZE is reached.
    """

    def __init__(self, maxsize: int = MAX_CACHE_SIZE) -> None:
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()  # key → (value, expires_at)
        self._lock = threading.Lock()
        self.maxsize = maxsize

    def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
        """Store a value with a TTL in seconds."""
        expires_at = time.monotonic() + ttl
        with self._lock:
            # If key exists, delete it so it's moved to the end when set
            if key in self._store:
                del self._store[key]
            self._store[key] = (value, expires_at)
            
            # Enforce maxsize (LRU eviction)
            while len(self._store) > self.maxsize:
                # popitem(last=False) removes the first (oldest) item
                self._store.popitem(last=False)

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value, or None if missing / expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                # Lazy expiry — remove stale entry
                del self._store[key]
                return None
            
            # Move to end to mark as recently used
            self._store.move_to_end(key)
            return value

    def invalidate(self, key: str) -> None:
        """Forcefully remove a cache entry."""
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Wipe the entire cache (useful for testing)."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        """Number of non-expired entries (approximate)."""
        now = time.monotonic()
        with self._lock:
            return sum(1 for _, exp in self._store.values() if exp > now)


# ─── Singleton instance used across the app ───────────────────────────────────
scrape_cache = TTLCache()
