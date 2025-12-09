#!/usr/bin/env python3
"""
Authentication & Authorization System - Secure access control.

Features:
- API key authentication
- Session token management
- Role-based access control (RBAC)
- Account lockout protection
- Audit logging
- Token expiration
"""

import logging
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class UserRole(Enum):
    """User roles for RBAC."""

    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"
    API_USER = "api_user"


class Permission(Enum):
    """System permissions."""

    # Account operations
    CREATE_ACCOUNT = "account:create"
    DELETE_ACCOUNT = "account:delete"
    VIEW_ACCOUNTS = "account:view"
    MODIFY_ACCOUNT = "account:modify"

    # Campaign operations
    CREATE_CAMPAIGN = "campaign:create"
    RUN_CAMPAIGN = "campaign:run"
    VIEW_CAMPAIGNS = "campaign:view"
    DELETE_CAMPAIGN = "campaign:delete"

    # Proxy operations
    MANAGE_PROXIES = "proxy:manage"
    VIEW_PROXIES = "proxy:view"

    # System operations
    VIEW_LOGS = "system:logs"
    MODIFY_SETTINGS = "system:settings"
    VIEW_ANALYTICS = "system:analytics"


# Role permission mappings
ROLE_PERMISSIONS = {
    UserRole.ADMIN: list(Permission),  # All permissions
    UserRole.OPERATOR: [
        Permission.VIEW_ACCOUNTS,
        Permission.MODIFY_ACCOUNT,
        Permission.CREATE_CAMPAIGN,
        Permission.RUN_CAMPAIGN,
        Permission.VIEW_CAMPAIGNS,
        Permission.VIEW_PROXIES,
        Permission.VIEW_ANALYTICS,
    ],
    UserRole.VIEWER: [
        Permission.VIEW_ACCOUNTS,
        Permission.VIEW_CAMPAIGNS,
        Permission.VIEW_PROXIES,
        Permission.VIEW_ANALYTICS,
    ],
    UserRole.API_USER: [
        Permission.CREATE_CAMPAIGN,
        Permission.RUN_CAMPAIGN,
        Permission.VIEW_CAMPAIGNS,
        Permission.VIEW_ACCOUNTS,
    ],
}


@dataclass
class Session:
    """User session."""

    session_id: str
    user_id: str
    role: UserRole
    created_at: datetime
    expires_at: datetime
    last_activity: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    is_active: bool = True


@dataclass
class LoginAttempt:
    """Login attempt tracking."""

    user_id: str
    timestamp: datetime
    success: bool
    ip_address: Optional[str] = None
    reason: Optional[str] = None


