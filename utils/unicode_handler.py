#!/usr/bin/env python3
"""
Unicode Handler - Safe Unicode operations.

Features:
- Unicode normalization
- Emoji handling
- Encoding safety
- Invalid character filtering
"""

import unicodedata
import logging
import re

logger = logging.getLogger(__name__)


class UnicodeHandler:
    """Safe Unicode text handling."""
    
    @staticmethod
    def normalize(text: str, form: str = 'NFC') -> str:
        """Normalize Unicode text."""
        if not isinstance(text, str):
            text = str(text)
        try:
            return unicodedata.normalize(form, text)
        except Exception as e:
            logger.error(f"Unicode normalization failed: {e}")
            return text
    
    @staticmethod
    def safe_encode(text: str, encoding: str = 'utf-8', errors: str = 'replace') -> bytes:
        """Safely encode text."""
        try:
            return text.encode(encoding, errors=errors)
        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            return text.encode('utf-8', errors='replace')
    
    @staticmethod
    def safe_decode(data: bytes, encoding: str = 'utf-8', errors: str = 'replace') -> str:
        """Safely decode bytes."""
        try:
            return data.decode(encoding, errors=errors)
        except Exception as e:
            logger.error(f"Decoding failed: {e}")
            return data.decode('utf-8', errors='replace')
    
    @staticmethod
    def filter_invalid_chars(text: str, allowed_chars: Optional[set] = None) -> str:
        """Remove invalid characters."""
        if allowed_chars:
            return ''.join(c for c in text if c in allowed_chars or c.isalnum() or c.isspace())
        
        # Remove control characters except common ones
        return ''.join(c for c in text if unicodedata.category(c)[0] != 'C' or c in '\n\r\t')
    
    @staticmethod
    def truncate_safe(text: str, max_length: int) -> str:
        """Truncate without breaking multi-byte characters."""
        if len(text) <= max_length:
            return text
        
        # Truncate and ensure valid UTF-8
        truncated = text[:max_length]
        try:
            truncated.encode('utf-8')
            return truncated
        except UnicodeEncodeError:
            # Back off until valid
            for i in range(max_length - 1, max(0, max_length - 4), -1):
                try:
                    truncated = text[:i]
                    truncated.encode('utf-8')
                    return truncated
                except UnicodeEncodeError:
                    continue
        return truncated



