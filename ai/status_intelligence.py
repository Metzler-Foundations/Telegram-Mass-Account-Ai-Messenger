"""
Status Intelligence - Read receipt and online status tracking system.

Features:
- Read receipt tracking
- Online/offline pattern monitoring
- Response time analysis
- Best time prediction for messaging
- Bulk status checking
"""

import asyncio
import logging
import random
import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import statistics

from pyrogram import Client
from pyrogram.types import User, Message
from pyrogram.enums import UserStatus
from pyrogram.errors import FloodWait, PeerIdInvalid

logger = logging.getLogger(__name__)


class OnlineStatus(Enum):
    """User online status."""

    ONLINE = "online"
    OFFLINE = "offline"
    RECENTLY = "recently"  # Within 1 hour
    LAST_WEEK = "last_week"
    LAST_MONTH = "last_month"
    LONG_AGO = "long_ago"


@dataclass
class StatusSnapshot:
    """Snapshot of user status at a point in time."""

    user_id: int
    status: OnlineStatus
    timestamp: datetime
    was_online_at: Optional[datetime] = None


@dataclass
class ReadReceiptData:
    """Read receipt information for a message."""

    message_id: int
    chat_id: int
    sent_at: datetime
    read_at: Optional[datetime] = None
    time_to_read: Optional[float] = None  # Seconds


@dataclass
class UserStatusProfile:
    """Comprehensive status profile for a user."""

    user_id: int

    # Current status
    current_status: OnlineStatus = OnlineStatus.OFFLINE
    last_seen: Optional[datetime] = None
    last_online: Optional[datetime] = None

    # Patterns
    typical_online_hours: List[int] = field(default_factory=list)  # Hours 0-23
    typical_online_days: List[int] = field(default_factory=list)  # Days 0-6
    avg_session_duration: Optional[float] = None  # Minutes

    # Response behavior
    avg_response_time: Optional[float] = None  # Minutes
    median_response_time: Optional[float] = None
    fastest_response: Optional[float] = None
    response_rate: float = 0.0  # 0-1

    # Activity metrics
    messages_sent: int = 0
    messages_received: int = 0
    total_checks: int = 0
    online_checks: int = 0

    # Metadata
    first_tracked: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


