#!/usr/bin/env python3
"""Warmup service control - cancel and stop functionality."""

import logging
import asyncio
from typing import Dict, Set

logger = logging.getLogger(__name__)


class WarmupController:
    """Controls warmup service operations."""
    
    def __init__(self):
        self.active_warmups: Dict[str, asyncio.Task] = {}
        self.cancelled_accounts: Set[str] = set()
    
    async def start_warmup(self, account_id: str, warmup_func):
        """Start warmup for account."""
        if account_id in self.active_warmups:
            logger.warning(f"Warmup already running for {account_id}")
            return False
        
        task = asyncio.create_task(warmup_func(account_id))
        self.active_warmups[account_id] = task
        logger.info(f"Started warmup for {account_id}")
        return True
    
    async def cancel_warmup(self, account_id: str) -> bool:
        """Cancel warmup for account."""
        if account_id not in self.active_warmups:
            logger.warning(f"No active warmup for {account_id}")
            return False
        
        task = self.active_warmups[account_id]
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            logger.info(f"Warmup cancelled for {account_id}")
        
        del self.active_warmups[account_id]
        self.cancelled_accounts.add(account_id)
        return True
    
    async def stop_all(self):
        """Stop all active warmups."""
        logger.info(f"Stopping {len(self.active_warmups)} active warmups")
        
        tasks = list(self.active_warmups.values())
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        self.active_warmups.clear()
        logger.info("All warmups stopped")
    
    def is_active(self, account_id: str) -> bool:
        """Check if warmup is active for account."""
        return account_id in self.active_warmups
    
    def get_active_count(self) -> int:
        """Get number of active warmups."""
        return len(self.active_warmups)


_controller = None

def get_warmup_controller():
    global _controller
    if _controller is None:
        _controller = WarmupController()
    return _controller




