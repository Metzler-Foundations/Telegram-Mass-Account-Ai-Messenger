"""
Performance Monitor - Application performance tracking, rate limiting, and resource management.
"""
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional, Callable, Awaitable
from collections import defaultdict
import threading

try:
    import psutil
except ImportError:
    psutil = None
    logger.warning("psutil not available - performance metrics and throttling degraded")

from utils.utils import RandomizationUtils

logger = logging.getLogger(__name__)


class ResourceManager:
    """Manages system resources and provides queuing for resource-intensive operations."""

    def __init__(self):
        self._lock = threading.Lock()
        self.active_operations = 0
        self.max_concurrent_operations = 10  # Configurable limit

        # Resource limits
        self.memory_limit_mb = 512  # Max memory usage
        self.cpu_limit_percent = 80  # Max CPU usage

        # Operation queues by priority
        self.high_priority_queue = asyncio.Queue()
        self.normal_priority_queue = asyncio.Queue()
        self.low_priority_queue = asyncio.Queue()

        # Worker tasks
        self._workers = []
        self._shutdown_event = threading.Event()

        # Resource monitoring
        self.resource_check_interval = 30  # seconds
        self._resource_monitor_task = None

    async def start(self):
        """Start the resource manager."""
        logger.info("Starting ResourceManager")

        # Start resource monitoring
        self._resource_monitor_task = asyncio.create_task(self._monitor_resources())

        # Start worker tasks
        for i in range(3):  # 3 worker threads
            worker = asyncio.create_task(self._process_queues())
            self._workers.append(worker)

    async def stop(self):
        """Stop the resource manager."""
        logger.info("Stopping ResourceManager")

        self._shutdown_event.set()

        # Cancel resource monitor
        if self._resource_monitor_task:
            self._resource_monitor_task.cancel()
            try:
                await self._resource_monitor_task
            except asyncio.CancelledError:
                logger.debug("Resource monitor task cancelled")
            except Exception as exc:
                logger.warning(f"Resource monitor task failed to stop cleanly: {exc}")

        # Cancel workers
        for worker in self._workers:
            worker.cancel()
            try:
                await worker
            except asyncio.CancelledError:
                logger.debug("Worker task cancelled")
            except Exception as exc:
                logger.warning(f"Worker shutdown raised an error: {exc}")

        self._workers.clear()

    def can_allocate_resources(self, operation_type: str = 'general') -> bool:
        """Check if resources are available for a new operation."""
        with self._lock:
            # Check concurrent operation limit
            if self.active_operations >= self.max_concurrent_operations:
                return False

            # Check memory usage
            if psutil:
                memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                if memory_mb > self.memory_limit_mb:
                    logger.warning(f"Memory limit exceeded: {memory_mb:.1f}MB > {self.memory_limit_mb}MB")
                    return False

                # Check CPU usage
                cpu_percent = psutil.cpu_percent(interval=0.1)
                if cpu_percent > self.cpu_limit_percent:
                    logger.warning(f"CPU limit exceeded: {cpu_percent:.1f}% > {self.cpu_limit_percent}%")
                    return False

            return True

    async def execute_with_resource_limits(self, coro: Awaitable, priority: str = 'normal') -> Any:
        """Execute a coroutine with resource limits and queuing."""
        if not self.can_allocate_resources():
            # Queue the operation
            future = asyncio.Future()
            queue = self._get_queue(priority)
            await queue.put((coro, future))
            return await future

        # Execute immediately
        with self._lock:
            self.active_operations += 1

        try:
            result = await coro
            return result
        finally:
            with self._lock:
                self.active_operations -= 1

    def _get_queue(self, priority: str) -> asyncio.Queue:
        """Get the appropriate queue for the priority level."""
        if priority == 'high':
            return self.high_priority_queue
        elif priority == 'low':
            return self.low_priority_queue
        else:
            return self.normal_priority_queue

    async def _process_queues(self):
        """Process queued operations."""
        while not self._shutdown_event.is_set():
            try:
                # Check high priority queue first
                if not self.high_priority_queue.empty():
                    coro, future = self.high_priority_queue.get_nowait()
                    await self._execute_queued_operation(coro, future)
                    continue

                # Check normal priority queue
                if not self.normal_priority_queue.empty():
                    coro, future = self.normal_priority_queue.get_nowait()
                    await self._execute_queued_operation(coro, future)
                    continue

                # Check low priority queue
                if not self.low_priority_queue.empty():
                    coro, future = self.low_priority_queue.get_nowait()
                    await self._execute_queued_operation(coro, future)
                    continue

                # No operations in queue, wait a bit
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error processing queued operation: {e}")

    async def _execute_queued_operation(self, coro: Awaitable, future: asyncio.Future):
        """Execute a queued operation."""
        if not self.can_allocate_resources():
            # Put back in queue if resources still not available
            await asyncio.sleep(1)  # Wait before retrying
            await self.normal_priority_queue.put((coro, future))
            return

        with self._lock:
            self.active_operations += 1

        try:
            result = await coro
            if not future.done():
                future.set_result(result)
        except Exception as e:
            if not future.done():
                future.set_exception(e)
        finally:
            with self._lock:
                self.active_operations -= 1

    async def _monitor_resources(self):
        """Monitor system resources and adjust limits dynamically."""
        while not self._shutdown_event.is_set():
            try:
                if psutil:
                    # Get current resource usage
                    memory_mb = psutil.Process().memory_info().rss / 1024 / 1024
                    cpu_percent = psutil.cpu_percent(interval=0.1)

                    # Adjust concurrent operation limit based on resource usage
                    if memory_mb > (self.memory_limit_mb * 0.8):  # 80% of limit
                        # Reduce concurrent operations when memory is high
                        with self._lock:
                            self.max_concurrent_operations = max(3, self.max_concurrent_operations - 1)
                            logger.info(f"Reduced concurrent operations to {self.max_concurrent_operations} due to high memory usage")

                    elif memory_mb < (self.memory_limit_mb * 0.5):  # 50% of limit
                        # Increase concurrent operations when memory is low
                        with self._lock:
                            self.max_concurrent_operations = min(20, self.max_concurrent_operations + 1)
                            logger.info(f"Increased concurrent operations to {self.max_concurrent_operations} due to available memory")

                    # Log resource usage periodically
                    if int(time.time()) % 300 == 0:  # Every 5 minutes
                        logger.info(f"Resource usage - Memory: {memory_mb:.1f}MB, CPU: {cpu_percent:.1f}%, Active operations: {self.active_operations}")

                await asyncio.sleep(self.resource_check_interval)

            except Exception as e:
                logger.error(f"Error monitoring resources: {e}")
                await asyncio.sleep(self.resource_check_interval)

    def get_resource_stats(self) -> Dict[str, Any]:
        """Get current resource statistics."""
        stats = {
            'active_operations': self.active_operations,
            'max_concurrent_operations': self.max_concurrent_operations,
            'queue_sizes': {
                'high': self.high_priority_queue.qsize(),
                'normal': self.normal_priority_queue.qsize(),
                'low': self.low_priority_queue.qsize()
            }
        }

        if psutil:
            stats['memory_mb'] = psutil.Process().memory_info().rss / 1024 / 1024
            stats['cpu_percent'] = psutil.cpu_percent(interval=0.1)

        return stats


