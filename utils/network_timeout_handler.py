#!/usr/bin/env python3
"""
Network Timeout Handler - Comprehensive timeout management for all network operations.

Features:
- Configurable timeouts for different operation types
- Automatic timeout detection and recovery
- Timeout statistics and monitoring
- Integration with retry logic
- Support for requests, aiohttp, and socket operations
"""

import asyncio
import logging
import time
import socket
import threading
from typing import Optional, Callable, TypeVar, Any
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar("T")


class TimeoutError(Exception):
    """Raised when an operation times out."""

    pass


class NetworkTimeoutHandler:
    """Handles network timeouts for various operation types."""

    # Default timeouts for different operation types (in seconds)
    DEFAULT_TIMEOUTS = {
        "api_call": 30.0,  # General API calls
        "telegram_api": 60.0,  # Telegram API calls (can be slow)
        "sms_provider": 45.0,  # SMS provider API calls
        "proxy_health_check": 10.0,  # Proxy health checks
        "gemini_api": 120.0,  # Gemini AI API (can be slow for long responses)
        "database_query": 30.0,  # Database operations
        "file_download": 300.0,  # File downloads (5 minutes)
        "socket_connect": 5.0,  # Socket connection
        "socket_send": 10.0,  # Socket send operation
        "socket_recv": 30.0,  # Socket receive operation
        "http_request": 30.0,  # HTTP requests
        "websocket": 60.0,  # WebSocket operations
    }

    def __init__(self, custom_timeouts: Optional[dict] = None):
        """Initialize the network timeout handler.

        Args:
            custom_timeouts: Custom timeout values to override defaults
        """
        self.timeouts = {**self.DEFAULT_TIMEOUTS}
        if custom_timeouts:
            self.timeouts.update(custom_timeouts)

        self._timeout_statistics = {
            "total_timeouts": 0,
            "timeouts_by_operation": {},
            "total_operations": 0,
            "avg_operation_time": 0.0,
        }

        # Thread synchronization
        self._stats_lock = threading.Lock()

    def get_timeout(self, operation_type: str) -> float:
        """Get timeout value for an operation type.

        Args:
            operation_type: Type of operation (e.g., 'api_call', 'telegram_api')

        Returns:
            Timeout value in seconds
        """
        return self.timeouts.get(operation_type, self.DEFAULT_TIMEOUTS["api_call"])

    def set_timeout(self, operation_type: str, timeout: float):
        """Set timeout value for an operation type.

        Args:
            operation_type: Type of operation
            timeout: Timeout value in seconds
        """
        self.timeouts[operation_type] = timeout
        logger.debug(f"Set timeout for {operation_type}: {timeout}s")

    async def execute_with_timeout_async(
        self, operation: Callable, operation_type: str, *args, **kwargs
    ) -> Any:
        """Execute an async operation with timeout.

        Args:
            operation: Async function to execute
            operation_type: Type of operation for timeout selection
            *args, **kwargs: Arguments to pass to the operation

        Returns:
            Result of the operation

        Raises:
            asyncio.TimeoutError: If operation times out
        """
        timeout = self.get_timeout(operation_type)
        start_time = time.time()

        try:
            self._timeout_statistics["total_operations"] += 1

            result = await asyncio.wait_for(operation(*args, **kwargs), timeout=timeout)

            # Record successful operation time
            elapsed = time.time() - start_time
            self._update_avg_time(elapsed)

            return result

        except asyncio.TimeoutError as e:
            elapsed = time.time() - start_time
            self._record_timeout(operation_type, elapsed)
            logger.error(
                f"Operation timeout: {operation_type} exceeded {timeout}s "
                f"(actual: {elapsed:.2f}s)"
            )
            raise TimeoutError(f"{operation_type} operation timed out after {timeout}s") from e

    def execute_with_timeout(
        self, operation: Callable, operation_type: str, *args, **kwargs
    ) -> Any:
        """Execute a synchronous operation with timeout (using threading).

        Args:
            operation: Function to execute
            operation_type: Type of operation for timeout selection
            *args, **kwargs: Arguments to pass to the operation

        Returns:
            Result of the operation

        Raises:
            TimeoutError: If operation times out
        """
        import threading

        timeout = self.get_timeout(operation_type)
        result = [None]
        exception = [None]
        start_time = time.time()

        def wrapper():
            try:
                operation_result = operation(*args, **kwargs)
                with self._stats_lock:
                    result[0] = operation_result
            except Exception as e:
                with self._stats_lock:
                    exception[0] = e

        thread = threading.Thread(target=wrapper)
        thread.daemon = True
        thread.start()
        thread.join(timeout=timeout)

        elapsed = time.time() - start_time

        if thread.is_alive():
            # Timeout occurred
            self._record_timeout(operation_type, elapsed)
            logger.error(
                f"Operation timeout: {operation_type} exceeded {timeout}s "
                f"(actual: {elapsed:.2f}s)"
            )
            raise TimeoutError(f"{operation_type} operation timed out after {timeout}s")

        # Synchronize access to shared result/exception
        with self._stats_lock:
            if exception[0]:
                raise exception[0]

            final_result = result[0]

        with self._stats_lock:
            self._timeout_statistics["total_operations"] += 1
            self._update_avg_time(elapsed)

        return final_result

    @contextmanager
    def socket_timeout(self, operation_type: str = "socket_connect"):
        """Context manager for socket timeout configuration.

        Usage:
            with handler.socket_timeout('socket_connect'):
                sock.connect((host, port))

        Args:
            operation_type: Type of socket operation
        """
        timeout = self.get_timeout(operation_type)
        old_timeout = socket.getdefaulttimeout()

        try:
            socket.setdefaulttimeout(timeout)
            yield timeout
        finally:
            socket.setdefaulttimeout(old_timeout)

    def configure_requests_session(self, session, operation_type: str = "http_request"):
        """Configure a requests.Session with appropriate timeouts.

        Args:
            session: requests.Session instance
            operation_type: Type of operation for timeout selection
        """
        timeout = self.get_timeout(operation_type)

        # Set default timeout for the session
        original_request = session.request

        def request_with_timeout(*args, **kwargs):
            if "timeout" not in kwargs:
                kwargs["timeout"] = (timeout / 2, timeout)  # (connect, read)
            return original_request(*args, **kwargs)

        session.request = request_with_timeout
        logger.debug(f"Configured requests session with {timeout}s timeout")

    def configure_aiohttp_session(
        self, session_kwargs: dict, operation_type: str = "http_request"
    ) -> dict:
        """Configure aiohttp.ClientSession kwargs with appropriate timeouts.

        Args:
            session_kwargs: Keyword arguments for aiohttp.ClientSession
            operation_type: Type of operation for timeout selection

        Returns:
            Updated kwargs dictionary
        """
        import aiohttp

        timeout = self.get_timeout(operation_type)

        if "timeout" not in session_kwargs:
            session_kwargs["timeout"] = aiohttp.ClientTimeout(
                total=timeout,
                connect=min(timeout / 3, 10.0),  # Max 10s for connection
                sock_connect=5.0,
                sock_read=timeout,
            )

        logger.debug(f"Configured aiohttp session with {timeout}s timeout")
        return session_kwargs

    def _record_timeout(self, operation_type: str, elapsed: float):
        """Record a timeout occurrence.

        Args:
            operation_type: Type of operation that timed out
            elapsed: Time elapsed before timeout
        """
        with self._stats_lock:
            self._timeout_statistics["total_timeouts"] += 1

            if operation_type not in self._timeout_statistics["timeouts_by_operation"]:
                self._timeout_statistics["timeouts_by_operation"][operation_type] = 0
            self._timeout_statistics["timeouts_by_operation"][operation_type] += 1

    def _update_avg_time(self, elapsed: float):
        """Update average operation time.

        Args:
            elapsed: Time elapsed for operation
        """
        with self._stats_lock:
            total_ops = self._timeout_statistics["total_operations"]
            current_avg = self._timeout_statistics["avg_operation_time"]

            # Running average calculation
            new_avg = ((current_avg * (total_ops - 1)) + elapsed) / total_ops
            self._timeout_statistics["avg_operation_time"] = new_avg

    def get_statistics(self) -> dict:
        """Get timeout statistics.

        Returns:
            Dictionary with timeout statistics
        """
        with self._stats_lock:
            stats_copy = self._timeout_statistics.copy()
            total_ops = stats_copy["total_operations"]
            total_timeouts = stats_copy["total_timeouts"]

        return {
            **stats_copy,
            "timeout_rate": (total_timeouts / total_ops * 100 if total_ops > 0 else 0.0),
            "success_rate": (
                (total_ops - total_timeouts) / total_ops * 100 if total_ops > 0 else 0.0
            ),
        }

    def reset_statistics(self):
        """Reset timeout statistics."""
        self._timeout_statistics = {
            "total_timeouts": 0,
            "timeouts_by_operation": {},
            "total_operations": 0,
            "avg_operation_time": 0.0,
        }


