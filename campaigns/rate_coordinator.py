#!/usr/bin/env python3
"""FloodWait coordination across accounts."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class FloodWaitCoordinator:
    """Coordinates FloodWait handling across multiple accounts."""
    
    def __init__(self):
        self.account_cooldowns: Dict[str, datetime] = {}
        self.lock = asyncio.Lock()
    
    async def record_floodwait(self, account_id: str, wait_seconds: int):
        """Record FloodWait event for account."""
        async with self.lock:
            cooldown_until = datetime.now() + timedelta(seconds=wait_seconds)
            self.account_cooldowns[account_id] = cooldown_until
            logger.warning(f"Account {account_id} on cooldown until {cooldown_until}")
    
    async def is_available(self, account_id: str) -> bool:
        """Check if account is available (not in cooldown)."""
        async with self.lock:
            if account_id not in self.account_cooldowns:
                return True
            
            cooldown = self.account_cooldowns[account_id]
            if datetime.now() >= cooldown:
                del self.account_cooldowns[account_id]
                return True
            
            return False
    
    async def get_available_account(self, account_ids: list) -> Optional[str]:
        """Get first available account from list."""
        for account_id in account_ids:
            if await self.is_available(account_id):
                return account_id
        
        return None
    
    async def wait_for_available(self, account_ids: list, timeout: float = 60.0) -> Optional[str]:
        """Wait for an account to become available."""
        start = datetime.now()
        
        while (datetime.now() - start).total_seconds() < timeout:
            account = await self.get_available_account(account_ids)
            if account:
                return account
            
            await asyncio.sleep(1)
        
        logger.error("No accounts available within timeout")
        return None


_coordinator = None

def get_floodwait_coordinator():
    global _coordinator
    if _coordinator is None:
        _coordinator = FloodWaitCoordinator()
    return _coordinator


