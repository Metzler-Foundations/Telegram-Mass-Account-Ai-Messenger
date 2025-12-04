#!/usr/bin/env python3
"""Error notification system - Alert users of errors."""

import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ErrorNotifier:
    """Notifies users of application errors."""
    
    def __init__(self):
        self.notification_handlers = []
    
    def register_handler(self, handler: Callable):
        """Register error notification handler."""
        self.notification_handlers.append(handler)
    
    def notify_error(self, error_msg: str, severity: str = "error", details: Optional[dict] = None):
        """Notify all handlers of error."""
        for handler in self.notification_handlers:
            try:
                handler(error_msg, severity, details)
            except Exception as e:
                logger.error(f"Error handler failed: {e}")
    
    def format_user_friendly_error(self, exception: Exception) -> str:
        """Convert technical exception to user-friendly message."""
        error_map = {
            'ConnectionError': 'Network connection failed. Please check your internet.',
            'TimeoutError': 'Operation timed out. Please try again.',
            'PermissionError': 'Permission denied. Check your account access.',
            'FileNotFoundError': 'Required file not found. Please verify configuration.',
            'ValueError': 'Invalid input provided. Please check your data.',
        }
        
        exc_name = type(exception).__name__
        return error_map.get(exc_name, 'An unexpected error occurred. Please contact support.')


_error_notifier = None

def get_error_notifier():
    global _error_notifier
    if _error_notifier is None:
        _error_notifier = ErrorNotifier()
    return _error_notifier





