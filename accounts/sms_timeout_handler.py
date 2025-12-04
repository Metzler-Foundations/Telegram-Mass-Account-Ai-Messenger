#!/usr/bin/env python3
"""SMS timeout handling - Handle expired verification codes."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class SMSTimeoutHandler:
    """Handles SMS verification code timeouts."""
    
    def __init__(self, timeout_seconds: int = 300, max_retries: int = 3):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
    
    async def wait_for_code(
        self,
        retrieve_func,
        phone_number: str,
        fallback_providers: Optional[list] = None
    ) -> Optional[str]:
        """Wait for SMS code with timeout and retry."""
        start_time = datetime.now()
        attempts = 0
        
        while attempts < self.max_retries:
            try:
                # Try to retrieve code with timeout
                code = await asyncio.wait_for(
                    retrieve_func(phone_number),
                    timeout=self.timeout_seconds
                )
                
                if code:
                    return code
                
                attempts += 1
                if attempts < self.max_retries:
                    logger.warning(f"Code retrieval attempt {attempts} failed, retrying...")
                    await asyncio.sleep(5)
                
            except asyncio.TimeoutError:
                logger.error(f"SMS code timeout after {self.timeout_seconds}s")
                attempts += 1
                
                # Try fallback provider
                if fallback_providers and attempts < self.max_retries:
                    logger.info("Trying fallback SMS provider...")
                    # Fallback logic here
                    await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"SMS retrieval error: {e}")
                attempts += 1
                if attempts < self.max_retries:
                    await asyncio.sleep(5)
        
        logger.error(f"Failed to retrieve SMS code after {attempts} attempts")
        return None


_sms_timeout_handler = None

def get_sms_timeout_handler():
    global _sms_timeout_handler
    if _sms_timeout_handler is None:
        _sms_timeout_handler = SMSTimeoutHandler()
    return _sms_timeout_handler

