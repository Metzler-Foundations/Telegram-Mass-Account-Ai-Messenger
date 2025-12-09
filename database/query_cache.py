#!/usr/bin/env python3
"""Query result caching layer."""

import hashlib
import time
import logging
from typing import Any, Optional, Callable
from utils.memory_manager import LRUCache

logger = logging.getLogger(__name__)


class QueryCache:
    """Caches database query results."""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.cache = LRUCache(max_size)
        self.ttl = ttl  # Time to live in seconds
        self.expiry_times = {}

    def _make_key(self, query: str, params: tuple) -> str:
        """Create cache key from query and params."""
        content = f"{query}:{params}"
        return hashlib.md5(
            content.encode(), usedforsecurity=False
        ).hexdigest()  # Used for caching, not security

    def get(self, query: str, params: tuple = ()) -> Optional[Any]:
        """Get cached query result."""
        key = self._make_key(query, params)

        # Check expiry
        if key in self.expiry_times:
            if time.time() > self.expiry_times[key]:
                self.cache.set(key, None)
                del self.expiry_times[key]
                return None

        return self.cache.get(key)

    def set(self, query: str, params: tuple, result: Any):
        """Cache query result."""
        key = self._make_key(query, params)
        self.cache.set(key, result)
        self.expiry_times[key] = time.time() + self.ttl

    def invalidate(self, query: str = None, params: tuple = None):
        """Invalidate cache entries."""
        if query:
            key = self._make_key(query, params or ())
            self.cache.set(key, None)
            self.expiry_times.pop(key, None)
        else:
            self.cache.clear()
            self.expiry_times.clear()


_query_cache = None


def get_query_cache():
    global _query_cache
    if _query_cache is None:
        _query_cache = QueryCache()
    return _query_cache
