#!/usr/bin/env python3
"""CSRF protection for state-changing operations."""

import secrets
import hmac
import hashlib
import time
from typing import Optional, Dict
import threading

class CSRFProtection:
    """CSRF token generation and validation."""
    
    def __init__(self, secret_key: Optional[bytes] = None, token_expiry: int = 3600):
        self.secret_key = secret_key or secrets.token_bytes(32)
        self.token_expiry = token_expiry
        self.tokens: Dict[str, float] = {}
        self.lock = threading.Lock()
    
    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        timestamp = str(int(time.time())).encode()
        message = session_id.encode() + timestamp
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
        token = f"{session_id}:{timestamp.decode()}:{signature}"
        
        with self.lock:
            self.tokens[token] = time.time()
        
        return token
    
    def validate_token(self, token: str, session_id: str) -> bool:
        """Validate CSRF token."""
        try:
            parts = token.split(':')
            if len(parts) != 3:
                return False
            
            tok_session, tok_time, tok_sig = parts
            
            if tok_session != session_id:
                return False
            
            # Check expiry
            if time.time() - int(tok_time) > self.token_expiry:
                return False
            
            # Verify signature
            message = tok_session.encode() + tok_time.encode()
            expected_sig = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()
            
            return hmac.compare_digest(tok_sig, expected_sig)
            
        except Exception:
            return False

_csrf = None

def get_csrf():
    global _csrf
    if _csrf is None:
        _csrf = CSRFProtection()
    return _csrf


