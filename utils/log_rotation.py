#!/usr/bin/env python3
"""Log rotation for audit and application logs."""

import gzip
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class LogRotationManager:
    """Manages log file rotation and compression."""
    
    def __init__(self, log_dir: str = "logs", max_size_mb: int = 50, keep_days: int = 30):
        self.log_dir = Path(log_dir)
        self.max_size = max_size_mb * 1024 * 1024
        self.keep_days = keep_days
    
    def rotate_if_needed(self, log_file: str) -> bool:
        """Rotate log file if needed."""
        path = self.log_dir / log_file
        
        if not path.exists():
            return False
        
        if path.stat().st_size > self.max_size:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            rotated_name = f"{log_file}.{timestamp}"
            rotated_path = self.log_dir / rotated_name
            
            # Rotate
            shutil.move(path, rotated_path)
            
            # Compress
            with open(rotated_path, 'rb') as f_in:
                with gzip.open(f"{rotated_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            rotated_path.unlink()
            logger.info(f"Rotated and compressed {log_file}")
            return True
        
        return False
    
    def cleanup_old_logs(self):
        """Remove old compressed logs."""
        cutoff = datetime.now() - timedelta(days=self.keep_days)
        
        for log_file in self.log_dir.glob("*.gz"):
            if datetime.fromtimestamp(log_file.stat().st_mtime) < cutoff:
                log_file.unlink()
                logger.debug(f"Removed old log: {log_file}")



