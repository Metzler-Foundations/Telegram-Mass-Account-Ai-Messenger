#!/usr/bin/env python3
"""Async DNS resolution to prevent blocking."""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AsyncDNSResolver:
    """Non-blocking DNS resolution."""
    
    @staticmethod
    async def resolve_hostname(hostname: str, timeout: float = 5.0) -> Optional[str]:
        """Resolve hostname asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            
            # Run blocking getaddrinfo in thread pool
            result = await asyncio.wait_for(
                loop.getaddrinfo(
                    hostname, None,
                    family=0, type=0, proto=0, flags=0
                ),
                timeout=timeout
            )
            
            if result:
                ip = result[0][4][0]
                logger.debug(f"Resolved {hostname} to {ip}")
                return ip
            
            return None
            
        except asyncio.TimeoutError:
            logger.warning(f"DNS resolution timeout for {hostname}")
            return None
        except Exception as e:
            logger.error(f"DNS resolution failed for {hostname}: {e}")
            return None


async def resolve_dns(hostname: str) -> Optional[str]:
    """Resolve DNS without blocking."""
    return await AsyncDNSResolver.resolve_hostname(hostname)



