#!/usr/bin/env python3
"""Phone number normalizer - Ensure consistent phone number format."""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PhoneNormalizer:
    """Normalizes phone numbers to prevent duplicates."""
    
    @staticmethod
    def normalize(phone: str) -> str:
        """Normalize phone number to E.164 format."""
        try:
            # Basic cleaning - remove all non-digits except leading +
            cleaned = re.sub(r'[^\d+]', '', phone)
            
            # Ensure it starts with +
            if not cleaned.startswith('+'):
                cleaned = '+' + cleaned
            
            # Validate it looks like a phone number
            if len(cleaned) < 8 or len(cleaned) > 20:
                logger.warning(f"Phone number length unusual: {cleaned}")
            
            return cleaned
        except Exception as e:
            logger.error(f"Phone normalization failed for {phone}: {e}")
            # Ultimate fallback
            return phone
    
    @staticmethod
    def is_duplicate(phone: str, existing_phones: list) -> bool:
        """Check if phone number is duplicate."""
        normalized = PhoneNormalizer.normalize(phone)
        normalized_existing = [PhoneNormalizer.normalize(p) for p in existing_phones]
        return normalized in normalized_existing





