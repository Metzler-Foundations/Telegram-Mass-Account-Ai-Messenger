#!/usr/bin/env python3
"""
Memory Manager - Prevents memory leaks and OOM errors.

Features:
- Cache size limits with LRU eviction
- Memory usage monitoring
- Automatic cleanup triggers
- Resource tracking
- Leak detection
"""

import psutil
import logging
import threading
import weakref
from typing import Any, Optional, Dict, Callable, List
from collections import OrderedDict
from datetime import datetime
import gc

logger = logging.getLogger(__name__)


class LRUCache:
    """
    LRU (Least Recently Used) cache with size limit.

    Prevents unbounded memory growth.
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize LRU cache.

        Args:
            max_size: Maximum number of items
        """
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.Lock()

        # Statistics
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: Any, default: Any = None) -> Any:
        """
        Get value from cache.

        Args:
            key: Cache key
            default: Default value if not found

        Returns:
            Cached value or default
        """
        with self.lock:
            if key in self.cache:
                # Move to end (most recent)
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]

            self.misses += 1
            return default

    def set(self, key: Any, value: Any):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        with self.lock:
            # Update or add
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                # Check size limit
                if len(self.cache) >= self.max_size:
                    # Evict oldest item
                    evicted_key, _ = self.cache.popitem(last=False)
                    self.evictions += 1
                    logger.debug(f"LRU eviction: {evicted_key}")

            self.cache[key] = value

    def clear(self):
        """Clear all cached items."""
        with self.lock:
            self.cache.clear()
            logger.debug("LRU cache cleared")

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self.lock:
            hit_rate = self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": hit_rate,
            }


