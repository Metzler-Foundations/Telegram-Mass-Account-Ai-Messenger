#!/usr/bin/env python3
"""Network configuration - Timeouts and connection settings."""

import aiohttp
import logging

logger = logging.getLogger(__name__)


class NetworkConfig:
    """Network configuration manager."""

    # Increased timeouts for reliability
    TELEGRAM_API_TIMEOUT = 60.0  # 60 seconds
    SMS_API_TIMEOUT = 45.0
    PROXY_CHECK_TIMEOUT = 15.0
    GEMINI_API_TIMEOUT = 90.0

    # Connection settings
    MAX_CONNECTIONS = 100
    KEEPALIVE_TIMEOUT = 30.0

    @staticmethod
    def get_aiohttp_timeout():
        """Get aiohttp timeout configuration."""
        return aiohttp.ClientTimeout(
            total=NetworkConfig.TELEGRAM_API_TIMEOUT,
            connect=10.0,
            sock_read=30.0,
            sock_connect=10.0,
        )

    @staticmethod
    def get_connector():
        """Get aiohttp connector with connection pooling."""
        return aiohttp.TCPConnector(
            limit=NetworkConfig.MAX_CONNECTIONS,
            limit_per_host=30,
            ttl_dns_cache=300,
            keepalive_timeout=NetworkConfig.KEEPALIVE_TIMEOUT,
            force_close=False,
            enable_cleanup_closed=True,
        )