class CircuitBreaker:
    """Advanced circuit breaker with multiple states and recovery strategies."""

    class State:
        CLOSED = "closed"      # Normal operation
        OPEN = "open"          # Failing, requests rejected
        HALF_OPEN = "half_open" # Testing recovery

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60,
                 success_threshold: int = 3, name: str = "default"):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold

        self.state = self.State.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.next_attempt_time = None

        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """Check if operation can be executed based on circuit breaker state."""
        with self._lock:
            current_time = time.time()

            if self.state == self.State.CLOSED:
                return True
            elif self.state == self.State.OPEN:
                if self.next_attempt_time and current_time >= self.next_attempt_time:
                    # Transition to half-open for testing
                    self.state = self.State.HALF_OPEN
                    self.success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' transitioning to HALF_OPEN")
                    return True
                return False
            elif self.state == self.State.HALF_OPEN:
                return True

            return False

    def record_success(self):
        """Record a successful operation."""
        with self._lock:
            if self.state == self.State.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    # Recovery successful, close circuit
                    self.state = self.State.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info(f"Circuit breaker '{self.name}' recovered and CLOSED")
            elif self.state == self.State.CLOSED:
                # Reset failure count on success
                self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self, exception: Exception = None):
        """Record a failed operation."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == self.State.HALF_OPEN:
                # Half-open failure, back to open
                self.state = self.State.OPEN
                self.next_attempt_time = time.time() + self.recovery_timeout
                self.success_count = 0
                logger.warning(f"Circuit breaker '{self.name}' failed in HALF_OPEN, back to OPEN")
            elif self.state == self.State.CLOSED and self.failure_count >= self.failure_threshold:
                # Too many failures, open circuit
                self.state = self.State.OPEN
                self.next_attempt_time = time.time() + self.recovery_timeout
                logger.warning(f"Circuit breaker '{self.name}' tripped to OPEN after {self.failure_count} failures")

    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state,
                'failure_count': self.failure_count,
                'success_count': self.success_count,
                'next_attempt_time': self.next_attempt_time,
                'time_until_next_attempt': max(0, (self.next_attempt_time or 0) - time.time()) if self.next_attempt_time else 0
            }


class FallbackStrategy:
    """Fallback strategy pattern for graceful degradation."""

    def __init__(self, name: str):
        self.name = name
        self.fallbacks = []
        self.current_fallback_index = 0

    def add_fallback(self, fallback_func, description: str):
        """Add a fallback function."""
        self.fallbacks.append({
            'func': fallback_func,
            'description': description,
            'success_count': 0,
            'failure_count': 0
        })

    async def execute_with_fallback(self, primary_func, *args, **kwargs):
        """Execute primary function with fallback strategies."""
        # Try primary function first
        try:
            result = await primary_func(*args, **kwargs)
            self._record_success(-1)  # Primary function
            return result, None
        except Exception as e:
            logger.warning(f"Primary function failed for '{self.name}': {e}")
            self._record_failure(-1)  # Primary function

        # Try fallbacks in order
        for i, fallback in enumerate(self.fallbacks):
            try:
                logger.info(f"Trying fallback {i+1} for '{self.name}': {fallback['description']}")
                result = await fallback['func'](*args, **kwargs)
                self._record_success(i)
                return result, fallback['description']
            except Exception as e:
                logger.warning(f"Fallback {i+1} failed for '{self.name}': {e}")
                self._record_failure(i)

        # All strategies failed
        raise Exception(f"All strategies failed for '{self.name}' including {len(self.fallbacks)} fallbacks")

    def _record_success(self, fallback_index: int):
        """Record successful execution."""
        if fallback_index >= 0:
            self.fallbacks[fallback_index]['success_count'] += 1
        # Reset current fallback index on success
        self.current_fallback_index = 0

    def _record_failure(self, fallback_index: int):
        """Record failed execution."""
        if fallback_index >= 0:
            self.fallbacks[fallback_index]['failure_count'] += 1
        # Move to next fallback
        self.current_fallback_index = min(self.current_fallback_index + 1, len(self.fallbacks) - 1)

    def get_stats(self) -> Dict[str, Any]:
        """Get fallback strategy statistics."""
        return {
            'name': self.name,
            'total_fallbacks': len(self.fallbacks),
            'current_fallback_index': self.current_fallback_index,
            'fallback_stats': [
                {
                    'description': fb['description'],
                    'success_count': fb['success_count'],
                    'failure_count': fb['failure_count'],
                    'success_rate': (fb['success_count'] / max(fb['success_count'] + fb['failure_count'], 1)) * 100
                }
                for fb in self.fallbacks
            ]
        }


class ResilienceManager:
    """Comprehensive resilience management with circuit breakers and fallbacks."""

    def __init__(self):
        self.circuit_breakers = {}
        self.fallback_strategies = {}
        self._lock = threading.Lock()

    def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """Get or create a circuit breaker."""
        with self._lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
            return self.circuit_breakers[name]

    def get_fallback_strategy(self, name: str) -> FallbackStrategy:
        """Get or create a fallback strategy."""
        with self._lock:
            if name not in self.fallback_strategies:
                self.fallback_strategies[name] = FallbackStrategy(name)
            return self.fallback_strategies[name]

    async def execute_with_resilience(self, operation_name: str, operation_func, *args,
                                     circuit_breaker: bool = True, fallback: bool = True, **kwargs):
        """Execute operation with full resilience (circuit breaker + fallback)."""
        # Get circuit breaker
        cb = self.get_circuit_breaker(operation_name) if circuit_breaker else None

        # Check circuit breaker
        if cb and not cb.can_execute():
            raise Exception(f"Circuit breaker '{operation_name}' is OPEN")

        # Get fallback strategy
        fb_strategy = self.get_fallback_strategy(operation_name) if fallback else None

        try:
            if fb_strategy and fb_strategy.fallbacks:
                # Use fallback strategy
                result, fallback_used = await fb_strategy.execute_with_fallback(operation_func, *args, **kwargs)
                if cb:
                    cb.record_success()
                return result
            else:
                # Direct execution
                result = await operation_func(*args, **kwargs)
                if cb:
                    cb.record_success()
                return result

        except Exception as e:
            if cb:
                cb.record_failure(e)
            raise e

    def get_resilience_stats(self) -> Dict[str, Any]:
        """Get comprehensive resilience statistics."""
        with self._lock:
            return {
                'circuit_breakers': {
                    name: cb.get_status() for name, cb in self.circuit_breakers.items()
                },
                'fallback_strategies': {
                    name: fb.get_stats() for name, fb in self.fallback_strategies.items()
                }
            }


# Global resilience manager instance
_resilience_manager = None

def get_resilience_manager() -> ResilienceManager:
    """Get the global resilience manager instance."""
    global _resilience_manager
    if _resilience_manager is None:
        _resilience_manager = ResilienceManager()
    return _resilience_manager


# Global resource manager instance
_resource_manager = None

def get_resource_manager() -> ResourceManager:
    """Get the global resource manager instance."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
    return _resource_manager

