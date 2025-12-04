#!/usr/bin/env python3
"""DateTime validation and safe parsing."""

from datetime import datetime, timezone
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DateTimeValidator:
    """Safe datetime operations with comprehensive validation."""
    
    FORMATS = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S.%f%z',
        '%Y-%m-%d',
        '%Y/%m/%d %H:%M:%S',
        '%d-%m-%Y %H:%M:%S',
    ]
    
    @staticmethod
    def safe_parse(date_string: str, default: Optional[datetime] = None) -> Optional[datetime]:
        """Safely parse datetime string with multiple format support."""
        if not date_string:
            return default
        
        if not isinstance(date_string, str):
            logger.warning(f"Expected string, got {type(date_string)}")
            return default
        
        # Try ISO format first (fastest)
        try:
            return datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            pass
        
        # Try common formats
        for fmt in DateTimeValidator.FORMATS:
            try:
                return datetime.strptime(date_string, fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse datetime: {date_string}")
        return default
    
    @staticmethod
    def to_utc(dt: datetime) -> datetime:
        """Convert datetime to UTC with validation."""
        if not isinstance(dt, datetime):
            logger.error(f"Expected datetime, got {type(dt)}")
            return datetime.now(timezone.utc)
        
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def format_iso(dt: datetime) -> str:
        """Format datetime as ISO string with validation."""
        if not isinstance(dt, datetime):
            logger.error(f"Expected datetime, got {type(dt)}")
            return datetime.now().isoformat()
        return dt.isoformat()
    
    @staticmethod
    def validate_range(dt: datetime, min_dt: Optional[datetime] = None, max_dt: Optional[datetime] = None) -> bool:
        """Validate datetime is within range."""
        if not isinstance(dt, datetime):
            return False
        
        if min_dt and dt < min_dt:
            logger.warning(f"DateTime {dt} is before minimum {min_dt}")
            return False
        
        if max_dt and dt > max_dt:
            logger.warning(f"DateTime {dt} is after maximum {max_dt}")
            return False
        
        return True
    
    @staticmethod
    def safe_now() -> datetime:
        """Get current datetime safely."""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def is_future(dt: datetime) -> bool:
        """Check if datetime is in the future."""
        if not isinstance(dt, datetime):
            return False
        return dt > datetime.now(timezone.utc) if dt.tzinfo else dt > datetime.now()
    
    @staticmethod
    def is_past(dt: datetime) -> bool:
        """Check if datetime is in the past."""
        if not isinstance(dt, datetime):
            return False
        return dt < datetime.now(timezone.utc) if dt.tzinfo else dt < datetime.now()



