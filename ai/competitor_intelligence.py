"""
Competitor Intelligence - Monitor and analyze competitor strategies.

Features:
- Track competitor account activities
- Collect competitor message templates
- Analyze what works for competitors
- Identify overlapping target audiences
"""

import asyncio
import logging
import sqlite3
import json
from typing import List, Dict, Optional, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from pyrogram import Client
from pyrogram.types import Message, User
from pyrogram.errors import FloodWait

logger = logging.getLogger(__name__)


@dataclass
class CompetitorProfile:
    """Competitor account profile."""

    competitor_id: str
    user_id: int
    username: Optional[str] = None
    display_name: Optional[str] = None

    # Activity metrics
    messages_tracked: int = 0
    groups_active_in: Set[int] = field(default_factory=set)
    avg_messages_per_day: float = 0.0

    # Strategy analysis
    common_keywords: List[str] = field(default_factory=list)
    message_templates: List[str] = field(default_factory=list)
    response_rate: float = 0.0

    # Tracking
    first_tracked: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class CompetitorMessage:
    """Competitor message record."""

    message_id: int
    competitor_id: str
    group_id: int
    text: str
    timestamp: datetime
    got_response: bool = False
    reactions_count: int = 0


class CompetitorIntelligence:
    """Monitor and analyze competitor activities."""

    def __init__(self, db_path: str = "competitor_intel.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except Exception as e:
            logger.debug(f"Error initializing competitor intelligence database (non-critical): {e}")
            pass
        self._init_database()

    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return self._get_connection()

    def _init_database(self):
        """Initialize intelligence database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Competitor profiles
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS competitors (
                competitor_id TEXT PRIMARY KEY,
                user_id INTEGER UNIQUE,
                username TEXT,
                display_name TEXT,
                messages_tracked INTEGER DEFAULT 0,
                groups_active_in TEXT,
                avg_messages_per_day REAL,
                common_keywords TEXT,
                message_templates TEXT,
                response_rate REAL,
                first_tracked TIMESTAMP,
                last_updated TIMESTAMP
            )
        """
        )

        # Competitor messages
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS competitor_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_id TEXT,
                group_id INTEGER,
                message_text TEXT,
                timestamp TIMESTAMP,
                got_response INTEGER,
                reactions_count INTEGER
            )
        """
        )

        # Target overlap (users in both our and competitor targets)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS target_overlap (
                user_id INTEGER,
                competitor_id TEXT,
                discovered_in_group INTEGER,
                discovered_at TIMESTAMP,
                PRIMARY KEY (user_id, competitor_id)
            )
        """
        )

        # Strategy patterns
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS strategy_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                competitor_id TEXT,
                pattern_type TEXT,
                pattern_data TEXT,
                effectiveness_score REAL,
                times_observed INTEGER,
                last_observed TIMESTAMP
            )
        """
        )

        conn.commit()
        conn.close()
        logger.info("Competitor intelligence database initialized")

    def add_competitor(self, user_id: int, username: str = None, display_name: str = None) -> str:
        """Add a competitor to track.

        Args:
            user_id: Telegram user ID
            username: Username
            display_name: Display name

        Returns:
            Competitor ID
        """
        competitor_id = f"comp_{user_id}"

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO competitors
            (competitor_id, user_id, username, display_name, first_tracked, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (competitor_id, user_id, username, display_name, datetime.now(), datetime.now()),
        )
        conn.commit()
        conn.close()

        logger.info(f"Added competitor: {competitor_id} ({username})")
        return competitor_id

    async def track_competitor_message(self, message: Message) -> bool:
        """Track a competitor's message.

        Args:
            message: Pyrogram Message object

        Returns:
            True if tracked
        """
        if not message.from_user:
            return False

        # Check if this is a tracked competitor
        competitor_id = f"comp_{message.from_user.id}"
        if not self._is_competitor(competitor_id):
            return False

        # Save message
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO competitor_messages
            (competitor_id, group_id, message_text, timestamp, got_response, reactions_count)
            VALUES (?, ?, ?, ?, 0, 0)
        """,
            (competitor_id, message.chat.id, message.text or "", datetime.now()),
        )
        conn.commit()
        conn.close()

        # Update competitor stats
        self._update_competitor_stats(competitor_id)

        return True

    def _is_competitor(self, competitor_id: str) -> bool:
        """Check if ID is a tracked competitor."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM competitors WHERE competitor_id = ?", (competitor_id,))
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def _update_competitor_stats(self, competitor_id: str):
        """Update competitor statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Count messages
        cursor.execute(
            """
            SELECT COUNT(*), COUNT(DISTINCT group_id) 
            FROM competitor_messages 
            WHERE competitor_id = ?
        """,
            (competitor_id,),
        )
        msg_count, group_count = cursor.fetchone()

        # Calculate messages per day
        cursor.execute(
            """
            SELECT MIN(timestamp), MAX(timestamp) 
            FROM competitor_messages 
            WHERE competitor_id = ?
        """,
            (competitor_id,),
        )
        first, last = cursor.fetchone()

        if first and last:
            days = max(1, (datetime.fromisoformat(last) - datetime.fromisoformat(first)).days)
            msg_per_day = msg_count / days
        else:
            msg_per_day = 0

        # Get active groups
        cursor.execute(
            """
            SELECT DISTINCT group_id FROM competitor_messages 
            WHERE competitor_id = ?
        """,
            (competitor_id,),
        )
        groups = [row[0] for row in cursor.fetchall()]

        # Update profile
        cursor.execute(
            """
            UPDATE competitors SET
                messages_tracked = ?,
                groups_active_in = ?,
                avg_messages_per_day = ?,
                last_updated = ?
            WHERE competitor_id = ?
        """,
            (msg_count, json.dumps(groups), msg_per_day, datetime.now(), competitor_id),
        )

        conn.commit()
        conn.close()

    def analyze_competitor_templates(self, competitor_id: str, limit: int = 50) -> List[str]:
        """Analyze and extract competitor message templates.

        Args:
            competitor_id: Competitor ID
            limit: Number of recent messages to analyze

        Returns:
            List of templates
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT message_text FROM competitor_messages
            WHERE competitor_id = ? AND message_text != ''
            ORDER BY timestamp DESC
            LIMIT ?
        """,
            (competitor_id, limit),
        )

        messages = [row[0] for row in cursor.fetchall()]
        conn.close()

        # Extract common patterns (simplified)
        templates = []
        for msg in messages:
            if len(msg) > 20:  # Only meaningful messages
                templates.append(msg)

        return templates[:10]  # Top 10 most recent

    def find_target_overlap(self, our_targets: List[int], competitor_id: str) -> List[int]:
        """Find users targeted by both us and competitor.

        Args:
            our_targets: Our target user IDs
            competitor_id: Competitor ID

        Returns:
            List of overlapping user IDs
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        overlap = []
        for user_id in our_targets:
            cursor.execute(
                """
                SELECT 1 FROM target_overlap 
                WHERE user_id = ? AND competitor_id = ?
            """,
                (user_id, competitor_id),
            )
            if cursor.fetchone():
                overlap.append(user_id)

        conn.close()
        return overlap

    def get_competitor_summary(self, competitor_id: str) -> Dict:
        """Get summary of competitor activity.

        Args:
            competitor_id: Competitor ID

        Returns:
            Summary dictionary
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM competitors WHERE competitor_id = ?
        """,
            (competitor_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return {}

        return {
            "competitor_id": row[0],
            "user_id": row[1],
            "username": row[2],
            "display_name": row[3],
            "messages_tracked": row[4],
            "groups_active_in": json.loads(row[5]) if row[5] else [],
            "avg_messages_per_day": row[6],
            "response_rate": row[9],
            "first_tracked": row[10],
            "last_updated": row[11],
        }

    def get_all_competitors(self) -> List[Dict]:
        """Get all tracked competitors."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT competitor_id FROM competitors")
        competitor_ids = [row[0] for row in cursor.fetchall()]
        conn.close()

        return [self.get_competitor_summary(cid) for cid in competitor_ids]

    def get_top_performing_strategies(self, limit: int = 10) -> List[Dict]:
        """Get top performing competitor strategies.

        Returns:
            List of strategy patterns
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT competitor_id, pattern_type, pattern_data, effectiveness_score, times_observed
            FROM strategy_patterns
            ORDER BY effectiveness_score DESC
            LIMIT ?
        """,
            (limit,),
        )

        strategies = []
        for row in cursor.fetchall():
            strategies.append(
                {
                    "competitor_id": row[0],
                    "pattern_type": row[1],
                    "pattern_data": json.loads(row[2]) if row[2] else {},
                    "effectiveness_score": row[3],
                    "times_observed": row[4],
                }
            )

        conn.close()
        return strategies
