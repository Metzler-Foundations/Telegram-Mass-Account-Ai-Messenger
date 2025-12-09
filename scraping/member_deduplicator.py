#!/usr/bin/env python3
"""Member deduplication system."""

import hashlib
import logging
from typing import Optional, Set

logger = logging.getLogger(__name__)


class MemberDeduplicator:
    """Detects and removes duplicate members."""

    def __init__(self):
        self.seen_hashes: Set[str] = set()

    @staticmethod
    def generate_member_hash(user_id: int, username: Optional[str], phone: Optional[str]) -> str:
        """Generate unique hash for member."""
        identifier = f"{user_id}:{username or ''}:{phone or ''}"
        return hashlib.sha256(identifier.encode()).hexdigest()

    def is_duplicate(
        self, user_id: int, username: Optional[str] = None, phone: Optional[str] = None
    ) -> bool:
        """Check if member is duplicate."""
        member_hash = self.generate_member_hash(user_id, username, phone)

        if member_hash in self.seen_hashes:
            logger.debug(f"Duplicate member detected: {user_id}")
            return True

        self.seen_hashes.add(member_hash)
        return False

    def clear(self):
        """Clear deduplication cache."""
        self.seen_hashes.clear()


_deduplicator = None


def get_member_deduplicator():
    global _deduplicator
    if _deduplicator is None:
        _deduplicator = MemberDeduplicator()
    return _deduplicator
