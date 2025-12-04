#!/usr/bin/env python3
"""Session file encryption at rest."""

import os
import logging
from pathlib import Path
from cryptography.fernet import Fernet
from typing import Optional

logger = logging.getLogger(__name__)


class SessionEncryption:
    """Encrypts Pyrogram session files at rest."""
    
    def __init__(self, key: Optional[bytes] = None):
        from core.secrets_manager import get_secrets_manager
        
        if key:
            self.fernet = Fernet(key)
        else:
            secrets = get_secrets_manager()
            key = secrets._get_or_create_key('session_encryption_key')
            self.fernet = Fernet(key)
    
    def encrypt_session_file(self, session_path: str) -> bool:
        """Encrypt session file in place."""
        try:
            path = Path(session_path)
            if not path.exists():
                return False
            
            # Read session data
            with open(path, 'rb') as f:
                data = f.read()
            
            # Encrypt
            encrypted = self.fernet.encrypt(data)
            
            # Write back with .enc extension
            enc_path = path.with_suffix(path.suffix + '.enc')
            with open(enc_path, 'wb') as f:
                f.write(encrypted)
            
            # Set restrictive permissions
            os.chmod(enc_path, 0o600)
            
            # Remove original
            path.unlink()
            
            logger.info(f"Encrypted session file: {session_path}")
            return True
            
        except Exception as e:
            logger.error(f"Session encryption failed: {e}")
            return False
    
    def decrypt_session_file(self, encrypted_path: str) -> Optional[bytes]:
        """Decrypt session file."""
        try:
            with open(encrypted_path, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted = self.fernet.decrypt(encrypted_data)
            return decrypted
            
        except Exception as e:
            logger.error(f"Session decryption failed: {e}")
            return None


_session_enc = None

def get_session_encryption():
    global _session_enc
    if _session_enc is None:
        _session_enc = SessionEncryption()
    return _session_enc



