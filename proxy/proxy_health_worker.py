#!/usr/bin/env python3
"""
Proxy Health Worker - Background worker for silent proxy testing.

This worker runs continuously in the background, testing proxies in batches
without blocking the UI or consuming too many resources.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ProxyPriority(Enum):
    """Priority levels for proxy testing."""

    CRITICAL = 1  # Assigned to accounts - check every 5 min
    HIGH = 2  # Active proxies - check every 15 min
    MEDIUM = 3  # Testing proxies - check once
    LOW = 4  # Other proxies - check every 30 min


@dataclass
class ProxyTestTask:
    """A proxy testing task."""

    proxy_key: str
    priority: ProxyPriority
    scheduled_time: datetime
    attempt: int = 0


class ProxyHealthWorker:
    """
    Background worker for continuous proxy health checking.

    Features:
    - Priority-based testing queue
    - Batched processing to prevent overload
    - Resource-aware operation
    - Automatic retry with backoff
    """

    def __init__(self, proxy_pool_manager, batch_size: int = 50, batch_delay: float = 2.0):
        """
        Initialize the health worker.

        Args:
            proxy_pool_manager: The ProxyPoolManager instance
            batch_size: Number of proxies to test per batch
            batch_delay: Delay between batches in seconds
        """
        self.proxy_pool_manager = proxy_pool_manager
        self.batch_size = batch_size
        self.batch_delay = batch_delay

        # Task queue
        self.task_queue: list[ProxyTestTask] = []
        self.tested_proxies: Set[str] = set()  # Recently tested proxies

        # Worker state
        self.is_running = False
        self.worker_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            "tests_completed": 0,
            "tests_failed": 0,
            "batches_processed": 0,
            "start_time": None,
            "last_test_time": None,
        }

        # Configuration
        self.config = {
            "max_concurrent_tests": 5,  # Max concurrent tests per batch
            "critical_interval": 300,  # 5 minutes
            "high_interval": 900,  # 15 minutes
            "medium_interval": 1800,  # 30 minutes (one-time test)
            "low_interval": 3600,  # 60 minutes
            "cleanup_interval": 300,  # Clean tested set every 5 min
            "max_test_age": 300,  # Don't retest if tested in last 5 min
        }

        logger.info("ProxyHealthWorker initialized")

    async def start(self):
        """Start the background worker."""
        if self.is_running:
            logger.warning("ProxyHealthWorker already running")
            return

        self.is_running = True
        self.stats["start_time"] = datetime.now()

        # Start worker task
        self.worker_task = asyncio.create_task(self._worker_loop())

        logger.info("🚀 ProxyHealthWorker started")

    async def stop(self):
        """Stop the background worker."""
        if not self.is_running:
            return

        self.is_running = False

        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        logger.info("ProxyHealthWorker stopped")

    async def _worker_loop(self):
        """Main worker loop."""
        last_cleanup = datetime.now()

        while self.is_running:
            try:
                # Populate queue if empty
                if not self.task_queue:
                    await self._populate_queue()

                # Process next batch
                if self.task_queue:
                    await self._process_batch()

                # Clean up tested set periodically
                if (datetime.now() - last_cleanup).total_seconds() > self.config[
                    "cleanup_interval"
                ]:
                    self._cleanup_tested_set()
                    last_cleanup = datetime.now()

                # Small delay between batches
                await asyncio.sleep(self.batch_delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ProxyHealthWorker error: {e}")
                await asyncio.sleep(5)  # Error backoff

    async def _populate_queue(self):
        """Populate the testing queue with prioritized tasks."""
        now = datetime.now()
        tasks = []

        # Get all proxies from the manager
        for proxy in self.proxy_pool_manager.proxies.values():
            # Skip if recently tested
            if proxy.proxy_key in self.tested_proxies:
                continue

            # Skip blacklisted proxies
            if proxy.status.value == "blacklisted":
                continue

            # Determine priority and scheduling
            priority = None
            interval = None

            if proxy.assigned_account:
                # Critical: Assigned to account
                priority = ProxyPriority.CRITICAL
                interval = self.config["critical_interval"]
            elif proxy.status.value == "active":
                # High: Active but unassigned
                priority = ProxyPriority.HIGH
                interval = self.config["high_interval"]
            elif proxy.status.value == "testing":
                # Medium: Testing status
                priority = ProxyPriority.MEDIUM
                interval = self.config["medium_interval"]
            else:
                # Low: Other statuses
                priority = ProxyPriority.LOW
                interval = self.config["low_interval"]

            # Check if proxy needs testing based on last check time
            if proxy.last_check:
                time_since_check = (now - proxy.last_check).total_seconds()
                if time_since_check < interval:
                    continue  # Too soon to retest

            # Create task
            task = ProxyTestTask(proxy_key=proxy.proxy_key, priority=priority, scheduled_time=now)
            tasks.append(task)

        # Sort by priority (critical first)
        tasks.sort(key=lambda t: (t.priority.value, t.scheduled_time))

        # Add to queue
        self.task_queue.extend(tasks)

        if tasks:
            logger.debug(f"Populated queue with {len(tasks)} proxy test tasks")

    async def _process_batch(self):
        """Process a batch of proxy tests."""
        # Get next batch
        batch_size = min(self.batch_size, len(self.task_queue))
        batch = self.task_queue[:batch_size]
        self.task_queue = self.task_queue[batch_size:]

        logger.debug(f"Processing batch of {len(batch)} proxy tests")

        # Limit concurrency within batch
        semaphore = asyncio.Semaphore(self.config["max_concurrent_tests"])

        async def test_proxy(task: ProxyTestTask):
            async with semaphore:
                await self._test_single_proxy(task)

        # Run tests
        await asyncio.gather(*[test_proxy(task) for task in batch], return_exceptions=True)

        # Update stats
        self.stats["batches_processed"] += 1
        self.stats["last_test_time"] = datetime.now()

    async def _test_single_proxy(self, task: ProxyTestTask):
        """Test a single proxy."""
        try:
            # Get proxy object
            proxy = self.proxy_pool_manager.proxies.get(task.proxy_key)
            if not proxy:
                return

            # Run health check
            await self.proxy_pool_manager._check_proxy_health(proxy)

            # Mark as tested
            self.tested_proxies.add(task.proxy_key)
            self.stats["tests_completed"] += 1

        except Exception as e:
            logger.debug(f"Failed to test proxy {task.proxy_key}: {e}")
            self.stats["tests_failed"] += 1

    def _cleanup_tested_set(self):
        """Clear the tested proxies set to allow retesting."""
        logger.debug(f"Clearing {len(self.tested_proxies)} tested proxies from memory")
        self.tested_proxies.clear()

    def get_stats(self) -> dict:
        """Get worker statistics."""
        stats = self.stats.copy()

        if stats["start_time"]:
            uptime = (datetime.now() - stats["start_time"]).total_seconds()
            stats["uptime_seconds"] = uptime
            stats["uptime_formatted"] = str(timedelta(seconds=int(uptime)))

        stats["queue_size"] = len(self.task_queue)
        stats["is_running"] = self.is_running

        return stats


# Global worker instance
_health_worker: Optional[ProxyHealthWorker] = None


def get_health_worker() -> Optional[ProxyHealthWorker]:
    """Get the global health worker instance."""
    return _health_worker


async def init_health_worker(proxy_pool_manager, batch_size: int = 50) -> ProxyHealthWorker:
    """
    Initialize and start the global health worker.

    Args:
        proxy_pool_manager: The ProxyPoolManager instance
        batch_size: Number of proxies to test per batch

    Returns:
        The initialized worker
    """
    global _health_worker

    if _health_worker is not None:
        logger.warning("Health worker already initialized")
        return _health_worker

    _health_worker = ProxyHealthWorker(proxy_pool_manager, batch_size=batch_size)
    await _health_worker.start()

    return _health_worker


async def stop_health_worker():
    """Stop the global health worker."""
    global _health_worker

    if _health_worker:
        await _health_worker.stop()
        _health_worker = None
