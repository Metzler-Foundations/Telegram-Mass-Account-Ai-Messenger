#!/usr/bin/env python3
"""Thread pool configuration for concurrent operations."""

import concurrent.futures
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ThreadPoolConfig:
    """Manages thread pool for blocking I/O operations."""
    
    def __init__(
        self,
        max_workers: Optional[int] = None,
        thread_name_prefix: str = "telegram-worker"
    ):
        # Auto-configure based on CPU count
        if max_workers is None:
            import os
            cpu_count = os.cpu_count() or 4
            max_workers = min(32, (cpu_count + 4))
        
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix
        )
        
        logger.info(f"Thread pool initialized with {max_workers} workers")
    
    def submit(self, func, *args, **kwargs):
        """Submit task to thread pool."""
        return self.executor.submit(func, *args, **kwargs)
    
    def shutdown(self, wait: bool = True):
        """Shutdown thread pool."""
        self.executor.shutdown(wait=wait)
        logger.info("Thread pool shutdown")


_thread_pool = None

def get_thread_pool():
    global _thread_pool
    if _thread_pool is None:
        _thread_pool = ThreadPoolConfig()
    return _thread_pool



