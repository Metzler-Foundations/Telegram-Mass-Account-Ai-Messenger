#!/usr/bin/env python3
"""Centralized timeout configuration for network operations."""

import logging
from typing import Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class TimeoutType(Enum):
    """Types of timeout operations."""
    HTTP_REQUEST = "http_request"
    DATABASE_QUERY = "database_query"
    TELEGRAM_API = "telegram_api"
    SMS_PROVIDER = "sms_provider"
    PROXY_CHECK = "proxy_check"
    GEMINI_API = "gemini_api"
    WEBSOCKET = "websocket"
    FILE_IO = "file_io"


class TimeoutConfig:
    """Standardized timeout configuration across all modules."""
    
    # Default timeouts in seconds
    DEFAULTS = {
        TimeoutType.HTTP_REQUEST: 30.0,
        TimeoutType.DATABASE_QUERY: 60.0,
        TimeoutType.TELEGRAM_API: 45.0,
        TimeoutType.SMS_PROVIDER: 120.0,  # SMS can be slow
        TimeoutType.PROXY_CHECK: 15.0,
        TimeoutType.GEMINI_API: 60.0,
        TimeoutType.WEBSOCKET: 30.0,
        TimeoutType.FILE_IO: 10.0,
    }
    
    # Connection timeouts (usually shorter)
    CONNECTION_TIMEOUTS = {
        TimeoutType.HTTP_REQUEST: 10.0,
        TimeoutType.DATABASE_QUERY: 5.0,
        TimeoutType.TELEGRAM_API: 15.0,
        TimeoutType.SMS_PROVIDER: 15.0,
        TimeoutType.PROXY_CHECK: 5.0,
        TimeoutType.GEMINI_API: 10.0,
        TimeoutType.WEBSOCKET: 10.0,
        TimeoutType.FILE_IO: 5.0,
    }
    
    # Read timeouts (usually longer)
    READ_TIMEOUTS = {
        TimeoutType.HTTP_REQUEST: 30.0,
        TimeoutType.DATABASE_QUERY: 60.0,
        TimeoutType.TELEGRAM_API: 45.0,
        TimeoutType.SMS_PROVIDER: 120.0,
        TimeoutType.PROXY_CHECK: 10.0,
        TimeoutType.GEMINI_API: 60.0,
        TimeoutType.WEBSOCKET: 30.0,
        TimeoutType.FILE_IO: 10.0,
    }
    
    _custom_timeouts: Dict[TimeoutType, float] = {}
    
    @classmethod
    def get_timeout(cls, timeout_type: TimeoutType) -> float:
        """Get timeout for operation type."""
        if timeout_type in cls._custom_timeouts:
            return cls._custom_timeouts[timeout_type]
        return cls.DEFAULTS.get(timeout_type, 30.0)
    
    @classmethod
    def get_connection_timeout(cls, timeout_type: TimeoutType) -> float:
        """Get connection timeout for operation type."""
        if timeout_type in cls._custom_timeouts:
            return cls._custom_timeouts[timeout_type] * 0.33  # 1/3 of total
        return cls.CONNECTION_TIMEOUTS.get(timeout_type, 10.0)
    
    @classmethod
    def get_read_timeout(cls, timeout_type: TimeoutType) -> float:
        """Get read timeout for operation type."""
        if timeout_type in cls._custom_timeouts:
            return cls._custom_timeouts[timeout_type] * 0.67  # 2/3 of total
        return cls.READ_TIMEOUTS.get(timeout_type, 30.0)
    
    @classmethod
    def set_timeout(cls, timeout_type: TimeoutType, seconds: float):
        """Set custom timeout for operation type."""
        if seconds <= 0:
            logger.error(f"Invalid timeout: {seconds}. Must be positive.")
            return
        
        if seconds > 600:  # 10 minutes max
            logger.warning(f"Timeout {seconds}s is very high. Capping at 600s.")
            seconds = 600.0
        
        cls._custom_timeouts[timeout_type] = seconds
        logger.info(f"Set {timeout_type.value} timeout to {seconds}s")
    
    @classmethod
    def reset_timeout(cls, timeout_type: TimeoutType):
        """Reset timeout to default."""
        if timeout_type in cls._custom_timeouts:
            del cls._custom_timeouts[timeout_type]
            logger.info(f"Reset {timeout_type.value} timeout to default")
    
    @classmethod
    def get_all_timeouts(cls) -> Dict[str, float]:
        """Get all configured timeouts."""
        result = {}
        for timeout_type in TimeoutType:
            result[timeout_type.value] = cls.get_timeout(timeout_type)
        return result
    
    @classmethod
    def load_from_config(cls, config: Dict[str, Any]):
        """Load timeout configuration from config dict."""
        timeouts = config.get('timeouts', {})
        for key, value in timeouts.items():
            try:
                timeout_type = TimeoutType(key)
                cls.set_timeout(timeout_type, float(value))
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid timeout config: {key}={value}: {e}")


# Global timeout configuration
def get_timeout(operation: str) -> float:
    """Get timeout for operation type (convenience function)."""
    try:
        timeout_type = TimeoutType(operation)
        return TimeoutConfig.get_timeout(timeout_type)
    except ValueError:
        logger.warning(f"Unknown timeout type: {operation}, using default 30s")
        return 30.0


def get_timeouts(operation: str) -> tuple:
    """Get (connection_timeout, read_timeout) tuple."""
    try:
        timeout_type = TimeoutType(operation)
        return (
            TimeoutConfig.get_connection_timeout(timeout_type),
            TimeoutConfig.get_read_timeout(timeout_type)
        )
    except ValueError:
        logger.warning(f"Unknown timeout type: {operation}, using defaults")
        return (10.0, 30.0)



