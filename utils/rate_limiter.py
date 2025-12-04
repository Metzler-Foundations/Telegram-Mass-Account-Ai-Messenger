#!/usr/bin/env python3
"""
Rate Limiter - Prevent abuse and cost overruns.

Features:
- Token bucket algorithm
- Sliding window rate limiting
- Per-resource rate limits
- Cost-based limiting
- Burst allowance
- Rate limit tracking
"""

import time
import threading
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimit:
    """Rate limit configuration."""
    max_requests: int
    window_seconds: float
    burst_allowance: int = 0  # Extra requests allowed in burst


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.
    
    Allows bursts while maintaining average rate.
    """
    
    def __init__(
        self,
        rate: float,  # Tokens per second
        capacity: int,  # Max tokens
        initial_tokens: Optional[int] = None
    ):
        """
        Initialize token bucket.
        
        Args:
            rate: Token refill rate (per second)
            capacity: Maximum tokens in bucket
            initial_tokens: Starting tokens (defaults to capacity)
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = initial_tokens if initial_tokens is not None else capacity
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def _refill(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update
        
        # Add tokens based on rate
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now
    
    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens consumed, False if rate limited
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            
            return False
    
    def peek(self) -> float:
        """
        Check available tokens without consuming.
        
        Returns:
            Current token count
        """
        with self.lock:
            self._refill()
            return self.tokens
    
    def wait_time(self, tokens: int = 1) -> float:
        """
        Calculate wait time for tokens to be available.
        
        Args:
            tokens: Desired token count
            
        Returns:
            Seconds to wait (0 if available now)
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                return 0.0
            
            needed = tokens - self.tokens
            return needed / self.rate


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter.
    
    More accurate than fixed windows, prevents boundary issues.
    """
    
    def __init__(self, max_requests: int, window_seconds: float):
        """
        Initialize sliding window limiter.
        
        Args:
            max_requests: Maximum requests in window
            window_seconds: Time window size
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: deque = deque()
        self.lock = threading.Lock()
    
    def _cleanup_old_requests(self):
        """Remove requests outside window."""
        cutoff = time.time() - self.window_seconds
        
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()
    
    def can_proceed(self) -> bool:
        """
        Check if request can proceed.
        
        Returns:
            True if under limit, False if rate limited
        """
        with self.lock:
            self._cleanup_old_requests()
            return len(self.requests) < self.max_requests
    
    def record_request(self) -> bool:
        """
        Record a request and check if allowed.
        
        Returns:
            True if allowed, False if rate limited
        """
        with self.lock:
            self._cleanup_old_requests()
            
            if len(self.requests) >= self.max_requests:
                return False
            
            self.requests.append(time.time())
            return True
    
    def get_remaining(self) -> int:
        """
        Get remaining requests in current window.
        
        Returns:
            Number of requests remaining
        """
        with self.lock:
            self._cleanup_old_requests()
            return max(0, self.max_requests - len(self.requests))
    
    def get_reset_time(self) -> float:
        """
        Get time until window resets.
        
        Returns:
            Seconds until reset (0 if window empty)
        """
        with self.lock:
            if not self.requests:
                return 0.0
            
            oldest = self.requests[0]
            reset_time = oldest + self.window_seconds
            return max(0.0, reset_time - time.time())


class MultiResourceRateLimiter:
    """
    Rate limiter supporting multiple resources.
    
    Each resource has independent limits.
    """
    
    def __init__(self):
        """Initialize multi-resource limiter."""
        self.limiters: Dict[str, SlidingWindowRateLimiter] = {}
        self.config: Dict[str, RateLimit] = {}
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = defaultdict(lambda: {
            'total_requests': 0,
            'rate_limited': 0,
            'last_request': None
        })
    
    def configure(self, resource: str, rate_limit: RateLimit):
        """
        Configure rate limit for resource.
        
        Args:
            resource: Resource identifier
            rate_limit: Rate limit configuration
        """
        with self.lock:
            self.config[resource] = rate_limit
            self.limiters[resource] = SlidingWindowRateLimiter(
                rate_limit.max_requests + rate_limit.burst_allowance,
                rate_limit.window_seconds
            )
        
        logger.info(
            f"Rate limit configured: {resource} = "
            f"{rate_limit.max_requests} req/{rate_limit.window_seconds}s "
            f"(burst: +{rate_limit.burst_allowance})"
        )
    
    def check_rate_limit(self, resource: str) -> Tuple[bool, Optional[float]]:
        """
        Check if request is allowed.
        
        Args:
            resource: Resource identifier
            
        Returns:
            Tuple of (allowed, retry_after_seconds)
        """
        with self.lock:
            # Auto-configure if not configured
            if resource not in self.limiters:
                # Default: 60 requests per minute
                self.configure(resource, RateLimit(60, 60.0))
            
            limiter = self.limiters[resource]
            stats = self.stats[resource]
            
            stats['total_requests'] += 1
            stats['last_request'] = datetime.now()
            
            if limiter.record_request():
                return True, None
            
            # Rate limited
            stats['rate_limited'] += 1
            retry_after = limiter.get_reset_time()
            
            logger.warning(
                f"Rate limit exceeded for {resource}. "
                f"Retry after {retry_after:.1f}s"
            )
            
            return False, retry_after
    
    def get_remaining(self, resource: str) -> int:
        """
        Get remaining requests for resource.
        
        Args:
            resource: Resource identifier
            
        Returns:
            Remaining requests
        """
        with self.lock:
            if resource not in self.limiters:
                return 999  # Unlimited if not configured
            
            return self.limiters[resource].get_remaining()
    
    def get_stats(self, resource: Optional[str] = None) -> dict:
        """
        Get rate limit statistics.
        
        Args:
            resource: Resource to get stats for (None = all)
            
        Returns:
            Statistics dictionary
        """
        with self.lock:
            if resource:
                return dict(self.stats[resource])
            
            return {res: dict(stats) for res, stats in self.stats.items()}
    
    def reset(self, resource: Optional[str] = None):
        """
        Reset rate limiter.
        
        Args:
            resource: Resource to reset (None = all)
        """
        with self.lock:
            if resource:
                if resource in self.limiters:
                    config = self.config[resource]
                    self.limiters[resource] = SlidingWindowRateLimiter(
                        config.max_requests + config.burst_allowance,
                        config.window_seconds
                    )
            else:
                for res, config in self.config.items():
                    self.limiters[res] = SlidingWindowRateLimiter(
                        config.max_requests + config.burst_allowance,
                        config.window_seconds
                    )


# Cost-based rate limiter
class CostBasedRateLimiter:
    """
    Rate limiter based on operation cost.
    
    Useful for limiting expensive operations (SMS, API calls, etc.)
    """
    
    def __init__(self, budget: float, window_seconds: float):
        """
        Initialize cost-based limiter.
        
        Args:
            budget: Cost budget per window
            window_seconds: Time window size
        """
        self.budget = budget
        self.window_seconds = window_seconds
        self.spending: deque = deque()  # (timestamp, cost) tuples
        self.lock = threading.Lock()
        
        # Statistics
        self.total_spent = 0.0
        self.total_operations = 0
        self.blocked_operations = 0
    
    def _cleanup_old_spending(self):
        """Remove spending outside window."""
        cutoff = time.time() - self.window_seconds
        
        while self.spending and self.spending[0][0] < cutoff:
            self.spending.popleft()
    
    def can_afford(self, cost: float) -> bool:
        """
        Check if cost is within budget.
        
        Args:
            cost: Operation cost
            
        Returns:
            True if affordable, False if over budget
        """
        with self.lock:
            self._cleanup_old_spending()
            
            current_spending = sum(c for _, c in self.spending)
            return current_spending + cost <= self.budget
    
    def record_spending(self, cost: float) -> bool:
        """
        Record spending and check if allowed.
        
        Args:
            cost: Operation cost
            
        Returns:
            True if allowed, False if over budget
        """
        with self.lock:
            self._cleanup_old_spending()
            
            current_spending = sum(c for _, c in self.spending)
            
            if current_spending + cost > self.budget:
                self.blocked_operations += 1
                logger.warning(
                    f"Cost budget exceeded: {current_spending + cost:.2f} > {self.budget:.2f}"
                )
                return False
            
            self.spending.append((time.time(), cost))
            self.total_spent += cost
            self.total_operations += 1
            return True
    
    def get_remaining_budget(self) -> float:
        """
        Get remaining budget in current window.
        
        Returns:
            Remaining budget
        """
        with self.lock:
            self._cleanup_old_spending()
            current_spending = sum(c for _, c in self.spending)
            return max(0.0, self.budget - current_spending)
    
    def get_stats(self) -> dict:
        """Get spending statistics."""
        with self.lock:
            self._cleanup_old_spending()
            current_spending = sum(c for _, c in self.spending)
            
            return {
                'budget': self.budget,
                'window_seconds': self.window_seconds,
                'current_spending': current_spending,
                'remaining_budget': self.budget - current_spending,
                'total_spent': self.total_spent,
                'total_operations': self.total_operations,
                'blocked_operations': self.blocked_operations,
                'utilization_pct': (current_spending / self.budget * 100) if self.budget > 0 else 0
            }


# Global rate limiter instance
_global_rate_limiter: Optional[MultiResourceRateLimiter] = None


def get_rate_limiter() -> MultiResourceRateLimiter:
    """
    Get global rate limiter instance.
    
    Returns:
        MultiResourceRateLimiter instance
    """
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = MultiResourceRateLimiter()
        
        # Configure default limits
        _global_rate_limiter.configure('proxy_health_check', RateLimit(60, 60.0))  # 60/min
        _global_rate_limiter.configure('sms_provider_smspool', RateLimit(10, 60.0))  # 10/min
        _global_rate_limiter.configure('sms_provider_textverified', RateLimit(10, 60.0))
        _global_rate_limiter.configure('sms_provider_sms_activate', RateLimit(15, 60.0))
        _global_rate_limiter.configure('telegram_api', RateLimit(20, 1.0, burst_allowance=5))  # 20/sec with burst
        _global_rate_limiter.configure('gemini_api', RateLimit(60, 60.0))  # 60/min
        _global_rate_limiter.configure('account_creation', RateLimit(5, 300.0))  # 5 per 5 min
        _global_rate_limiter.configure('campaign_send', RateLimit(50, 3600.0))  # 50/hour
        
        logger.info("Global rate limiter initialized with default limits")
    
    return _global_rate_limiter


# Decorator for rate-limited functions
def rate_limited(resource: str):
    """
    Decorator to rate limit function calls.
    
    Args:
        resource: Resource identifier
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            allowed, retry_after = limiter.check_rate_limit(resource)
            
            if not allowed:
                raise RateLimitExceeded(
                    f"Rate limit exceeded for {resource}. "
                    f"Retry after {retry_after:.1f}s"
                )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass





