#!/usr/bin/env python3
"""
UI Update Optimization - Debouncing and Throttling.

Prevents excessive UI updates that can cause lag and performance issues.
"""

import time
import logging
from typing import Callable, Any, Dict, Optional, List
from functools import wraps
from collections import defaultdict
import threading
from PyQt6.QtCore import QTimer

logger = logging.getLogger(__name__)


class Debouncer:
    """
    Debounce function calls - only execute after quiet period.

    Useful for search boxes, text inputs, etc.
    """

    def __init__(self, wait_ms: int = 300):
        """
        Initialize debouncer.

        Args:
            wait_ms: Wait time in milliseconds
        """
        self.wait_ms = wait_ms
        self.timer: Optional[QTimer] = None
        self.pending_call: Optional[tuple] = None

    def debounce(self, func: Callable):
        """
        Debounce decorator for functions.

        Usage:
            @debouncer.debounce
            def on_text_changed(self, text):
                # This will only run after user stops typing
                self.search(text)
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Cancel existing timer
            if self.timer is not None:
                self.timer.stop()

            # Schedule new call
            def execute():
                func(*args, **kwargs)

            self.timer = QTimer()
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(execute)
            self.timer.start(self.wait_ms)

        return wrapper


class Throttler:
    """
    Throttle function calls - execute at most once per time period.

    Useful for scroll events, resize events, etc.
    """

    def __init__(self, min_interval_ms: int = 100):
        """
        Initialize throttler.

        Args:
            min_interval_ms: Minimum interval between calls in milliseconds
        """
        self.min_interval = min_interval_ms / 1000.0  # Convert to seconds
        self.last_call_time: Dict[str, float] = {}
        self.lock = threading.Lock()

    def throttle(self, func: Callable):
        """
        Throttle decorator for functions.

        Usage:
            @throttler.throttle
            def on_scroll(self, value):
                # This will run at most once per min_interval
                self.load_more_data()
        """
        func_id = id(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()

            with self.lock:
                last_time = self.last_call_time.get(func_id, 0)

                if current_time - last_time >= self.min_interval:
                    self.last_call_time[func_id] = current_time
                    return func(*args, **kwargs)
                else:
                    # Too soon, skip this call
                    return None

        return wrapper


class BatchUIUpdater:
    """
    Batch UI updates to prevent excessive redraws.

    Collects multiple update requests and executes them together.
    """

    def __init__(self, flush_interval_ms: int = 100):
        """
        Initialize batch updater.

        Args:
            flush_interval_ms: How often to flush updates
        """
        self.flush_interval = flush_interval_ms
        self.pending_updates: Dict[str, Any] = {}
        self.lock = threading.Lock()
        self.timer: Optional[QTimer] = None
        self.update_callback: Optional[Callable] = None

    def set_update_callback(self, callback: Callable):
        """Set the callback to execute on flush."""
        self.update_callback = callback

    def schedule_update(self, key: str, value: Any):
        """
        Schedule a UI update.

        Args:
            key: Update identifier
            value: Update data
        """
        with self.lock:
            self.pending_updates[key] = value

            # Start timer if not running
            if self.timer is None or not self.timer.isActive():
                self.timer = QTimer()
                self.timer.setSingleShot(True)
                self.timer.timeout.connect(self._flush_updates)
                self.timer.start(self.flush_interval)

    def _flush_updates(self):
        """Execute all pending updates."""
        with self.lock:
            if not self.pending_updates:
                return

            updates = dict(self.pending_updates)
            self.pending_updates.clear()

        # Execute callback with all updates
        if self.update_callback:
            try:
                self.update_callback(updates)
            except Exception as e:
                logger.error(f"Batch update callback error: {e}")

    def flush_now(self):
        """Immediately flush all pending updates."""
        if self.timer and self.timer.isActive():
            self.timer.stop()
        self._flush_updates()


class RateLimiter:
    """
    Rate limiter for function calls.

    Limits how many times a function can be called within a time window.
    """

    def __init__(self, max_calls: int = 10, time_window: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum calls allowed in time window
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.call_times: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()

    def rate_limit(self, func: Callable):
        """
        Rate limit decorator.

        Usage:
            @rate_limiter.rate_limit
            def expensive_operation(self):
                # Limited to max_calls per time_window
                pass
        """
        func_id = id(func)

        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()

            with self.lock:
                # Clean old calls outside time window
                cutoff_time = current_time - self.time_window
                self.call_times[func_id] = [t for t in self.call_times[func_id] if t > cutoff_time]

                # Check if we're within rate limit
                if len(self.call_times[func_id]) < self.max_calls:
                    self.call_times[func_id].append(current_time)
                    return func(*args, **kwargs)
                else:
                    # Rate limit exceeded
                    logger.debug(f"Rate limit exceeded for {func.__name__}")
                    return None

        return wrapper


# Global instances
_debouncers: Dict[str, Debouncer] = {}
_throttlers: Dict[str, Throttler] = {}
_batch_updaters: Dict[str, BatchUIUpdater] = {}
_rate_limiters: Dict[str, RateLimiter] = {}


def get_debouncer(name: str = "default", wait_ms: int = 300) -> Debouncer:
    """Get or create a named debouncer."""
    if name not in _debouncers:
        _debouncers[name] = Debouncer(wait_ms=wait_ms)
    return _debouncers[name]


def get_throttler(name: str = "default", min_interval_ms: int = 100) -> Throttler:
    """Get or create a named throttler."""
    if name not in _throttlers:
        _throttlers[name] = Throttler(min_interval_ms=min_interval_ms)
    return _throttlers[name]


def get_batch_updater(name: str = "default", flush_interval_ms: int = 100) -> BatchUIUpdater:
    """Get or create a named batch updater."""
    if name not in _batch_updaters:
        _batch_updaters[name] = BatchUIUpdater(flush_interval_ms=flush_interval_ms)
    return _batch_updaters[name]


def get_rate_limiter(
    name: str = "default", max_calls: int = 10, time_window: float = 1.0
) -> RateLimiter:
    """Get or create a named rate limiter."""
    if name not in _rate_limiters:
        _rate_limiters[name] = RateLimiter(max_calls=max_calls, time_window=time_window)
    return _rate_limiters[name]


# Convenience decorators
def debounce(wait_ms: int = 300):
    """Debounce decorator with custom wait time."""
    return get_debouncer(wait_ms=wait_ms).debounce


def throttle(min_interval_ms: int = 100):
    """Throttle decorator with custom interval."""
    return get_throttler(min_interval_ms=min_interval_ms).throttle


def rate_limit(max_calls: int = 10, time_window: float = 1.0):
    """Rate limit decorator with custom limits."""
    return get_rate_limiter(max_calls=max_calls, time_window=time_window).rate_limit
