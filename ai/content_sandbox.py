#!/usr/bin/env python3
"""AI content sandboxing - Validate and sanitize AI-generated content."""

import re
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class ContentSandbox:
    """Sandbox for AI-generated content validation."""
    
    # Dangerous patterns in AI responses
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # JavaScript
        r'javascript:',  # JS URLs
        r'on\w+\s*=',  # Event handlers
        r'eval\s*\(',  # Code execution
        r'exec\s*\(',
        r'__import__',  # Python imports
        r'subprocess\.',
        r'os\.system',
        r'os\.popen',
    ]
    
    # Policy violations
    POLICY_VIOLATIONS = [
        r'(hate|racist|sexist|violent)\s+speech',
        r'illegal\s+(activity|content)',
        r'(spam|scam|phishing)',
        r'personal\s+information',
        r'credit\s+card',
        r'password',
    ]
    
    @staticmethod
    def validate_content(content: str) -> tuple:
        """Validate AI-generated content."""
        if not isinstance(content, str):
            return False, "Invalid content type"
        
        # Check for dangerous patterns
        for pattern in ContentSandbox.DANGEROUS_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected: {pattern}")
                return False, "Content contains potentially dangerous code"
        
        # Check for policy violations
        for pattern in ContentSandbox.POLICY_VIOLATIONS:
            if re.search(pattern, content, re.IGNORECASE):
                logger.warning(f"Policy violation detected: {pattern}")
                return False, "Content violates usage policy"
        
        return True, "OK"
    
    @staticmethod
    def sanitize_content(content: str) -> str:
        """Sanitize AI-generated content."""
        from utils.input_validation import InputValidator
        from utils.unicode_handler import UnicodeHandler
        
        # Remove dangerous patterns
        for pattern in ContentSandbox.DANGEROUS_PATTERNS:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # Sanitize HTML
        content = InputValidator.sanitize_html(content)
        
        # Normalize Unicode
        content = UnicodeHandler.normalize(content)
        
        return content


def validate_ai_response(response: str) -> Optional[str]:
    """Validate and sanitize AI response."""
    valid, msg = ContentSandbox.validate_content(response)
    if not valid:
        logger.error(f"AI response validation failed: {msg}")
        return None
    
    return ContentSandbox.sanitize_content(response)





