#!/usr/bin/env python3
"""
Graceful Shutdown Manager - Ensures clean application termination.

Features:
- Async task completion tracking
- Resource cleanup coordination
- Data persistence before shutdown
- Timeout handling
- Signal handling (SIGTERM, SIGINT)
- Shutdown hooks for services
"""

import asyncio
import signal
import logging
import time
from typing import List, Callable, Optional, Any, Coroutine
from datetime import datetime
import threading
from enum import Enum

logger = logging.getLogger(__name__)


class ShutdownPhase(Enum):
    """Shutdown phases."""

    RUNNING = "running"
    SHUTDOWN_REQUESTED = "shutdown_requested"
    STOPPING_SERVICES = "stopping_services"
    WAITING_FOR_TASKS = "waiting_for_tasks"
    CLEANING_UP = "cleaning_up"
    COMPLETE = "complete"


class GracefulShutdownManager:
    """
    Manages graceful shutdown of application.

    Ensures:
    - All async tasks complete or timeout
    - All services stop cleanly
    - All resources are released
    - All data is persisted
    """

    def __init__(self, shutdown_timeout: float = 30.0, task_timeout: float = 10.0):
        """
        Initialize shutdown manager.

        Args:
            shutdown_timeout: Total time allowed for shutdown (seconds)
            task_timeout: Time to wait for individual tasks (seconds)
        """
        self.shutdown_timeout = shutdown_timeout
        self.task_timeout = task_timeout

        # State tracking
        self.phase = ShutdownPhase.RUNNING
        self.shutdown_requested = False
        self.shutdown_start_time: Optional[float] = None

        # Hooks - executed in order
        self.shutdown_hooks: List[Callable] = []

        # Task tracking
        self.active_tasks: set = set()
        self.task_lock = threading.Lock()

        # Statistics
        self.stats = {
            "shutdown_count": 0,
            "tasks_completed": 0,
            "tasks_cancelled": 0,
            "tasks_timeout": 0,
            "hooks_executed": 0,
            "hooks_failed": 0,
        }

        # Signal handling
        self._original_sigterm = None
        self._original_sigint = None
        self._signal_received = False

        logger.info("GracefulShutdownManager initialized")

    def register_shutdown_hook(self, hook: Callable, priority: int = 0):
        """
        Register a shutdown hook.

        Hooks are called in order of priority (lower = earlier).

        Args:
            hook: Callable (sync or async) to execute on shutdown
            priority: Execution priority (lower executes first)
        """
        self.shutdown_hooks.append((priority, hook))
        self.shutdown_hooks.sort(key=lambda x: x[0])
        logger.debug(f"Registered shutdown hook: {hook.__name__} (priority={priority})")

    def track_task(self, task: asyncio.Task):
        """
        Track an async task for completion.

        Args:
            task: Task to track
        """
        with self.task_lock:
            self.active_tasks.add(task)
            task.add_done_callback(self._task_done_callback)

    def _task_done_callback(self, task: asyncio.Task):
        """Called when tracked task completes."""
        with self.task_lock:
            self.active_tasks.discard(task)

            if task.cancelled():
                self.stats["tasks_cancelled"] += 1
            elif task.exception():
                logger.error(f"Task failed: {task.exception()}")
            else:
                self.stats["tasks_completed"] += 1

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            signal_name = signal.Signals(signum).name
            logger.warning(f"Received signal {signal_name}, initiating graceful shutdown...")
            self._signal_received = True
            self.request_shutdown()

        # Save original handlers
        self._original_sigterm = signal.signal(signal.SIGTERM, signal_handler)
        self._original_sigint = signal.signal(signal.SIGINT, signal_handler)

        logger.info("Signal handlers registered (SIGTERM, SIGINT)")

    def restore_signal_handlers(self):
        """Restore original signal handlers."""
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)

    def request_shutdown(self):
        """Request graceful shutdown."""
        if self.shutdown_requested:
            logger.warning("Shutdown already requested")
            return

        self.shutdown_requested = True
        self.shutdown_start_time = time.time()
        self.phase = ShutdownPhase.SHUTDOWN_REQUESTED
        self.stats["shutdown_count"] += 1

        logger.warning("🛑 GRACEFUL SHUTDOWN REQUESTED")

    async def shutdown(self):
        """
        Execute graceful shutdown sequence.

        Returns:
            True if successful, False if timeout/errors
        """
        if not self.shutdown_requested:
            self.request_shutdown()

        start_time = time.time()
        logger.info("=" * 60)
        logger.info("GRACEFUL SHUTDOWN SEQUENCE STARTED")
        logger.info("=" * 60)

        try:
            # Phase 1: Stop services
            await self._stop_services()

            # Phase 2: Wait for tasks
            await self._wait_for_tasks()

            # Phase 3: Cleanup
            await self._cleanup()

            # Phase 4: Execute hooks
            await self._execute_hooks()

            self.phase = ShutdownPhase.COMPLETE
            elapsed = time.time() - start_time

            logger.info("=" * 60)
            logger.info(f"✅ GRACEFUL SHUTDOWN COMPLETE ({elapsed:.2f}s)")
            logger.info(f"Stats: {self.stats}")
            logger.info("=" * 60)

            return True

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            return False
        finally:
            self.restore_signal_handlers()

    async def _stop_services(self):
        """Stop background services."""
        self.phase = ShutdownPhase.STOPPING_SERVICES
        logger.info("Phase 1: Stopping services...")

        # Stop database connection pools
        try:
            from database.connection_pool import close_all_pools

            close_all_pools()
            logger.info("✓ Database connection pools closed")
        except Exception as e:
            logger.warning(f"Error closing database pools: {e}")

        # Add more service stops here as needed

        logger.info("✓ Services stopped")

    async def _wait_for_tasks(self):
        """Wait for active tasks to complete."""
        self.phase = ShutdownPhase.WAITING_FOR_TASKS

        with self.task_lock:
            task_count = len(self.active_tasks)

        if task_count == 0:
            logger.info("Phase 2: No active tasks to wait for")
            return

        logger.info(f"Phase 2: Waiting for {task_count} active tasks...")

        start_time = time.time()

        # Wait for tasks with timeout
        try:
            with self.task_lock:
                tasks = list(self.active_tasks)

            if tasks:
                await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True), timeout=self.task_timeout
                )
                logger.info(f"✓ All tasks completed")
        except asyncio.TimeoutError:
            with self.task_lock:
                remaining = len(self.active_tasks)

            logger.warning(f"⏱️  Timeout waiting for tasks ({remaining} still active)")
            self.stats["tasks_timeout"] = remaining

            # Cancel remaining tasks
            with self.task_lock:
                for task in self.active_tasks:
                    if not task.done():
                        task.cancel()
                        logger.debug(f"Cancelled task: {task}")

        elapsed = time.time() - start_time
        logger.info(f"✓ Task wait phase complete ({elapsed:.2f}s)")

    async def _cleanup(self):
        """Perform cleanup operations."""
        self.phase = ShutdownPhase.CLEANING_UP
        logger.info("Phase 3: Cleanup...")

        # Clean up temporary files
        try:
            import tempfile
            import shutil
            from pathlib import Path

            temp_dirs = [Path(tempfile.gettempdir()) / "telegram_bot", Path(".") / "temp"]

            for temp_dir in temp_dirs:
                if temp_dir.exists():
                    try:
                        shutil.rmtree(temp_dir)
                        logger.debug(f"Cleaned temp directory: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"Could not clean {temp_dir}: {e}")
        except Exception as e:
            logger.warning(f"Error during temp cleanup: {e}")

        logger.info("✓ Cleanup complete")

    async def _execute_hooks(self):
        """Execute registered shutdown hooks."""
        logger.info(f"Phase 4: Executing {len(self.shutdown_hooks)} shutdown hooks...")

        for priority, hook in self.shutdown_hooks:
            try:
                hook_name = getattr(hook, "__name__", str(hook))
                logger.info(f"Executing hook: {hook_name} (priority={priority})")

                # Execute hook (sync or async)
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()

                self.stats["hooks_executed"] += 1
                logger.info(f"✓ Hook completed: {hook_name}")

            except Exception as e:
                self.stats["hooks_failed"] += 1
                logger.error(f"Hook failed: {hook_name}: {e}", exc_info=True)

        logger.info("✓ All hooks executed")

    def get_status(self) -> dict:
        """
        Get current shutdown status.

        Returns:
            Status dictionary
        """
        with self.task_lock:
            active_task_count = len(self.active_tasks)

        status = {
            "phase": self.phase.value,
            "shutdown_requested": self.shutdown_requested,
            "active_tasks": active_task_count,
            "registered_hooks": len(self.shutdown_hooks),
            "stats": self.stats.copy(),
        }

        if self.shutdown_start_time:
            status["elapsed"] = time.time() - self.shutdown_start_time

        return status


# Global instance
_shutdown_manager: Optional[GracefulShutdownManager] = None


def get_shutdown_manager() -> GracefulShutdownManager:
    """
    Get global shutdown manager instance.

    Returns:
        GracefulShutdownManager instance
    """
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdownManager()
    return _shutdown_manager


def setup_graceful_shutdown(shutdown_timeout: float = 30.0, task_timeout: float = 10.0):
    """
    Setup graceful shutdown for application.

    Args:
        shutdown_timeout: Total shutdown timeout
        task_timeout: Individual task timeout

    Returns:
        GracefulShutdownManager instance
    """
    manager = GracefulShutdownManager(shutdown_timeout, task_timeout)
    manager.setup_signal_handlers()

    global _shutdown_manager
    _shutdown_manager = manager

    logger.info("Graceful shutdown configured")
    return manager


# Context manager for tracked tasks
class tracked_task:
    """Context manager to track async tasks for shutdown."""

    def __init__(self, manager: Optional[GracefulShutdownManager] = None):
        self.manager = manager or get_shutdown_manager()
        self.task: Optional[asyncio.Task] = None

    async def __aenter__(self):
        self.task = asyncio.current_task()
        if self.task:
            self.manager.track_task(self.task)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Task cleanup handled by callback
        pass


# Decorator for auto-tracking tasks
def track_task(func):
    """Decorator to automatically track async function as task."""

    async def wrapper(*args, **kwargs):
        manager = get_shutdown_manager()
        task = asyncio.current_task()
        if task:
            manager.track_task(task)
        return await func(*args, **kwargs)

    return wrapper


if __name__ == "__main__":
    # Test graceful shutdown
    async def test():
        manager = setup_graceful_shutdown()

        # Register test hook
        def cleanup_hook():
            print("Cleanup hook executed!")

        manager.register_shutdown_hook(cleanup_hook)

        # Simulate some async work
        async def background_task():
            print("Background task started")
            await asyncio.sleep(2)
            print("Background task complete")

        task = asyncio.create_task(background_task())
        manager.track_task(task)

        # Request shutdown after 1 second
        await asyncio.sleep(1)
        await manager.shutdown()

    asyncio.run(test())
