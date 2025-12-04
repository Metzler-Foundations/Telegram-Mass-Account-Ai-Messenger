#!/usr/bin/env python3
"""
File Security - Secure file operations with permission management.

Features:
- File permission enforcement
- Integrity checking
- Secure temp file handling
- Path sanitization
"""

import os
import hashlib
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict
import json

logger = logging.getLogger(__name__)


class FileSecurityManager:
    """Manages secure file operations."""
    
    SENSITIVE_FILES = {
        'config.json': 0o600,
        '.secrets.encrypted': 0o600,
        '*.db': 0o600,
        '*.session': 0o600,
        'encryption_key.bin': 0o600,
        'master.key': 0o600,
    }
    
    def __init__(self):
        self.integrity_hashes: Dict[str, str] = {}
        self.integrity_file = Path('.file_integrity.json')
        self._load_integrity_db()
    
    def secure_write(self, file_path: str, content: bytes, permissions: int = 0o600) -> bool:
        """Write file with secure permissions."""
        try:
            path = Path(file_path)
            
            # Atomic write
            temp_fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix='.tmp_')
            try:
                os.write(temp_fd, content)
                os.close(temp_fd)
                os.chmod(temp_path, permissions)
                shutil.move(temp_path, path)
                
                # Update integrity hash
                self._update_integrity_hash(file_path)
                
                logger.debug(f"Securely wrote {file_path} with permissions {oct(permissions)}")
                return True
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"Secure write failed for {file_path}: {e}")
            return False
    
    def check_permissions(self, file_path: str) -> bool:
        """Check if file has secure permissions."""
        try:
            path = Path(file_path)
            if not path.exists():
                return True
            
            stat_info = path.stat()
            mode = stat_info.st_mode & 0o777
            
            # Check against sensitive files
            for pattern, required_perms in self.SENSITIVE_FILES.items():
                if pattern.startswith('*'):
                    if file_path.endswith(pattern[1:]):
                        if mode != required_perms:
                            logger.warning(
                                f"File {file_path} has insecure permissions "
                                f"{oct(mode)} (should be {oct(required_perms)})"
                            )
                            return False
                elif pattern in file_path:
                    if mode != required_perms:
                        logger.warning(
                            f"File {file_path} has insecure permissions "
                            f"{oct(mode)} (should be {oct(required_perms)})"
                        )
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Permission check failed for {file_path}: {e}")
            return False
    
    def fix_permissions(self, file_path: str) -> bool:
        """Fix file permissions."""
        try:
            path = Path(file_path)
            if not path.exists():
                return True
            
            # Determine required permissions
            required_perms = 0o600
            for pattern, perms in self.SENSITIVE_FILES.items():
                if pattern.startswith('*'):
                    if file_path.endswith(pattern[1:]):
                        required_perms = perms
                        break
                elif pattern in file_path:
                    required_perms = perms
                    break
            
            os.chmod(path, required_perms)
            logger.info(f"Fixed permissions for {file_path} to {oct(required_perms)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to fix permissions for {file_path}: {e}")
            return False
    
    def _calculate_hash(self, file_path: str) -> Optional[str]:
        """Calculate SHA256 hash of file."""
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for block in iter(lambda: f.read(4096), b''):
                    sha256.update(block)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Hash calculation failed for {file_path}: {e}")
            return None
    
    def _update_integrity_hash(self, file_path: str):
        """Update integrity hash for file."""
        hash_val = self._calculate_hash(file_path)
        if hash_val:
            self.integrity_hashes[file_path] = hash_val
            self._save_integrity_db()
    
    def verify_integrity(self, file_path: str) -> bool:
        """Verify file integrity against stored hash."""
        if file_path not in self.integrity_hashes:
            logger.debug(f"No integrity hash for {file_path}")
            return True
        
        current_hash = self._calculate_hash(file_path)
        expected_hash = self.integrity_hashes[file_path]
        
        if current_hash != expected_hash:
            logger.error(f"Integrity check FAILED for {file_path}")
            return False
        
        return True
    
    def _load_integrity_db(self):
        """Load integrity database."""
        if self.integrity_file.exists():
            try:
                with open(self.integrity_file, 'r') as f:
                    self.integrity_hashes = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load integrity db: {e}")
    
    def _save_integrity_db(self):
        """Save integrity database."""
        try:
            with open(self.integrity_file, 'w') as f:
                json.dump(self.integrity_hashes, f, indent=2)
            os.chmod(self.integrity_file, 0o600)
        except Exception as e:
            logger.error(f"Failed to save integrity db: {e}")


_file_security = None

def get_file_security():
    global _file_security
    if _file_security is None:
        _file_security = FileSecurityManager()
    return _file_security



