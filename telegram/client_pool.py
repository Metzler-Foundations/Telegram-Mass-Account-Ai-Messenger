#!/usr/bin/env python3
"""Telegram client pooling - Reuse clients instead of reinitializing."""

import asyncio
import logging
from typing import Dict, Optional
from pyrogram import Client

logger = logging.getLogger(__name__)


class TelegramClientPool:
    """Pool of Pyrogram clients to avoid reinitialization."""
    
    def __init__(self):
        self._clients: Dict[str, Client] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
    
    async def get_client(self, phone_number: str, **client_kwargs) -> Optional[Client]:
        """Get or create client for phone number."""
        async with self._lock:
            if phone_number not in self._clients:
                try:
                    client = Client(
                        name=f"session_{phone_number}",
                        **client_kwargs
                    )
                    await client.start()
                    self._clients[phone_number] = client
                    self._locks[phone_number] = asyncio.Lock()
                    logger.info(f"Created new client for {phone_number}")
                except Exception as e:
                    logger.error(f"Failed to create client: {e}")
                    return None
            
            return self._clients.get(phone_number)
    
    async def release_client(self, phone_number: str):
        """Release (but don't stop) client."""
        # Client stays in pool for reuse
        pass
    
    async def remove_client(self, phone_number: str):
        """Remove and stop client."""
        async with self._lock:
            if phone_number in self._clients:
                try:
                    client = self._clients[phone_number]
                    await client.stop()
                    del self._clients[phone_number]
                    del self._locks[phone_number]
                    logger.info(f"Removed client for {phone_number}")
                except Exception as e:
                    logger.error(f"Error removing client: {e}")
    
    async def close_all(self):
        """Close all clients."""
        async with self._lock:
            for phone, client in self._clients.items():
                try:
                    await client.stop()
                except Exception as e:
                    logger.error(f"Error stopping client {phone}: {e}")
            
            self._clients.clear()
            self._locks.clear()
            logger.info("All clients closed")


_client_pool = None

def get_client_pool():
    global _client_pool
    if _client_pool is None:
        _client_pool = TelegramClientPool()
    return _client_pool

