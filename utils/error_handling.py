#!/usr/bin/env python3
"""
Enhanced Error Handling Utilities.

Provides standardized exception handling patterns and specific error types
to replace broad 'except Exception' blocks throughout the application.
"""

import logging
import functools
from typing import Callable, Any, Optional, Type, Union, Tuple
from contextlib import contextmanager
import traceback

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    """Base exception for application-specific errors."""
    pass


class DatabaseError(ApplicationError):
    """Database operation errors."""
    pass


class NetworkError(ApplicationError):
    """Network and API communication errors."""
    pass


class AuthenticationError(ApplicationError):
    """Authentication and authorization errors."""
    pass


class ValidationError(ApplicationError):
    """Data validation errors."""
    pass


class ConfigurationError(ApplicationError):
    """Configuration and setup errors."""
    pass


class ResourceError(ApplicationError):
    """Resource management errors (memory, file handles, etc.)."""
    pass


def handle_errors(
    *expected_exceptions: Type[Exception],
    log_level: int = logging.ERROR,
    default_message: str = "An error occurred",
    reraise: bool = True,
    return_on_error: Any = None
) -> Callable:
    """
    Decorator for standardized error handling.

    Args:
        *expected_exceptions: Exception types to catch specifically
        log_level: Logging level for errors
        default_message: Default error message
        reraise: Whether to re-raise the exception after logging
        return_on_error: Value to return on error (if not reraising)

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except expected_exceptions as e:
                logger.log(log_level, f"{func.__name__}: {e}")
                if not reraise:
                    return return_on_error
                raise
            except Exception as e:
                # Log unexpected exceptions with full traceback
                logger.error(f"Unexpected error in {func.__name__}: {e}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                if not reraise:
                    return return_on_error
                raise
        return wrapper
    return decorator


@contextmanager
def error_context(
    operation: str,
    *expected_exceptions: Type[Exception],
    log_level: int = logging.ERROR
):
    """
    Context manager for error handling in code blocks.

    Args:
        operation: Description of the operation being performed
        *expected_exceptions: Exception types to catch specifically
        log_level: Logging level for errors
    """
    try:
        yield
    except expected_exceptions as e:
        logger.log(log_level, f"{operation} failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in {operation}: {e}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        raise


def safe_call(
    func: Callable,
    *args,
    default: Any = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    log_errors: bool = True,
    **kwargs
) -> Any:
    """
    Safely call a function with error handling.

    Args:
        func: Function to call
        *args: Positional arguments
        default: Default value to return on error
        exceptions: Exception types to catch
        log_errors: Whether to log errors
        **kwargs: Keyword arguments

    Returns:
        Function result or default value on error
    """
    try:
        return func(*args, **kwargs)
    except exceptions as e:
        if log_errors:
            logger.warning(f"Safe call to {func.__name__} failed: {e}")
        return default


def validate_and_raise(
    condition: bool,
    error_class: Type[ApplicationError],
    message: str,
    *args,
    **kwargs
) -> None:
    """
    Validate a condition and raise an exception if it fails.

    Args:
        condition: Condition to validate
        error_class: Exception class to raise
        message: Error message
        *args, **kwargs: Additional arguments for exception
    """
    if not condition:
        raise error_class(message, *args, **kwargs)


def log_exception(exc: Exception, level: int = logging.ERROR) -> None:
    """
    Log an exception with full context.

    Args:
        exc: Exception to log
        level: Logging level
    """
    logger.log(level, f"Exception: {exc}")
    logger.debug(f"Exception traceback: {traceback.format_exc()}")


# Specific error handling patterns for common operations

def handle_database_operation(operation_name: str):
    """Decorator for database operations."""
    return handle_errors(
        sqlite3.Error, DatabaseError,
        default_message=f"Database operation '{operation_name}' failed"
    )


def handle_network_operation(operation_name: str):
    """Decorator for network operations."""
    return handle_errors(
        aiohttp.ClientError, asyncio.TimeoutError, NetworkError,
        default_message=f"Network operation '{operation_name}' failed"
    )


def handle_ui_operation(operation_name: str):
    """Decorator for UI operations."""
    return handle_errors(
        RuntimeError, AttributeError, TypeError,
        default_message=f"UI operation '{operation_name}' failed",
        log_level=logging.WARNING
    )


def handle_file_operation(operation_name: str):
    """Decorator for file operations."""
    return handle_errors(
        OSError, IOError, PermissionError,
        default_message=f"File operation '{operation_name}' failed"
    )


# Import required modules for type hints
try:
    import sqlite3
    import aiohttp
    import asyncio
except ImportError:
    # Define dummy classes for type hints when modules aren't available
    class sqlite3:
        class Error(Exception): pass

    class aiohttp:
        class ClientError(Exception): pass

    class asyncio:
        class TimeoutError(Exception): pass
