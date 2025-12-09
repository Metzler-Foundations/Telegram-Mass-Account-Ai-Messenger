#!/usr/bin/env python3
"""
Security Audit Logger - Comprehensive audit logging for sensitive operations.

Features:
- Tamper-evident audit logging
- Cryptographic integrity verification
- Context-aware logging (user, session, IP)
- Compliance-ready audit trails
- Automatic log rotation and archival
"""

import getpass
import hashlib
import hmac
import json
import logging
import os
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    """Audit event data structure."""

    event_type: str
    user: str = None
    session_id: str = None
    ip_address: str = None
    hostname: str = None
    operation: str = None
    resource: str = None
    success: bool = True
    details: Dict[str, Any] = None
    risk_level: str = "low"  # low, medium, high, critical
    integrity_hash: str = None
    timestamp: str = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Remove None values for cleaner JSON
        return {k: v for k, v in data.items() if v is not None}


class SecurityAuditLogger:
    """Enterprise-grade security audit logging system."""

    def __init__(self, audit_dir: str = "logs/audit", integrity_key: Optional[bytes] = None):
        """
        Initialize audit logger.

        Args:
            audit_dir: Directory for audit logs
            integrity_key: Key for log integrity verification (auto-generated if None)
        """
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        # Thread safety
        self._lock = Lock()

        # Integrity verification
        self.integrity_key = integrity_key or self._generate_integrity_key()

        # Current log file
        self.current_log_file = self._get_current_log_file()
        self._last_integrity_hash = self._get_last_integrity_hash()

        # Context tracking
        self._context = self._get_system_context()

    def _generate_integrity_key(self) -> bytes:
        """Generate a key for log integrity verification."""
        key_file = self.audit_dir / ".integrity_key"
        if key_file.exists():
            with open(key_file, "rb") as f:
                return f.read()

        # Generate new RSA key pair for integrity
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        # Save private key securely
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        with open(key_file, "wb") as f:
            f.write(pem)

        return pem

    def _get_system_context(self) -> Dict[str, Any]:
        """Get system context information."""
        try:
            return {
                "hostname": socket.gethostname(),
                "username": getpass.getuser(),
                "pid": os.getpid(),
                "platform": os.uname().sysname if hasattr(os, "uname") else "unknown",
            }
        except Exception:
            return {
                "hostname": "unknown",
                "username": "unknown",
                "pid": os.getpid(),
                "platform": "unknown",
            }

    def _get_current_log_file(self) -> Path:
        """Get current audit log file (daily rotation)."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.audit_dir / f"audit_{today}.log"

    def _get_last_integrity_hash(self) -> str:
        """Get last integrity hash from current log file."""
        if not self.current_log_file.exists():
            return ""

        try:
            with open(self.current_log_file) as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    if last_line.startswith("#INTEGRITY:"):
                        return last_line.split("#INTEGRITY:")[1]
        except Exception:
            pass
        return ""

    def _calculate_integrity_hash(self, data: str) -> str:
        """Calculate integrity hash for audit data."""
        # Create HMAC with previous hash for chain of trust
        message = f"{self._last_integrity_hash}{data}".encode()
        return hmac.new(self.integrity_key[:32], message, hashlib.sha256).hexdigest()

    def _rotate_log_if_needed(self):
        """Rotate log file if date changed."""
        new_file = self._get_current_log_file()
        if new_file != self.current_log_file:
            self.current_log_file = new_file
            self._last_integrity_hash = ""

    def log_event(self, event: AuditEvent):
        """
        Log a security audit event.

        Args:
            event: Audit event to log
        """
        with self._lock:
            try:
                self._rotate_log_if_needed()

                # Set context if not provided
                if event.user is None:
                    event.user = self._context.get("username")
                if event.hostname is None:
                    event.hostname = self._context.get("hostname")
                if event.session_id is None:
                    event.session_id = f"pid_{self._context.get('pid')}"

                # Convert to dict and serialize
                event_dict = event.to_dict()
                json_data = json.dumps(event_dict, sort_keys=True, default=str)

                # Calculate integrity hash
                event.integrity_hash = self._calculate_integrity_hash(json_data)
                event_dict["integrity_hash"] = event.integrity_hash

                # Serialize final event
                final_json = json.dumps(event_dict, sort_keys=True, default=str)

                # Write to log file
                with open(self.current_log_file, "a") as f:
                    f.write(f"{final_json}\n")
                    f.flush()

                # Update last hash for chain
                self._last_integrity_hash = event.integrity_hash

                # Log to application logger
                logger.info(
                    f"AUDIT: {event.event_type} - {event.operation or 'unknown'} "
                    f"on {event.resource or 'unknown'} - Success: {event.success}"
                )

            except Exception as e:
                logger.error(f"Failed to write audit log: {e}")

    def log_credential_access(self, key: str, source: str, success: bool = True, user: str = None):
        """Log credential access operations."""
        event = AuditEvent(
            event_type="credential_access",
            operation="read",
            resource=f"secret:{key}",
            success=success,
            details={"source": source},
            user=user,
            risk_level="medium",
        )
        self.log_event(event)

    def log_credential_modification(
        self, key: str, operation: str, success: bool = True, user: str = None
    ):
        """Log credential modification operations."""
        event = AuditEvent(
            event_type="credential_modification",
            operation=operation,
            resource=f"secret:{key}",
            success=success,
            user=user,
            risk_level="high",
        )
        self.log_event(event)

    def log_api_key_validation(self, provider: str, success: bool = True, user: str = None):
        """Log API key validation attempts."""
        event = AuditEvent(
            event_type="api_validation",
            operation="validate",
            resource=f"api:{provider}",
            success=success,
            user=user,
            risk_level="medium",
        )
        self.log_event(event)

    def log_authentication_attempt(
        self, method: str, success: bool = True, user: str = None, details: Dict = None
    ):
        """Log authentication attempts."""
        event = AuditEvent(
            event_type="authentication",
            operation=method,
            success=success,
            details=details or {},
            user=user,
            risk_level="high" if not success else "low",
        )
        self.log_event(event)

    def log_security_violation(
        self, violation_type: str, details: Dict[str, Any], user: str = None
    ):
        """Log security violations."""
        event = AuditEvent(
            event_type="security_violation",
            operation=violation_type,
            success=False,
            details=details,
            user=user,
            risk_level="critical",
        )
        self.log_event(event)

    def verify_integrity(self, log_file: Optional[Path] = None) -> bool:
        """
        Verify integrity of audit log.

        Args:
            log_file: Specific log file to verify (current if None)

        Returns:
            True if integrity is valid
        """
        log_file = log_file or self.current_log_file
        if not log_file.exists():
            return True

        try:
            with open(log_file) as f:
                lines = f.readlines()

            # Start with empty hash for first entry
            previous_hash = ""
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Extract integrity hash from line
                try:
                    event_data = json.loads(line)
                    stored_hash = event_data.pop("integrity_hash", "")

                    # Recalculate hash using the previous hash in the chain
                    json_data = json.dumps(event_data, sort_keys=True, default=str)
                    message = f"{previous_hash}{json_data}".encode()
                    calculated_hash = hmac.new(
                        self.integrity_key[:32], message, hashlib.sha256
                    ).hexdigest()

                    if stored_hash != calculated_hash:
                        logger.error(f"Integrity violation in {log_file}: hash mismatch")
                        logger.error(f"  Stored: {stored_hash}")
                        logger.error(f"  Calculated: {calculated_hash}")
                        return False

                    # Update previous hash for next iteration
                    previous_hash = calculated_hash

                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in audit log: {line}")
                    return False

            return True

        except Exception as e:
            logger.error(f"Failed to verify audit log integrity: {e}")
            return False

    def get_audit_trail(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get audit trail for specified number of days.

        Args:
            days: Number of days to include

        Returns:
            List of audit events
        """
        events = []
        cutoff_date = datetime.now() - timedelta(days=days)

        # Get all audit files in date range
        audit_files = []
        for file_path in self.audit_dir.glob("audit_*.log"):
            try:
                date_str = file_path.stem.split("_")[1]
                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                if file_date >= cutoff_date:
                    audit_files.append((file_date, file_path))
            except (ValueError, IndexError):
                continue

        # Sort by date
        audit_files.sort(key=lambda x: x[0])

        # Read events from each file
        for _, file_path in audit_files:
            try:
                with open(file_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            try:
                                event = json.loads(line)
                                events.append(event)
                            except json.JSONDecodeError:
                                continue
            except Exception as e:
                logger.warning(f"Failed to read audit file {file_path}: {e}")

        return events


# Global audit logger instance
_audit_logger = None


def get_audit_logger() -> SecurityAuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = SecurityAuditLogger()
    return _audit_logger


def audit_credential_access(key: str, source: str, success: bool = True, user: str = None):
    """Convenience function for logging credential access."""
    get_audit_logger().log_credential_access(key, source, success, user)


def audit_credential_modification(key: str, operation: str, success: bool = True, user: str = None):
    """Convenience function for logging credential modifications."""
    get_audit_logger().log_credential_modification(key, operation, success, user)


def audit_api_validation(provider: str, success: bool = True, user: str = None):
    """Convenience function for logging API validations."""
    get_audit_logger().log_api_key_validation(provider, success, user)


def audit_security_violation(violation_type: str, details: Dict[str, Any], user: str = None):
    """Convenience function for logging security violations."""
    get_audit_logger().log_security_violation(violation_type, details, user)
