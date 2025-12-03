#!/usr/bin/env python3
"""
Memory Optimization and Profiling Utilities.

Advanced memory management techniques:
- Weak references for caching
- Memory profiling
- Automatic cleanup
- Memory pool tracking
"""

import gc
import logging
import weakref
import sys
import threading
from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import psutil for memory monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logger.warning("psutil not available - memory monitoring limited")


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    timestamp: datetime
    rss_mb: float  # Resident set size
    vms_mb: float  # Virtual memory size
    percent: float  # Memory percentage
    available_mb: float
    
    def __str__(self) -> str:
        return (
            f"Memory: {self.rss_mb:.1f}MB RSS, "
            f"{self.vms_mb:.1f}MB VMS, "
            f"{self.percent:.1f}% used"
        )


class WeakValueCache:
    """
    Cache using weak references.
    
    Objects are automatically removed when no longer referenced elsewhere.
    Prevents memory leaks from caching.
    """
    
    def __init__(self, name: str = "unnamed"):
        self.name = name
        self._cache: weakref.WeakValueDictionary = weakref.WeakValueDictionary()
        self.lock = threading.RLock()
        self.stats = {'hits': 0, 'misses': 0, 'sets': 0}
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            value = self._cache.get(key)
            if value is not None:
                self.stats['hits'] += 1
            else:
                self.stats['misses'] += 1
            return value
    
    def set(self, key: str, value: Any):
        """Set value in cache."""
        with self.lock:
            try:
                self._cache[key] = value
                self.stats['sets'] += 1
            except TypeError:
                # Object doesn't support weak references
                logger.debug(f"Object type {type(value).__name__} doesn't support weak references")
    
    def clear(self):
        """Clear the cache."""
        with self.lock:
            self._cache.clear()
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self.lock:
            total = self.stats['hits'] + self.stats['misses']
            hit_rate = (self.stats['hits'] / total * 100) if total > 0 else 0.0
            
            return {
                'name': self.name,
                'size': len(self._cache),
                'hits': self.stats['hits'],
                'misses': self.stats['misses'],
                'hit_rate': f"{hit_rate:.2f}%",
            }


class MemoryMonitor:
    """
    Memory usage monitor and profiler.
    
    Tracks memory usage and provides insights.
    """
    
    def __init__(self):
        self.enabled = PSUTIL_AVAILABLE
        self.process = psutil.Process() if PSUTIL_AVAILABLE else None
        self.snapshots: List[MemorySnapshot] = []
        self.max_snapshots = 100
    
    def take_snapshot(self) -> Optional[MemorySnapshot]:
        """Take a memory usage snapshot."""
        if not self.enabled:
            return None
        
        try:
            mem_info = self.process.memory_info()
            mem_percent = self.process.memory_percent()
            vm = psutil.virtual_memory()
            
            snapshot = MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=mem_info.rss / 1024 / 1024,
                vms_mb=mem_info.vms / 1024 / 1024,
                percent=mem_percent,
                available_mb=vm.available / 1024 / 1024
            )
            
            # Store snapshot (limit size)
            self.snapshots.append(snapshot)
            if len(self.snapshots) > self.max_snapshots:
                self.snapshots.pop(0)
            
            return snapshot
        except Exception as e:
            logger.error(f"Failed to take memory snapshot: {e}")
            return None
    
    def get_current_usage(self) -> Optional[Dict[str, float]]:
        """Get current memory usage."""
        snapshot = self.take_snapshot()
        return {
            'rss_mb': snapshot.rss_mb,
            'vms_mb': snapshot.vms_mb,
            'percent': snapshot.percent,
            'available_mb': snapshot.available_mb
        } if snapshot else None
    
    def get_trend(self) -> Optional[str]:
        """Get memory usage trend."""
        if len(self.snapshots) < 2:
            return "insufficient data"
        
        recent = self.snapshots[-10:]  # Last 10 snapshots
        if len(recent) < 2:
            return "stable"
        
        start_rss = recent[0].rss_mb
        end_rss = recent[-1].rss_mb
        change = end_rss - start_rss
        
        if change > 50:  # More than 50 MB increase
            return "increasing (potential leak)"
        elif change < -50:  # More than 50 MB decrease
            return "decreasing (cleanup working)"
        else:
            return "stable"
    
    def force_gc(self) -> Dict[str, int]:
        """
        Force garbage collection and return stats.
        
        Returns:
            Dict with collection stats
        """
        before = self.get_current_usage()
        
        # Run garbage collection
        collected = gc.collect()
        
        after = self.get_current_usage()
        
        stats = {
            'collected_objects': collected,
            'unreachable_objects': len(gc.garbage),
        }
        
        if before and after:
            freed_mb = before['rss_mb'] - after['rss_mb']
            stats['freed_mb'] = round(freed_mb, 2)
        
        logger.info(f"Garbage collection: {collected} objects collected, {stats.get('freed_mb', 0):.2f}MB freed")
        
        return stats


# Global instances
_weak_caches: Dict[str, WeakValueCache] = {}
_memory_monitor: Optional[MemoryMonitor] = None
_monitor_lock = threading.Lock()


def get_weak_cache(name: str = 'default') -> WeakValueCache:
    """Get or create a named weak value cache."""
    if name not in _weak_caches:
        _weak_caches[name] = WeakValueCache(name)
    return _weak_caches[name]


def get_memory_monitor() -> MemoryMonitor:
    """Get the global memory monitor."""
    global _memory_monitor
    
    with _monitor_lock:
        if _memory_monitor is None:
            _memory_monitor = MemoryMonitor()
        return _memory_monitor


def log_memory_usage(label: str = "Memory"):
    """Decorator to log memory usage before/after function."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            monitor = get_memory_monitor()
            
            before = monitor.take_snapshot()
            result = func(*args, **kwargs)
            after = monitor.take_snapshot()
            
            if before and after:
                change = after.rss_mb - before.rss_mb
                logger.debug(
                    f"{label} - {func.__name__}: "
                    f"{before.rss_mb:.1f}MB -> {after.rss_mb:.1f}MB "
                    f"({change:+.1f}MB)"
                )
            
            return result
        return wrapper
    return decorator


def optimize_memory():
    """Run memory optimization procedures."""
    monitor = get_memory_monitor()
    
    logger.info("Running memory optimization...")
    
    # Force garbage collection
    gc_stats = monitor.force_gc()
    
    # Clear weak caches
    for cache in _weak_caches.values():
        cache.clear()
    
    # Take snapshot
    snapshot = monitor.take_snapshot()
    
    logger.info(f"Memory optimization complete: {snapshot}")
    logger.info(f"GC stats: {gc_stats}")













