#!/usr/bin/env python3
"""
Create Missing Database Tables - Fix gaps in database schemas.

This script creates all the missing tables identified during the audit.
"""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_account_risk_scores_table():
    """Create account_risk_scores table in anti_detection.db"""
    print("\n📊 Creating account_risk_scores table...")

    try:
        conn = sqlite3.connect("anti_detection.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS account_risk_scores (
                account_phone TEXT PRIMARY KEY,
                risk_score REAL DEFAULT 0.0,
                ban_probability REAL DEFAULT 0.0,
                risk_level TEXT DEFAULT 'safe',
                suspicious_activities INTEGER DEFAULT 0,
                rate_limit_hits INTEGER DEFAULT 0,
                failed_actions INTEGER DEFAULT 0,
                last_risk_increase TIMESTAMP,
                last_assessment TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                quarantine_status TEXT DEFAULT 'active',
                quarantine_reason TEXT,
                notes TEXT
            )
        """
        )

        # Create indexes
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_account_risk_level
            ON account_risk_scores(risk_level)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_account_quarantine
            ON account_risk_scores(quarantine_status)
        """
        )

        conn.commit()
        conn.close()

        print("✅ account_risk_scores table created")
        return True

    except Exception as e:
        print(f"❌ Failed to create account_risk_scores: {e}")
        return False


def create_shadowban_monitor_table():
    """Create shadowban_monitor table in anti_detection.db"""
    print("\n📊 Creating shadowban_monitor table...")

    try:
        conn = sqlite3.connect("anti_detection.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS shadowban_monitor (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_phone TEXT NOT NULL,
                check_type TEXT NOT NULL,
                is_shadowbanned BOOLEAN DEFAULT 0,
                confidence_score REAL DEFAULT 0.0,
                indicators TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                detection_method TEXT,
                test_message_id INTEGER,
                test_result TEXT,
                recommendations TEXT
            )
        """
        )

        # Create indexes
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_shadowban_account
            ON shadowban_monitor(account_phone)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_shadowban_status
            ON shadowban_monitor(is_shadowbanned)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_shadowban_checked_at
            ON shadowban_monitor(checked_at)
        """
        )

        conn.commit()
        conn.close()

        print("✅ shadowban_monitor table created")
        return True

    except Exception as e:
        print(f"❌ Failed to create shadowban_monitor: {e}")
        return False


def create_schema_migrations_table_accounts():
    """Create schema_migrations table in accounts.db"""
    print("\n📊 Creating schema_migrations table in accounts.db...")

    try:
        conn = sqlite3.connect("accounts.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT
            )
        """
        )

        # Insert initial version
        cursor.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, description)
            VALUES (1, 'Initial schema - accounts and account_metrics')
        """
        )

        conn.commit()
        conn.close()

        print("✅ schema_migrations table created in accounts.db")
        return True

    except Exception as e:
        print(f"❌ Failed to create schema_migrations: {e}")
        return False


def create_conversation_context_table():
    """Create conversation_context table for AI persistence"""
    print("\n📊 Creating conversation_context table...")

    try:
        conn = sqlite3.connect("conversation_analytics.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_context (
                chat_id INTEGER PRIMARY KEY,
                account_phone TEXT,
                conversation_history TEXT,
                last_message_at TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                context_summary TEXT,
                sentiment_trend TEXT,
                topics TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create indexes
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_account
            ON conversation_context(account_phone)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversation_updated
            ON conversation_context(updated_at)
        """
        )

        conn.commit()
        conn.close()

        print("✅ conversation_context table created")
        return True

    except Exception as e:
        print(f"❌ Failed to create conversation_context: {e}")
        return False


def create_warmup_jobs_table():
    """Create warmup_jobs table for warmup tracking"""
    print("\n📊 Creating warmup_jobs table...")

    try:
        # Check if warmup_jobs.json exists, if so, we might want to migrate it
        warmup_json = Path("warmup_jobs.json")
        if warmup_json.exists():
            print("  ℹ️  Found existing warmup_jobs.json (manual migration may be needed)")

        conn = sqlite3.connect("warmup.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS warmup_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_phone TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                current_stage INTEGER DEFAULT 1,
                stage_progress REAL DEFAULT 0.0,
                messages_sent INTEGER DEFAULT 0,
                conversations_held INTEGER DEFAULT 0,
                groups_joined INTEGER DEFAULT 0,
                last_activity TIMESTAMP,
                next_activity TIMESTAMP,
                error_count INTEGER DEFAULT 0,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                config TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_warmup_account
            ON warmup_jobs(account_phone)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_warmup_status
            ON warmup_jobs(status)
        """
        )

        conn.commit()
        conn.close()

        print("✅ warmup_jobs table created")
        return True

    except Exception as e:
        print(f"❌ Failed to create warmup_jobs: {e}")
        return False


