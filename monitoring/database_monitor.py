#!/usr/bin/env python3
"""Database monitoring - Track size, performance, health."""

import os
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DatabaseMonitor:
    """Monitors database health and metrics."""
    
    def __init__(self, db_paths: list, alert_size_mb: int = 1000):
        self.db_paths = [Path(p) for p in db_paths]
        self.alert_size_mb = alert_size_mb
        self.metrics = {}
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect database metrics."""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'databases': {}
        }
        
        for db_path in self.db_paths:
            if not db_path.exists():
                continue
            
            size_bytes = db_path.stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            
            db_metrics = {
                'size_bytes': size_bytes,
                'size_mb': round(size_mb, 2),
                'modified': datetime.fromtimestamp(db_path.stat().st_mtime).isoformat(),
                'alert': size_mb > self.alert_size_mb
            }
            
            if db_metrics['alert']:
                logger.warning(f"Database {db_path.name} exceeds size limit: {size_mb:.2f}MB")
            
            metrics['databases'][str(db_path)] = db_metrics
        
        self.metrics = metrics
        return metrics
    
    def get_total_size_mb(self) -> float:
        """Get total database size in MB."""
        total = sum(
            m['size_mb']
            for m in self.metrics.get('databases', {}).values()
        )
        return round(total, 2)
    
    def should_alert(self) -> bool:
        """Check if any database needs attention."""
        return any(
            m.get('alert', False)
            for m in self.metrics.get('databases', {}).values()
        )


_db_monitor = None

def get_db_monitor(db_paths: list = None):
    global _db_monitor
    if _db_monitor is None and db_paths:
        _db_monitor = DatabaseMonitor(db_paths)
    return _db_monitor



