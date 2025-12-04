#!/usr/bin/env python3
"""Telegram API retry wrapper with connection handling."""

import asyncio
import logging
from pyrogram.errors import (
    FloodWait, AuthKeyUnregistered, UserDeactivated,
    SessionPasswordNeeded, PhoneNumberInvalid, NetworkError
)
from utils.retry_logic import retry_on_exception

logger = logging.getLogger(__name__)


class TelegramRetryWrapper:
    """Wraps Telegram client with retry logic."""
    
    @staticmethod
    @retry_on_exception(
        exceptions=(NetworkError, ConnectionError, TimeoutError),
        max_attempts=5,
        base_delay=2.0,
        max_delay=30.0
    )
    async def send_message_with_retry(client, *args, **kwargs):
        """Send message with automatic retry on network errors."""
        try:
            return await client.send_message(*args, **kwargs)
        except FloodWait as e:
            logger.warning(f"FloodWait: {e.value}s")
            await asyncio.sleep(e.value)
            return await client.send_message(*args, **kwargs)
    
    @staticmethod
    @retry_on_exception(
        exceptions=(NetworkError, ConnectionError),
        max_attempts=3,
        base_delay=1.0
    )
    async def get_messages_with_retry(client, *args, **kwargs):
        """Get messages with retry."""
        return await client.get_messages(*args, **kwargs)


