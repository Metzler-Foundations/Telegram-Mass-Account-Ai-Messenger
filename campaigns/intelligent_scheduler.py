"""
Intelligent Scheduler - Smart scheduling with timezone intelligence.

Features:
- Timezone-aware message scheduling
- Peak time targeting based on user activity
- Automatic send time optimization
- Follow-up automation
"""

import logging
import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import random

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


class IntelligentScheduler:
    """Smart message scheduling system."""
    
    def __init__(self, db_path: str = "scheduler.db",
                 status_db: str = "status_intelligence.db"):
        """Initialize intelligent scheduler."""
        self.db_path = db_path
        self.status_db = status_db
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool
            self._connection_pool = get_pool(self.db_path)
        except Exception as exc:
            logger.debug(f"Connection pool unavailable for scheduler: {exc}")
        self._init_database()
        self.cleanup_stale_records()
        self.blackout_windows: List[Tuple[int, int]] = [(0, 6)]
    
    def _get_connection(self):
        """Return a DB connection from pool or direct sqlite."""
        if self._connection_pool:
            return self._connection_pool.get_connection()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_database(self):
        """Initialize scheduler database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                message_text TEXT,
                scheduled_time TIMESTAMP,
                optimal_time TIMESTAMP,
                timezone TEXT,
                status TEXT DEFAULT 'pending',
                sent_at TIMESTAMP,
                created_at TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def schedule_optimal(self, user_id: int, message: str,
                        timezone: str = "UTC") -> datetime:
        """Schedule message at optimal time for user.
        
        Args:
            user_id: User ID
            message: Message to send
            timezone: User's timezone
            
        Returns:
            Scheduled datetime
        """
        # Get user's typical online hours from status intelligence
        online_hours = self._get_user_online_hours(user_id)
        
        if not online_hours:
            # Default to afternoon if no data
            online_hours = [14, 15, 16, 17, 18]

        allowed_hours = [h for h in online_hours if not self._is_blackout_hour(h)]
        if not allowed_hours:
            allowed_hours = [h for h in range(0, 24) if not self._is_blackout_hour(h)] or online_hours

        # Pick best hour
        best_hour = random.choice(allowed_hours)
        
        # Calculate next occurrence
        now = datetime.now()
        scheduled = now.replace(hour=best_hour, minute=random.randint(0, 59), 
                               second=0, microsecond=0)
        
        if scheduled <= now:
            scheduled += timedelta(days=1)

        if self._is_blackout_hour(scheduled.hour):
            scheduled = self._next_available_time(scheduled)

        # Save to database
        self._save_scheduled_message(user_id, message, scheduled, timezone)
        
        logger.info(f"Scheduled message for user {user_id} at {scheduled}")
        return scheduled

    def _is_blackout_hour(self, hour: int) -> bool:
        return any(start <= hour < end for start, end in self.blackout_windows)

    def _next_available_time(self, start_time: datetime) -> datetime:
        """Find the next time slot outside blackout windows."""
        current = start_time
        for _ in range(48):  # scan up to two days
            current += timedelta(hours=1)
            if not self._is_blackout_hour(current.hour):
                return current.replace(minute=random.randint(0, 59), second=0, microsecond=0)
        return start_time
    
    def _get_user_online_hours(self, user_id: int) -> List[int]:
        """Get user's typical online hours from status intelligence."""
        try:
            conn = sqlite3.connect(self.status_db)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT typical_online_hours FROM status_profiles WHERE user_id = ?
            """, (user_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0]:
                return json.loads(row[0])
        except Exception as e:
            logger.debug(f"Error getting online hours: {e}")
        
        return []
    
    def _save_scheduled_message(self, user_id: int, message: str, 
                                scheduled_time: datetime, timezone: str):
        """Save scheduled message to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scheduled_messages 
            (user_id, message_text, scheduled_time, timezone, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, message, scheduled_time, timezone, datetime.now()))
        conn.commit()
        conn.close()
    
    def get_due_messages(self) -> List[Dict]:
        """Get messages that are due to be sent."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, message_text FROM scheduled_messages
            WHERE status = 'pending' AND scheduled_time <= ?
        """, (datetime.now(),))
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'id': row[0],
                'user_id': row[1],
                'message': row[2]
            })
        
        conn.close()
        return messages
    
    def mark_as_sent(self, message_id: int):
        """Mark scheduled message as sent."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE scheduled_messages
            SET status = 'sent', sent_at = ?
            WHERE id = ?
        """, (datetime.now(), message_id))
        conn.commit()
        conn.close()

    def cleanup_stale_records(self, sent_retention_days: int = 30, pending_retention_days: int = 14):
        """Remove stale scheduled message records to prevent unbounded growth."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cutoff_sent = datetime.now() - timedelta(days=sent_retention_days)
            cutoff_pending = datetime.now() - timedelta(days=pending_retention_days)
            cursor.execute(
                "DELETE FROM scheduled_messages WHERE status = 'sent' AND sent_at < ?",
                (cutoff_sent,)
            )
            cursor.execute(
                "DELETE FROM scheduled_messages WHERE status IN ('pending','failed') AND scheduled_time < ?",
                (cutoff_pending,)
            )
            conn.commit()
            conn.close()
        except Exception as exc:
            logger.debug(f"Failed to cleanup stale scheduled messages: {exc}")

