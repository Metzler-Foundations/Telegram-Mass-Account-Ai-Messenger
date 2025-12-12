#!/usr/bin/env python3
"""
Database Queries - REAL database query functions for production use
All functions connect to actual database and return real data
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class DatabaseQueryHelper:
    """Helper for executing REAL database queries."""

    def __init__(self, db_path: str = "members.db"):
        self.db_path = db_path

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """Execute a query and return results as list of dicts."""
        conn = None
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(query, params)
            rows = cursor.fetchall()

            # Convert to list of dicts
            results = [dict(row) for row in rows]

            return results

        except sqlite3.Error as e:
            logger.error(f"Database query failed: {e}")
            logger.error(f"Query: {query}")
            logger.error(f"Params: {params}")
            return []
        finally:
            # Ensure connection is always closed
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing database connection: {e}")

    def execute_single(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """Execute query and return single result."""
        results = self.execute_query(query, params)
        return results[0] if results else None

    def execute_count(self, query: str, params: tuple = ()) -> int:
        """Execute count query."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, params)
            result = cursor.fetchone()
            count = result[0] if result else 0

            return count

        except sqlite3.Error as e:
            logger.error(f"Count query failed: {e}")
            return 0
        finally:
            # Ensure connection is always closed
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing database connection: {e}")

    def execute_update(self, query: str, params: tuple = ()) -> bool:
        """Execute update/insert/delete query."""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(query, params)
            conn.commit()

            affected = cursor.rowcount

            logger.debug(f"Update affected {affected} rows")
            return True

        except sqlite3.Error as e:
            logger.error(f"Update query failed: {e}")
            return False
        finally:
            # Ensure connection is always closed
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.warning(f"Error closing database connection: {e}")