class AuthenticationManager:
    """
    Manages authentication and authorization.

    Features:
    - API key validation
    - Session management
    - Role-based access control
    - Account lockout
    """

    def __init__(
        self,
        session_timeout: int = 3600,  # 1 hour
        max_failed_attempts: int = 5,
        lockout_duration: int = 900,  # 15 minutes
    ):
        """
        Initialize authentication manager.

        Args:
            session_timeout: Session timeout in seconds
            max_failed_attempts: Max failed login attempts before lockout
            lockout_duration: Account lockout duration in seconds
        """
        self.session_timeout = session_timeout
        self.max_failed_attempts = max_failed_attempts
        self.lockout_duration = lockout_duration

        # Storage
        self.sessions: Dict[str, Session] = {}
        self.api_keys: Dict[str, Dict] = {}  # api_key -> {user_id, role, created_at}
        self.login_attempts: Dict[str, List[LoginAttempt]] = {}
        self.locked_accounts: Dict[str, datetime] = {}  # user_id -> unlock_time

        # Thread safety
        self.lock = threading.Lock()

        # Statistics
        self.stats = {
            "total_logins": 0,
            "failed_logins": 0,
            "active_sessions": 0,
            "api_calls": 0,
            "lockouts": 0,
        }

        logger.info("AuthenticationManager initialized")

    def create_api_key(self, user_id: str, role: UserRole) -> str:
        """
        Create new API key for user.

        Args:
            user_id: User identifier
            role: User role

        Returns:
            API key string
        """
        with self.lock:
            # Generate secure API key
            api_key = secrets.token_urlsafe(32)

            self.api_keys[api_key] = {
                "user_id": user_id,
                "role": role,
                "created_at": datetime.now(),
                "last_used": None,
            }

            logger.info(f"API key created for user {user_id} with role {role.value}")
            return api_key

    def validate_api_key(self, api_key: str) -> Optional[Dict]:
        """
        Validate API key.

        Args:
            api_key: API key to validate

        Returns:
            User info if valid, None otherwise
        """
        with self.lock:
            if api_key not in self.api_keys:
                logger.warning("Invalid API key used")
                return None

            user_info = self.api_keys[api_key]
            user_info["last_used"] = datetime.now()
            self.stats["api_calls"] += 1

            return user_info

    def is_account_locked(self, user_id: str) -> bool:
        """
        Check if account is locked.

        Args:
            user_id: User identifier

        Returns:
            True if locked
        """
        with self.lock:
            if user_id not in self.locked_accounts:
                return False

            unlock_time = self.locked_accounts[user_id]

            if datetime.now() >= unlock_time:
                # Lockout expired
                del self.locked_accounts[user_id]
                logger.info(f"Account {user_id} unlocked (timeout expired)")
                return False

            return True

    def record_login_attempt(
        self,
        user_id: str,
        success: bool,
        ip_address: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        """
        Record login attempt.

        Args:
            user_id: User identifier
            success: Whether login succeeded
            ip_address: Client IP address
            reason: Failure reason
        """
        with self.lock:
            attempt = LoginAttempt(
                user_id=user_id,
                timestamp=datetime.now(),
                success=success,
                ip_address=ip_address,
                reason=reason,
            )

            if user_id not in self.login_attempts:
                self.login_attempts[user_id] = []

            self.login_attempts[user_id].append(attempt)

            # Keep only recent attempts (last hour)
            cutoff = datetime.now() - timedelta(hours=1)
            self.login_attempts[user_id] = [
                a for a in self.login_attempts[user_id] if a.timestamp > cutoff
            ]

            if success:
                self.stats["total_logins"] += 1
            else:
                self.stats["failed_logins"] += 1

                # Check for lockout
                recent_failures = [
                    a
                    for a in self.login_attempts[user_id]
                    if not a.success and a.timestamp > datetime.now() - timedelta(minutes=15)
                ]

                if len(recent_failures) >= self.max_failed_attempts:
                    self._lock_account(user_id)

    def _lock_account(self, user_id: str):
        """
        Lock account due to failed login attempts.

        Args:
            user_id: User identifier
        """
        unlock_time = datetime.now() + timedelta(seconds=self.lockout_duration)
        self.locked_accounts[user_id] = unlock_time
        self.stats["lockouts"] += 1

        logger.warning(
            f"Account {user_id} locked until {unlock_time} " f"(too many failed attempts)"
        )

    def create_session(
        self,
        user_id: str,
        role: UserRole,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """
        Create new session.

        Args:
            user_id: User identifier
            role: User role
            ip_address: Client IP
            user_agent: Client user agent

        Returns:
            Session ID
        """
        with self.lock:
            # Generate secure session ID
            session_id = secrets.token_urlsafe(32)

            now = datetime.now()
            expires_at = now + timedelta(seconds=self.session_timeout)

            session = Session(
                session_id=session_id,
                user_id=user_id,
                role=role,
                created_at=now,
                expires_at=expires_at,
                last_activity=now,
                ip_address=ip_address,
                user_agent=user_agent,
            )

            self.sessions[session_id] = session
            self.stats["active_sessions"] = len([s for s in self.sessions.values() if s.is_active])

            logger.info(f"Session created for user {user_id} (expires: {expires_at})")
            return session_id

    def validate_session(self, session_id: str) -> Optional[Session]:
        """
        Validate session and refresh expiration.

        Args:
            session_id: Session ID

        Returns:
            Session if valid, None otherwise
        """
        with self.lock:
            if session_id not in self.sessions:
                return None

            session = self.sessions[session_id]

            # Check if expired
            if datetime.now() > session.expires_at:
                logger.info(f"Session {session_id} expired")
                session.is_active = False
                return None

            # Check if active
            if not session.is_active:
                return None

            # Refresh session
            session.last_activity = datetime.now()
            session.expires_at = datetime.now() + timedelta(seconds=self.session_timeout)

            return session

    def invalidate_session(self, session_id: str):
        """
        Invalidate session (logout).

        Args:
            session_id: Session ID
        """
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id].is_active = False
                logger.info(f"Session {session_id} invalidated")

    def has_permission(self, session_id: str, permission: Permission) -> bool:
        """
        Check if session has permission.

        Args:
            session_id: Session ID
            permission: Permission to check

        Returns:
            True if authorized
        """
        session = self.validate_session(session_id)
        if not session:
            return False

        # Get role permissions
        role_perms = ROLE_PERMISSIONS.get(session.role, [])
        return permission in role_perms

    def cleanup_expired_sessions(self):
        """Remove expired sessions."""
        with self.lock:
            now = datetime.now()
            expired = [sid for sid, session in self.sessions.items() if now > session.expires_at]

            for sid in expired:
                del self.sessions[sid]

            if expired:
                logger.info(f"Cleaned up {len(expired)} expired sessions")

            self.stats["active_sessions"] = len([s for s in self.sessions.values() if s.is_active])

    def get_stats(self) -> dict:
        """Get authentication statistics."""
        with self.lock:
            return {
                **self.stats,
                "locked_accounts": len(self.locked_accounts),
                "total_api_keys": len(self.api_keys),
            }


# Global instance
_auth_manager: Optional[AuthenticationManager] = None


def get_auth_manager() -> AuthenticationManager:
    """
    Get global authentication manager.

    Returns:
        AuthenticationManager instance
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthenticationManager()
    return _auth_manager


# Decorator for requiring authentication
def require_auth(permission: Optional[Permission] = None):
    """
    Decorator requiring authentication.

    Args:
        permission: Required permission (None = just authentication)
    """

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            # Extract session_id from kwargs or self
            session_id = kwargs.get("session_id") or getattr(self, "session_id", None)

            if not session_id:
                raise PermissionError("No session ID provided")

            auth = get_auth_manager()
            session = auth.validate_session(session_id)

            if not session:
                raise PermissionError("Invalid or expired session")

            if permission and not auth.has_permission(session_id, permission):
                raise PermissionError(f"Permission denied: {permission.value}")

            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class PermissionError(Exception):
    """Raised when permission check fails."""

    pass


if __name__ == "__main__":
    # Test authentication
    auth = get_auth_manager()

    # Create API key
    api_key = auth.create_api_key("user123", UserRole.ADMIN)
    print(f"API Key created: {api_key}")

    # Validate API key
    user_info = auth.validate_api_key(api_key)
    print(f"User info: {user_info}")

    # Create session
    session_id = auth.create_session("user123", UserRole.ADMIN)
    print(f"Session created: {session_id}")

    # Check permission
    has_perm = auth.has_permission(session_id, Permission.CREATE_ACCOUNT)
    print(f"Has permission: {has_perm}")
