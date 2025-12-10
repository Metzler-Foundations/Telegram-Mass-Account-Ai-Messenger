#!/usr/bin/env python3
"""
Scraping Database Layer - Database operations for member scraping.

Contains MemberDatabase and EliteDataAccessLayer classes.
"""

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MemberDatabase:
    """Database manager for scraped member data."""

    def __init__(self, db_path: str = "members.db"):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._lock = threading.RLock()

        # Initialize database
        self._create_tables()
        self._create_indexes()

    @contextmanager
    def get_connection(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, "connection"):
            self._local.connection = sqlite3.connect(
                str(self.db_path), check_same_thread=False, timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrency
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            self._local.connection.execute("PRAGMA synchronous=NORMAL")
            self._local.connection.execute("PRAGMA foreign_keys=ON")
            self._local.connection.execute("PRAGMA busy_timeout=30000")

        try:
            yield self._local.connection
        except Exception:
            # Rollback on error
            if hasattr(self._local, "connection"):
                try:
                    self._local.connection.rollback()
                except Exception:
                    pass
            raise

    def _create_tables(self):
        """Create database tables."""
        with self.get_connection() as conn:
            # Members table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    group_id INTEGER NOT NULL,
                    joined_date TIMESTAMP,
                    last_seen TIMESTAMP,
                    status TEXT DEFAULT 'member',
                    is_bot BOOLEAN DEFAULT FALSE,
                    is_verified BOOLEAN DEFAULT FALSE,
                    is_scam BOOLEAN DEFAULT FALSE,
                    language_code TEXT,
                    country TEXT,
                    city TEXT,
                    timezone TEXT,
                    profile_data TEXT,  -- JSON field for additional data
                    threat_score REAL DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Groups table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    username TEXT,
                    member_count INTEGER,
                    description TEXT,
                    type TEXT,  -- 'group', 'supergroup', 'channel'
                    is_public BOOLEAN DEFAULT FALSE,
                    is_verified BOOLEAN DEFAULT FALSE,
                    is_scam BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_scraped TIMESTAMP
                )
            """
            )

            # Scraping sessions table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scraping_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    account_id TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    groups_processed INTEGER DEFAULT 0,
                    members_found INTEGER DEFAULT 0,
                    errors INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                )
            """
            )

            # Error log table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS error_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    group_id INTEGER,
                    error_type TEXT NOT NULL,
                    error_message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()

    def _create_indexes(self):
        """Create database indexes for better performance."""
        with self.get_connection() as conn:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_members_user_id ON members(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_members_group_id ON members(group_id)",
                "CREATE INDEX IF NOT EXISTS idx_members_username ON members(username)",
                "CREATE INDEX IF NOT EXISTS idx_members_country ON members(country)",
                "CREATE INDEX IF NOT EXISTS idx_members_created_at ON members(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_groups_group_id ON groups(group_id)",
                "CREATE INDEX IF NOT EXISTS idx_groups_type ON groups(type)",
                "CREATE INDEX IF NOT EXISTS idx_error_log_session_id ON error_log(session_id)",
                "CREATE INDEX IF NOT EXISTS idx_scraping_sessions_account_id "
                "ON scraping_sessions(account_id)",
            ]

            for index_sql in indexes:
                try:
                    conn.execute(index_sql)
                except Exception as e:
                    logger.warning(f"Failed to create index: {e}")

            conn.commit()

    def add_member(self, member_data: Dict[str, Any]) -> bool:
        """
        Add or update a member in the database.

        Args:
            member_data: Member information dictionary

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                # Prepare data
                user_id = member_data["user_id"]
                profile_data = json.dumps(member_data.get("profile_data", {}))

                # Insert or replace member
                conn.execute(
                    """
                    INSERT OR REPLACE INTO members (
                        user_id, username, first_name, last_name, phone,
                        group_id, joined_date, last_seen, status, is_bot,
                        is_verified, is_scam, language_code, country, city,
                        timezone, profile_data, threat_score, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        user_id,
                        member_data.get("username"),
                        member_data.get("first_name"),
                        member_data.get("last_name"),
                        member_data.get("phone"),
                        member_data["group_id"],
                        member_data.get("joined_date"),
                        member_data.get("last_seen"),
                        member_data.get("status", "member"),
                        member_data.get("is_bot", False),
                        member_data.get("is_verified", False),
                        member_data.get("is_scam", False),
                        member_data.get("language_code"),
                        member_data.get("country"),
                        member_data.get("city"),
                        member_data.get("timezone"),
                        profile_data,
                        member_data.get("threat_score", 0.0),
                        datetime.now(),
                    ),
                )

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to add member {member_data.get('user_id')}: {e}")
            return False

    def get_member(self, user_id: int, group_id: int) -> Optional[Dict[str, Any]]:
        """
        Get member information.

        Args:
            user_id: Telegram user ID
            group_id: Group ID

        Returns:
            Member data dictionary or None
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM members
                    WHERE user_id = ? AND group_id = ?
                """,
                    (user_id, group_id),
                )

                row = cursor.fetchone()
                if row:
                    data = dict(row)
                    # Parse JSON profile data
                    if data.get("profile_data"):
                        data["profile_data"] = json.loads(data["profile_data"])
                    return data

        except Exception as e:
            logger.error(f"Failed to get member {user_id}: {e}")

        return None

    def get_group_members(self, group_id: int, limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Get members of a group.

        Args:
            group_id: Group ID
            limit: Maximum number of members to return

        Returns:
            List of member dictionaries
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM members
                    WHERE group_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (group_id, limit),
                )

                members = []
                for row in cursor.fetchall():
                    data = dict(row)
                    # Parse JSON profile data
                    if data.get("profile_data"):
                        data["profile_data"] = json.loads(data["profile_data"])
                    members.append(data)

                return members

        except Exception as e:
            logger.error(f"Failed to get group members for {group_id}: {e}")

        return []

    def update_member_threat_score(self, user_id: int, threat_score: float) -> bool:
        """
        Update threat score for a member.

        Args:
            user_id: User ID
            threat_score: New threat score

        Returns:
            True if successful
        """
        try:
            with self.get_connection() as conn:
                conn.execute(
                    """
                    UPDATE members
                    SET threat_score = ?, updated_at = ?
                    WHERE user_id = ?
                """,
                    (threat_score, datetime.now(), user_id),
                )

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to update threat score for {user_id}: {e}")

        return False

    def get_member_stats(self) -> Dict[str, Any]:
        """
        Get overall member statistics.

        Returns:
            Statistics dictionary
        """
        try:
            with self.get_connection() as conn:
                # Total members
                cursor = conn.execute("SELECT COUNT(*) as total FROM members")
                total_members = cursor.fetchone()[0]

                # Total groups
                cursor = conn.execute("SELECT COUNT(DISTINCT group_id) as total FROM members")
                total_groups = cursor.fetchone()[0]

                # Members by country
                cursor = conn.execute(
                    """
                    SELECT country, COUNT(*) as count
                    FROM members
                    WHERE country IS NOT NULL
                    GROUP BY country
                    ORDER BY count DESC
                    LIMIT 10
                """
                )
                top_countries = {row[0]: row[1] for row in cursor.fetchall()}

                # Recent additions (last 24 hours)
                yesterday = datetime.now() - timedelta(days=1)
                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as recent
                    FROM members
                    WHERE created_at > ?
                """,
                    (yesterday,),
                )
                recent_members = cursor.fetchone()[0]

                return {
                    "total_members": total_members,
                    "total_groups": total_groups,
                    "top_countries": top_countries,
                    "recent_members_24h": recent_members,
                    "avg_members_per_group": total_members / max(total_groups, 1),
                }

        except Exception as e:
            logger.error(f"Failed to get member stats: {e}")

        return {}

    def cleanup_old_data(self, days_to_keep: int = 90) -> int:
        """
        Clean up old member data.

        Args:
            days_to_keep: Number of days of data to keep

        Returns:
            Number of records deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            with self.get_connection() as conn:
                # Delete old members (but keep at least basic info for active users)
                cursor = conn.execute(
                    """
                    DELETE FROM members
                    WHERE updated_at < ? AND threat_score < 0.5
                """,
                    (cutoff_date,),
                )

                deleted_count = cursor.rowcount
                conn.commit()

                logger.info(f"Cleaned up {deleted_count} old member records")
                return deleted_count

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")

        return 0

    def optimize_database(self):
        """Optimize database performance."""
        try:
            with self.get_connection() as conn:
                # Run optimization pragmas
                conn.execute("VACUUM")
                conn.execute("ANALYZE")
                logger.info("Database optimized")

        except Exception as e:
            logger.error(f"Failed to optimize database: {e}")