class MemberQueries:
    """REAL queries for member data."""

    def __init__(self):
        self.db = DatabaseQueryHelper("members.db")

    def get_all_members(self, limit: int = None) -> List[Dict]:
        """Get ALL real members from database."""
        query = """
            SELECT
                user_id, username, first_name, last_name, phone,
                bio, is_bot, is_verified, is_premium, has_photo,
                language_code, scraped_at, last_seen, message_count,
                channel_id, channel_title
            FROM members
            ORDER BY scraped_at DESC
        """

        params = ()
        if limit:
            query += " LIMIT ?"
            params = (limit,)

        members = self.db.execute_query(query, params)
        logger.info(f"Retrieved {len(members)} REAL members from database")
        return members

    def get_member_statistics(self) -> Dict[str, float]:
        """Return aggregated member statistics without loading full datasets."""
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()

        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        active_cutoff = (datetime.now() - timedelta(days=30)).isoformat()

        stats = {}
        try:
            cursor.execute("SELECT COUNT(*) FROM members")
            stats["total"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM members WHERE scraped_at >= ?", (today_start,))
            stats["new_today"] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM members WHERE username IS NOT NULL AND username != ''"
            )
            stats["with_username"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM members WHERE is_verified = 1")
            stats["verified"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM members WHERE is_premium = 1")
            stats["premium"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM members WHERE last_seen >= ?", (active_cutoff,))
            stats["active_30d"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM channels")
            stats["total_channels"] = cursor.fetchone()[0]
        finally:
            conn.close()

        return stats

    def get_filtered_members(self, filter_criteria: Dict) -> List[Dict]:
        """Get filtered members with REAL database query."""
        conditions = []
        params = []

        # Build WHERE clause from filter criteria
        if filter_criteria.get("has_username"):
            conditions.append("username IS NOT NULL AND username != ''")

        if filter_criteria.get("has_photo"):
            conditions.append("has_photo = 1")

        if filter_criteria.get("exclude_bots"):
            conditions.append("(is_bot = 0 OR is_bot IS NULL)")

        if filter_criteria.get("is_verified"):
            conditions.append("is_verified = 1")

        if filter_criteria.get("premium_only"):
            conditions.append("is_premium = 1")

        if filter_criteria.get("name_contains"):
            conditions.append("(first_name LIKE ? OR last_name LIKE ?)")
            search = f"%{filter_criteria['name_contains']}%"
            params.extend([search, search])

        if filter_criteria.get("bio_contains"):
            conditions.append("bio LIKE ?")
            params.append(f"%{filter_criteria['bio_contains']}%")

        if filter_criteria.get("username_pattern"):
            conditions.append("username LIKE ?")
            params.append(f"%{filter_criteria['username_pattern']}%")

        if filter_criteria.get("joined_after"):
            conditions.append("scraped_at >= ?")
            params.append(filter_criteria["joined_after"].isoformat())

        if filter_criteria.get("last_seen_days"):
            cutoff = datetime.now() - timedelta(days=filter_criteria["last_seen_days"])
            conditions.append("last_seen >= ?")
            params.append(cutoff.isoformat())

        if filter_criteria.get("min_messages"):
            conditions.append("message_count >= ?")
            params.append(filter_criteria["min_messages"])

        if filter_criteria.get("language"):
            lang_code = filter_criteria["language"].lower()[:2]
            conditions.append("language_code = ?")
            params.append(lang_code)

        # Build final query
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT
                user_id, username, first_name, last_name, phone,
                bio, is_bot, is_verified, is_premium, has_photo,
                language_code, scraped_at, last_seen, message_count,
                channel_id, channel_title
            FROM members
            WHERE {where_clause}
            ORDER BY scraped_at DESC
        """

        if filter_criteria.get("limit"):
            query += " LIMIT ?"
            params.append(filter_criteria["limit"])

        members = self.db.execute_query(query, tuple(params))
        logger.info(f"Filtered query returned {len(members)} REAL members")
        return members

    def get_members_paginated(
        self, page: int = 1, page_size: int = 100, filter_criteria: Dict = None
    ) -> tuple:
        """
        Get paginated members with optional filtering.

        Returns:
            Tuple of (members_list, total_count)
        """
        conditions = []
        params = []

        # Build WHERE clause from filter criteria (same as get_filtered_members)
        if filter_criteria:
            if filter_criteria.get("has_username"):
                conditions.append("username IS NOT NULL AND username != ''")

            if filter_criteria.get("has_photo"):
                conditions.append("has_photo = 1")

            if filter_criteria.get("exclude_bots"):
                conditions.append("(is_bot = 0 OR is_bot IS NULL)")

            if filter_criteria.get("is_verified"):
                conditions.append("is_verified = 1")

            if filter_criteria.get("premium_only"):
                conditions.append("is_premium = 1")

            if filter_criteria.get("name_contains"):
                conditions.append("(first_name LIKE ? OR last_name LIKE ?)")
                search = f"%{filter_criteria['name_contains']}%"
                params.extend([search, search])

            if filter_criteria.get("bio_contains"):
                conditions.append("bio LIKE ?")
                params.append(f"%{filter_criteria['bio_contains']}%")

            if filter_criteria.get("username_pattern"):
                conditions.append("username LIKE ?")
                params.append(f"%{filter_criteria['username_pattern']}%")

            if filter_criteria.get("joined_after"):
                conditions.append("scraped_at >= ?")
                params.append(filter_criteria["joined_after"].isoformat())

            if filter_criteria.get("last_seen_days"):
                cutoff = datetime.now() - timedelta(days=filter_criteria["last_seen_days"])
                conditions.append("last_seen >= ?")
                params.append(cutoff.isoformat())

            if filter_criteria.get("min_messages"):
                conditions.append("message_count >= ?")
                params.append(filter_criteria["min_messages"])

            if filter_criteria.get("language"):
                lang_code = filter_criteria["language"].lower()[:2]
                conditions.append("language_code = ?")
                params.append(lang_code)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Get total count
        count_query = f"SELECT COUNT(*) FROM members WHERE {where_clause}"
        total_count = self.db.execute_count(count_query, tuple(params))

        # Get paginated data
        offset = (page - 1) * page_size
        data_query = f"""
            SELECT
                user_id, username, first_name, last_name, phone,
                bio, is_bot, is_verified, is_premium, has_photo,
                language_code, scraped_at, last_seen, message_count,
                channel_id, channel_title
            FROM members
            WHERE {where_clause}
            ORDER BY scraped_at DESC
            LIMIT ? OFFSET ?
        """

        paginated_params = params + [page_size, offset]
        members = self.db.execute_query(data_query, tuple(paginated_params))
        logger.info(f"Retrieved page {page} of members ({len(members)} items, {total_count} total)")

        return members, total_count

    def get_member_count(self, filter_criteria: Dict = None) -> int:
        """Get ACTUAL count of members matching criteria."""
        if not filter_criteria:
            query = "SELECT COUNT(*) FROM members"
            return self.db.execute_count(query)

        conditions = []
        params = []

        # Same filter logic as above
        if filter_criteria.get("has_username"):
            conditions.append("username IS NOT NULL AND username != ''")

        if filter_criteria.get("exclude_bots"):
            conditions.append("(is_bot = 0 OR is_bot IS NULL)")

        if filter_criteria.get("is_verified"):
            conditions.append("is_verified = 1")

        if filter_criteria.get("name_contains"):
            conditions.append("(first_name LIKE ? OR last_name LIKE ?)")
            search = f"%{filter_criteria['name_contains']}%"
            params.extend([search, search])

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT COUNT(*) FROM members WHERE {where_clause}"

        count = self.db.execute_count(query, tuple(params))
        logger.info(f"Actual member count: {count}")
        return count

    def get_members_by_channel(self, channel_id: int) -> List[Dict]:
        """Get all REAL members from a specific channel."""
        query = """
            SELECT
                user_id, username, first_name, last_name, phone,
                bio, is_bot, is_verified, is_premium, has_photo,
                language_code, scraped_at, last_seen, message_count
            FROM members
            WHERE channel_id = ?
            ORDER BY scraped_at DESC
        """

        members = self.db.execute_query(query, (channel_id,))
        logger.info(f"Retrieved {len(members)} REAL members from channel {channel_id}")
        return members

    def get_channels(self) -> List[Dict]:
        """Get all REAL channels from database."""
        query = """
            SELECT DISTINCT
                channel_id, channel_title,
                COUNT(*) as member_count,
                MAX(scraped_at) as last_scraped
            FROM members
            WHERE channel_id IS NOT NULL
            GROUP BY channel_id, channel_title
            ORDER BY last_scraped DESC
        """

        channels = self.db.execute_query(query)
        logger.info(f"Retrieved {len(channels)} REAL channels")
        return channels

    def update_member(self, user_id: int, updates: Dict) -> bool:
        """Update a member's data."""
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        params = list(updates.values()) + [user_id]

        query = f"UPDATE members SET {set_clause} WHERE user_id = ?"

        success = self.db.execute_update(query, tuple(params))
        if success:
            logger.info(f"Updated member {user_id}")
        return success


class CampaignQueries:
    """REAL queries for campaign data."""

    def __init__(self):
        self.db = DatabaseQueryHelper("campaigns.db")

    def get_all_campaigns(self) -> List[Dict]:
        """Get ALL real campaigns from database."""
        query = """
            SELECT
                id, name, status, message_template,
                total_targets, sent_count, failed_count,
                created_at, started_at, completed_at,
                accounts_used, delay_seconds
            FROM campaigns
            ORDER BY created_at DESC
        """

        campaigns = self.db.execute_query(query)
        logger.info(f"Retrieved {len(campaigns)} REAL campaigns")
        return campaigns

    def get_campaign_by_id(self, campaign_id: int) -> Optional[Dict]:
        """Get a specific campaign."""
        query = """
            SELECT
                id, name, status, message_template,
                total_targets, sent_count, failed_count,
                created_at, started_at, completed_at,
                accounts_used, delay_seconds
            FROM campaigns
            WHERE id = ?
        """

        campaign = self.db.execute_single(query, (campaign_id,))
        if campaign:
            logger.info(f"Retrieved campaign {campaign_id}")
        return campaign

    def get_campaign_stats(self) -> Dict:
        """Get REAL aggregate campaign statistics."""
        query = """
            SELECT
                COUNT(*) as total_campaigns,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(sent_count) as total_sent,
                SUM(failed_count) as total_failed
            FROM campaigns
        """

        stats = self.db.execute_single(query)
        if stats:
            logger.info(f"Campaign stats: {stats}")
        return stats or {}


class AccountQueries:
    """REAL queries for account data."""

    def __init__(self):
        self.db = DatabaseQueryHelper("members.db")

    def get_all_accounts(self) -> List[Dict]:
        """Get ALL real accounts from database."""
        query = """
            SELECT
                phone_number, status, session_file,
                created_at, last_active, messages_sent,
                is_warmed_up, warmup_stage, proxy_used,
                api_id, api_hash
            FROM accounts
            ORDER BY created_at DESC
        """

        accounts = self.db.execute_query(query)
        logger.info(f"Retrieved {len(accounts)} REAL accounts")
        return accounts

    def get_account_by_phone(self, phone_number: str) -> Optional[Dict]:
        """Get specific account."""
        query = """
            SELECT
                phone_number, status, session_file,
                created_at, last_active, messages_sent,
                is_warmed_up, warmup_stage, proxy_used
            FROM accounts
            WHERE phone_number = ?
        """

        account = self.db.execute_single(query, (phone_number,))
        return account

    def get_account_stats(self) -> Dict:
        """Get REAL aggregate account statistics."""
        query = """
            SELECT
                COUNT(*) as total_accounts,
                SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                SUM(CASE WHEN is_warmed_up = 1 THEN 1 ELSE 0 END) as warmed_up,
                SUM(messages_sent) as total_messages
            FROM accounts
        """

        stats = self.db.execute_single(query)
        return stats or {}


# Convenience instances
member_queries = MemberQueries()
campaign_queries = CampaignQueries()
account_queries = AccountQueries()
