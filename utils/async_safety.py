#!/usr/bin/env python3
"""
Async Safety - Deadlock prevention and async best practices.

Features:
- Deadlock detection
- Timeout enforcement
- Task cancellation safety
- Event loop isolation
- Semaphore management
"""

import asyncio
import logging
import time
import threading
from typing import Optional, Callable, Any, Coroutine
from datetime import datetime, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


class DeadlockDetector:
    """
    Detects potential deadlocks in async operations.
    
    Monitors task execution time and alerts on suspicious delays.
    """
    
    def __init__(self, timeout_threshold: float = 30.0):
        """
        Initialize deadlock detector.
        
        Args:
            timeout_threshold: Time before flagging potential deadlock
        """
        self.timeout_threshold = timeout_threshold
        self.active_tasks: Dict[asyncio.Task, float] = {}  # task -> start_time
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'tasks_monitored': 0,
            'timeouts_detected': 0,
            'deadlocks_suspected': 0
        }
    
    def monitor_task(self, task: asyncio.Task):
        """
        Start monitoring a task.
        
        Args:
            task: Task to monitor
        """
        with self.lock:
            self.active_tasks[task] = time.time()
            self.stats['tasks_monitored'] += 1
            
            # Add done callback
            task.add_done_callback(self._task_done)
    
    def _task_done(self, task: asyncio.Task):
        """Called when monitored task completes."""
        with self.lock:
            if task in self.active_tasks:
                start_time = self.active_tasks[task]
                duration = time.time() - start_time
                
                if duration > self.timeout_threshold:
                    self.stats['timeouts_detected'] += 1
                    logger.warning(
                        f"Task took {duration:.2f}s (threshold: {self.timeout_threshold}s): "
                        f"{task.get_name()}"
                    )
                
                del self.active_tasks[task]
    
    def check_for_deadlocks(self) -> List[asyncio.Task]:
        """
        Check for potential deadlocks.
        
        Returns:
            List of tasks suspected to be deadlocked
        """
        with self.lock:
            now = time.time()
            suspected = []
            
            for task, start_time in list(self.active_tasks.items()):
                duration = now - start_time
                
                if duration > self.timeout_threshold * 2:  # 2x threshold
                    suspected.append(task)
                    self.stats['deadlocks_suspected'] += 1
                    logger.error(
                        f"Potential deadlock detected in task {task.get_name()} "
                        f"(running for {duration:.2f}s)"
                    )
            
            return suspected


class AsyncSemaphoreManager:
    """
    Manages semaphores to prevent over-concurrency.
    
    Ensures system doesn't attempt too many operations simultaneously.
    """
    
    def __init__(self):
        """Initialize semaphore manager."""
        self.semaphores: Dict[str, asyncio.Semaphore] = {}
        self.lock = threading.Lock()
    
    def get_semaphore(self, name: str, limit: int) -> asyncio.Semaphore:
        """
        Get or create named semaphore.
        
        Args:
            name: Semaphore name
            limit: Concurrent operation limit
            
        Returns:
            Semaphore instance
        """
        with self.lock:
            if name not in self.semaphores:
                self.semaphores[name] = asyncio.Semaphore(limit)
                logger.debug(f"Created semaphore '{name}' with limit {limit}")
            
            return self.semaphores[name]


def timeout_after(seconds: float):
    """
    Decorator to enforce timeout on async functions.
    
    Args:
        seconds: Timeout in seconds
        
    Example:
        @timeout_after(30.0)
        async def slow_operation():
            await asyncio.sleep(100)  # Will timeout after 30s
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"Function {func.__name__} timed out after {seconds}s")
                raise
        
        return wrapper
    return decorator


def safe_task_cancel(task: asyncio.Task, timeout: float = 5.0) -> bool:
    """
    Safely cancel async task with timeout.
    
    Args:
        task: Task to cancel
        timeout: Time to wait for cancellation
        
    Returns:
        True if cancelled successfully
    """
    if task.done():
        return True
    
    task.cancel()
    
    try:
        # Wait for task to acknowledge cancellation
        loop = asyncio.get_event_loop()
        loop.run_until_complete(asyncio.wait_for(
            asyncio.shield(task),
            timeout=timeout
        ))
        return True
    except (asyncio.CancelledError, asyncio.TimeoutError):
        return True
    except Exception as e:
        logger.warning(f"Error cancelling task: {e}")
        return False


async def run_with_semaphore(
    semaphore: asyncio.Semaphore,
    coro: Coroutine
) -> Any:
    """
    Run coroutine with semaphore limiting concurrency.
    
    Args:
        semaphore: Semaphore to use
        coro: Coroutine to run
        
    Returns:
        Coroutine result
    """
    async with semaphore:
        return await coro


# Context manager for monitored tasks
class monitored_task:
    """Context manager for deadlock detection."""
    
    def __init__(self, detector: Optional[DeadlockDetector] = None):
        self.detector = detector
        self.task: Optional[asyncio.Task] = None
    
    async def __aenter__(self):
        if self.detector:
            self.task = asyncio.current_task()
            if self.task:
                self.detector.monitor_task(self.task)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # Cleanup handled by callback
        pass


# Global detector
_deadlock_detector: Optional[DeadlockDetector] = None


def get_deadlock_detector() -> DeadlockDetector:
    """Get global deadlock detector."""
    global _deadlock_detector
    if _deadlock_detector is None:
        _deadlock_detector = DeadlockDetector()
    return _deadlock_detector