def create_audit_events_table():
    """Create audit_events table for account audit logging"""
    print("\n📊 Creating audit_events table...")

    try:
        conn = sqlite3.connect("accounts_audit.db")
        cursor = conn.cursor()

        # Check if table exists and has columns
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_events'")
        table_exists = cursor.fetchone() is not None

        if table_exists:
            # Table exists, try to add missing columns
            print("  ℹ️  Table exists, checking for missing columns...")
            try:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN account_phone TEXT")
                print("  ✅ Added account_phone column")
            except Exception:
                pass  # Column might already exist

            try:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN severity TEXT DEFAULT 'info'")
                print("  ✅ Added severity column")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN user_id TEXT")
                print("  ✅ Added user_id column")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN ip_address TEXT")
                print("  ✅ Added ip_address column")
            except Exception:
                pass

            try:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN session_id TEXT")
                print("  ✅ Added session_id column")
            except Exception:
                pass
        else:
            # Create new table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    account_phone TEXT,
                    severity TEXT DEFAULT 'info',
                    message TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT,
                    ip_address TEXT,
                    session_id TEXT
                )
            """
            )

        # Create indexes (IF NOT EXISTS is safe)
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_account
            ON audit_events(account_phone)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_type
            ON audit_events(event_type)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_events(timestamp)
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_severity
            ON audit_events(severity)
        """
        )

        conn.commit()
        conn.close()

        print("✅ audit_events table created/updated")
        return True

    except Exception as e:
        print(f"❌ Failed to create/update audit_events: {e}")
        import traceback

        traceback.print_exc()
        return False


def create_phone_blacklist_table():
    """Create phone_blacklist table"""
    print("\n📊 Creating phone_blacklist table...")

    try:
        conn = sqlite3.connect("accounts.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS phone_blacklist (
                phone_number TEXT PRIMARY KEY,
                reason TEXT,
                blacklisted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                blacklisted_by TEXT,
                notes TEXT,
                expires_at TIMESTAMP
            )
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_phone_blacklist_expires
            ON phone_blacklist(expires_at)
        """
        )

        conn.commit()
        conn.close()

        print("✅ phone_blacklist table created")
        return True

    except Exception as e:
        print(f"❌ Failed to create phone_blacklist: {e}")
        return False


def main():
    """Create all missing tables."""
    print("=" * 70)
    print("  Creating Missing Database Tables")
    print("=" * 70)

    project_root = Path(__file__).parent.parent
    import os

    os.chdir(project_root)

    results = []

    # Create each missing table
    results.append(("account_risk_scores", create_account_risk_scores_table()))
    results.append(("shadowban_monitor", create_shadowban_monitor_table()))
    results.append(("schema_migrations (accounts.db)", create_schema_migrations_table_accounts()))
    results.append(("conversation_context", create_conversation_context_table()))
    results.append(("warmup_jobs", create_warmup_jobs_table()))
    results.append(("audit_events", create_audit_events_table()))
    results.append(("phone_blacklist", create_phone_blacklist_table()))

    # Summary
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)

    success_count = sum(1 for _, success in results if success)
    total_count = len(results)

    for table_name, success in results:
        symbol = "✅" if success else "❌"
        print(f"{symbol} {table_name}")

    print(f"\n{success_count}/{total_count} tables created successfully")

    if success_count == total_count:
        print("\n✅ All missing tables created!")
        print("\nNext: Run validation")
        print("  ./venv/bin/python3 scripts/verify_databases.py")
        return 0
    else:
        print(f"\n⚠️  {total_count - success_count} table(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
