#!/usr/bin/env python3
"""Group join request management with cooldown."""

import asyncio
import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class GroupJoinManager:
    """Manages group join requests with comprehensive rate limiting."""

    def __init__(
        self, cooldown_seconds: int = 300, max_joins_per_hour: int = 10, max_joins_per_day: int = 50
    ):
        self.cooldown_seconds = cooldown_seconds
        self.max_joins_per_hour = max_joins_per_hour
        self.max_joins_per_day = max_joins_per_day
        self.last_join: Dict[str, datetime] = {}
        self.hourly_joins: Dict[str, list] = {}  # account -> list of join timestamps
        self.daily_joins: Dict[str, list] = {}  # account -> list of join timestamps
        self.lock = asyncio.Lock()

    async def can_join_group(self, account_id: str) -> tuple[bool, float]:
        """Check if account can join a group with multi-tier rate limiting."""
        async with self.lock:
            now = datetime.now()

            # Check cooldown
            if account_id in self.last_join:
                elapsed = (now - self.last_join[account_id]).total_seconds()
                remaining = self.cooldown_seconds - elapsed

                if remaining > 0:
                    logger.debug(f"Account {account_id} in cooldown: {remaining:.0f}s remaining")
                    return False, remaining

            # Clean old timestamps
            self._clean_old_timestamps(account_id, now)

            # Check hourly limit
            hourly_count = len(self.hourly_joins.get(account_id, []))
            if hourly_count >= self.max_joins_per_hour:
                logger.warning(
                    f"Account {account_id} hit hourly limit: "
                    f"{hourly_count}/{self.max_joins_per_hour}"
                )
                # Calculate time until oldest join expires
                if account_id in self.hourly_joins and self.hourly_joins[account_id]:
                    oldest = self.hourly_joins[account_id][0]
                    wait_time = 3600 - (now - oldest).total_seconds()
                    return False, max(wait_time, 0)
                return False, 3600

            # Check daily limit
            daily_count = len(self.daily_joins.get(account_id, []))
            if daily_count >= self.max_joins_per_day:
                logger.warning(
                    f"Account {account_id} hit daily limit: {daily_count}/{self.max_joins_per_day}"
                )
                # Calculate time until oldest join expires
                if account_id in self.daily_joins and self.daily_joins[account_id]:
                    oldest = self.daily_joins[account_id][0]
                    wait_time = 86400 - (now - oldest).total_seconds()
                    return False, max(wait_time, 0)
                return False, 86400

            return True, 0.0

    def _clean_old_timestamps(self, account_id: str, now: datetime):
        """Remove timestamps older than tracking windows."""
        # Clean hourly (> 1 hour old)
        if account_id in self.hourly_joins:
            self.hourly_joins[account_id] = [
                ts for ts in self.hourly_joins[account_id] if (now - ts).total_seconds() < 3600
            ]

        # Clean daily (> 24 hours old)
        if account_id in self.daily_joins:
            self.daily_joins[account_id] = [
                ts for ts in self.daily_joins[account_id] if (now - ts).total_seconds() < 86400
            ]

    async def record_join(self, account_id: str):
        """Record group join attempt with multi-tier tracking."""
        now = datetime.now()
        async with self.lock:
            self.last_join[account_id] = now

            # Track hourly
            if account_id not in self.hourly_joins:
                self.hourly_joins[account_id] = []
            self.hourly_joins[account_id].append(now)

            # Track daily
            if account_id not in self.daily_joins:
                self.daily_joins[account_id] = []
            self.daily_joins[account_id].append(now)

            logger.debug(
                f"Recorded group join for {account_id} "
                f"(hourly: {len(self.hourly_joins[account_id])}/"
                f"{self.max_joins_per_hour}, daily: "
                f"{len(self.daily_joins[account_id])}/{self.max_joins_per_day})"
            )

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
