"""
Automated Proxy Cleanup Service - Background cleanup with operator notifications.

Features:
- Scheduled cleanup of failed/expired proxies
- Operator notifications for cleanup events
- Audit logs for destructive actions
- Configurable cleanup thresholds
- Manual override controls
"""

import logging
import sqlite3
import asyncio
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class CleanupReason(Enum):
    """Reasons for proxy cleanup."""
    LOW_SCORE = "low_score"
    HIGH_FRAUD = "high_fraud"
    REPEATED_FAILURES = "repeated_failures"
    EXPIRED = "expired"
    BLACKLISTED = "blacklisted"
    MANUAL = "manual"


@dataclass
class CleanupEvent:
    """Cleanup event record."""
    event_id: Optional[int]
    proxy_key: str
    reason: CleanupReason
    score: float
    failure_count: int
    age_days: int
    operator_notified: bool
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'event_id': self.event_id,
            'proxy_key': self.proxy_key,
            'reason': self.reason.value,
            'score': self.score,
            'failure_count': self.failure_count,
            'age_days': self.age_days,
            'operator_notified': self.operator_notified,
            'timestamp': self.timestamp.isoformat()
        }


class AutomatedProxyCleanupService:
    """
    Automated cleanup service for proxy pool maintenance.
    """
    
    def __init__(
        self,
        proxy_pool_manager,
        db_path: str = "proxy_cleanup_audit.db"
    ):
        """Initialize cleanup service."""
        self.proxy_pool_manager = proxy_pool_manager
        self.db_path = db_path
        self._init_database()
        
        # Cleanup configuration
        self.config = {
            'cleanup_interval_hours': 6,       # Run cleanup every 6 hours
            'min_score_threshold': 20,         # Remove proxies below this score
            'max_failure_threshold': 10,       # Remove after this many failures
            'max_age_days': 30,                # Remove proxies older than this
            'max_fraud_score': 0.8,            # Remove if fraud score exceeds this
            'notify_on_cleanup': True,         # Send notifications
            'batch_size': 100,                 # Clean up max this many per run
        }
        
        # Notification callbacks
        self.notification_callbacks: List[Callable] = []
        
        # Service state
        self.is_running = False
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.stats = {
            'total_cleaned': 0,
            'last_cleanup': None,
            'last_cleanup_count': 0
        }
    
    def _init_database(self):
        """Initialize audit database."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cleanup_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy_key TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    score REAL,
                    failure_count INTEGER,
                    age_days INTEGER,
                    operator_notified INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_cleanup_timestamp 
                ON cleanup_events(timestamp DESC)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_cleanup_reason 
                ON cleanup_events(reason, timestamp DESC)
            ''')
            
            conn.commit()
    
    def add_notification_callback(self, callback: Callable):
        """Add a callback for cleanup notifications."""
        self.notification_callbacks.append(callback)
    
    def _notify_operators(self, event: CleanupEvent):
        """Send notification to operators."""
        if not self.config['notify_on_cleanup']:
            return
        
        for callback in self.notification_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning(f"Notification callback failed: {e}")
    
    async def start(self):
        """Start automated cleanup service."""
        if self.is_running:
            logger.warning("Cleanup service already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting automated proxy cleanup service")
        
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
    
    async def stop(self):
        """Stop cleanup service."""
        self.is_running = False
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Stopped automated proxy cleanup service")
    
    async def _cleanup_loop(self):
        """Main cleanup loop."""
        while self.is_running:
            try:
                await self.run_cleanup()
                
                # Wait for next cleanup interval
                await asyncio.sleep(self.config['cleanup_interval_hours'] * 3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup loop error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def run_cleanup(self) -> Dict[str, Any]:
        """
        Run cleanup operation.
        
        Returns:
            Dict with cleanup results
        """
        logger.info("🧹 Running automated proxy cleanup...")
        
        cleanup_events = []
        proxies_to_remove = []
        
        try:
            # Get all proxies
            proxies, _ = self.proxy_pool_manager.get_proxies_paginated(
                page=1,
                page_size=10000,
                assigned_only=False
            )
            
            now = datetime.now()
            
            for proxy in proxies:
                # Skip assigned proxies
                if proxy.get('assigned_account'):
                    continue
                
                proxy_key = proxy.get('proxy_key') or f"{proxy.get('ip')}:{proxy.get('port')}"
                score = proxy.get('score', 100)
                failure_count = proxy.get('failure_count', 0)
                fraud_score = proxy.get('fraud_score', 0)
                
                # Calculate age
                first_seen = proxy.get('first_seen')
                if first_seen:
                    try:
                        first_seen_dt = datetime.fromisoformat(first_seen)
                        age_days = (now - first_seen_dt).days
                    except:
                        age_days = 0
                else:
                    age_days = 0
                
                # Determine if should be cleaned up
                reason = None
                
                if score < self.config['min_score_threshold']:
                    reason = CleanupReason.LOW_SCORE
                elif failure_count >= self.config['max_failure_threshold']:
                    reason = CleanupReason.REPEATED_FAILURES
                elif fraud_score >= self.config['max_fraud_score']:
                    reason = CleanupReason.HIGH_FRAUD
                elif age_days > self.config['max_age_days'] and score < 50:
                    reason = CleanupReason.EXPIRED
                elif proxy.get('status') == 'blacklisted':
                    reason = CleanupReason.BLACKLISTED
                
                if reason:
                    event = CleanupEvent(
                        event_id=None,
                        proxy_key=proxy_key,
                        reason=reason,
                        score=score,
                        failure_count=failure_count,
                        age_days=age_days,
                        operator_notified=False,
                        timestamp=now
                    )
                    cleanup_events.append(event)
                    proxies_to_remove.append(proxy_key)
                    
                    # Limit batch size
                    if len(proxies_to_remove) >= self.config['batch_size']:
                        break
            
            # Perform cleanup
            if proxies_to_remove:
                await self._remove_proxies(proxies_to_remove)
                
                # Log events
                for event in cleanup_events:
                    self._log_cleanup_event(event)
                    
                    # Notify operators
                    if self.config['notify_on_cleanup']:
                        event.operator_notified = True
                        self._notify_operators(event)
                
                # Update statistics
                self.stats['total_cleaned'] += len(proxies_to_remove)
                self.stats['last_cleanup'] = now
                self.stats['last_cleanup_count'] = len(proxies_to_remove)
                
                logger.info(
                    f"✅ Cleaned up {len(proxies_to_remove)} proxies. "
                    f"Total cleaned: {self.stats['total_cleaned']}"
                )
            else:
                logger.info("✨ No proxies need cleanup at this time")
            
            return {
                'success': True,
                'proxies_cleaned': len(proxies_to_remove),
                'reasons': {r.value: sum(1 for e in cleanup_events if e.reason == r) for r in CleanupReason},
                'timestamp': now.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cleanup operation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def _remove_proxies(self, proxy_keys: List[str]):
        """Remove proxies from pool."""
        try:
            import sqlite3
            with sqlite3.connect(self.proxy_pool_manager.db_path) as conn:
                # Remove from database
                conn.executemany(
                    'DELETE FROM proxies WHERE proxy_key = ?',
                    [(key,) for key in proxy_keys]
                )
                conn.commit()
            
            # Remove from memory
            for key in proxy_keys:
                if key in self.proxy_pool_manager.proxies:
                    del self.proxy_pool_manager.proxies[key]
                if key in self.proxy_pool_manager.available_proxies:
                    self.proxy_pool_manager.available_proxies.discard(key)
            
            logger.info(f"Removed {len(proxy_keys)} proxies from pool")
            
        except Exception as e:
            logger.error(f"Failed to remove proxies: {e}")
            raise
    
    def _log_cleanup_event(self, event: CleanupEvent):
        """Log cleanup event to audit database."""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO cleanup_events
                    (proxy_key, reason, score, failure_count, age_days, operator_notified)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    event.proxy_key,
                    event.reason.value,
                    event.score,
                    event.failure_count,
                    event.age_days,
                    1 if event.operator_notified else 0
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to log cleanup event: {e}")
    
    def get_cleanup_history(self, limit: int = 100) -> List[CleanupEvent]:
        """Get cleanup history."""
        events = []
        
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM cleanup_events
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (limit,))
                
                for row in cursor:
                    events.append(CleanupEvent(
                        event_id=row['event_id'],
                        proxy_key=row['proxy_key'],
                        reason=CleanupReason(row['reason']),
                        score=row['score'],
                        failure_count=row['failure_count'],
                        age_days=row['age_days'],
                        operator_notified=bool(row['operator_notified']),
                        timestamp=datetime.fromisoformat(row['timestamp'])
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to get cleanup history: {e}")
        
        return events


# Singleton
_cleanup_service: Optional[AutomatedProxyCleanupService] = None


def get_cleanup_service(proxy_pool_manager=None) -> AutomatedProxyCleanupService:
    """Get singleton cleanup service."""
    global _cleanup_service
    if _cleanup_service is None and proxy_pool_manager:
        _cleanup_service = AutomatedProxyCleanupService(proxy_pool_manager)
    return _cleanup_service