class StatusIntelligence:
    """Status and read receipt intelligence system."""

    def __init__(self, db_path: str = "status_intelligence.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except Exception as e:
            logger.debug(f"Error initializing status intelligence database (non-critical): {e}")
            pass
        self._init_database()

    def _get_connection(self):
        """Get database connection."""
        if self._connection_pool:
            return self._connection_pool.get_connection()
        else:
            import sqlite3

            return sqlite3.connect(self.db_path)

    def _init_database(self):
        """Initialize status tracking database."""
        if self._connection_pool:
            with self._connection_pool.get_connection() as conn:
                cursor = conn.cursor()
                self._create_tables(cursor)
                conn.commit()
        else:
            import sqlite3

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            self._create_tables(cursor)
            conn.commit()
            conn.close()

    def _create_tables(self, cursor):
        """Create database tables."""

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS status_profiles (
                user_id INTEGER PRIMARY KEY,
                current_status TEXT,
                last_seen TIMESTAMP,
                last_online TIMESTAMP,
                typical_online_hours TEXT,
                typical_online_days TEXT,
                avg_session_duration REAL,
                avg_response_time REAL,
                median_response_time REAL,
                fastest_response REAL,
                response_rate REAL,
                messages_sent INTEGER DEFAULT 0,
                messages_received INTEGER DEFAULT 0,
                total_checks INTEGER DEFAULT 0,
                online_checks INTEGER DEFAULT 0,
                first_tracked TIMESTAMP,
                last_updated TIMESTAMP
            )
        """
        )

        # Status history
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS status_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                status TEXT,
                timestamp TIMESTAMP,
                was_online_at TIMESTAMP
            )
        """
        )

        # Read receipts
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS read_receipts (
                message_id INTEGER PRIMARY KEY,
                chat_id INTEGER,
                user_id INTEGER,
                sent_at TIMESTAMP,
                read_at TIMESTAMP,
                time_to_read REAL
            )
        """
        )

        # Response times
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS response_times (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                our_message_time TIMESTAMP,
                their_response_time TIMESTAMP,
                response_delay REAL,
                hour_of_day INTEGER,
                day_of_week INTEGER
            )
        """
        )

        # Best time predictions
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS best_times (
                user_id INTEGER,
                hour INTEGER,
                day_of_week INTEGER,
                score REAL,
                PRIMARY KEY (user_id, hour, day_of_week)
            )
        """
        )

        # Indexes
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_status_history_user ON status_history(user_id, timestamp)"
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_receipts_user ON read_receipts(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_response_user ON response_times(user_id)")

        logger.info("Status intelligence database tables created")

    def _load_seen_receipts(self):
        """Load previously stored read receipts to avoid reprocessing after restarts."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT message_id FROM read_receipts")
            self._seen_receipts = {row[0] for row in cursor.fetchall()}
            conn.close()
        except Exception as exc:
            logger.debug(f"Failed to hydrate read receipt cache: {exc}")

    async def track_user_status(self, client: Client, user_id: int) -> Optional[UserStatusProfile]:
        """Track and record user status.

        Args:
            client: Pyrogram client
            user_id: User ID to track

        Returns:
            UserStatusProfile or None
        """
        try:
            user = await client.get_users(user_id)

            # Parse status
            status = self._parse_status(user.status)
            was_online_at = self._parse_last_online(user.status)

            # Record snapshot
            snapshot = StatusSnapshot(
                user_id=user_id,
                status=status,
                timestamp=datetime.now(),
                was_online_at=was_online_at,
            )
            self._save_status_snapshot(snapshot)

            # Update or create profile
            profile = self._get_or_create_profile(user_id)
            profile.current_status = status
            profile.last_seen = datetime.now()
            profile.total_checks += 1

            if status == OnlineStatus.ONLINE:
                profile.last_online = datetime.now()
                profile.online_checks += 1
            elif was_online_at:
                profile.last_online = was_online_at

            profile.last_updated = datetime.now()

            # Update cache
            self._status_cache[user_id] = profile

            # Save to database periodically (every 10 checks)
            if profile.total_checks % 10 == 0:
                self._save_profile(profile)
                self._analyze_patterns(user_id)

            return profile

        except FloodWait as e:
            logger.warning(f"FloodWait tracking status for {user_id}: {e.value}s")
            await asyncio.sleep(e.value)
            return None
        except PeerIdInvalid:
            logger.debug(f"Invalid peer ID: {user_id}")
            return None
        except Exception as e:
            logger.error(f"Error tracking status for {user_id}: {e}")
            return None

    async def bulk_check_status(
        self, client: Client, user_ids: List[int], delay_range: Tuple[float, float] = (0.5, 2.0)
    ) -> Dict[int, OnlineStatus]:
        """Check online status for multiple users.

        Args:
            client: Pyrogram client
            user_ids: List of user IDs
            delay_range: Delay range between checks

        Returns:
            Dictionary mapping user_id to OnlineStatus
        """
        results = {}

        # Enforce per-client pacing to prevent FloodWait collisions when bulk refreshing
        client_key = (
            getattr(client, "phone_number", None)
            or getattr(client, "session_name", None)
            or "default"
        )
        min_gap = max(delay_range[0], 1.5)
        last_bulk = self._pending_receipts.get("_last_bulk_check", {})  # reuse dict store
        last_seen = last_bulk.get(client_key)
        if last_seen:
            elapsed = (datetime.now() - last_seen).total_seconds()
            if elapsed < min_gap:
                sleep_for = min_gap - elapsed
                logger.info(
                    f"Throttling bulk status checks for {client_key} by {sleep_for:.2f}s to avoid FloodWait"
                )
                await asyncio.sleep(sleep_for)
        last_bulk[client_key] = datetime.now()
        self._pending_receipts["_last_bulk_check"] = last_bulk

        for i, user_id in enumerate(user_ids):
            profile = await self.track_user_status(client, user_id)
            if profile:
                results[user_id] = profile.current_status

            # Rate limiting with jitter to avoid bursty patterns
            if i < len(user_ids) - 1:
                delay = random.uniform(*delay_range)
                jitter = random.uniform(0.05, 0.35)
                await asyncio.sleep(delay + jitter)

        logger.info(f"Bulk checked status for {len(results)}/{len(user_ids)} users")
        return results

    def track_message_sent(self, message_id: int, chat_id: int, user_id: int):
        """Track a message sent to a user for read receipt monitoring.

        Args:
            message_id: Message ID
            chat_id: Chat ID
            user_id: Recipient user ID
        """
        if message_id in self._seen_receipts:
            logger.debug(f"Skipping tracking for already persisted receipt {message_id}")
            return

        receipt = ReadReceiptData(message_id=message_id, chat_id=chat_id, sent_at=datetime.now())
        self._pending_receipts[message_id] = receipt

        # Update profile
        profile = self._get_or_create_profile(user_id)
        profile.messages_sent += 1
        self._status_cache[user_id] = profile

    async def check_read_receipt(self, client: Client, message_id: int, chat_id: int) -> bool:
        """Check if a message has been read.

        Args:
            client: Pyrogram client
            message_id: Message ID
            chat_id: Chat ID

        Returns:
            True if read, False otherwise
        """
        backoff = 1.0
        for attempt in range(3):
            try:
                message = await client.get_messages(chat_id, message_id)

                if not message:
                    return False

                # Pyrogram exposes read_date for private dialogs; fall back to explicit views for channels
                read_date = getattr(message, "read_date", None)
                if read_date:
                    self._mark_as_read(message_id)
                    return True

                if getattr(message, "views", None) is not None:
                    # Consider channel messages read only when views are present
                    if message.views > 0:
                        self._mark_as_read(message_id)
                        return True

                # Otherwise keep the receipt pending until we have explicit confirmation
                return False

            except Exception as e:
                logger.debug(f"Error checking read receipt (attempt {attempt + 1}): {e}")
                await asyncio.sleep(backoff)
                backoff *= 2

        return False

    def _mark_as_read(self, message_id: int):
        """Mark a message as read."""
        if message_id in self._pending_receipts:
            receipt = self._pending_receipts[message_id]
            receipt.read_at = datetime.now()
            receipt.time_to_read = (receipt.read_at - receipt.sent_at).total_seconds()

            # Save to database
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO read_receipts
                (message_id, chat_id, sent_at, read_at, time_to_read)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    receipt.message_id,
                    receipt.chat_id,
                    receipt.sent_at,
                    receipt.read_at,
                    receipt.time_to_read,
                ),
            )
            conn.commit()
            conn.close()

            self._seen_receipts.add(message_id)

            # Remove from pending
            del self._pending_receipts[message_id]

    def record_response(
        self, user_id: int, our_message_time: datetime, their_response_time: datetime
    ):
        """Record a user's response to our message.

        Args:
            user_id: User ID
            our_message_time: When we sent the message
            their_response_time: When they responded
        """
        delay = (their_response_time - our_message_time).total_seconds() / 60.0  # Minutes

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO response_times 
            (user_id, our_message_time, their_response_time, response_delay, hour_of_day, day_of_week)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (
                user_id,
                our_message_time,
                their_response_time,
                delay,
                their_response_time.hour,
                their_response_time.weekday(),
            ),
        )
        conn.commit()
        conn.close()

        # Update profile
        profile = self._get_or_create_profile(user_id)
        profile.messages_received += 1
        self._recalculate_response_metrics(user_id, profile)
        self._status_cache[user_id] = profile
        self._save_profile(profile)

    def _recalculate_response_metrics(self, user_id: int, profile: UserStatusProfile):
        """Recalculate response time metrics for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT response_delay FROM response_times 
            WHERE user_id = ? 
            ORDER BY their_response_time DESC 
            LIMIT 50
        """,
            (user_id,),
        )

        delays = [row[0] for row in cursor.fetchall()]
        conn.close()

        if delays:
            profile.avg_response_time = statistics.mean(delays)
            profile.median_response_time = statistics.median(delays)
            profile.fastest_response = min(delays)

        if profile.messages_sent > 0:
            profile.response_rate = profile.messages_received / profile.messages_sent

    def _analyze_patterns(self, user_id: int):
        """Analyze activity patterns for a user."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get online times from last 30 days
        since = datetime.now() - timedelta(days=30)
        cursor.execute(
            """
            SELECT timestamp FROM status_history
            WHERE user_id = ? AND status = 'online' AND timestamp > ?
        """,
            (user_id, since),
        )

        online_times = [datetime.fromisoformat(row[0]) for row in cursor.fetchall()]

        if online_times:
            # Calculate typical hours
            hours = [t.hour for t in online_times]
            hour_counts = defaultdict(int)
            for h in hours:
                hour_counts[h] += 1

            # Top 5 hours
            typical_hours = sorted(hour_counts.keys(), key=lambda h: hour_counts[h], reverse=True)[
                :5
            ]

            # Calculate typical days
            days = [t.weekday() for t in online_times]
            day_counts = defaultdict(int)
            for d in days:
                day_counts[d] += 1

            typical_days = sorted(day_counts.keys(), key=lambda d: day_counts[d], reverse=True)[:3]

            # Update profile
            if user_id in self._status_cache:
                profile = self._status_cache[user_id]
                profile.typical_online_hours = typical_hours
                profile.typical_online_days = typical_days

        conn.close()

    def predict_best_time(self, user_id: int) -> Optional[Tuple[int, int]]:
        """Predict best time to message a user.

        Args:
            user_id: User ID

        Returns:
            (hour, day_of_week) tuple or None
        """
        profile = self._get_profile(user_id)
        if not profile or not profile.typical_online_hours:
            return None

        # Calculate scores for each hour/day combination
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get response times by hour and day
        cursor.execute(
            """
            SELECT hour_of_day, day_of_week, AVG(response_delay) as avg_delay, COUNT(*) as count
            FROM response_times
            WHERE user_id = ?
            GROUP BY hour_of_day, day_of_week
            HAVING count >= 2
            ORDER BY avg_delay ASC, count DESC
            LIMIT 1
        """,
            (user_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return (row[0], row[1])

        # Fallback to most common online hour/day
        if profile.typical_online_hours and profile.typical_online_days:
            return (profile.typical_online_hours[0], profile.typical_online_days[0])

        return None

    def get_online_probability(self, user_id: int, hour: int, day_of_week: int) -> float:
        """Get probability that user is online at specific time.

        Args:
            user_id: User ID
            hour: Hour of day (0-23)
            day_of_week: Day of week (0-6, Monday=0)

        Returns:
            Probability (0-1)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        since = datetime.now() - timedelta(days=30)

        # Count online occurrences at this time
        cursor.execute(
            """
            SELECT COUNT(*) FROM status_history
            WHERE user_id = ? AND status = 'online' AND timestamp > ?
            AND CAST(strftime('%H', timestamp) AS INTEGER) = ?
            AND CAST(strftime('%w', timestamp) AS INTEGER) = ?
        """,
            (user_id, since, hour, (day_of_week + 1) % 7),
        )  # SQLite %w is 0=Sunday

        online_count = cursor.fetchone()[0]

        # Count total checks at this time
        cursor.execute(
            """
            SELECT COUNT(*) FROM status_history
            WHERE user_id = ? AND timestamp > ?
            AND CAST(strftime('%H', timestamp) AS INTEGER) = ?
            AND CAST(strftime('%w', timestamp) AS INTEGER) = ?
        """,
            (user_id, since, hour, (day_of_week + 1) % 7),
        )

        total_count = cursor.fetchone()[0]
        conn.close()

        if total_count == 0:
            return 0.0

        return online_count / total_count

    def _parse_status(self, status: UserStatus) -> OnlineStatus:
        """Parse Pyrogram UserStatus to OnlineStatus."""
        if status == UserStatus.ONLINE:
            return OnlineStatus.ONLINE
        elif status == UserStatus.RECENTLY:
            return OnlineStatus.RECENTLY
        elif status == UserStatus.LAST_WEEK:
            return OnlineStatus.LAST_WEEK
        elif status == UserStatus.LAST_MONTH:
            return OnlineStatus.LAST_MONTH
        else:
            return OnlineStatus.OFFLINE

    def _parse_last_online(self, status: UserStatus) -> Optional[datetime]:
        """Parse last online time from status."""
        now = datetime.now()
        if status == UserStatus.ONLINE:
            return now
        elif status == UserStatus.RECENTLY:
            return now - timedelta(minutes=30)
        elif status == UserStatus.LAST_WEEK:
            return now - timedelta(days=5)
        elif status == UserStatus.LAST_MONTH:
            return now - timedelta(days=20)
        return None

    def _get_or_create_profile(self, user_id: int) -> UserStatusProfile:
        """Get existing profile or create new one."""
        if user_id in self._status_cache:
            return self._status_cache[user_id]

        profile = self._get_profile(user_id)
        if profile:
            self._status_cache[user_id] = profile
            return profile

        # Create new
        profile = UserStatusProfile(user_id=user_id)
        self._status_cache[user_id] = profile
        return profile

    def _get_profile(self, user_id: int) -> Optional[UserStatusProfile]:
        """Get profile from database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM status_profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return UserStatusProfile(
            user_id=row[0],
            current_status=OnlineStatus(row[1]) if row[1] else OnlineStatus.OFFLINE,
            last_seen=datetime.fromisoformat(row[2]) if row[2] else None,
            last_online=datetime.fromisoformat(row[3]) if row[3] else None,
            typical_online_hours=json.loads(row[4]) if row[4] else [],
            typical_online_days=json.loads(row[5]) if row[5] else [],
            avg_session_duration=row[6],
            avg_response_time=row[7],
            median_response_time=row[8],
            fastest_response=row[9],
            response_rate=row[10] or 0.0,
            messages_sent=row[11] or 0,
            messages_received=row[12] or 0,
            total_checks=row[13] or 0,
            online_checks=row[14] or 0,
            first_tracked=datetime.fromisoformat(row[15]) if row[15] else datetime.now(),
            last_updated=datetime.fromisoformat(row[16]) if row[16] else datetime.now(),
        )

    def _save_profile(self, profile: UserStatusProfile):
        """Save profile to database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO status_profiles VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """,
            (
                profile.user_id,
                profile.current_status.value,
                profile.last_seen.isoformat() if profile.last_seen else None,
                profile.last_online.isoformat() if profile.last_online else None,
                json.dumps(profile.typical_online_hours),
                json.dumps(profile.typical_online_days),
                profile.avg_session_duration,
                profile.avg_response_time,
                profile.median_response_time,
                profile.fastest_response,
                profile.response_rate,
                profile.messages_sent,
                profile.messages_received,
                profile.total_checks,
                profile.online_checks,
                profile.first_tracked.isoformat(),
                profile.last_updated.isoformat(),
            ),
        )

        conn.commit()
        conn.close()

    def _save_status_snapshot(self, snapshot: StatusSnapshot):
        """Save status snapshot to history."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO status_history (user_id, status, timestamp, was_online_at)
            VALUES (?, ?, ?, ?)
        """,
            (
                snapshot.user_id,
                snapshot.status.value,
                snapshot.timestamp.isoformat(),
                snapshot.was_online_at.isoformat() if snapshot.was_online_at else None,
            ),
        )
        conn.commit()
        conn.close()

    def get_statistics(self) -> Dict:
        """Get status intelligence statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Total tracked users
        cursor.execute("SELECT COUNT(*) FROM status_profiles")
        total_users = cursor.fetchone()[0]

        # Average response rate
        cursor.execute("SELECT AVG(response_rate) FROM status_profiles WHERE response_rate > 0")
        avg_response_rate = cursor.fetchone()[0] or 0.0

        # Average response time
        cursor.execute(
            "SELECT AVG(avg_response_time) FROM status_profiles WHERE avg_response_time IS NOT NULL"
        )
        avg_response_time = cursor.fetchone()[0] or 0.0

        conn.close()

        return {
            "total_tracked_users": total_users,
            "average_response_rate": avg_response_rate,
            "average_response_time_minutes": avg_response_time,
        }
