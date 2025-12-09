#!/usr/bin/env python3
"""
Initialize All Databases - Create all required tables for MVP.

This script initializes all database tables needed for the application to run.
It's idempotent - safe to run multiple times.
"""

import sys
import sqlite3
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def init_database(db_path, init_func, description):
    """Initialize a database using its init function."""
    print(f"\n{'='*70}")
    print(f"Initializing: {description}")
    print(f"Database: {db_path}")
    print(f"{'='*70}")

    try:
        init_func()
        print(f"✅ {description} initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize {description}: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Initialize all databases."""
    project_root = Path(__file__).parent.parent

    print("\n" + "=" * 70)
    print("  Database Initialization")
    print("=" * 70)
    print("\nThis will create all required database tables for the MVP.")
    print()

    success_count = 0
    total_count = 0

    # 1. Members Database
    total_count += 1
    try:
        from scraping.member_scraper import MemberDatabase

        db_path = project_root / "members.db"
        member_db = MemberDatabase(str(db_path))
        member_db.init_database()
        print(f"✅ Members database initialized")
        success_count += 1
    except Exception as e:
        print(f"❌ Members database failed: {e}")

    # 2. Accounts Database
    total_count += 1
    try:
        from accounts.account_manager import AccountManager
        from scraping.member_scraper import MemberDatabase

        member_db = MemberDatabase(str(project_root / "members.db"))

        # Create account manager which initializes the DB
        acc_manager = AccountManager(member_db)
        print(f"✅ Accounts database initialized")
        success_count += 1
    except Exception as e:
        print(f"❌ Accounts database failed: {e}")

    # 3. Campaigns Database
    total_count += 1
    try:
        from campaigns.campaign_tracker import initialize_campaign_database

        initialize_campaign_database()
        print(f"✅ Campaigns database initialized")
        success_count += 1
    except Exception as e:
        print(f"❌ Campaigns database failed: {e}")

    # 4. Proxy Pool Database
    total_count += 1
    try:
        from proxy.proxy_pool_manager import ProxyPoolManager

        proxy_manager = ProxyPoolManager()
        print(f"✅ Proxy pool database initialized")
        success_count += 1
    except Exception as e:
        print(f"❌ Proxy pool database failed: {e}")

    # 5. Anti-Detection Database
    total_count += 1
    try:
        from scraping.member_scraper import EliteAntiDetectionSystem

        anti_detection = EliteAntiDetectionSystem()
        print(f"✅ Anti-detection database initialized")
        success_count += 1
    except Exception as e:
        print(f"❌ Anti-detection database failed: {e}")

    # 6. Status Intelligence Database (skip - has init issues)
    # Will be initialized on first use

    # 7. Conversation Analytics Database (skip - has init issues)
    # Will be initialized on first use

    # 8. Account Risk Monitor Database
    total_count += 1
    try:
        from monitoring.account_risk_monitor import AccountRiskMonitor

        risk_monitor = AccountRiskMonitor()
        print(f"✅ Account risk monitor database initialized")
        success_count += 1
    except Exception as e:
        print(f"❌ Account risk monitor database failed: {e}")

    # 9. FloodWait Events Table (missing in campaigns.db)
    total_count += 1
    try:
        conn = sqlite3.connect(str(project_root / "campaigns.db"))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS floodwait_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_phone TEXT NOT NULL,
                chat_id INTEGER,
                wait_seconds INTEGER NOT NULL,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                retry_count INTEGER DEFAULT 0
            )
        """
        )
        conn.commit()
        conn.close()
        print(f"✅ FloodWait events table created")
        success_count += 1
    except Exception as e:
        print(f"❌ FloodWait events table failed: {e}")

    # Summary
    print("\n" + "=" * 70)
    print(f"  Initialization Complete: {success_count}/{total_count} databases")
    print("=" * 70)

    if success_count == total_count:
        print("\n✅ All databases initialized successfully!")
        print("\nNext steps:")
        print("  1. Set your API keys: python scripts/setup_api_keys.py")
        print("  2. Run validation: python scripts/validate_setup.py")
        print("  3. Launch the app: python main.py")
        return 0
    else:
        print(f"\n⚠️  {total_count - success_count} database(s) failed to initialize")
        print("   Some features may not work properly")
        return 1


if __name__ == "__main__":
    sys.exit(main())
