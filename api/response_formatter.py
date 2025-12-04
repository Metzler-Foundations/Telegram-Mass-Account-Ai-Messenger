#!/usr/bin/env python3
"""Standardized API response formatting."""

from typing import Any, Optional
from datetime import datetime


class APIResponse:
    """Standardized API response format."""
    
    @staticmethod
    def success(data: Any = None, message: str = "Success") -> dict:
        """Create success response."""
        return {
            'status': 'success',
            'message': message,
            'data': data,
            'timestamp': datetime.now().isoformat(),
            'version': 'v1'
        }
    
    @staticmethod
    def error(error_msg: str, error_code: str = "GENERIC_ERROR", details: Any = None) -> dict:
        """Create error response."""
        return {
            'status': 'error',
            'message': error_msg,
            'error_code': error_code,
            'details': details,
            'timestamp': datetime.now().isoformat(),
            'version': 'v1'
        }
    
    @staticmethod
    def paginated(data: list, page: int, page_size: int, total: int) -> dict:
        """Create paginated response."""
        total_pages = (total + page_size - 1) // page_size
        
        return {
            'status': 'success',
            'data': data,
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_items': total,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'timestamp': datetime.now().isoformat(),
            'version': 'v1'
        }


def success_response(data=None, message="Success"):
    """Create success response."""
    return APIResponse.success(data, message)


def error_response(message, code="ERROR"):
    """Create error response."""
    return APIResponse.error(message, code)


