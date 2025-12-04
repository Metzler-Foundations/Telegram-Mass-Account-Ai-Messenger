"""
Account Audit Log - Comprehensive tracking for account lifecycle events.

Features:
- Track proxy assignments and changes
- Record device fingerprints used
- Log SMS provider costs and transaction IDs
- Track username generation outcomes
- Store creation timestamps and success/failure reasons
- Enable forensic analysis and cost reporting
"""

import logging
import sqlite3
import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    ACCOUNT_CREATION_START = "account_creation_start"
    ACCOUNT_CREATION_SUCCESS = "account_creation_success"
    ACCOUNT_CREATION_FAILURE = "account_creation_failure"
    
    PROXY_ASSIGNED = "proxy_assigned"
    PROXY_CHANGED = "proxy_changed"
    PROXY_FAILED = "proxy_failed"
    
    SMS_NUMBER_PURCHASED = "sms_number_purchased"
    SMS_CODE_RECEIVED = "sms_code_received"
    SMS_CODE_FAILED = "sms_code_failed"
    
    USERNAME_GENERATED = "username_generated"
    USERNAME_ASSIGNED = "username_assigned"
    USERNAME_COLLISION = "username_collision"
    
    DEVICE_FINGERPRINT_CREATED = "device_fingerprint_created"
    
    PROFILE_PHOTO_UPLOADED = "profile_photo_uploaded"
    BIO_SET = "bio_set"
    
    WARMUP_STARTED = "warmup_started"
    WARMUP_COMPLETED = "warmup_completed"
    
    ACCOUNT_BANNED = "account_banned"
    ACCOUNT_QUARANTINED = "account_quarantined"


@dataclass
class AuditEvent:
    """Audit event data structure."""
    event_id: Optional[int]
    phone_number: str
    event_type: AuditEventType
    timestamp: datetime
    
    # Context data
    proxy_used: Optional[str] = None  # Format: ip:port
    proxy_country: Optional[str] = None
    device_fingerprint: Optional[str] = None  # Hash of device parameters
    
    # SMS provider details
    sms_provider: Optional[str] = None
    sms_transaction_id: Optional[str] = None
    sms_operator: Optional[str] = None
    sms_cost: Optional[float] = None
    sms_currency: str = "USD"
    
    # Username details
    username_attempted: Optional[str] = None
    username_success: Optional[bool] = None
    
    # Status and metadata
    success: bool = True
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    # Cost tracking
    total_cost: Optional[float] = None  # Running total for this account
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        if self.metadata:
            data['metadata'] = json.dumps(self.metadata)
        return data


