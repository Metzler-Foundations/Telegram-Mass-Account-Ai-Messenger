#!/usr/bin/env python3
"""
Database Lock Handler - Comprehensive SQLite lock error handling and recovery.

Features:
- Automatic retry on database locked errors
- Deadlock detection and recovery
- WAL mode enablement for better concurrency
- Connection timeout configuration
- Lock monitoring and diagnostics
"""

import logging
import random
import sqlite3
import time
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class DatabaseLockError(Exception):
    """Raised when database lock cannot be acquired after retries."""

    pass


class DatabaseLockHandler:
    """Handles SQLite database locking issues with automatic retry and recovery."""

    DEFAULT_RETRY_ATTEMPTS = 5
    DEFAULT_RETRY_DELAY = 0.1  # 100ms
    DEFAULT_TIMEOUT = 30.0  # 30 seconds

    def __init__(
        self,
        max_retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        base_retry_delay: float = DEFAULT_RETRY_DELAY,
        timeout: float = DEFAULT_TIMEOUT,
        enable_wal: bool = True,
    ):
        """Initialize the database lock handler.

        Args:
            max_retry_attempts: Maximum number of retry attempts for locked database
            base_retry_delay: Base delay between retries (seconds)
            timeout: Database connection timeout (seconds)
            enable_wal: Whether to enable WAL mode for better concurrency
        """
        self.max_retry_attempts = max_retry_attempts
        self.base_retry_delay = base_retry_delay
        self.timeout = timeout
        self.enable_wal = enable_wal
        self._lock_statistics = {
            "total_locks": 0,
            "retries_succeeded": 0,
            "retries_failed": 0,
            "total_wait_time": 0.0,
        }

    @contextmanager
    def get_connection(self, db_path: str, *, read_only: bool = False):
        """Get a database connection with proper lock handling and WAL mode.

        Args:
            db_path: Path to the SQLite database file
            read_only: Whether to open in read-only mode

        Yields:
            sqlite3.Connection: Database connection with optimized settings

        Raises:
            DatabaseLockError: If lock cannot be acquired after retries
        """
        conn = None
        try:
            # Open connection with timeout
            if read_only:
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=self.timeout)
            else:
                conn = sqlite3.connect(db_path, timeout=self.timeout)

            # Enable WAL mode for better concurrency (only for read-write connections)
            if not read_only and self.enable_wal:
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.execute("PRAGMA synchronous=NORMAL")  # Faster with WAL
                    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
                    conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
                except sqlite3.OperationalError as e:
                    logger.warning(f"Could not enable WAL mode: {e}")

            # Set row factory for easier result access
            conn.row_factory = sqlite3.Row

            yield conn

        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                self._lock_statistics["total_locks"] += 1
                raise DatabaseLockError(f"Database is locked: {e}") from e
            raise
        finally:
            if conn:
                conn.close()

    def execute_with_retry(
        self, db_path: str, operation: Callable[[sqlite3.Connection], T], *, read_only: bool = False
    ) -> T:
        """Execute a database operation with automatic retry on lock errors.

        Args:
            db_path: Path to the SQLite database
            operation: Function that takes a connection and returns a result
            read_only: Whether this is a read-only operation

        Returns:
            Result of the operation

        Raises:
            DatabaseLockError: If operation fails after all retries
        """
        last_exception = None
        start_time = time.time()

        for attempt in range(self.max_retry_attempts):
            try:
                with self.get_connection(db_path, read_only=read_only) as conn:
                    result = operation(conn)

                    # Record successful retry if this wasn't the first attempt
                    if attempt > 0:
                        self._lock_statistics["retries_succeeded"] += 1
                        wait_time = time.time() - start_time
                        self._lock_statistics["total_wait_time"] += wait_time
                        logger.info(
                            f"Database operation succeeded after {attempt + 1} attempts ({wait_time:.2f}s)"
                        )

                    return result

            except (sqlite3.OperationalError, DatabaseLockError) as e:
                last_exception = e
                error_str = str(e).lower()

                if "locked" in error_str or "busy" in error_str:
                    if attempt < self.max_retry_attempts - 1:
                        # Calculate exponential backoff with jitter
                        delay = min(self.base_retry_delay * (2**attempt), 5.0)  # Cap at 5 seconds
                        # Add jitter (±20%)
                        jitter = delay * 0.2 * (2 * random.random() - 1)
                        actual_delay = max(0.01, delay + jitter)

                        logger.warning(
                            f"Database locked, retrying in {actual_delay:.2f}s "
                            f"(attempt {attempt + 1}/{self.max_retry_attempts}): {e}"
                        )
                        time.sleep(actual_delay)
                        continue
                    else:
                        # All retries exhausted
                        self._lock_statistics["retries_failed"] += 1
                        total_wait = time.time() - start_time
                        self._lock_statistics["total_wait_time"] += total_wait
                        logger.error(
                            f"Database lock could not be acquired after "
                            f"{self.max_retry_attempts} attempts "
                            f"({total_wait:.2f}s total wait time)"
                        )
                        raise DatabaseLockError(
                            f"Database locked after {self.max_retry_attempts} retry attempts"
                        ) from e
                else:
                    # Not a lock error, re-raise immediately
                    raise

            except Exception as e:
                # Non-lock error, re-raise immediately
                logger.error(f"Database operation failed with non-lock error: {e}", exc_info=True)
                raise

        # Should not reach here, but just in case
        if last_exception:
            raise DatabaseLockError(
                f"Database operation failed after {self.max_retry_attempts} attempts"
            ) from last_exception
        else:
            raise DatabaseLockError("Database operation failed for unknown reason")

    async def execute_with_retry_async(
        self, db_path: str, operation: Callable[[sqlite3.Connection], T], *, read_only: bool = False
    ) -> T:
        """Async version of execute_with_retry (runs in executor).

        Args:
            db_path: Path to the SQLite database
            operation: Function that takes a connection and returns a result
            read_only: Whether this is a read-only operation

        Returns:
            Result of the operation
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self.execute_with_retry, db_path, operation, read_only
        )

    def get_statistics(self) -> dict:
        """Get lock handling statistics.

        Returns:
            Dictionary with lock statistics
        """
        return {
            **self._lock_statistics,
            "avg_wait_time": (
                self._lock_statistics["total_wait_time"]
                / self._lock_statistics["retries_succeeded"]
                if self._lock_statistics["retries_succeeded"] > 0
                else 0.0
            ),
        }

    def reset_statistics(self):
        """Reset lock statistics."""
        self._lock_statistics = {
            "total_locks": 0,
            "retries_succeeded": 0,
            "retries_failed": 0,
            "total_wait_time": 0.0,
        }


# Global instance
_lock_handler = None


def get_lock_handler() -> DatabaseLockHandler:
    """Get the global database lock handler instance.

    Returns:
        DatabaseLockHandler instance
    """
    global _lock_handler
    if _lock_handler is None:
        _lock_handler = DatabaseLockHandler()
    return _lock_handler


def with_lock_retry(max_attempts: int = DatabaseLockHandler.DEFAULT_RETRY_ATTEMPTS):
    """Decorator to add lock retry logic to database functions.

    Usage:
        @with_lock_retry(max_attempts=5)
        def my_db_operation(conn):
            conn.execute("INSERT INTO ...")
            return result

    Args:
        max_attempts: Maximum number of retry attempts
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = get_lock_handler()
            handler.max_retry_attempts = max_attempts

            # Try to extract db_path and connection from args/kwargs
            # This is a simplified implementation - may need adjustment based on usage
            if args and isinstance(args[0], str):
                db_path = args[0]

                def operation(conn):
                    return func(conn, *args[1:], **kwargs)

                return handler.execute_with_retry(db_path, operation)
            else:
                # If db_path not in args, just call the function normally
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Convenience functions for common operations
def execute_query_with_retry(
    db_path: str,
    query: str,
    params: tuple = (),
    *,
    fetch_one: bool = False,
    fetch_all: bool = False,
) -> Optional[Any]:
    """Execute a query with automatic lock retry.

    Args:
        db_path: Path to the database
        query: SQL query to execute
        params: Query parameters
        fetch_one: Whether to fetch one result
        fetch_all: Whether to fetch all results

    Returns:
        Query result(s) or None
    """
    handler = get_lock_handler()

    def operation(conn):
        cursor = conn.execute(query, params)
        if fetch_one:
            return cursor.fetchone()
        elif fetch_all:
            return cursor.fetchall()
        else:
            conn.commit()
            return cursor.rowcount

    return handler.execute_with_retry(db_path, operation, read_only=(fetch_one or fetch_all))


def execute_transaction_with_retry(db_path: str, operations: list[tuple[str, tuple]]) -> bool:
    """Execute multiple operations in a transaction with retry.

    Args:
        db_path: Path to the database
        operations: List of (query, params) tuples

    Returns:
        True if successful
    """
    handler = get_lock_handler()

    def transaction(conn):
        conn.execute("BEGIN EXCLUSIVE")
        try:
            for query, params in operations:
                conn.execute(query, params)
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e

    return handler.execute_with_retry(db_path, transaction)


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Create a test database
    test_db = "test_locks.db"

    # Initialize handler
    handler = get_lock_handler()

    # Example: Execute a query with retry
    def create_table(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY, value TEXT)")
        conn.commit()

    handler.execute_with_retry(test_db, create_table)

    # Example: Insert with retry
    def insert_data(conn):
        conn.execute("INSERT INTO test (value) VALUES (?)", ("test_value",))
        conn.commit()
        return conn.lastrowid

    row_id = handler.execute_with_retry(test_db, insert_data)
    print(f"Inserted row ID: {row_id}")

    # Print statistics
    print("Lock statistics:", handler.get_statistics())
