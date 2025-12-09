#!/usr/bin/env python3
"""
Database migration script for proxy pool.

This script adds missing indexes and updates the database schema to improve performance.
"""

import logging
import sqlite3
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def migrate_proxy_database(db_path: str = "proxy_pool.db"):
    """Migrate proxy database to add missing indexes."""

    if not Path(db_path).exists():
        logger.info(f"Database {db_path} does not exist. No migration needed.")
        return

    logger.info("=" * 70)
    logger.info("Proxy Database Migration")
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
                    "idx_proxy_fraud_score",
                    "CREATE INDEX IF NOT EXISTS idx_proxy_fraud_score ON proxies(fraud_score)",
                ),
                (
                    "idx_proxy_last_check",
                    "CREATE INDEX IF NOT EXISTS idx_proxy_last_check ON proxies(last_check)",
                ),
                (
                    "idx_proxy_status_score",
                    "CREATE INDEX IF NOT EXISTS idx_proxy_status_score ON proxies(status, score DESC)",
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
    migrate_proxy_database()
