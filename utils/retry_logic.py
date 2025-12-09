#!/usr/bin/env python3
"""
Retry Logic - Automatic retry with exponential backoff.

Features:
- Exponential backoff with jitter
- Configurable retry attempts
- Per-error-type retry strategies
- Circuit breaker pattern
- Timeout handling
"""

import asyncio
import time
import random
import logging
import threading
from typing import Callable, Optional, Any, Type, List
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class RetryConfig:
    """Retry configuration."""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        jitter_range: float = 0.5
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum retry attempts
            base_delay: Base delay between retries (seconds)
            max_delay: Maximum delay cap (seconds)
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter
            jitter_range: Jitter range (0.0-1.0)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter
        self.jitter_range = jitter_range
    
    def get_delay(self, attempt: int) -> float:
        """
        Calculate delay for attempt number.
        
        Args:
            attempt: Current attempt number (0-indexed)
            
        Returns:
            Delay in seconds
        """
        # Calculate base delay
        delay = self.base_delay * (self.exponential_base ** attempt)
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
        # Add jitter
        if self.jitter:
            jitter_amount = delay * self.jitter_range
            delay += random.uniform(-jitter_amount, jitter_amount)
            delay = max(0.1, delay)  # Ensure positive
        
        return delay


def retry_on_exception(
    exceptions: tuple = (Exception,),
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True
):
    """
    Decorator for automatic retry on exceptions.
    
    Args:
        exceptions: Tuple of exception types to retry on
        max_attempts: Maximum retry attempts
        base_delay: Base delay between retries
        max_delay: Maximum delay cap
        exponential_base: Exponential backoff base
        jitter: Whether to add jitter
        
    Example:
        @retry_on_exception(exceptions=(ConnectionError,), max_attempts=5)
        async def fetch_data():
            # Will retry up to 5 times on ConnectionError
            pass
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            config = RetryConfig(max_attempts, base_delay, max_delay, exponential_base, jitter)
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )
            
            # All retries exhausted
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            config = RetryConfig(max_attempts, base_delay, max_delay, exponential_base, jitter)
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_attempts - 1:
                        delay = config.get_delay(attempt)
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )
            
            raise last_exception
        
        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by stopping requests to failing service.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Time before attempting recovery
            expected_exception: Exception type to catch
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'total_calls': 0,
            'successful_calls': 0,
            'failed_calls': 0,
            'rejected_calls': 0,
            'circuit_opened': 0,
            'circuit_closed': 0
        }
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function through circuit breaker.
        
        Args:
            func: Function to call
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitBreakerOpen: If circuit is open
        """
        with self.lock:
            self.stats['total_calls'] += 1
            
            # Check circuit state
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout elapsed
                if self.last_failure_time:
                    elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                    
                    if elapsed >= self.recovery_timeout:
                        logger.info("Circuit breaker entering HALF_OPEN state")
                        self.state = CircuitState.HALF_OPEN
                    else:
                        self.stats['rejected_calls'] += 1
                        raise CircuitBreakerOpen(
                            f"Circuit breaker is OPEN. "
                            f"Retry after {self.recovery_timeout - elapsed:.1f}s"
                        )
        
        # Attempt call
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful call."""
        with self.lock:
            self.stats['successful_calls'] += 1
            self.last_success_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                # Recovery successful, close circuit
                logger.info("Circuit breaker recovered, closing circuit")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.stats['circuit_closed'] += 1
    
    def _on_failure(self):
        """Handle failed call."""
        with self.lock:
            self.stats['failed_calls'] += 1
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    logger.warning(
                        f"Circuit breaker threshold reached ({self.failure_count} failures), "
                        f"opening circuit"
                    )
                    self.state = CircuitState.OPEN
                    self.stats['circuit_opened'] += 1
    
    def reset(self):
        """Reset circuit breaker to closed state."""
        with self.lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            logger.info("Circuit breaker manually reset")
    
    def get_state(self) -> dict:
        """Get circuit breaker state."""
        with self.lock:
            return {
                'state': self.state.value,
                'failure_count': self.failure_count,
                'stats': self.stats.copy()
            }


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""
    pass


# Decorator for circuit breaker
def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0
):
    """
    Decorator to wrap function with circuit breaker.
    
    Args:
        failure_threshold: Failures before opening circuit
        recovery_timeout: Time before attempting recovery
    """
    def decorator(func):
        breaker = CircuitBreaker(failure_threshold, recovery_timeout)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)
        
        # Attach breaker to wrapper for access
        wrapper.circuit_breaker = breaker
        return wrapper
    
    return decorator





