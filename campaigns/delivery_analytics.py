"""
Delivery Analytics - Track message delivery, read receipts, and response times.

Features:
- Delivery confirmation tracking
- Read receipt detection
- Response time calculation
- Per-campaign delivery metrics
- Per-account delivery performance
- Real-time analytics dashboard data
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DeliveryStatus(Enum):
    """Message delivery status."""

    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    REPLIED = "replied"
    FAILED = "failed"


@dataclass
class DeliveryEvent:
    """Delivery event tracking."""

    message_id: int
    campaign_id: int
    user_id: int
    account_phone: str

    sent_at: datetime
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None

    delivery_time_seconds: Optional[float] = None
    read_time_seconds: Optional[float] = None
    response_time_seconds: Optional[float] = None

    status: DeliveryStatus = DeliveryStatus.SENT

    def calculate_times(self):
        """Calculate delivery, read, and response times."""
        if self.delivered_at and self.sent_at:
            self.delivery_time_seconds = (self.delivered_at - self.sent_at).total_seconds()

        if self.read_at and self.sent_at:
            self.read_time_seconds = (self.read_at - self.sent_at).total_seconds()

        if self.replied_at and self.sent_at:
            self.response_time_seconds = (self.replied_at - self.sent_at).total_seconds()


class DeliveryAnalytics:
    """
    Track and analyze message delivery, read receipts, and response times.
    """

    def __init__(self, db_path: str = "campaigns.db"):
        """Initialize delivery analytics."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except Exception:
            pass
        self._init_database()

    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return sqlite3.connect(self.db_path)

    def _init_database(self):
        """Initialize delivery analytics tables."""
        with self._get_connection() as conn:
            # Delivery events table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS delivery_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL,
                    campaign_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    account_phone TEXT NOT NULL,

                    sent_at TIMESTAMP NOT NULL,
                    delivered_at TIMESTAMP,
                    read_at TIMESTAMP,
                    replied_at TIMESTAMP,

                    delivery_time_seconds REAL,
                    read_time_seconds REAL,
                    response_time_seconds REAL,

                    status TEXT NOT NULL,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(campaign_id, user_id)
                )
            """
            )

            # Indexes for performance
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_campaign
                ON delivery_events(campaign_id, status)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_account
                ON delivery_events(account_phone, sent_at DESC)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_status
                ON delivery_events(status, sent_at DESC)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_delivery_user
                ON delivery_events(user_id, campaign_id)
            """
            )

            # Response time statistics per campaign
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS campaign_response_stats (
                    campaign_id INTEGER PRIMARY KEY,
                    total_sent INTEGER DEFAULT 0,
                    total_delivered INTEGER DEFAULT 0,
                    total_read INTEGER DEFAULT 0,
                    total_replied INTEGER DEFAULT 0,

                    avg_delivery_time_seconds REAL,
                    avg_read_time_seconds REAL,
                    avg_response_time_seconds REAL,

                    median_response_time_seconds REAL,

                    delivery_rate REAL,
                    read_rate REAL,
                    response_rate REAL,

                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY(campaign_id) REFERENCES campaigns(id)
                )
            """
            )

            conn.commit()

    def record_message_sent(
        self,
        message_id: int,
        campaign_id: int,
        user_id: int,
        account_phone: str,
        sent_at: Optional[datetime] = None,
    ) -> bool:
        """Record a message being sent."""
        if sent_at is None:
            sent_at = datetime.now()

        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO delivery_events
                    (message_id, campaign_id, user_id, account_phone, sent_at, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id, user_id) DO UPDATE SET
                        message_id = excluded.message_id,
                        sent_at = excluded.sent_at,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        message_id,
                        campaign_id,
                        user_id,
                        account_phone,
                        sent_at,
                        DeliveryStatus.SENT.value,
                    ),
                )
                conn.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to record message sent: {e}")
            return False

    def record_delivery(
        self, campaign_id: int, user_id: int, delivered_at: Optional[datetime] = None
    ) -> bool:
        """Record message delivery confirmation."""
        if delivered_at is None:
            delivered_at = datetime.now()

        try:
            with self._get_connection() as conn:
                # Calculate delivery time
                cursor = conn.execute(
                    """
                    SELECT sent_at FROM delivery_events
                    WHERE campaign_id = ? AND user_id = ?
                """,
                    (campaign_id, user_id),
                )

                row = cursor.fetchone()
                if not row:
                    logger.warning(
                        f"No sent record found for campaign {campaign_id}, user {user_id}"
                    )
                    return False

                sent_at = datetime.fromisoformat(row[0])
                delivery_time = (delivered_at - sent_at).total_seconds()

                conn.execute(
                    """
                    UPDATE delivery_events
                    SET delivered_at = ?,
                        delivery_time_seconds = ?,
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_id = ? AND user_id = ?
                """,
                    (
                        delivered_at,
                        delivery_time,
                        DeliveryStatus.DELIVERED.value,
                        campaign_id,
                        user_id,
                    ),
                )

                conn.commit()

            self._update_campaign_stats(campaign_id)
            return True

        except Exception as e:
            logger.error(f"Failed to record delivery: {e}")
            return False

    def record_read_receipt(
        self, campaign_id: int, user_id: int, read_at: Optional[datetime] = None
    ) -> bool:
        """Record message read receipt."""
        if read_at is None:
            read_at = datetime.now()

        try:
            with self._get_connection() as conn:
                # Calculate read time
                cursor = conn.execute(
                    """
                    SELECT sent_at FROM delivery_events
                    WHERE campaign_id = ? AND user_id = ?
                """,
                    (campaign_id, user_id),
                )

                row = cursor.fetchone()
                if not row:
                    return False

                sent_at = datetime.fromisoformat(row[0])
                read_time = (read_at - sent_at).total_seconds()

                conn.execute(
                    """
                    UPDATE delivery_events
                    SET read_at = ?,
                        read_time_seconds = ?,
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_id = ? AND user_id = ?
                """,
                    (read_at, read_time, DeliveryStatus.READ.value, campaign_id, user_id),
                )

                conn.commit()

            self._update_campaign_stats(campaign_id)
            return True

        except Exception as e:
            logger.error(f"Failed to record read receipt: {e}")
            return False

    def record_response(
        self, campaign_id: int, user_id: int, replied_at: Optional[datetime] = None
    ) -> bool:
        """Record user response to message."""
        if replied_at is None:
            replied_at = datetime.now()

        try:
            with self._get_connection() as conn:
                # Calculate response time
                cursor = conn.execute(
                    """
                    SELECT sent_at FROM delivery_events
                    WHERE campaign_id = ? AND user_id = ?
                """,
                    (campaign_id, user_id),
                )

                row = cursor.fetchone()
                if not row:
                    return False

                sent_at = datetime.fromisoformat(row[0])
                response_time = (replied_at - sent_at).total_seconds()

                conn.execute(
                    """
                    UPDATE delivery_events
                    SET replied_at = ?,
                        response_time_seconds = ?,
                        status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE campaign_id = ? AND user_id = ?
                """,
                    (replied_at, response_time, DeliveryStatus.REPLIED.value, campaign_id, user_id),
                )

                conn.commit()

            self._update_campaign_stats(campaign_id)
            return True

        except Exception as e:
            logger.error(f"Failed to record response: {e}")
            return False

    def _update_campaign_stats(self, campaign_id: int):
        """Update aggregated statistics for a campaign."""
        try:
            with self._get_connection() as conn:
                # Calculate statistics
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) as total_delivered,
                        SUM(CASE WHEN read_at IS NOT NULL THEN 1 ELSE 0 END) as total_read,
                        SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) as total_replied,
                        AVG(delivery_time_seconds) as avg_delivery,
                        AVG(read_time_seconds) as avg_read,
                        AVG(response_time_seconds) as avg_response
                    FROM delivery_events
                    WHERE campaign_id = ?
                """,
                    (campaign_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return

                total_sent = row[0] or 0
                total_delivered = row[1] or 0
                total_read = row[2] or 0
                total_replied = row[3] or 0

                delivery_rate = (total_delivered / total_sent * 100) if total_sent > 0 else 0
                read_rate = (total_read / total_sent * 100) if total_sent > 0 else 0
                response_rate = (total_replied / total_sent * 100) if total_sent > 0 else 0

                # Calculate median response time
                cursor = conn.execute(
                    """
                    SELECT response_time_seconds
                    FROM delivery_events
                    WHERE campaign_id = ? AND response_time_seconds IS NOT NULL
                    ORDER BY response_time_seconds
                """,
                    (campaign_id,),
                )

                response_times = [r[0] for r in cursor.fetchall()]
                median_response = None
                if response_times:
                    mid = len(response_times) // 2
                    median_response = response_times[mid]

                # Update stats
                conn.execute(
                    """
                    INSERT INTO campaign_response_stats
                    (campaign_id, total_sent, total_delivered, total_read, total_replied,
                     avg_delivery_time_seconds, avg_read_time_seconds, avg_response_time_seconds,
                     median_response_time_seconds, delivery_rate, read_rate, response_rate, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(campaign_id) DO UPDATE SET
                        total_sent = excluded.total_sent,
                        total_delivered = excluded.total_delivered,
                        total_read = excluded.total_read,
                        total_replied = excluded.total_replied,
                        avg_delivery_time_seconds = excluded.avg_delivery_time_seconds,
                        avg_read_time_seconds = excluded.avg_read_time_seconds,
                        avg_response_time_seconds = excluded.avg_response_time_seconds,
                        median_response_time_seconds = excluded.median_response_time_seconds,
                        delivery_rate = excluded.delivery_rate,
                        read_rate = excluded.read_rate,
                        response_rate = excluded.response_rate,
                        updated_at = excluded.updated_at
                """,
                    (
                        campaign_id,
                        total_sent,
                        total_delivered,
                        total_read,
                        total_replied,
                        row[4],
                        row[5],
                        row[6],
                        median_response,
                        delivery_rate,
                        read_rate,
                        response_rate,
                        datetime.now(),
                    ),
                )

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to update campaign stats: {e}")

    def get_campaign_delivery_stats(self, campaign_id: int) -> Dict[str, Any]:
        """Get delivery statistics for a campaign."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM campaign_response_stats
                    WHERE campaign_id = ?
                """,
                    (campaign_id,),
                )

                row = cursor.fetchone()
                if not row:
                    return self._empty_stats()

                return dict(row)

        except Exception as e:
            logger.error(f"Failed to get campaign delivery stats: {e}")
            return self._empty_stats()

    def get_account_delivery_performance(
        self, account_phone: str, days: int = 30
    ) -> Dict[str, Any]:
        """Get delivery performance for an account over specified period."""
        try:
            cutoff = datetime.now() - timedelta(days=days)

            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) as total_delivered,
                        SUM(CASE WHEN read_at IS NOT NULL THEN 1 ELSE 0 END) as total_read,
                        SUM(CASE WHEN replied_at IS NOT NULL THEN 1 ELSE 0 END) as total_replied,
                        AVG(delivery_time_seconds) as avg_delivery,
                        AVG(read_time_seconds) as avg_read,
                        AVG(response_time_seconds) as avg_response
                    FROM delivery_events
                    WHERE account_phone = ? AND sent_at >= ?
                """,
                    (account_phone, cutoff),
                )

                row = cursor.fetchone()
                if not row:
                    return self._empty_stats()

                total_sent = row["total_sent"] or 0
                total_delivered = row["total_delivered"] or 0
                total_read = row["total_read"] or 0
                total_replied = row["total_replied"] or 0

                return {
                    "account_phone": account_phone,
                    "period_days": days,
                    "total_sent": total_sent,
                    "total_delivered": total_delivered,
                    "total_read": total_read,
                    "total_replied": total_replied,
                    "delivery_rate": (total_delivered / total_sent * 100) if total_sent > 0 else 0,
                    "read_rate": (total_read / total_sent * 100) if total_sent > 0 else 0,
                    "response_rate": (total_replied / total_sent * 100) if total_sent > 0 else 0,
                    "avg_delivery_time_seconds": row["avg_delivery"],
                    "avg_read_time_seconds": row["avg_read"],
                    "avg_response_time_seconds": row["avg_response"],
                }

        except Exception as e:
            logger.error(f"Failed to get account delivery performance: {e}")
            return self._empty_stats()

    def get_overall_delivery_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get overall delivery statistics across all campaigns."""
        try:
            cutoff = datetime.now() - timedelta(days=days)

            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT
                        COUNT(*) as total_sent,
                        SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as total_delivered,
                        SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as total_read,
                        SUM(CASE WHEN status = ? THEN 1 ELSE 0 END) as total_replied,
                        AVG(delivery_time_seconds) as avg_delivery,
                        AVG(read_time_seconds) as avg_read,
                        AVG(response_time_seconds) as avg_response,
                        COUNT(DISTINCT campaign_id) as campaigns_tracked,
                        COUNT(DISTINCT account_phone) as accounts_used
                    FROM delivery_events
                    WHERE sent_at >= ?
                """,
                    (
                        DeliveryStatus.DELIVERED.value,
                        DeliveryStatus.READ.value,
                        DeliveryStatus.REPLIED.value,
                        cutoff,
                    ),
                )

                row = cursor.fetchone()
                return dict(row) if row else self._empty_stats()

        except Exception as e:
            logger.error(f"Failed to get overall delivery stats: {e}")
            return self._empty_stats()

    def get_response_time_distribution(
        self, campaign_id: Optional[int] = None, bins: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get response time distribution for visualization.

        Args:
            campaign_id: Optional campaign filter
            bins: Number of time bins

        Returns:
            List of bins with count and time range
        """
        try:
            with self._get_connection() as conn:
                if campaign_id:
                    cursor = conn.execute(
                        """
                        SELECT response_time_seconds
                        FROM delivery_events
                        WHERE campaign_id = ? AND response_time_seconds IS NOT NULL
                        ORDER BY response_time_seconds
                    """,
                        (campaign_id,),
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT response_time_seconds
                        FROM delivery_events
                        WHERE response_time_seconds IS NOT NULL
                        ORDER BY response_time_seconds
                    """
                    )

                response_times = [r[0] for r in cursor.fetchall()]

                if not response_times:
                    return []

                # Create bins
                min_time = min(response_times)
                max_time = max(response_times)
                bin_size = (max_time - min_time) / bins if bins > 0 else 1

                distribution = []
                for i in range(bins):
                    bin_start = min_time + (i * bin_size)
                    bin_end = bin_start + bin_size

                    count = sum(1 for t in response_times if bin_start <= t < bin_end)

                    distribution.append(
                        {
                            "bin": i + 1,
                            "start_seconds": bin_start,
                            "end_seconds": bin_end,
                            "count": count,
                            "percentage": (
                                (count / len(response_times) * 100) if response_times else 0
                            ),
                        }
                    )

                return distribution

        except Exception as e:
            logger.error(f"Failed to get response time distribution: {e}")
            return []

    @staticmethod
    def _empty_stats() -> Dict[str, Any]:
        """Return empty statistics."""
        return {
            "total_sent": 0,
            "total_delivered": 0,
            "total_read": 0,
            "total_replied": 0,
            "delivery_rate": 0.0,
            "read_rate": 0.0,
            "response_rate": 0.0,
            "avg_delivery_time_seconds": None,
            "avg_read_time_seconds": None,
            "avg_response_time_seconds": None,
        }


# Singleton instance
_delivery_analytics: Optional[DeliveryAnalytics] = None


def get_delivery_analytics() -> DeliveryAnalytics:
    """Get singleton delivery analytics instance."""
    global _delivery_analytics
    if _delivery_analytics is None:
        _delivery_analytics = DeliveryAnalytics()
    return _delivery_analytics
