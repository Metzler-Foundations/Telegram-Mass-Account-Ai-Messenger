#!/usr/bin/env python3
"""
Security Event Logger - Comprehensive security audit logging.

Features:
- Failed authentication attempts
- Unauthorized access attempts
- Rate limit violations
- Suspicious activity detection
- PII redaction
- Structured logging format
"""

import logging
import re
import hashlib
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class SecurityEventType:
    """Security event types."""

    AUTH_FAILURE = "auth_failure"
    AUTH_SUCCESS = "auth_success"
    UNAUTHORIZED_ACCESS = "unauthorized_access"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    INVALID_INPUT = "invalid_input"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    DATA_BREACH_ATTEMPT = "data_breach_attempt"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SESSION_HIJACK = "session_hijack"
    ACCOUNT_LOCKOUT = "account_lockout"


class PIIRedactor:
    """Redacts PII from logs."""

    # PII patterns
    PATTERNS = {
        "phone": re.compile(r"\+?\d{10,15}"),
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "api_key": re.compile(r"[A-Za-z0-9\-_]{20,}"),
        "ip_address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
    }

    @staticmethod
    def redact(text: str, redact_types: Optional[List[str]] = None) -> str:
        """
        Redact PII from text.

        Args:
            text: Text to redact
            redact_types: Types to redact (None = all)

        Returns:
            Redacted text
        """
        if not isinstance(text, str):
            text = str(text)

        redacted = text
        redact_types = redact_types or list(PIIRedactor.PATTERNS.keys())

        for pii_type in redact_types:
            if pii_type in PIIRedactor.PATTERNS:
                pattern = PIIRedactor.PATTERNS[pii_type]

                def replace_with_hash(match):
                    value = match.group(0)
                    # Hash first 6 chars for reference
                    hash_val = hashlib.sha256(value.encode()).hexdigest()[:6]
                    return f"[{pii_type.upper()}:{hash_val}]"

                redacted = pattern.sub(replace_with_hash, redacted)

        return redacted

    @staticmethod
    def hash_sensitive(value: str) -> str:
        """
        Hash sensitive value for logging.

        Args:
            value: Value to hash

        Returns:
            SHA256 hash (first 12 chars)
        """
        if not value:
            return "[EMPTY]"

        hash_val = hashlib.sha256(str(value).encode()).hexdigest()
        return f"[HASH:{hash_val[:12]}]"


class SecurityLogger:
    """
    Logs security events with PII redaction.

    Separate from application logs for security analysis.
    """

    def __init__(self, log_file: str = "logs/security_events.log"):
        """
        Initialize security logger.

        Args:
            log_file: Path to security log file
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Setup dedicated security logger
        self.logger = logging.getLogger("security_events")
        self.logger.setLevel(logging.INFO)

        # File handler with rotation
        from logging.handlers import RotatingFileHandler

        handler = RotatingFileHandler(
            self.log_file, maxBytes=10 * 1024 * 1024, backupCount=10  # 10MB
        )

        # JSON format for parsing
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "event": %(message)s}'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        # Statistics
        self.stats = {
            "events_logged": 0,
            "auth_failures": 0,
            "rate_limits": 0,
            "suspicious_activities": 0,
        }

    def log_auth_failure(
        self,
        user_id: str,
        reason: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """
        Log authentication failure.

        Args:
            user_id: User identifier
            reason: Failure reason
            ip_address: Client IP
            user_agent: Client user agent
        """
        # Redact PII
        user_id_redacted = PIIRedactor.hash_sensitive(user_id)
        ip_redacted = PIIRedactor.redact(ip_address or "unknown", ["ip_address"])

        event = {
            "type": SecurityEventType.AUTH_FAILURE,
            "user_id": user_id_redacted,
            "reason": reason,
            "ip_address": ip_redacted,
            "user_agent": user_agent[:100] if user_agent else None,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(json.dumps(event))
        self.stats["events_logged"] += 1
        self.stats["auth_failures"] += 1

    def log_auth_success(self, user_id: str, role: str, ip_address: Optional[str] = None):
        """Log successful authentication."""
        user_id_redacted = PIIRedactor.hash_sensitive(user_id)
        ip_redacted = PIIRedactor.redact(ip_address or "unknown", ["ip_address"])

        event = {
            "type": SecurityEventType.AUTH_SUCCESS,
            "user_id": user_id_redacted,
            "role": role,
            "ip_address": ip_redacted,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(json.dumps(event))
        self.stats["events_logged"] += 1

    def log_rate_limit_exceeded(self, resource: str, identifier: str, limit: int, window: float):
        """Log rate limit violation."""
        identifier_redacted = PIIRedactor.hash_sensitive(identifier)

        event = {
            "type": SecurityEventType.RATE_LIMIT_EXCEEDED,
            "resource": resource,
            "identifier": identifier_redacted,
            "limit": limit,
            "window_seconds": window,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(json.dumps(event))
        self.stats["events_logged"] += 1
        self.stats["rate_limits"] += 1

    def log_unauthorized_access(self, user_id: str, resource: str, required_permission: str):
        """Log unauthorized access attempt."""
        user_id_redacted = PIIRedactor.hash_sensitive(user_id)

        event = {
            "type": SecurityEventType.UNAUTHORIZED_ACCESS,
            "user_id": user_id_redacted,
            "resource": resource,
            "required_permission": required_permission,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(json.dumps(event))
        self.stats["events_logged"] += 1

    def log_suspicious_activity(
        self, activity_type: str, details: Dict[str, Any], severity: str = "medium"
    ):
        """Log suspicious activity."""
        # Redact PII from details
        redacted_details = {}
        for key, value in details.items():
            if isinstance(value, str):
                redacted_details[key] = PIIRedactor.redact(value)
            else:
                redacted_details[key] = value

        event = {
            "type": SecurityEventType.SUSPICIOUS_ACTIVITY,
            "activity_type": activity_type,
            "severity": severity,
            "details": redacted_details,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.warning(json.dumps(event))
        self.stats["events_logged"] += 1
        self.stats["suspicious_activities"] += 1

    def log_invalid_input(
        self, input_type: str, validation_error: str, source: Optional[str] = None
    ):
        """Log invalid input attempt."""
        event = {
            "type": SecurityEventType.INVALID_INPUT,
            "input_type": input_type,
            "validation_error": validation_error,
            "source": source,
            "timestamp": datetime.now().isoformat(),
        }

        self.logger.info(json.dumps(event))
        self.stats["events_logged"] += 1

    def get_stats(self) -> Dict:
        """Get logging statistics."""
        return self.stats.copy()


# Global instance
_security_logger: Optional[SecurityLogger] = None


def get_security_logger() -> SecurityLogger:
    """Get global security logger instance."""
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger


# Convenience functions
def log_auth_failure(user_id: str, reason: str, ip: Optional[str] = None):
    """Log authentication failure."""
    get_security_logger().log_auth_failure(user_id, reason, ip)


def log_rate_limit(resource: str, identifier: str, limit: int, window: float):
    """Log rate limit exceeded."""
    get_security_logger().log_rate_limit_exceeded(resource, identifier, limit, window)


def redact_pii(text: str) -> str:
    """Redact PII from text."""
    return PIIRedactor.redact(text)
