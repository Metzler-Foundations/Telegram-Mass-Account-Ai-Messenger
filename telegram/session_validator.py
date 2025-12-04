#!/usr/bin/env python3
"""Pyrogram session corruption detection."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class SessionValidator:
    """Validates Pyrogram session files."""
    
    @staticmethod
    def validate_session_file(session_path: str) -> bool:
        """Check if session file is valid."""
        path = Path(session_path)
        
        if not path.exists():
            logger.warning(f"Session file not found: {session_path}")
            return False
        
        # Check file size (corrupted sessions are often 0 bytes)
        size = path.stat().st_size
        if size == 0:
            logger.error(f"Session file is empty (corrupted): {session_path}")
            return False
        
        if size < 100:  # Minimum reasonable size
            logger.warning(f"Session file suspiciously small: {size} bytes")
            return False
        
        # Check file can be read
        try:
            with open(path, 'rb') as f:
                header = f.read(4)
                if not header:
                    logger.error(f"Cannot read session file: {session_path}")
                    return False
        except Exception as e:
            logger.error(f"Session file read error: {e}")
            return False
        
        return True
    
    @staticmethod
    def backup_session(session_path: str) -> Optional[str]:
        """Create backup of session file."""
        import shutil
        from datetime import datetime
        
        try:
            path = Path(session_path)
            if not path.exists():
                return None
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = path.with_suffix(f'.backup_{timestamp}.session')
            
            shutil.copy2(path, backup_path)
            logger.info(f"Session backed up to {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Session backup failed: {e}")
            return None


def validate_session(session_path: str) -> bool:
    """Validate session file before use."""
    return SessionValidator.validate_session_file(session_path)





