"""
Data Access Layer - Repository pattern for clean data access.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base repository with common database operations."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_connection(self):
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute query and return results as dict list."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute update and return affected rows."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount


class MemberRepository(BaseRepository):
    """Repository for member data operations."""

    def get_member_by_id(self, user_id: int) -> Optional[Dict]:
        """Get member by user ID."""
        results = self.execute_query(
            """
            SELECT m.*, mp.profile_quality_score, bi.messaging_potential_score
            FROM members m
            LEFT JOIN member_profiles mp ON m.user_id = mp.user_id
            LEFT JOIN member_behavioral_insights bi ON m.user_id = bi.user_id
            WHERE m.user_id = ?
            """,
            (user_id,),
        )
        return results[0] if results else None

    def get_members_for_campaign(self, channel_id: str, criteria: Dict) -> List[Dict]:
        """Get members suitable for campaigning with filtering."""
        query = """
            SELECT m.user_id, m.username, m.first_name, m.last_name,
                   mp.profile_quality_score, bi.messaging_potential_score
            FROM members m
            LEFT JOIN member_profiles mp ON m.user_id = mp.user_id
            LEFT JOIN member_behavioral_insights bi ON m.user_id = bi.user_id
            WHERE m.channel_id = ? AND m.is_safe_target = 1
        """
        params = [channel_id]

        # Add criteria filters
        if criteria.get("min_quality"):
            query += " AND (mp.profile_quality_score >= ? OR mp.profile_quality_score IS NULL)"
            params.append(criteria["min_quality"])

        if criteria.get("max_risk"):
            query += " AND m.threat_score < ?"
            params.append(criteria["max_risk"])

        query += " ORDER BY bi.messaging_potential_score DESC"

        return self.execute_query(query, tuple(params))

    def save_member(self, member_data: Dict) -> bool:
        """Save member data."""
        try:
            self.execute_update(
                """
                INSERT OR REPLACE INTO members
                (user_id, username, first_name, last_name, channel_id, status, activity_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    member_data["user_id"],
                    member_data.get("username"),
                    member_data.get("first_name"),
                    member_data.get("last_name"),
                    member_data.get("channel_id"),
                    member_data.get("status", "active"),
                    member_data.get("activity_score", 0),
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Error saving member: {e}")
            return False


class CampaignRepository(BaseRepository):
    """Repository for campaign data operations."""

    def get_all_campaigns(self) -> List[Dict]:
        """Get all campaigns."""
        return self.execute_query("SELECT * FROM campaigns ORDER BY created_at DESC")

    def get_campaign_by_id(self, campaign_id: int) -> Optional[Dict]:
        """Get campaign by ID."""
        results = self.execute_query("SELECT * FROM campaigns WHERE id = ?", (campaign_id,))
        return results[0] if results else None

    def create_campaign(self, campaign_data: Dict) -> Optional[int]:
        """Create new campaign and return ID."""
        try:
            cursor = self._get_connection().cursor()
            cursor.execute(
                """
                INSERT INTO campaigns
                (name, template, target_member_ids, account_ids, status, config, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign_data["name"],
                    campaign_data["template"],
                    ",".join(map(str, campaign_data["target_member_ids"])),
                    ",".join(campaign_data["account_ids"]),
                    campaign_data.get("status", "created"),
                    str(campaign_data.get("config", {})),
                    datetime.now().isoformat(),
                ),
            )
            campaign_id = cursor.lastrowid
            self._get_connection().commit()
            return campaign_id
        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            return None

    def update_campaign_stats(self, campaign_id: int, stats: Dict) -> bool:
        """Update campaign statistics."""
        try:
            self.execute_update(
                """
                UPDATE campaigns
                SET sent_count = ?, failed_count = ?, blocked_count = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    stats.get("sent_count", 0),
                    stats.get("failed_count", 0),
                    stats.get("blocked_count", 0),
                    datetime.now().isoformat(),
                    campaign_id,
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Error updating campaign stats: {e}")
            return False


class AccountRepository(BaseRepository):
    """Repository for account data operations."""

    def get_all_accounts(self) -> List[Dict]:
        """Get all accounts."""
        return self.execute_query("SELECT * FROM accounts ORDER BY created_at DESC")

    def get_account_by_phone(self, phone_number: str) -> Optional[Dict]:
        """Get account by phone number."""
        results = self.execute_query(
            "SELECT * FROM accounts WHERE phone_number = ?", (phone_number,)
        )
        return results[0] if results else None

    def save_account(self, account_data: Dict) -> bool:
        """Save account data."""
        try:
            self.execute_update(
                """
                INSERT OR REPLACE INTO accounts
                (phone_number, username, first_name, last_name, status, config, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_data["phone_number"],
                    account_data.get("username"),
                    account_data.get("first_name"),
                    account_data.get("last_name"),
                    account_data.get("status", "created"),
                    str(account_data.get("config", {})),
                    account_data.get("created_at", datetime.now().isoformat()),
                    datetime.now().isoformat(),
                ),
            )
            return True
        except Exception as e:
            logger.error(f"Error saving account: {e}")
            return False

    def update_account_status(self, phone_number: str, status: str, metadata: Dict = None) -> bool:
        """Update account status."""
        try:
            metadata_str = str(metadata) if metadata else None
            self.execute_update(
                """
                UPDATE accounts
                SET status = ?, metadata = ?, updated_at = ?
                WHERE phone_number = ?
                """,
                (status, metadata_str, datetime.now().isoformat(), phone_number),
            )
            return True
        except Exception as e:
            logger.error(f"Error updating account status: {e}")
            return False
