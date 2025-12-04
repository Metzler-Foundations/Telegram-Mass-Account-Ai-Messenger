#!/usr/bin/env python3
"""Proxy response validation."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class ProxyValidator:
    """Validates proxy responses for malicious content."""
    
    MALICIOUS_HEADERS = ['x-inject', 'x-backdoor', 'x-redirect-to']
    SUSPICIOUS_RESPONSES = ['<script', 'javascript:', 'phishing']
    
    @staticmethod
    def validate_response(response_text: str, headers: dict) -> bool:
        """Validate proxy response is safe."""
        # Check headers
        for header in ProxyValidator.MALICIOUS_HEADERS:
            if header.lower() in [h.lower() for h in headers.keys()]:
                logger.error(f"Malicious header detected: {header}")
                return False
        
        # Check response content
        if response_text:
            response_lower = response_text.lower()
            for pattern in ProxyValidator.SUSPICIOUS_RESPONSES:
                if pattern in response_lower:
                    logger.warning(f"Suspicious content in proxy response: {pattern}")
                    return False
        
        return True
    
    @staticmethod
    def validate_proxy_format(proxy_url: str) -> bool:
        """Validate proxy URL format."""
        from utils.input_validation import InputValidator
        
        try:
            return InputValidator.validate_url(proxy_url, allowed_schemes=['http', 'https', 'socks5'])
        except Exception as e:
            logger.error(f"Proxy validation failed: {e}")
            return False


def is_proxy_safe(response_text: str, headers: dict) -> bool:
    """Check if proxy response is safe."""
    return ProxyValidator.validate_response(response_text, headers)





