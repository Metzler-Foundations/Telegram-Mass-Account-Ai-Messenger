#!/usr/bin/env python3
"""
Advanced Query Result Caching System.

Features:
- LRU cache with TTL (time-to-live)
- Thread-safe caching
- Automatic invalidation
- Cache warming
- Statistics tracking
"""

import threading
import time
import hashlib
import pickle
import logging
from typing import Any, Optional, Dict, Callable, Tuple
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int
    ttl: float
    
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return (time.time() - self.created_at) > self.ttl
    
    def touch(self):
        """Update last accessed time."""
        self.last_accessed = time.time()
        self.access_count += 1


class QueryCache:
    """
    LRU cache with TTL for query results.
    
    Advanced features:
    - Thread-safe operations
    - Automatic expiration
    - LRU eviction when full
    - Cache statistics
    - Invalidation patterns
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0):
        """
        Initialize query cache.
        
        Args:
            max_size: Maximum number of cached entries
            default_ttl: Default time-to-live in seconds
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        # Cache storage (OrderedDict for LRU)
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Thread safety
        self.lock = threading.RLock()
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'invalidations': 0,
        }
        
        logger.info(f"Query cache initialized (max_size={max_size}, ttl={default_ttl}s)")
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        # Create deterministic key from args and kwargs
        key_data = {
            'prefix': prefix,
            'args': args,
            'kwargs': sorted(kwargs.items())
        }
        key_str = str(key_data)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            if key not in self.cache:
                self.stats['misses'] += 1
                return None
            
            entry = self.cache[key]
            
            # Check expiration
            if entry.is_expired():
                self.stats['expirations'] += 1
                del self.cache[key]
                return None
            
            # Update access and move to end (LRU)
            entry.touch()
            self.cache.move_to_end(key)
            
            self.stats['hits'] += 1
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Set value in cache."""
        with self.lock:
            # Use default TTL if not specified
            ttl = ttl if ttl is not None else self.default_ttl
            
            # Create entry
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                access_count=0,
                ttl=ttl
            )
            
            # Add to cache
            if key in self.cache:
                # Update existing
                del self.cache[key]
            elif len(self.cache) >= self.max_size:
                # Evict oldest (first item in OrderedDict)
                evicted_key, evicted_entry = self.cache.popitem(last=False)
                self.stats['evictions'] += 1
                logger.debug(f"Evicted cache entry: {evicted_key}")
            
            self.cache[key] = entry
    
    def invalidate(self, pattern: str = None):
        """
        Invalidate cache entries.
        
        Args:
            pattern: If provided, only invalidate keys containing this pattern
                    If None, invalidate all
        """
        with self.lock:
            if pattern is None:
                # Clear all
                count = len(self.cache)
                self.cache.clear()
                self.stats['invalidations'] += count
                logger.info(f"Invalidated entire cache ({count} entries)")
            else:
                # Invalidate matching pattern
                keys_to_remove = [k for k in self.cache.keys() if pattern in k]
                for key in keys_to_remove:
                    del self.cache[key]
                self.stats['invalidations'] += len(keys_to_remove)
                logger.debug(f"Invalidated {len(keys_to_remove)} cache entries matching '{pattern}'")
    
    def cleanup_expired(self):
        """Remove expired entries from cache."""
        with self.lock:
            keys_to_remove = [
                key for key, entry in self.cache.items()
                if entry.is_expired()
            ]
            
            for key in keys_to_remove:
                del self.cache[key]
                self.stats['expirations'] += 1
            
            if keys_to_remove:
                logger.debug(f"Cleaned up {len(keys_to_remove)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0.0
            
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate': f"{hit_rate:.2f}%",
                'evictions': self.stats['evictions'],
                'expirations': self.stats['expirations'],
                'invalidations': self.stats['invalidations'],
            }
    
    def cached_query(self, ttl: Optional[float] = None):
        """
        Decorator for caching query results.
        
        Usage:
            @cache.cached_query(ttl=300)
            def get_expensive_data(self, param1, param2):
                # Expensive query
                return results
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = self._generate_key(func.__name__, *args, **kwargs)
                
                # Try to get from cache
                cached_value = self.get(cache_key)
                if cached_value is not None:
                    return cached_value
                
                # Cache miss - execute function
                result = func(*args, **kwargs)
                
                # Store in cache
                self.set(cache_key, result, ttl=ttl)
                
                return result
            
            return wrapper
        return decorator


# Global cache instances
_caches: Dict[str, QueryCache] = {}
_cache_lock = threading.Lock()


def get_cache(cache_name: str = 'default', **kwargs) -> QueryCache:
    """
    Get or create a named cache instance.
    
    Args:
        cache_name: Name of the cache
        **kwargs: Cache configuration options
    
    Returns:
        QueryCache instance
    """
    with _cache_lock:
        if cache_name not in _caches:
            _caches[cache_name] = QueryCache(**kwargs)
        return _caches[cache_name]


def invalidate_all_caches():
    """Invalidate all caches."""
    with _cache_lock:
        for cache in _caches.values():
            cache.invalidate()
        logger.info("Invalidated all caches")


def get_all_cache_stats() -> Dict[str, Dict]:
    """Get statistics for all caches."""
    with _cache_lock:
        return {name: cache.get_stats() for name, cache in _caches.items()}













