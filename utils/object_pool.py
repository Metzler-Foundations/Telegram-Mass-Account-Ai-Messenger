#!/usr/bin/env python3
"""
Object Pooling for Performance Optimization.

Reuses objects instead of creating/destroying them repeatedly.
Reduces memory allocations and garbage collection pressure.
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class PoolStats:
    """Object pool statistics."""

    total_created: int = 0
    total_acquired: int = 0
    total_released: int = 0
    current_size: int = 0
    peak_size: int = 0
    reuse_count: int = 0

    def reuse_rate(self) -> float:
        """Calculate object reuse rate."""
        return (self.reuse_count / self.total_acquired * 100) if self.total_acquired > 0 else 0.0


class ObjectPool(Generic[T]):
    """
    Generic object pool with automatic cleanup.

    Features:
    - Thread-safe object acquisition/release
    - Automatic object creation
    - Object validation before reuse
    - Pool size limits
    - Statistics tracking
    """

    def __init__(
        self,
        factory: Callable[[], T],
        reset: Optional[Callable[[T], None]] = None,
        validator: Optional[Callable[[T], bool]] = None,
        max_size: int = 100,
        min_size: int = 0,
    ):
        """
        Initialize object pool.

        Args:
            factory: Function to create new objects
            reset: Function to reset object state before reuse
            validator: Function to validate object is still usable
            max_size: Maximum pool size
            min_size: Minimum objects to keep in pool
        """
        self.factory = factory
        self.reset = reset
        self.validator = validator or (lambda obj: True)
        self.max_size = max_size
        self.min_size = min_size

        # Pool storage
        self.pool: deque[T] = deque()

        # Thread safety
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)

        # Statistics
        self.stats = PoolStats()

        # Pre-create minimum objects
        self._initialize_pool()

        logger.debug(f"Object pool initialized (min={min_size}, max={max_size})")

    def _initialize_pool(self):
        """Create minimum number of objects."""
        with self.lock:
            for _ in range(self.min_size):
                try:
                    obj = self.factory()
                    self.pool.append(obj)
                    self.stats.total_created += 1
                    self.stats.current_size += 1
                except Exception as e:
                    logger.error(f"Failed to create pool object: {e}")

    def acquire(self, timeout: Optional[float] = None) -> T:
        """
        Acquire an object from the pool.

        Args:
            timeout: Maximum time to wait for object (seconds)

        Returns:
            Object from pool or newly created
        """
        start_time = time.time() if timeout else None

        with self.lock:
            while True:
                # Try to get object from pool
                while self.pool:
                    obj = self.pool.popleft()
                    self.stats.current_size -= 1

                    # Validate object
                    if self.validator(obj):
                        # Reset object state
                        if self.reset:
                            try:
                                self.reset(obj)
                            except Exception as e:
                                logger.warning(f"Failed to reset pool object: {e}")
                                continue  # Try next object

                        self.stats.total_acquired += 1
                        self.stats.reuse_count += 1
                        return obj

                # No objects in pool, create new one
                try:
                    obj = self.factory()
                    self.stats.total_created += 1
                    self.stats.total_acquired += 1
                    return obj
                except Exception as e:
                    logger.error(f"Failed to create new object: {e}")

                    # Wait for object to be released if timeout specified
                    if timeout:
                        elapsed = time.time() - start_time
                        remaining = timeout - elapsed

                        if remaining <= 0:
                            raise TimeoutError("Timeout waiting for pool object") from None

                        self.condition.wait(timeout=remaining)
                    else:
                        raise

    def release(self, obj: T):
        """
        Release object back to pool.

        Args:
            obj: Object to release
        """
        with self.lock:
            self.stats.total_released += 1

            # Only keep if under max size
            if self.stats.current_size < self.max_size:
                self.pool.append(obj)
                self.stats.current_size += 1

                # Update peak size
                if self.stats.current_size > self.stats.peak_size:
                    self.stats.peak_size = self.stats.current_size

            # Notify waiting threads
            self.condition.notify()

    def get_stats(self) -> dict:
        """Get pool statistics."""
        with self.lock:
            return {
                "total_created": self.stats.total_created,
                "total_acquired": self.stats.total_acquired,
                "total_released": self.stats.total_released,
                "current_size": self.stats.current_size,
                "peak_size": self.stats.peak_size,
                "reuse_rate": f"{self.stats.reuse_rate():.2f}%",
            }


class StringBuilderPool:
    """
    Specialized pool for string building operations.

    Reuses lists for efficient string concatenation.
    """

    def __init__(self, max_size: int = 50):
        self.pool = ObjectPool[List[str]](
            factory=list, reset=lambda lst: lst.clear(), max_size=max_size
        )

    def acquire(self) -> List[str]:
        """Get a string builder list."""
        return self.pool.acquire()

    def release(self, builder: List[str]):
        """Return string builder to pool."""
        self.pool.release(builder)

    def build_and_release(self, builder: List[str], separator: str = "") -> str:
        """Join builder and return to pool."""
        result = separator.join(builder)
        self.release(builder)
        return result


# Global pools
_string_builder_pool: Optional[StringBuilderPool] = None
_pool_lock = threading.Lock()


def get_string_builder_pool() -> StringBuilderPool:
    """Get the global string builder pool."""
    global _string_builder_pool

    with _pool_lock:
        if _string_builder_pool is None:
            _string_builder_pool = StringBuilderPool()
        return _string_builder_pool
