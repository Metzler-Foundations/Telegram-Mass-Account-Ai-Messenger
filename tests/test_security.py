#!/usr/bin/env python3
"""Security module tests."""

import pytest
from core.authentication import AuthenticationManager, UserRole, Permission
from utils.csrf_protection import CSRFProtection
from utils.security_logger import PIIRedactor


class TestAuthentication:
    """Test authentication system."""
    
    def test_api_key_creation(self):
        auth = AuthenticationManager()
        api_key = auth.create_api_key("user123", UserRole.ADMIN)
        assert len(api_key) > 20
    
    def test_api_key_validation(self):
        auth = AuthenticationManager()
        api_key = auth.create_api_key("user123", UserRole.ADMIN)
        user_info = auth.validate_api_key(api_key)
        assert user_info['user_id'] == "user123"
    
    def test_session_creation(self):
        auth = AuthenticationManager()
        session_id = auth.create_session("user123", UserRole.OPERATOR)
        assert len(session_id) > 20
    
    def test_session_validation(self):
        auth = AuthenticationManager()
        session_id = auth.create_session("user123", UserRole.ADMIN)
        session = auth.validate_session(session_id)
        assert session is not None
        assert session.user_id == "user123"
    
    def test_permission_check(self):
        auth = AuthenticationManager()
        session_id = auth.create_session("user123", UserRole.ADMIN)
        has_perm = auth.has_permission(session_id, Permission.CREATE_ACCOUNT)
        assert has_perm is True
    
    def test_account_lockout(self):
        auth = AuthenticationManager(max_failed_attempts=3)
        
        for i in range(5):
            auth.record_login_attempt("user123", False)
        
        assert auth.is_account_locked("user123") is True


class TestCSRFProtection:
    """Test CSRF protection."""
    
    def test_token_generation(self):
        csrf = CSRFProtection()
        token = csrf.generate_token("session123")
        assert len(token) > 20
    
    def test_token_validation(self):
        csrf = CSRFProtection()
        token = csrf.generate_token("session123")
        valid = csrf.validate_token(token, "session123")
        assert valid is True
    
    def test_token_wrong_session(self):
        csrf = CSRFProtection()
        token = csrf.generate_token("session123")
        valid = csrf.validate_token(token, "wrong_session")
        assert valid is False


class TestPIIRedaction:
    """Test PII redaction."""
    
    def test_phone_redaction(self):
        text = "Call me at +1234567890"
        redacted = PIIRedactor.redact(text, ['phone'])
        assert "+1234567890" not in redacted
        assert "[PHONE:" in redacted
    
    def test_email_redaction(self):
        text = "Email: user@example.com"
        redacted = PIIRedactor.redact(text, ['email'])
        assert "user@example.com" not in redacted
    
    def test_hash_sensitive(self):
        hashed = PIIRedactor.hash_sensitive("secret123")
        assert "secret123" not in hashed
        assert "[HASH:" in hashed

