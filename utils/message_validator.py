#!/usr/bin/env python3
"""Message validator - Validate Telegram messages for length, emoji, formatting."""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class MessageValidator:
    """Validates messages before sending."""
    
    TELEGRAM_MAX_LENGTH = 4096
    TELEGRAM_MAX_CAPTION = 1024
    
    @staticmethod
    def validate_length(message: str, max_length: Optional[int] = None) -> tuple:
        """Validate message length."""
        max_len = max_length or MessageValidator.TELEGRAM_MAX_LENGTH
        
        if len(message) > max_len:
            return False, f"Message too long ({len(message)} > {max_len} chars)"
        
        return True, "OK"
    
    @staticmethod
    def validate_emoji(message: str) -> tuple:
        """Validate emoji encoding."""
        try:
            message.encode('utf-8')
            return True, "OK"
        except UnicodeEncodeError as e:
            return False, f"Invalid emoji encoding: {e}"
    
    @staticmethod
    def sanitize_message(message: str) -> str:
        """Sanitize message for safe sending."""
        from utils.unicode_handler import UnicodeHandler
        
        # Normalize Unicode
        message = UnicodeHandler.normalize(message)
        
        # Truncate if needed
        if len(message) > MessageValidator.TELEGRAM_MAX_LENGTH:
            message = UnicodeHandler.truncate_safe(message, MessageValidator.TELEGRAM_MAX_LENGTH)
            logger.warning(f"Message truncated to {MessageValidator.TELEGRAM_MAX_LENGTH} chars")
        
        return message
    
    @staticmethod
    def validate_template(template: str) -> tuple:
        """Validate message template."""
        from utils.input_validation import InputValidator
        
        try:
            InputValidator.validate_template_string(template)
            InputValidator.validate_message_length(template)
            return True, "OK"
        except Exception as e:
            return False, str(e)