# Global instance
_timeout_handler = None


def get_timeout_handler() -> NetworkTimeoutHandler:
    """Get the global network timeout handler instance.

    Returns:
        NetworkTimeoutHandler instance
    """
    global _timeout_handler
    if _timeout_handler is None:
        _timeout_handler = NetworkTimeoutHandler()
    return _timeout_handler


def with_timeout(operation_type: str):
    """Decorator to add timeout handling to async functions.

    Usage:
        @with_timeout('telegram_api')
        async def send_message(...):
            # Your async code here
            pass

    Args:
        operation_type: Type of operation for timeout selection
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            handler = get_timeout_handler()
            return await handler.execute_with_timeout_async(func, operation_type, *args, **kwargs)

        return wrapper

    return decorator


def with_timeout_sync(operation_type: str):
    """Decorator to add timeout handling to synchronous functions.

    Usage:
        @with_timeout_sync('api_call')
        def make_api_call(...):
            # Your sync code here
            pass

    Args:
        operation_type: Type of operation for timeout selection
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            handler = get_timeout_handler()
            return handler.execute_with_timeout(func, operation_type, *args, **kwargs)

        return wrapper

    return decorator


# Convenience functions for common timeout configurations
def get_telegram_timeout() -> float:
    """Get timeout for Telegram API operations."""
    return get_timeout_handler().get_timeout("telegram_api")


def get_sms_timeout() -> float:
    """Get timeout for SMS provider operations."""
    return get_timeout_handler().get_timeout("sms_provider")


def get_gemini_timeout() -> float:
    """Get timeout for Gemini API operations."""
    return get_timeout_handler().get_timeout("gemini_api")


def get_proxy_timeout() -> float:
    """Get timeout for proxy health check operations."""
    return get_timeout_handler().get_timeout("proxy_health_check")


if __name__ == "__main__":
    # Example usage
    import asyncio

    logging.basicConfig(level=logging.INFO)

    handler = get_timeout_handler()

    # Example 1: Async operation with timeout
    @with_timeout("telegram_api")
    async def example_async_operation():
        await asyncio.sleep(2)
        return "Success"

    # Example 2: Sync operation with timeout
    @with_timeout_sync("api_call")
    def example_sync_operation():
        time.sleep(1)
        return "Success"

    # Run examples
    async def main():
        result1 = await example_async_operation()
        print(f"Async result: {result1}")

        result2 = example_sync_operation()
        print(f"Sync result: {result2}")

        # Print statistics
        print("Statistics:", handler.get_statistics())

    asyncio.run(main())
