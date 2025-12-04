#!/usr/bin/env python3
"""Account banned status detection."""

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class BanDetector:
    """Detects if Telegram account is banned."""
    
    BAN_INDICATORS = [
        'USER_DEACTIVATED',
        'AUTH_KEY_UNREGISTERED',
        'USER_BANNED_IN_CHANNEL',
        'PHONE_NUMBER_BANNED',
        'ACCOUNT_BANNED'
    ]
    
    @staticmethod
    async def check_ban_status(client, account_id: str) -> tuple[bool, Optional[str]]:
        """Check if account is banned."""
        try:
            # Try to get own user info
            me = await client.get_me()
            
            if not me:
                logger.warning(f"Could not fetch user info for {account_id}")
                return True, "UNABLE_TO_FETCH_INFO"
            
            # Account exists and accessible
            return False, None
            
        except Exception as e:
            error_str = str(e)
            
            # Check for ban indicators
            for indicator in BanDetector.BAN_INDICATORS:
                if indicator in error_str:
                    logger.error(f"Account {account_id} appears banned: {indicator}")
                    return True, indicator
            
            # Unknown error
            logger.error(f"Error checking ban status for {account_id}: {e}")
            return False, None
    
    @staticmethod
    def record_ban(account_id: str, reason: str, db_path: str = "database.db"):
        """Record account ban in database."""
        try:
            from database.connection_pool import get_pool
            
            pool = get_pool(db_path)
            with pool.get_connection() as conn:
                conn.execute("""
                    UPDATE accounts
                    SET status = 'banned',
                        ban_reason = ?,
                        banned_at = ?
                    WHERE id = ?
                """, (reason, datetime.now().isoformat(), account_id))
                conn.commit()
                
                logger.info(f"Recorded ban for account {account_id}: {reason}")
        except Exception as e:
            logger.error(f"Failed to record ban: {e}")


async def detect_ban_status(client, account_id: str) -> bool:
    """Check if account is banned."""
    is_banned, reason = await BanDetector.check_ban_status(client, account_id)
    if is_banned and reason:
        BanDetector.record_ban(account_id, reason)
    return is_banned


