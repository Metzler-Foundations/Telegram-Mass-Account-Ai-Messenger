#!/usr/bin/env python3
"""
Rate Limiter - Client-side rate limiting for API calls.

Features:
- Token bucket algorithm
- Domain-specific limits
- Automatic backoff
- Async support
- Configurable limits
"""

import asyncio
import time
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: float = 1.0
    burst_limit: int = 5
    backoff_factor: float = 2.0
    max_backoff: float = 60.0


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter implementation.
    """

    def __init__(self, config: RateLimitConfig):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config
        self.tokens = config.burst_limit
        self.last_update = time.time()
        self.backoff_until = 0
        self._lock = asyncio.Lock()

    async def wait_if_needed(self):
        """
        Wait if rate limit would be exceeded.

        This implements the token bucket algorithm with backoff.
        """
        async with self._lock:
            now = time.time()

            # Check if we're in backoff period
            if now < self.backoff_until:
                sleep_time = self.backoff_until - now
                logger.debug(f"Rate limit backoff: sleeping {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                self.backoff_until = now + sleep_time * self.config.backoff_factor
                return

            # Refill tokens based on time passed
            time_passed = now - self.last_update
            tokens_to_add = time_passed * self.config.requests_per_second
            self.tokens = min(self.config.burst_limit, self.tokens + tokens_to_add)
            self.last_update = now

            # Check if we have tokens
            if self.tokens >= 1:
                self.tokens -= 1
                # Reset backoff on successful request
                self.backoff_until = 0
            else:
                # No tokens available, enter backoff
                wait_time = (1 - self.tokens) / self.config.requests_per_second
                wait_time = min(wait_time, self.config.max_backoff)
                self.backoff_until = now + wait_time

                logger.debug(f"Rate limit exceeded: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)


class RateLimitManager:
    """
    Manages rate limiters for different domains/endpoints.
    """

    def __init__(self):
        """Initialize rate limit manager."""
        self.limiters: Dict[str, TokenBucketRateLimiter] = {}
        self.default_config = RateLimitConfig()

        # Domain-specific rate limits (requests per second)
        self.domain_limits = {
            'api.telegram.org': RateLimitConfig(requests_per_second=1.0, burst_limit=2),
            'api.sms-activate.org': RateLimitConfig(requests_per_second=2.0, burst_limit=5),
            'smshub.org': RateLimitConfig(requests_per_second=2.0, burst_limit=5),
            '5sim.net': RateLimitConfig(requests_per_second=1.0, burst_limit=3),
            'daisysms.com': RateLimitConfig(requests_per_second=2.0, burst_limit=5),
            'api.smspool.net': RateLimitConfig(requests_per_second=2.0, burst_limit=5),
            'textverified.com': RateLimitConfig(requests_per_second=1.0, burst_limit=3),
            'generativelanguage.googleapis.com': RateLimitConfig(requests_per_second=2.0, burst_limit=10),
        }

    def get_limiter(self, domain: str) -> TokenBucketRateLimiter:
        """
        Get or create a rate limiter for a domain.

        Args:
            domain: Target domain

        Returns:
            TokenBucketRateLimiter instance
        """
        if domain not in self.limiters:
            config = self.domain_limits.get(domain, self.default_config)
            self.limiters[domain] = TokenBucketRateLimiter(config)
            logger.debug(f"Created rate limiter for {domain}: {config.requests_per_second} req/s")

        return self.limiters[domain]

    def set_domain_limit(self, domain: str, config: RateLimitConfig):
        """
        Set custom rate limit for a domain.

        Args:
            domain: Target domain
            config: Rate limit configuration
        """
        self.limiters[domain] = TokenBucketRateLimiter(config)
        logger.info(f"Set custom rate limit for {domain}: {config.requests_per_second} req/s")

    async def wait_for_domain(self, domain: str):
        """
        Wait if rate limit would be exceeded for a domain.

        Args:
            domain: Target domain
        """
        limiter = self.get_limiter(domain)
        await limiter.wait_if_needed()

    def get_metrics(self) -> Dict[str, Any]:
        """Get rate limiting metrics."""
        return {
            'active_limiters': len(self.limiters),
            'domains': list(self.limiters.keys()),
            'default_config': {
                'requests_per_second': self.default_config.requests_per_second,
                'burst_limit': self.default_config.burst_limit
            }
        }


# Global instance
_rate_limit_manager = None

def get_rate_limit_manager() -> RateLimitManager:
    """Get the global rate limit manager instance."""
    global _rate_limit_manager

    if _rate_limit_manager is None:
        _rate_limit_manager = RateLimitManager()

    return _rate_limit_manager