class AccountAuditLog:
    """
    Comprehensive audit logging for account lifecycle events.
    """
    
    def __init__(self, db_path: str = "accounts_audit.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool
            self._connection_pool = get_pool(self.db_path)
        except: pass
        self._init_database()
    
    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return self._get_connection()
    
    def _init_database(self):
        """Initialize audit log database."""
        with self._get_connection() as conn:
            # Main audit events table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    proxy_used TEXT,
                    proxy_country TEXT,
                    device_fingerprint TEXT,
                    
                    sms_provider TEXT,
                    sms_transaction_id TEXT,
                    sms_operator TEXT,
                    sms_cost REAL,
                    sms_currency TEXT DEFAULT 'USD',
                    
                    username_attempted TEXT,
                    username_success INTEGER,
                    
                    success INTEGER DEFAULT 1,
                    error_message TEXT,
                    metadata TEXT,
                    
                    total_cost REAL
                )
            ''')
            
            # Indexes for fast queries
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_phone 
                ON audit_events(phone_number, timestamp DESC)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_event_type 
                ON audit_events(event_type, timestamp DESC)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_proxy 
                ON audit_events(proxy_used, timestamp DESC)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_sms_provider 
                ON audit_events(sms_provider, timestamp DESC)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_audit_timestamp 
                ON audit_events(timestamp DESC)
            ''')
            
            # Account summary view for quick cost/proxy lookups
            conn.execute('''
                CREATE TABLE IF NOT EXISTS account_summary (
                    phone_number TEXT PRIMARY KEY,
                    created_at TIMESTAMP,
                    total_cost_usd REAL DEFAULT 0,
                    proxy_used TEXT,
                    device_fingerprint TEXT,
                    sms_provider TEXT,
                    username TEXT,
                    status TEXT,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def log_event(self, event: AuditEvent) -> int:
        """
        Log an audit event.
        
        Args:
            event: AuditEvent to log
            
        Returns:
            Event ID
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    INSERT INTO audit_events (
                        phone_number, event_type, timestamp,
                        proxy_used, proxy_country, device_fingerprint,
                        sms_provider, sms_transaction_id, sms_operator, sms_cost, sms_currency,
                        username_attempted, username_success,
                        success, error_message, metadata, total_cost
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    event.phone_number,
                    event.event_type.value,
                    event.timestamp,
                    event.proxy_used,
                    event.proxy_country,
                    event.device_fingerprint,
                    event.sms_provider,
                    event.sms_transaction_id,
                    event.sms_operator,
                    event.sms_cost,
                    event.sms_currency,
                    event.username_attempted,
                    event.username_success,
                    event.success,
                    event.error_message,
                    json.dumps(event.metadata) if event.metadata else None,
                    event.total_cost
                ))
                
                event_id = cursor.lastrowid
                conn.commit()
                
                # Update summary if this is a significant event
                self._update_account_summary(conn, event)
                
                logger.debug(f"Logged audit event {event_id}: {event.event_type.value} for {event.phone_number}")
                return event_id
                
        except Exception as e:
            logger.error(f"Failed to log audit event: {e}")
            return -1
    
    def _update_account_summary(self, conn: sqlite3.Connection, event: AuditEvent):
        """Update account summary based on event."""
        try:
            # Get current summary
            cursor = conn.execute(
                'SELECT total_cost_usd FROM account_summary WHERE phone_number = ?',
                (event.phone_number,)
            )
            row = cursor.fetchone()
            
            current_cost = row[0] if row else 0.0
            new_cost = current_cost + (event.sms_cost or 0.0)
            
            # Upsert summary
            conn.execute('''
                INSERT INTO account_summary (
                    phone_number, created_at, total_cost_usd, proxy_used, 
                    device_fingerprint, sms_provider, username, status, last_updated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(phone_number) DO UPDATE SET
                    total_cost_usd = ?,
                    proxy_used = COALESCE(excluded.proxy_used, proxy_used),
                    device_fingerprint = COALESCE(excluded.device_fingerprint, device_fingerprint),
                    sms_provider = COALESCE(excluded.sms_provider, sms_provider),
                    username = COALESCE(excluded.username, username),
                    status = excluded.status,
                    last_updated = excluded.last_updated
            ''', (
                event.phone_number,
                event.timestamp if event.event_type == AuditEventType.ACCOUNT_CREATION_START else None,
                new_cost,
                event.proxy_used,
                event.device_fingerprint,
                event.sms_provider,
                event.username_attempted if event.username_success else None,
                self._event_type_to_status(event.event_type),
                event.timestamp,
                new_cost
            ))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"Failed to update account summary: {e}")
    
    @staticmethod
    def _event_type_to_status(event_type: AuditEventType) -> str:
        """Convert event type to account status."""
        status_map = {
            AuditEventType.ACCOUNT_CREATION_START: "creating",
            AuditEventType.ACCOUNT_CREATION_SUCCESS: "created",
            AuditEventType.ACCOUNT_CREATION_FAILURE: "failed",
            AuditEventType.WARMUP_STARTED: "warming_up",
            AuditEventType.WARMUP_COMPLETED: "ready",
            AuditEventType.ACCOUNT_BANNED: "banned",
            AuditEventType.ACCOUNT_QUARANTINED: "quarantined",
        }
        return status_map.get(event_type, "active")
    
    def get_account_history(
        self, 
        phone_number: str, 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get audit history for a specific account.
        
        Args:
            phone_number: Phone number to query
            limit: Maximum events to return
            
        Returns:
            List of audit events
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM audit_events 
                    WHERE phone_number = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (phone_number, limit))
                
                events = []
                for row in cursor:
                    event_dict = dict(row)
                    # Parse metadata if present
                    if event_dict.get('metadata'):
                        try:
                            event_dict['metadata'] = json.loads(event_dict['metadata'])
                        except:
                            pass
                    events.append(event_dict)
                
                return events
                
        except Exception as e:
            logger.error(f"Failed to get account history: {e}")
            return []
    
    def get_account_cost(self, phone_number: str) -> float:
        """Get total cost for an account."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    'SELECT total_cost_usd FROM account_summary WHERE phone_number = ?',
                    (phone_number,)
                )
                row = cursor.fetchone()
                return row[0] if row else 0.0
        except Exception as e:
            logger.error(f"Failed to get account cost: {e}")
            return 0.0
    
    def get_total_costs(
        self, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by_provider: bool = False
    ) -> Dict[str, float]:
        """
        Get total costs with optional filtering and grouping.
        
        Args:
            start_date: Start date for filtering
            end_date: End date for filtering
            group_by_provider: Group costs by SMS provider
            
        Returns:
            Dictionary of costs
        """
        try:
            with self._get_connection() as conn:
                if group_by_provider:
                    query = '''
                        SELECT sms_provider, SUM(sms_cost) as total_cost
                        FROM audit_events
                        WHERE sms_cost IS NOT NULL
                    '''
                    params = []
                    
                    if start_date:
                        query += ' AND timestamp >= ?'
                        params.append(start_date)
                    if end_date:
                        query += ' AND timestamp <= ?'
                        params.append(end_date)
                    
                    query += ' GROUP BY sms_provider'
                    
                    cursor = conn.execute(query, params)
                    return {row[0] or 'unknown': row[1] for row in cursor}
                else:
                    query = 'SELECT SUM(sms_cost) FROM audit_events WHERE sms_cost IS NOT NULL'
                    params = []
                    
                    if start_date:
                        query += ' AND timestamp >= ?'
                        params.append(start_date)
                    if end_date:
                        query += ' AND timestamp <= ?'
                        params.append(end_date)
                    
                    cursor = conn.execute(query, params)
                    total = cursor.fetchone()[0] or 0.0
                    return {'total': total}
                    
        except Exception as e:
            logger.error(f"Failed to get total costs: {e}")
            return {}
    
    def get_proxy_usage_stats(self, proxy_key: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for proxies."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                
                if proxy_key:
                    # Stats for specific proxy
                    cursor = conn.execute('''
                        SELECT 
                            COUNT(*) as total_uses,
                            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
                            MIN(timestamp) as first_used,
                            MAX(timestamp) as last_used
                        FROM audit_events
                        WHERE proxy_used = ?
                    ''', (proxy_key,))
                    
                    row = cursor.fetchone()
                    return dict(row) if row else {}
                else:
                    # Top proxies by usage
                    cursor = conn.execute('''
                        SELECT 
                            proxy_used,
                            COUNT(*) as total_uses,
                            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes
                        FROM audit_events
                        WHERE proxy_used IS NOT NULL
                        GROUP BY proxy_used
                        ORDER BY total_uses DESC
                        LIMIT 20
                    ''')
                    
                    return [dict(row) for row in cursor]
                    
        except Exception as e:
            logger.error(f"Failed to get proxy usage stats: {e}")
            return {}


# Singleton instance
_audit_log: Optional[AccountAuditLog] = None


def get_audit_log() -> AccountAuditLog:
    """Get singleton audit log instance."""
    global _audit_log
    if _audit_log is None:
        _audit_log = AccountAuditLog()
    return _audit_log