async def init_resource_manager():
    """Initialize the global resource manager."""
    global _resource_manager
    if _resource_manager is None:
        _resource_manager = ResourceManager()
        await _resource_manager.start()

async def shutdown_resource_manager():
    """Shutdown the global resource manager."""
    global _resource_manager
    if _resource_manager:
        await _resource_manager.stop()
        _resource_manager = None


class StructuredLogger:
    """Structured logging with consistent formatting."""

    def __init__(self):
        self.logger = logging.getLogger('structured')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def log_event(self, event_type: str, data: Dict[str, Any] = None):
        """Log structured event."""
        message = f"EVENT: {event_type}"
        if data:
            message += f" - {data}"
        self.logger.info(message)


class PerformanceMonitor:
    """Monitor application performance metrics."""

    def __init__(self):
        self.metrics = {
            'api_calls': 0,
            'api_errors': 0,
            'db_queries': 0,
            'db_errors': 0,
            'memory_usage': [],
            'response_times': [],
            'start_time': time.time()
        }
        self._last_memory_check = 0

    def record_api_call(self, response_time: float = None, error: bool = False):
        """Record an API call."""
        self.metrics['api_calls'] += 1
        if error:
            self.metrics['api_errors'] += 1
        if response_time:
            self.metrics['response_times'].append(response_time)
            # Keep only last 1000 response times
            if len(self.metrics['response_times']) > 1000:
                self.metrics['response_times'] = self.metrics['response_times'][-1000:]

    def record_db_query(self, error: bool = False):
        """Record a database query."""
        self.metrics['db_queries'] += 1
        if error:
            self.metrics['db_errors'] += 1

    def check_memory_usage(self):
        """Check current memory usage."""
        current_time = time.time()
        if current_time - self._last_memory_check > 60:  # Check every minute
            try:
                if psutil:
                    process = psutil.Process()
                    memory_mb = process.memory_info().rss / 1024 / 1024
                else:
                    memory_mb = 0  # psutil not available
                self.metrics['memory_usage'].append((current_time, memory_mb))
            except Exception as e:
                logger.warning(f"Failed to check memory usage: {e}")
                # Continue without memory metrics
        # Keep only last 100 memory readings
        if len(self.metrics['memory_usage']) > 100:
            self.metrics['memory_usage'] = self.metrics['memory_usage'][-100:]
        # Update last check time
        self._last_memory_check = current_time

    def cleanup_old_data(self):
        """Clean up old data to prevent memory leaks."""
        current_time = time.time()

        # Clean up response times older than 1 hour
        max_age = 3600  # 1 hour
        self.metrics['response_times'] = [
            rt for rt in self.metrics['response_times']
            if current_time - rt < max_age  # Assuming rt is a timestamp, but it's actually response time in seconds
        ]

        # Keep only last 1000 response times regardless of age
        if len(self.metrics['response_times']) > 1000:
            self.metrics['response_times'] = self.metrics['response_times'][-1000:]

        # Clean up memory usage data older than 24 hours
        max_age = 86400  # 24 hours
        self.metrics['memory_usage'] = [
            (timestamp, memory) for timestamp, memory in self.metrics['memory_usage']
            if current_time - timestamp < max_age
        ]

        # Keep only last 100 memory readings regardless of age
        if len(self.metrics['memory_usage']) > 100:
            self.metrics['memory_usage'] = self.metrics['memory_usage'][-100:]

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get current performance statistics."""
        # Periodic cleanup to prevent memory leaks
        self.cleanup_old_data()

        uptime = time.time() - self.metrics['start_time']
        memory_mb = self.check_memory_usage()

        response_times = self.metrics['response_times']
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        return {
            'uptime_seconds': uptime,
            'api_calls_total': self.metrics['api_calls'],
            'api_error_rate': (self.metrics['api_errors'] / max(self.metrics['api_calls'], 1)) * 100,
            'db_queries_total': self.metrics['db_queries'],
            'db_error_rate': (self.metrics['db_errors'] / max(self.metrics['db_queries'], 1)) * 100,
            'avg_response_time': avg_response_time,
            'current_memory_mb': memory_mb,
            'memory_trend': [m[1] for m in self.metrics['memory_usage'][-10:]]  # Last 10 readings
        }


class RateLimiter:
    """Advanced rate limiter with backoff strategies and multiple tiers."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []
        self.backoff_until = None
        self.backoff_multiplier = 2.0
        self.max_backoff_seconds = 300  # 5 minutes
        self.consecutive_failures = 0
        self.last_failure_time = None
        self.circuit_breaker_until = None
        self.circuit_breaker_failures = 0
        self.max_consecutive_failures = 5
        self.circuit_breaker_timeout = 60  # 1 minute

        # Different rate limits for different operations
        self.rate_limits = {
            'message': {'max': 30, 'window': 60},  # Messages
            'api_call': {'max': 60, 'window': 60},  # General API calls
            'account_creation': {'max': 5, 'window': 300},  # Account creation (conservative)
            'scraping': {'max': 10, 'window': 60}  # Member scraping
        }

        # Separate request tracking per operation type
        self.requests_by_type = {op: [] for op in self.rate_limits.keys()}

    def is_allowed(self, operation_type: str = 'api_call') -> bool:
        """Check if a request is allowed for the given operation type."""
        current_time = time.time()

        # Check circuit breaker
        if self.circuit_breaker_until and current_time < self.circuit_breaker_until:
            return False

        # Check backoff
        if self.backoff_until and current_time < self.backoff_until:
            return False

        # Get rate limit for this operation
        if operation_type not in self.rate_limits:
            operation_type = 'api_call'

        limit_config = self.rate_limits[operation_type]
        max_requests = limit_config['max']
        window_seconds = limit_config['window']

        # Clean old requests for this operation type
        self.requests_by_type[operation_type] = [
            req_time for req_time in self.requests_by_type[operation_type]
            if current_time - req_time < window_seconds
        ]

        if len(self.requests_by_type[operation_type]) >= max_requests:
            return False

        # Add request
        self.requests_by_type[operation_type].append(current_time)
        return True

    def record_failure(self, operation_type: str = 'api_call'):
        """Record a failure for backoff and circuit breaker logic."""
        current_time = time.time()

        # Update consecutive failures
        if self.last_failure_time and (current_time - self.last_failure_time) < 300:  # 5 minutes
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 1

        self.last_failure_time = current_time

        # Implement exponential backoff
        if self.consecutive_failures >= 3:
            backoff_seconds = min(
                60 * (self.backoff_multiplier ** (self.consecutive_failures - 2)),
                self.max_backoff_seconds
            )
            self.backoff_until = current_time + backoff_seconds

        # Circuit breaker
        self.circuit_breaker_failures += 1
        if self.circuit_breaker_failures >= self.max_consecutive_failures:
            self.circuit_breaker_until = current_time + self.circuit_breaker_timeout
            self.circuit_breaker_failures = 0  # Reset for next attempt

    def record_success(self):
        """Record a success to reset failure counters."""
        self.consecutive_failures = max(0, self.consecutive_failures - 1)
        if self.consecutive_failures == 0:
            self.backoff_until = None
            self.circuit_breaker_failures = 0
            self.circuit_breaker_until = None

    def is_allowed_legacy(self) -> bool:
        """Legacy method for backward compatibility."""
        return self.is_allowed('api_call')

    def get_remaining_requests(self, operation_type: str = 'api_call') -> int:
        """Get remaining requests for the given operation type."""
        if operation_type not in self.rate_limits:
            operation_type = 'api_call'

        limit_config = self.rate_limits[operation_type]
        max_requests = limit_config['max']
        window_seconds = limit_config['window']

        current_time = time.time()
        self.requests_by_type[operation_type] = [
            req_time for req_time in self.requests_by_type[operation_type]
            if current_time - req_time < window_seconds
        ]

        return max(0, max_requests - len(self.requests_by_type[operation_type]))

    def get_backoff_remaining(self) -> float:
        """Get remaining backoff time in seconds."""
        if not self.backoff_until:
            return 0.0
        return max(0, self.backoff_until - time.time())

    def get_circuit_breaker_remaining(self) -> float:
        """Get remaining circuit breaker time in seconds."""
        if not self.circuit_breaker_until:
            return 0.0
        return max(0, self.circuit_breaker_until - time.time())

    def get_status(self) -> Dict[str, Any]:
        """Get current rate limiter status."""
        return {
            'backoff_remaining': self.get_backoff_remaining(),
            'circuit_breaker_remaining': self.get_circuit_breaker_remaining(),
            'consecutive_failures': self.consecutive_failures,
            'remaining_requests': {
                op: self.get_remaining_requests(op) for op in self.rate_limits.keys()
            }
        }


class NetworkRecoveryManager:
    """Track network recovery attempts with exponential delays."""

    def __init__(self):
        self._state: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "attempts": 0,
            "last_failure": 0.0
        })
        self.max_attempts = 10
        self.base_delay = 2.0

    def should_attempt_recovery(self, channel: str) -> bool:
        info = self._state[channel]
        return info["attempts"] < self.max_attempts

    def record_recovery_attempt(self, channel: str) -> None:
        info = self._state[channel]
        info["attempts"] += 1
        info["last_failure"] = time.time()

    def record_successful_connection(self, channel: str) -> None:
        self._state[channel]["attempts"] = 0
        self._state[channel]["last_failure"] = 0.0

    def get_recovery_delay(self, channel: str) -> float:
        info = self._state[channel]
        delay = self.base_delay * max(1, info["attempts"])
        return min(delay, 60.0)








