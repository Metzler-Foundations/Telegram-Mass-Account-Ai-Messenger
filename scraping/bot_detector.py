#!/usr/bin/env python3
"""Bot account detection in scraped members."""

import logging
import re

logger = logging.getLogger(__name__)


class BotDetector:
    """Detects bot accounts in member lists."""
    
    BOT_USERNAME_PATTERNS = [
        r'.*bot$',
        r'.*_bot$',
        r'bot_.*',
        r'.*service$',
        r'.*helper$'
    ]
    
    @staticmethod
    def is_bot(username: Optional[str], is_bot_flag: bool = False) -> bool:
        """Detect if account is a bot."""
        # Check Telegram's is_bot flag first
        if is_bot_flag:
            return True
        
        # Check username patterns
        if username:
            username_lower = username.lower()
            for pattern in BotDetector.BOT_USERNAME_PATTERNS:
                if re.match(pattern, username_lower):
                    logger.debug(f"Bot detected by pattern: {username}")
                    return True
        
        return False
    
    @staticmethod
    def filter_bots(members: list) -> list:
        """Filter out bots from member list."""
        filtered = []
        bot_count = 0
        
        for member in members:
            if not BotDetector.is_bot(
                member.get('username'),
                member.get('is_bot', False)
            ):
                filtered.append(member)
            else:
                bot_count += 1
        
        logger.info(f"Filtered out {bot_count} bots from {len(members)} members")
        return filtered


def filter_bot_accounts(members: list) -> list:
    """Remove bot accounts from member list."""
    return BotDetector.filter_bots(members)

