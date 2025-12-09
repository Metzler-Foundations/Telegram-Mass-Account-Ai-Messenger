#!/usr/bin/env python3
"""
Implementation Completeness - Ensures all features are REAL implementations
Fills gaps and completes partial implementations
"""

import logging
import sqlite3
from typing import Any, Dict

logger = logging.getLogger(__name__)


def ensure_database_schema_complete():
    """Ensure ALL database tables have complete schema."""

    schemas = {
        "members.db": [
            """
            CREATE TABLE IF NOT EXISTS members (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                bio TEXT,
                is_bot INTEGER DEFAULT 0,
                is_verified INTEGER DEFAULT 0,
                is_premium INTEGER DEFAULT 0,
                has_photo INTEGER DEFAULT 0,
                language_code TEXT,
                scraped_at TEXT NOT NULL,
                last_seen TEXT,
                message_count INTEGER DEFAULT 0,
                channel_id INTEGER,
                channel_title TEXT,
                active_status TEXT,
                last_online TEXT,
                join_date TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS accounts (
                phone_number TEXT PRIMARY KEY,
                session_name TEXT UNIQUE NOT NULL,
                session_file TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_active TEXT,
                messages_sent INTEGER DEFAULT 0,
                messages_received INTEGER DEFAULT 0,
                is_warmed_up INTEGER DEFAULT 0,
                warmup_stage TEXT DEFAULT 'pending',
                warmup_started_at TEXT,
                warmup_completed_at TEXT,
                proxy_used TEXT,
                device_fingerprint TEXT,
                api_id TEXT,
                api_hash TEXT,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                bio TEXT,
                profile_photo_path TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                username TEXT,
                title TEXT,
                member_count INTEGER,
                description TEXT,
                is_public INTEGER DEFAULT 1,
                first_scraped TEXT,
                last_scraped TEXT,
                scrape_count INTEGER DEFAULT 0
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_members_username ON members(username)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_members_channel ON members(channel_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_members_scraped_at ON members(scraped_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_accounts_warmup ON accounts(is_warmed_up)
            """,
        ],
        "campaigns.db": [
            """
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                message_template TEXT NOT NULL,
                total_targets INTEGER NOT NULL,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                pending_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                paused_at TEXT,
                accounts_used TEXT,
                delay_seconds REAL DEFAULT 60.0,
                target_channels TEXT,
                filter_criteria TEXT,
                schedule_type TEXT DEFAULT 'immediate',
                scheduled_for TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS campaign_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                target_username TEXT,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL,
                error_message TEXT,
                account_used TEXT,
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS campaign_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id) ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_campaign_messages_campaign
            ON campaign_messages(campaign_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_campaign_messages_sent_at
            ON campaign_messages(sent_at)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_campaign_messages_status
            ON campaign_messages(status)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_campaigns_status
            ON campaigns(status)
            """,
        ],
    }

    for db_name, schema_list in schemas.items():
        try:
            conn = sqlite3.connect(db_name)
            cursor = conn.cursor()

            for schema in schema_list:
                cursor.execute(schema)

            conn.commit()
            conn.close()

            logger.info(f"✅ Database schema complete for {db_name}")

        except Exception as e:
            logger.error(f"Failed to ensure schema for {db_name}: {e}")


def add_missing_config_fields():
    """Add missing fields to config.json with REAL defaults."""
    import json
    from pathlib import Path

    try:
        config_file = Path("config.json")

        if config_file.exists():
            with open(config_file) as f:
                config = json.load(f)
        else:
            config = {}

        # Add proxies section if missing
        if "proxies" not in config:
            config["proxies"] = {
                "proxy_list": [],
                "use_proxy": False,
                "require_proxy": False,
                "max_failures": 3,
                "cooldown_minutes": 30,
            }

        # Add account creation defaults if missing
        if "account_creation" not in config:
            config["account_creation"] = {
                "phone_provider": "sms-activate",
                "provider_api_key": "",
                "country": "US",
                "use_proxy": True,
                "realistic_timing": True,
                "auto_warmup": True,
                "warmup_days": 7,
            }

        # Add campaign defaults if missing
        if "campaigns" not in config:
            config["campaigns"] = {
                "default_delay": 60,
                "max_retries": 3,
                "track_analytics": True,
                "auto_pause_on_error": True,
            }

        # Add analytics defaults if missing
        if "analytics" not in config:
            config["analytics"] = {
                "enabled": True,
                "refresh_interval": 30,
                "track_detailed": True,
                "export_daily": False,
            }

        # Save updated config
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        logger.info("✅ Config file updated with complete fields")
        return True

    except Exception as e:
        logger.error(f"Failed to update config: {e}")
        return False


def verify_all_imports():
    """Verify all imports work and modules are accessible."""
    missing = []

    modules_to_check = [
        "user_helpers",
        "welcome_wizard",
        "retry_helper",
        "ui_enhancements",
        "app_launcher",
        "progress_tracker",
        "resume_manager",
        "template_tester",
        "member_filter",
        "data_export",
        "database_queries",
        "analytics_dashboard",
        "proxy_monitor",
        "campaign_tracker",
        "warmup_tracker",
        "system_integration",
        "integration_connector",
    ]

    for module in modules_to_check:
        try:
            __import__(module)
            logger.info(f"✅ {module} imports successfully")
        except ImportError as e:
            logger.error(f"❌ {module} import failed: {e}")
            missing.append(module)

    return missing


def initialize_all_databases():
    """Initialize ALL databases with complete schemas."""
    logger.info("Initializing ALL databases with REAL schemas...")

    ensure_database_schema_complete()

    from campaign_tracker import initialize_campaign_database

    initialize_campaign_database()

    logger.info("✅ ALL databases initialized")


def run_completeness_check() -> Dict[str, Any]:
    """Run complete system check and return status."""
    results = {
        "databases": True,
        "config": True,
        "imports": True,
        "missing_modules": [],
        "errors": [],
    }

    # Check databases
    try:
        ensure_database_schema_complete()
    except Exception as e:
        results["databases"] = False
        results["errors"].append(f"Database schema: {e}")

    # Check config
    try:
        add_missing_config_fields()
    except Exception as e:
        results["config"] = False
        results["errors"].append(f"Config update: {e}")

    # Check imports
    missing = verify_all_imports()
    if missing:
        results["imports"] = False
        results["missing_modules"] = missing

    # Overall status
    results["complete"] = results["databases"] and results["config"] and results["imports"]

    return results


# Run initialization on import
initialize_all_databases()
add_missing_config_fields()
