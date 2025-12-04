#!/usr/bin/env python3
"""Telegram ToS-compliant scraping rate limits."""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict

logger = logging.getLogger(__name__)


class ScrapingRateLimits:
    """Enforces Telegram ToS-compliant rate limits for scraping."""
    
    # Conservative limits to respect Telegram ToS
    MAX_MEMBERS_PER_HOUR = 1000
    MAX_GROUPS_PER_HOUR = 50
    MAX_CONCURRENT_SCRAPES = 3
    DELAY_BETWEEN_REQUESTS = 2.0  # seconds
    
    def __init__(self):
        self.members_scraped: Dict[str, list] = {}
        self.groups_scraped: Dict[str, list] = {}
        self.active_scrapes = 0
        self.lock = asyncio.Lock()
        self.last_request = None
    
    async def check_member_limit(self, account_id: str) -> tuple[bool, str]:
        """Check if member scraping is allowed."""
        async with self.lock:
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            
            # Clean old entries
            if account_id in self.members_scraped:
                self.members_scraped[account_id] = [
                    ts for ts in self.members_scraped[account_id]
                    if ts > hour_ago
                ]
            else:
                self.members_scraped[account_id] = []
            
            # Check limit
            count = len(self.members_scraped[account_id])
            if count >= self.MAX_MEMBERS_PER_HOUR:
                remaining = min(self.members_scraped[account_id]) - hour_ago
                return False, f"Rate limit reached. Wait {remaining.total_seconds():.0f}s"
            
            return True, ""
    
    async def check_group_limit(self, account_id: str) -> tuple[bool, str]:
        """Check if group scraping is allowed."""
        async with self.lock:
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            
            # Clean old entries
            if account_id in self.groups_scraped:
                self.groups_scraped[account_id] = [
                    ts for ts in self.groups_scraped[account_id]
                    if ts > hour_ago
                ]
            else:
                self.groups_scraped[account_id] = []
            
            # Check limit
            count = len(self.groups_scraped[account_id])
            if count >= self.MAX_GROUPS_PER_HOUR:
                return False, "Group scraping limit reached for this hour"
            
            return True, ""
    
    async def record_member_scrape(self, account_id: str, count: int = 1):
        """Record member scraping activity."""
        async with self.lock:
            if account_id not in self.members_scraped:
                self.members_scraped[account_id] = []
            
            now = datetime.now()
            for _ in range(count):
                self.members_scraped[account_id].append(now)
            
            logger.debug(f"Recorded {count} member scrapes for {account_id}")
    
    async def record_group_scrape(self, account_id: str):
        """Record group scraping activity."""
        async with self.lock:
            if account_id not in self.groups_scraped:
                self.groups_scraped[account_id] = []
            
            self.groups_scraped[account_id].append(datetime.now())
            logger.debug(f"Recorded group scrape for {account_id}")
    
    async def wait_for_rate_limit(self):
        """Wait for rate limit delay between requests."""
        async with self.lock:
            if self.last_request:
                elapsed = (datetime.now() - self.last_request).total_seconds()
                if elapsed < self.DELAY_BETWEEN_REQUESTS:
                    wait_time = self.DELAY_BETWEEN_REQUESTS - elapsed
                    await asyncio.sleep(wait_time)
            
            self.last_request = datetime.now()


_scraping_limits = None

def get_scraping_rate_limits():
    global _scraping_limits
    if _scraping_limits is None:
        _scraping_limits = ScrapingRateLimits()
    return _scraping_limits

