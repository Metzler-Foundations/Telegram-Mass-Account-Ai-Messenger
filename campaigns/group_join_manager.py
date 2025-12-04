#!/usr/bin/env python3
"""Group join request management with cooldown."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class GroupJoinManager:
    """Manages group join requests with cooldown."""
    
    def __init__(self, cooldown_seconds: int = 300):
        self.cooldown_seconds = cooldown_seconds
        self.last_join: Dict[str, datetime] = {}
        self.lock = asyncio.Lock()
    
    async def can_join_group(self, account_id: str) -> tuple[bool, float]:
        """Check if account can join a group."""
        async with self.lock:
            if account_id not in self.last_join:
                return True, 0.0
            
            elapsed = (datetime.now() - self.last_join[account_id]).total_seconds()
            remaining = self.cooldown_seconds - elapsed
            
            if remaining <= 0:
                return True, 0.0
            
            return False, remaining
    
    async def record_join(self, account_id: str):
        """Record group join attempt."""
        async with self.lock:
            self.last_join[account_id] = datetime.now()
            logger.debug(f"Recorded group join for {account_id}")
    
    async def wait_for_cooldown(self, account_id: str):
        """Wait for cooldown to complete."""
        can_join, wait_time = await self.can_join_group(account_id)
        
        if not can_join:
            logger.info(f"Waiting {wait_time:.0f}s for group join cooldown: {account_id}")
            await asyncio.sleep(wait_time)


_manager = None

def get_group_join_manager():
    global _manager
    if _manager is None:
        _manager = GroupJoinManager()
    return _manager


