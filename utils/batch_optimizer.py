#!/usr/bin/env python3
"""
Batch Operations Optimizer.

Automatically batches database operations for better performance.
Reduces database I/O by buffering and batching writes.
"""

import threading
import time
import logging
from typing import List, Dict, Any, Callable, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class BatchOperation:
    """Represents a batched database operation."""

    query: str
    params: tuple
    timestamp: float
    callback: Optional[Callable] = None


class BatchOptimizer:
    """
    Automatic batch optimizer for database operations.

    Buffers operations and executes them in batches for better performance.
    """

    def __init__(
        self, max_batch_size: int = 100, max_wait_time: float = 1.0, auto_flush: bool = True
    ):
        """
        Initialize batch optimizer.

        Args:
            max_batch_size: Maximum operations per batch
            max_wait_time: Maximum time to wait before flushing (seconds)
            auto_flush: Automatically flush on timer
        """
        self.max_batch_size = max_batch_size
        self.max_wait_time = max_wait_time
        self.auto_flush = auto_flush

        # Operation buffers (grouped by query)
        self.buffers: Dict[str, List[BatchOperation]] = defaultdict(list)

        # Thread safety
        self.lock = threading.RLock()

        # Flush timer
        self.flush_timer: Optional[threading.Timer] = None
        self.last_flush = time.time()

        # Statistics
        self.stats = {
            "total_operations": 0,
            "batches_executed": 0,
            "operations_saved": 0,  # Individual ops saved by batching
        }

        # Start auto-flush timer if enabled
        if self.auto_flush:
            self._start_flush_timer()

        logger.info(
            f"Batch optimizer initialized (batch_size={max_batch_size}, wait_time={max_wait_time}s)"
        )

    def add_operation(self, query: str, params: tuple, callback: Optional[Callable] = None):
        """
        Add operation to batch buffer.

        Args:
            query: SQL query string
            params: Query parameters
            callback: Optional callback after execution
        """
        with self.lock:
            operation = BatchOperation(
                query=query, params=params, timestamp=time.time(), callback=callback
            )

            self.buffers[query].append(operation)
            self.stats["total_operations"] += 1

            # Check if we should flush this query's batch
            if len(self.buffers[query]) >= self.max_batch_size:
                self._flush_query(query)

    def _flush_query(self, query: str):
        """Flush operations for a specific query."""
        if query not in self.buffers or not self.buffers[query]:
            return

        operations = self.buffers[query]
        self.buffers[query] = []

        if not operations:
            return

        # Execute batch
        try:
            # Get connection (would need to be injected or use pool)
            from database_pool import get_pool

            # Try to determine database from query context
            # This is a simple heuristic - could be improved
            db_path = "members.db"  # Default
            if "proxies" in query or "proxy_" in query:
                db_path = "proxy_pool.db"
            elif "campaign" in query:
                db_path = "campaigns.db"
            elif "account" in query:
                db_path = "accounts.db"

            pool = get_pool(db_path)

            # Batch execute
            params_list = [op.params for op in operations]
            pool.executemany(query, params_list)

            # Execute callbacks
            for op in operations:
                if op.callback:
                    try:
                        op.callback()
                    except Exception as e:
                        logger.error(f"Batch callback error: {e}")

            # Update stats
            self.stats["batches_executed"] += 1
            self.stats["operations_saved"] += max(0, len(operations) - 1)

            logger.debug(f"Executed batch of {len(operations)} operations")

        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            # Re-add operations to buffer for retry
            self.buffers[query].extend(operations)

    def flush_all(self):
        """Flush all pending operations."""
        with self.lock:
            queries_to_flush = list(self.buffers.keys())
            for query in queries_to_flush:
                self._flush_query(query)

            self.last_flush = time.time()

    def _start_flush_timer(self):
        """Start automatic flush timer."""

        def flush_and_reschedule():
            self.flush_all()
            with self.lock:
                if self.auto_flush:
                    self._start_flush_timer()

        with self.lock:
            if self.flush_timer:
                self.flush_timer.cancel()

            self.flush_timer = threading.Timer(self.max_wait_time, flush_and_reschedule)
            self.flush_timer.daemon = True
            self.flush_timer.start()

    def stop(self):
        """Stop the batch optimizer and flush pending operations."""
        with self.lock:
            self.auto_flush = False
            if self.flush_timer:
                self.flush_timer.cancel()
                self.flush_timer = None

            # Flush all pending
            self.flush_all()

        logger.info("Batch optimizer stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get optimizer statistics."""
        with self.lock:
            total_ops = self.stats["total_operations"]
            batches = self.stats["batches_executed"]
            saved = self.stats["operations_saved"]

            reduction = (saved / total_ops * 100) if total_ops > 0 else 0.0

            return {
                "total_operations": total_ops,
                "batches_executed": batches,
                "operations_saved": saved,
                "reduction_percent": f"{reduction:.2f}%",
                "pending_operations": sum(len(ops) for ops in self.buffers.values()),
                "pending_queries": len(self.buffers),
            }


# Global batch optimizer instance
_batch_optimizer: Optional[BatchOptimizer] = None
_optimizer_lock = threading.Lock()


def get_batch_optimizer(**kwargs) -> BatchOptimizer:
    """Get or create the global batch optimizer."""
    global _batch_optimizer

    with _optimizer_lock:
        if _batch_optimizer is None:
            _batch_optimizer = BatchOptimizer(**kwargs)
        return _batch_optimizer


def stop_batch_optimizer():
    """Stop and clean up the global batch optimizer."""
    global _batch_optimizer

    with _optimizer_lock:
        if _batch_optimizer:
            _batch_optimizer.stop()
            _batch_optimizer = None
