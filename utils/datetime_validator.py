#!/usr/bin/env python3
"""DateTime validation and safe parsing."""

from datetime import datetime, timezone
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DateTimeValidator:
    """Safe datetime operations."""
    
    FORMATS = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%d',
    ]
    
    @staticmethod
    def safe_parse(date_string: str, default: Optional[datetime] = None) -> Optional[datetime]:
        """Safely parse datetime string."""
        if not date_string:
            return default
        
        for fmt in DateTimeValidator.FORMATS:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse datetime: {date_string}")
        return default
    
    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """Convert datetime to UTC."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def format_iso(dt: datetime) -> str:
        """Format datetime as ISO string."""
        return dt.isoformat()

