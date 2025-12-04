#!/usr/bin/env python3
"""Phone number blacklist management."""

import logging
from typing import Set
from pathlib import Path

logger = logging.getLogger(__name__)


class PhoneBlacklist:
    """Manages blacklisted phone numbers."""
    
    def __init__(self, blacklist_file: str = "phone_blacklist.txt"):
        self.blacklist_file = Path(blacklist_file)
        self.blacklist: Set[str] = self._load_blacklist()
    
    def _load_blacklist(self) -> Set[str]:
        """Load blacklist from file."""
        if not self.blacklist_file.exists():
            return set()
        
        try:
            with open(self.blacklist_file, 'r') as f:
                phones = {line.strip() for line in f if line.strip()}
            logger.info(f"Loaded {len(phones)} blacklisted phone numbers")
            return phones
        except Exception as e:
            logger.error(f"Failed to load blacklist: {e}")
            return set()
    
    def is_blacklisted(self, phone: str) -> bool:
        """Check if phone number is blacklisted."""
        from accounts.phone_normalizer import PhoneNormalizer
        normalized = PhoneNormalizer.normalize(phone)
        return normalized in self.blacklist
    
    def add(self, phone: str, reason: str = None):
        """Add phone to blacklist."""
        from accounts.phone_normalizer import PhoneNormalizer
        normalized = PhoneNormalizer.normalize(phone)
        
        if normalized not in self.blacklist:
            self.blacklist.add(normalized)
            self._save_blacklist()
            logger.warning(f"Added {phone} to blacklist. Reason: {reason}")
    
    def _save_blacklist(self):
        """Save blacklist to file."""
        try:
            with open(self.blacklist_file, 'w') as f:
                for phone in sorted(self.blacklist):
                    f.write(f"{phone}\n")
        except Exception as e:
            logger.error(f"Failed to save blacklist: {e}")


_blacklist = None

def get_phone_blacklist():
    global _blacklist
    if _blacklist is None:
        _blacklist = PhoneBlacklist()
    return _blacklist


