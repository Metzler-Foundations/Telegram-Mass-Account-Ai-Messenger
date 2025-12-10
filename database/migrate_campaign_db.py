#!/usr/bin/env python3
"""
Database migration script for campaigns database.

Adds indexes for campaign message queries to improve performance.
"""

import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def migrate_campaign_database(db_path: str = "campaigns.db"):
    """Migrate campaigns database to add missing indexes."""

    if not Path(db_path).exists():
        logger.info(f"Database {db_path} does not exist. No migration needed.")
        return

    logger.info("=" * 70)
    logger.info("Campaign Database Migration")
    logger.info("=" * 70)

    try:
        with sqlite3.connect(db_path) as conn:
            # Check existing indexes
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            existing_indexes = {row[0] for row in cursor.fetchall()}

            logger.info(f"\nFound {len(existing_indexes)} existing indexes")

            # Define all required indexes
            indexes_to_create = [
                (
                    "idx_campaign_messages_campaign_id",
                    "CREATE INDEX IF NOT EXISTS idx_campaign_messages_campaign_id "
                    "ON campaign_messages(campaign_id)",
                ),
                (
                    "idx_campaign_messages_sent_at",
                    "CREATE INDEX IF NOT EXISTS idx_campaign_messages_sent_at "
                    "ON campaign_messages(sent_at DESC)",
                ),
                (
                    "idx_campaign_messages_status",
                    "CREATE INDEX IF NOT EXISTS idx_campaign_messages_status "
                    "ON campaign_messages(status)",
                ),
                (
                    "idx_campaign_messages_campaign_sent",
                    "CREATE INDEX IF NOT EXISTS idx_campaign_messages_campaign_sent "
                    "ON campaign_messages(campaign_id, sent_at DESC)",
                ),
                (
                    "idx_campaigns_status",
                    "CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)",
                ),
                (
                    "idx_campaigns_created_at",
                    "CREATE INDEX IF NOT EXISTS idx_campaigns_created_at ON campaigns(created_at DESC)",
                ),
            ]

            created_count = 0
            for index_name, create_sql in indexes_to_create:
                if index_name not in existing_indexes:
                    logger.info(f"Creating index: {index_name}")
                    conn.execute(create_sql)
                    created_count += 1
                else:
                    logger.info(f"Index already exists: {index_name}")

            conn.commit()

            logger.info(f"\n✅ Migration complete: {created_count} new indexes created")

            # Verify all indexes
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
            final_indexes = [row[0] for row in cursor.fetchall()]

            logger.info(f"\nFinal index count: {len(final_indexes)}")
            for idx in sorted(final_indexes):
                if not idx.startswith("sqlite_"):  # Skip internal indexes
                    logger.info(f"  ✅ {idx}")

    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise

    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    migrate_campaign_database()
