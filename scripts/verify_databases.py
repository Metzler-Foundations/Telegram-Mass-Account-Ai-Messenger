#!/usr/bin/env python3
"""
Database Verification Script - Check all database tables are created.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_database_tables(db_path, expected_tables):
    """Check if expected tables exist in database."""
    print(f"\n📊 Checking {db_path.name}...")

    if not db_path.exists():
        print("  ❌ Database file doesn't exist!")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        conn.close()

        print(f"  Found {len(existing_tables)} tables")

        all_good = True
        for table in expected_tables:
            if table in existing_tables:
                print(f"    ✅ {table}")
            else:
                print(f"    ❌ {table} - MISSING!")
                all_good = False

        # Show extra tables
        extra = existing_tables - set(expected_tables)
        if extra:
            print(f"  Additional tables: {', '.join(extra)}")

        return all_good

    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def main():
    """Verify all database schemas."""
    project_root = Path(__file__).parent.parent

    databases = {
        "accounts.db": ["accounts", "account_metrics", "schema_migrations"],
        "members.db": [
            "members",
            "channels",
            "member_activity",
            "member_profiles",
            "member_activity_patterns",
            "member_network",
            "member_behavioral_insights",
            "scraping_analytics",
            "schema_migrations",
            "backups",
        ],
        "campaigns.db": [
            "campaigns",
            "campaign_messages",
            "campaign_analytics",
            "campaign_response_stats",
            "delivery_events",
            "floodwait_events",
        ],
        "proxy_pool.db": ["proxies", "proxy_assignments", "proxy_health_log", "proxy_pool_stats"],
        "anti_detection.db": ["account_risk_scores", "shadowban_monitor"],
    }

    print("=" * 70)
    print("  Database Schema Verification")
    print("=" * 70)

    all_good = True
    for db_name, tables in databases.items():
        db_path = project_root / db_name
        result = check_database_tables(db_path, tables)
        if not result:
            all_good = False

    print("\n" + "=" * 70)
    if all_good:
        print("✅ All databases verified successfully!")
        return 0
    else:
        print("❌ Some databases have missing tables")
        print("   Run: python database/migration_system.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
