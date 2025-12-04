#!/usr/bin/env python3
"""SMS timeout handling - Handle expired verification codes."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class SMSTimeoutHandler:
    """Handles SMS verification code timeouts with enhanced retry and expiration logic."""
    
    def __init__(self, timeout_seconds: int = 300, max_retries: int = 3, code_expiry_seconds: int = 600):
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.code_expiry_seconds = code_expiry_seconds  # Telegram codes typically expire after 10 min
        self.code_request_times = {}  # Track when codes were requested
    
    async def wait_for_code(
        self,
        retrieve_func,
        phone_number: str,
        fallback_providers: Optional[list] = None,
        request_time: Optional[datetime] = None
    ) -> Optional[str]:
        """Wait for SMS code with timeout, retry, and expiration handling."""
        start_time = datetime.now()
        request_time = request_time or start_time
        self.code_request_times[phone_number] = request_time
        attempts = 0
        
        while attempts < self.max_retries:
            # Check if code has expired (Telegram codes expire after ~10 minutes)
            elapsed_since_request = (datetime.now() - request_time).total_seconds()
            if elapsed_since_request > self.code_expiry_seconds:
                logger.error(f"SMS code expired after {elapsed_since_request:.0f}s (max: {self.code_expiry_seconds}s)")
                return None
            
            # Adjust timeout based on remaining time
            remaining_time = self.code_expiry_seconds - elapsed_since_request
            actual_timeout = min(self.timeout_seconds, remaining_time)
            
            try:
                # Try to retrieve code with adjusted timeout
                code = await asyncio.wait_for(
                    retrieve_func(phone_number),
                    timeout=actual_timeout
                )
                
                if code:
                    # Clean up tracking
                    if phone_number in self.code_request_times:
                        del self.code_request_times[phone_number]
                    return code
                
                attempts += 1
                if attempts < self.max_retries:
                    # Exponential backoff
                    wait_time = min(5 * (2 ** (attempts - 1)), 30)
                    logger.warning(f"Code retrieval attempt {attempts} failed, retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                
            except asyncio.TimeoutError:
                logger.error(f"SMS code timeout after {actual_timeout:.0f}s (attempt {attempts + 1}/{self.max_retries})")
                attempts += 1
                
                # Try fallback provider if available and not expired
                if fallback_providers and attempts < self.max_retries and elapsed_since_request < self.code_expiry_seconds:
                    logger.info("Trying fallback SMS provider...")
                    await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"SMS retrieval error: {e}")
                attempts += 1
                if attempts < self.max_retries:
                    wait_time = min(5 * (2 ** (attempts - 1)), 30)
                    await asyncio.sleep(wait_time)
        
        # Clean up tracking
        if phone_number in self.code_request_times:
            del self.code_request_times[phone_number]
        
        logger.error(f"Failed to retrieve SMS code after {attempts} attempts (total time: {elapsed_since_request:.0f}s)")
        return None
    
    def is_code_expired(self, phone_number: str) -> bool:
        """Check if a requested code has expired."""
        if phone_number not in self.code_request_times:
            return False
        
        elapsed = (datetime.now() - self.code_request_times[phone_number]).total_seconds()
        return elapsed > self.code_expiry_seconds


_sms_timeout_handler = None

def get_sms_timeout_handler():
    global _sms_timeout_handler
    if _sms_timeout_handler is None:
        _sms_timeout_handler = SMSTimeoutHandler()
    return _sms_timeout_handler



