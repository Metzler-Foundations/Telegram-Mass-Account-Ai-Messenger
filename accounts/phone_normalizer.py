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
        from utils.input_validation import validate_phone
        
        try:
            # Use validation framework
            normalized = validate_phone(phone, normalize=True)
            return normalized
        except Exception as e:
            logger.error(f"Phone normalization failed for {phone}: {e}")
            # Fallback: basic cleaning
            cleaned = re.sub(r'[^\d+]', '', phone)
            if not cleaned.startswith('+'):
                cleaned = '+' + cleaned
            return cleaned
    
    @staticmethod
    def is_duplicate(phone: str, existing_phones: list) -> bool:
        """Check if phone number is duplicate."""
        normalized = PhoneNormalizer.normalize(phone)
        normalized_existing = [PhoneNormalizer.normalize(p) for p in existing_phones]
        return normalized in normalized_existing





