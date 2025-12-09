#!/usr/bin/env python3
"""
HTTP Connection Pool Manager - Reusable connection pools for external APIs.

Features:
- aiohttp ClientSession pooling
- Automatic connection reuse
- Request/response middleware
- Rate limiting integration
- Connection health monitoring
- Timeout management
"""

import asyncio
import aiohttp
import logging
from typing import Optional, Dict, Any, Callable, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import time

logger = logging.getLogger(__name__)


@dataclass
class HTTPMetrics:
    """HTTP connection metrics."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_response_time: float = 0.0
    avg_response_time: float = 0.0
    active_connections: int = 0


class HTTPConnectionPool:
    """
    Manages HTTP connection pools for external API calls.
    """

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize HTTP connection pool manager.

        Args:
            config: Pool configuration
        """
        self.config = config or {}
        self.pools: Dict[str, aiohttp.ClientSession] = {}
        self.metrics = HTTPMetrics()
        self.rate_limiters: Dict[str, Any] = {}

        # Default configuration
        self.max_connections = self.config.get('max_connections', 50)
        self.max_connections_per_host = self.config.get('max_connections_per_host', 10)
        self.connection_timeout = self.config.get('connection_timeout', 30)
        self.request_timeout = self.config.get('request_timeout', 60)

        # Connection pool settings
        self.connector_kwargs = {
            'limit': self.max_connections,
            'limit_per_host': self.max_connections_per_host,
            'ttl_dns_cache': 300,  # 5 minutes DNS cache
            'use_dns_cache': True,
            'keepalive_timeout': 60,
            'enable_cleanup_closed': True,
        }

    async def get_session(self, domain: str) -> aiohttp.ClientSession:
        """
        Get or create a ClientSession for a domain.

        Args:
            domain: Target domain/host

        Returns:
            aiohttp ClientSession
        """
        if domain not in self.pools:
            # Create new session for this domain
            timeout = aiohttp.ClientTimeout(
                total=self.request_timeout,
                connect=self.connection_timeout
            )

            connector = aiohttp.TCPConnector(**self.connector_kwargs)

            self.pools[domain] = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                trust_env=True  # Use environment proxy settings
            )

            logger.debug(f"Created HTTP session pool for {domain}")

        return self.pools[domain]

    @asynccontextmanager
    async def request(self, method: str, url: str, **kwargs):
        """
        Make an HTTP request using the connection pool.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional request parameters

        Yields:
            aiohttp.ClientResponse
        """
        # Extract domain from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc

        session = await self.get_session(domain)

        start_time = time.time()
        self.metrics.total_requests += 1
        self.metrics.active_connections += 1

        try:
            # Apply rate limiting if configured
            await self._apply_rate_limiting(domain)

            # Make request with automatic retry
            response = await self._make_request_with_retry(session, method, url, **kwargs)

            self.metrics.successful_requests += 1
            yield response

        except Exception as e:
            self.metrics.failed_requests += 1
            logger.error(f"HTTP request failed: {method} {url} - {e}")
            raise
        finally:
            response_time = time.time() - start_time
            self.metrics.total_response_time += response_time
            self.metrics.avg_response_time = (
                self.metrics.total_response_time / self.metrics.total_requests
            )
            self.metrics.active_connections -= 1

    async def _make_request_with_retry(
        self,
        session: aiohttp.ClientSession,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Make HTTP request with automatic retry logic.

        Args:
            session: aiohttp ClientSession
            method: HTTP method
            url: Request URL
            max_retries: Maximum retry attempts
            **kwargs: Request parameters

        Returns:
            aiohttp ClientResponse
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                response = await session.request(method, url, **kwargs)

                # Check for server errors that should be retried
                if response.status >= 500:
                    response.close()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue

                return response

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    raise e

        raise last_exception

    async def _apply_rate_limiting(self, domain: str):
        """
        Apply rate limiting for a domain if configured.

        Args:
            domain: Target domain
        """
        if domain in self.rate_limiters:
            limiter = self.rate_limiters[domain]
            await limiter.wait_if_needed()

    def add_rate_limiter(self, domain: str, limiter):
        """
        Add a rate limiter for a specific domain.

        Args:
            domain: Target domain
            limiter: Rate limiter instance
        """
        self.rate_limiters[domain] = limiter

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make GET request."""
        async with self.request('GET', url, **kwargs) as response:
            return response

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make POST request."""
        async with self.request('POST', url, **kwargs) as response:
            return response

    async def put(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make PUT request."""
        async with self.request('PUT', url, **kwargs) as response:
            return response

    async def delete(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make DELETE request."""
        async with self.request('DELETE', url, **kwargs) as response:
            return response

    def get_metrics(self) -> Dict[str, Any]:
        """Get HTTP connection metrics."""
        return {
            'total_requests': self.metrics.total_requests,
            'successful_requests': self.metrics.successful_requests,
            'failed_requests': self.metrics.failed_requests,
            'success_rate': (
                self.metrics.successful_requests / self.metrics.total_requests * 100
                if self.metrics.total_requests > 0 else 0
            ),
            'avg_response_time': self.metrics.avg_response_time,
            'active_connections': self.metrics.active_connections,
            'pool_count': len(self.pools)
        }

    async def close_all(self):
        """Close all connection pools."""
        for session in self.pools.values():
            await session.close()

        self.pools.clear()
        logger.info("Closed all HTTP connection pools")


# Global instance
_http_pool = None

def get_http_connection_pool(config: Dict[str, Any] = None) -> HTTPConnectionPool:
    """Get the global HTTP connection pool instance."""
    global _http_pool

    if _http_pool is None:
        _http_pool = HTTPConnectionPool(config)

    return _http_pool


