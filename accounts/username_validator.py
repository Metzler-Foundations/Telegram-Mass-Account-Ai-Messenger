#!/usr/bin/env python3
"""Username validator - Ensure valid Telegram usernames."""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class UsernameValidator:
    """Validates Telegram usernames."""
    
    # Telegram username rules
    MIN_LENGTH = 5
    MAX_LENGTH = 32
    PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$')
    
    RESERVED_USERNAMES = {
        'telegram', 'admin', 'support', 'help', 'info',
        'bot', 'channel', 'group', 'official'
    }
    
    @staticmethod
    def validate(username: str) -> tuple:
        """Validate username format."""
        from utils.input_validation import InputValidator
        
        try:
            validated = InputValidator.validate_username(username)
            
            # Check reserved
            if validated.lower() in UsernameValidator.RESERVED_USERNAMES:
                return False, f"Username '{username}' is reserved"
            
            return True, validated
            
        except Exception as e:
            return False, str(e)
    
    @staticmethod
    def generate_safe_username(base: str, suffix: Optional[str] = None) -> Optional[str]:
        """Generate safe username from base."""
        # Clean base
        base = re.sub(r'[^a-zA-Z0-9_]', '', base)
        
        if not base or not base[0].isalpha():
            base = 'user_' + base
        
        username = base[:32]
        if suffix:
            username = username[:27] + '_' + suffix[:4]
        
        valid, result = UsernameValidator.validate(username)
        return result if valid else None





