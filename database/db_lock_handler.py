#!/usr/bin/env python3
"""Database lock handler - Handle SQLite lock errors gracefully."""

import logging
import sqlite3
import time
from functools import wraps
from typing import Any, Optional

logger = logging.getLogger(__name__)


def retry_on_db_lock(max_retries: int = 5, base_delay: float = 0.1):
    """Decorator to retry on database lock errors."""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except sqlite3.OperationalError as e:
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        delay = base_delay * (2**attempt)
                        logger.warning(f"Database locked, retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        raise
            return None

        return wrapper

    return decorator


class DatabaseLockHandler:
    """Handle database locking gracefully."""

    @staticmethod
    def execute_with_retry(
        conn, query: str, params: tuple = (), max_retries: int = 5
    ) -> Optional[Any]:
        """Execute query with lock retry."""
        for attempt in range(max_retries):
            try:
                return conn.execute(query, params)
            except sqlite3.OperationalError as e:
                if "locked" in str(e).lower() and attempt < max_retries - 1:
                    time.sleep(0.1 * (2**attempt))
                else:
                    raise
        return None