class MemoryMonitor:
    """
    Monitors memory usage and triggers cleanup.

    Prevents OOM errors.
    """

    def __init__(
        self,
        warning_threshold_mb: float = 500.0,
        critical_threshold_mb: float = 1000.0,
        check_interval: float = 30.0,
    ):
        """
        Initialize memory monitor.

        Args:
            warning_threshold_mb: Warning threshold in MB
            critical_threshold_mb: Critical threshold in MB
            check_interval: Check interval in seconds
        """
        self.warning_threshold = warning_threshold_mb * 1024 * 1024  # Convert to bytes
        self.critical_threshold = critical_threshold_mb * 1024 * 1024
        self.check_interval = check_interval

        # Cleanup callbacks
        self.cleanup_callbacks: List[Callable] = []

        # State
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None

        # Statistics
        self.stats = {
            "checks_performed": 0,
            "warnings_triggered": 0,
            "critical_triggered": 0,
            "cleanups_performed": 0,
            "peak_memory_mb": 0.0,
        }

    def start(self):
        """Start memory monitoring."""
        if self.is_monitoring:
            logger.warning("Memory monitor already running")
            return

        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

        logger.info(
            f"Memory monitor started (warning: {self.warning_threshold/1024/1024:.0f}MB, "
            f"critical: {self.critical_threshold/1024/1024:.0f}MB)"
        )

    def stop(self):
        """Stop memory monitoring."""
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5.0)
        logger.info("Memory monitor stopped")

    def register_cleanup_callback(self, callback: Callable):
        """
        Register callback to run on high memory usage.

        Args:
            callback: Cleanup function
        """
        self.cleanup_callbacks.append(callback)
        logger.debug(f"Registered cleanup callback: {callback.__name__}")

    def _monitor_loop(self):
        """Background monitoring loop."""
        import time

        while self.is_monitoring:
            try:
                self._check_memory()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Memory monitor error: {e}")

    def _check_memory(self):
        """Check current memory usage."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            rss_mb = memory_info.rss / 1024 / 1024

            self.stats["checks_performed"] += 1
            self.stats["peak_memory_mb"] = max(self.stats["peak_memory_mb"], rss_mb)

            # Check thresholds
            if memory_info.rss > self.critical_threshold:
                self.stats["critical_triggered"] += 1
                logger.critical(
                    f"CRITICAL: Memory usage at {rss_mb:.1f}MB! Triggering emergency cleanup..."
                )
                self._trigger_cleanup(force=True)

            elif memory_info.rss > self.warning_threshold:
                self.stats["warnings_triggered"] += 1
                logger.warning(f"Memory usage at {rss_mb:.1f}MB (warning threshold)")
                self._trigger_cleanup(force=False)

        except Exception as e:
            logger.error(f"Failed to check memory: {e}")

    def _trigger_cleanup(self, force: bool = False):
        """
        Trigger cleanup callbacks.

        Args:
            force: Whether this is a forced cleanup (critical threshold)
        """
        logger.info(f"Triggering cleanup (force={force})...")

        # Run registered callbacks
        for callback in self.cleanup_callbacks:
            try:
                logger.debug(f"Running cleanup: {callback.__name__}")
                callback()
            except Exception as e:
                logger.error(f"Cleanup callback failed: {e}")

        # Force garbage collection
        gc.collect()

        self.stats["cleanups_performed"] += 1

        # Log memory after cleanup
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            rss_mb = memory_info.rss / 1024 / 1024
            logger.info(f"Memory after cleanup: {rss_mb:.1f}MB")
        except Exception:
            pass

    def get_current_usage(self) -> dict:
        """
        Get current memory usage.

        Returns:
            Memory usage statistics
        """
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            return {
                "rss_mb": memory_info.rss / 1024 / 1024,
                "vms_mb": memory_info.vms / 1024 / 1024,
                "percent": process.memory_percent(),
                "stats": self.stats.copy(),
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {e}")
            return {"error": str(e)}


class ResourceTracker:
    """
    Tracks resource allocation for leak detection.

    Uses weak references to avoid preventing garbage collection.
    """

    def __init__(self):
        """Initialize resource tracker."""
        self.resources: Dict[str, set] = {}  # resource_type -> set of weakrefs
        self.lock = threading.Lock()

        # Statistics
        self.stats = {"total_allocated": 0, "total_released": 0, "leaks_detected": 0}

    def track(self, resource_type: str, resource: Any):
        """
        Track a resource.

        Args:
            resource_type: Type of resource
            resource: Resource object
        """
        with self.lock:
            if resource_type not in self.resources:
                self.resources[resource_type] = set()

            # Use weak reference
            try:
                ref = weakref.ref(resource, lambda r: self._on_resource_released(resource_type))
                self.resources[resource_type].add(ref)
                self.stats["total_allocated"] += 1
            except TypeError:
                # Object doesn't support weak references
                logger.debug(f"Cannot weakref {resource_type}")

    def _on_resource_released(self, resource_type: str):
        """Called when resource is garbage collected."""
        self.stats["total_released"] += 1

    def get_active_count(self, resource_type: Optional[str] = None) -> Dict[str, int]:
        """
        Get count of active resources.

        Args:
            resource_type: Specific resource type (None = all)

        Returns:
            Dictionary of resource_type -> count
        """
        with self.lock:
            # Clean up dead weak references
            for rtype in self.resources:
                alive = {ref for ref in self.resources[rtype] if ref() is not None}
                dead_count = len(self.resources[rtype]) - len(alive)
                self.resources[rtype] = alive

                if dead_count > 0:
                    self.stats["total_released"] += dead_count

            if resource_type:
                return {resource_type: len(self.resources.get(resource_type, set()))}

            return {rtype: len(refs) for rtype, refs in self.resources.items()}

    def detect_leaks(self, threshold: int = 100) -> Dict[str, int]:
        """
        Detect potential memory leaks.

        Args:
            threshold: Alert if resource count exceeds this

        Returns:
            Dictionary of resource_type -> count for leaks
        """
        counts = self.get_active_count()
        leaks = {rtype: count for rtype, count in counts.items() if count > threshold}

        if leaks:
            self.stats["leaks_detected"] += len(leaks)
            logger.warning(f"Potential memory leaks detected: {leaks}")

        return leaks


# Global instances
_memory_monitor: Optional[MemoryMonitor] = None
_resource_tracker: Optional[ResourceTracker] = None


def get_memory_monitor() -> MemoryMonitor:
    """Get global memory monitor."""
    global _memory_monitor
    if _memory_monitor is None:
        _memory_monitor = MemoryMonitor()
    return _memory_monitor


def get_resource_tracker() -> ResourceTracker:
    """Get global resource tracker."""
    global _resource_tracker
    if _resource_tracker is None:
        _resource_tracker = ResourceTracker()
    return _resource_tracker


def setup_memory_management(
    warning_mb: float = 500.0, critical_mb: float = 1000.0
) -> MemoryMonitor:
    """
    Setup automatic memory management.

    Args:
        warning_mb: Warning threshold
        critical_mb: Critical threshold

    Returns:
        MemoryMonitor instance
    """
    monitor = MemoryMonitor(warning_mb, critical_mb)
    monitor.start()

    global _memory_monitor
    _memory_monitor = monitor

    return monitor
