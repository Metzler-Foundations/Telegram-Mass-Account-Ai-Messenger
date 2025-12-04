#!/usr/bin/env python3
"""Security headers for HTTP responses."""

import logging

logger = logging.getLogger(__name__)


class SecurityHeaders:
    """Manages HTTP security headers."""
    
    @staticmethod
    def get_security_headers() -> dict:
        """Get recommended security headers."""
        return {
            # CORS
            'Access-Control-Allow-Origin': 'https://yourdomain.com',
            'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-API-Key',
            'Access-Control-Max-Age': '3600',
            'Access-Control-Allow-Credentials': 'true',
            
            # CSP
            'Content-Security-Policy': (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self' https://fonts.gstatic.com; "
                "connect-src 'self' https://api.yourdomain.com; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
            
            # Other security headers
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
            
            # Cookie security (set individually)
            # Set-Cookie: name=value; HttpOnly; Secure; SameSite=Strict
        }
    
    @staticmethod
    def apply_headers(response):
        """Apply security headers to response."""
        headers = SecurityHeaders.get_security_headers()
        for key, value in headers.items():
            response.headers[key] = value
        return response
    
    @staticmethod
    def create_secure_cookie(name: str, value: str, max_age: int = 3600) -> str:
        """Create secure cookie string."""
        return f"{name}={value}; HttpOnly; Secure; SameSite=Strict; Max-Age={max_age}; Path=/"


def apply_security_headers(response):
    """Apply security headers to HTTP response."""
    return SecurityHeaders.apply_headers(response)




