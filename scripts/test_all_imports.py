#!/usr/bin/env python3
"""
Test All Module Imports - Systematically verify every module imports cleanly.

This script imports every Python module in the project to identify any issues
that don't require API keys.
"""

import sys
import importlib
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_imports():
    """Test importing all major modules."""

    modules_to_test = {
        # Core
        "core.config_manager": "Configuration Manager",
        "core.secrets_manager": "Secrets Manager",
        "core.authentication": "Authentication System",
        "core.service_container": "Service Container",
        "core.services": "Business Logic Services",
        "core.repositories": "Data Repositories",
        "core.error_handler": "Error Handler",
        "core.graceful_shutdown": "Graceful Shutdown",
        # Database
        "database.connection_pool": "Connection Pool",
        "database.transaction_manager": "Transaction Manager",
        "database.lock_handler": "Lock Handler",
        "database.migration_system": "Migration System",
        "database.backup_manager": "Backup Manager",
        # Accounts
        "accounts.account_creator": "Account Creator",
        "accounts.account_manager": "Account Manager",
        "accounts.account_warmup_service": "Account Warmup Service",
        "accounts.username_generator": "Username Generator",
        "accounts.username_validator": "Username Validator",
        "accounts.phone_normalizer": "Phone Normalizer",
        "accounts.phone_blacklist": "Phone Blacklist",
        "accounts.ban_detector": "Ban Detector",
        "accounts.account_audit_log": "Account Audit Log",
        # AI
        "ai.gemini_service": "Gemini Service",
        "ai.status_intelligence": "Status Intelligence",
        "ai.conversation_analyzer": "Conversation Analyzer",
        "ai.media_intelligence": "Media Intelligence",
        "ai.intelligence_engine": "Intelligence Engine",
        "ai.response_optimizer": "Response Optimizer",
        # Campaigns
        "campaigns.dm_campaign_manager": "DM Campaign Manager",
        "campaigns.campaign_tracker": "Campaign Tracker",
        "campaigns.delivery_analytics": "Delivery Analytics",
        "campaigns.intelligent_scheduler": "Intelligent Scheduler",
        "campaigns.engagement_automation": "Engagement Automation",
        # Scraping
        "scraping.member_scraper": "Member Scraper",
        "scraping.member_filter": "Member Filter",
        "scraping.resumable_scraper": "Resumable Scraper",
        "scraping.group_discovery_engine": "Group Discovery Engine",
        # Proxy
        "proxy.proxy_pool_manager": "Proxy Pool Manager",
        # 'proxy.proxy_manager': 'Proxy Manager',  # Module doesn't exist
        "proxy.automated_cleanup_service": "Automated Cleanup Service",
        # Anti-Detection
        "anti_detection.anti_detection_system": "Anti-Detection System",
        "anti_detection.device_fingerprint_randomizer": "Device Fingerprint Randomizer",
        "anti_detection.shadowban_detector": "Shadowban Detector",
        "anti_detection.timing_optimizer": "Timing Optimizer",
        "anti_detection.user_agent_rotation": "User Agent Rotation",
        # Telegram
        "telegram.telegram_client": "Telegram Client",
        "telegram.client_pool": "Client Pool",
        "telegram.persistent_connection_manager": "Persistent Connection Manager",
        # Monitoring
        "monitoring.performance_monitor": "Performance Monitor",
        "monitoring.health_check": "Health Check",
        "monitoring.account_risk_monitor": "Account Risk Monitor",
        "monitoring.cost_alert_system": "Cost Alert System",
        "monitoring.advanced_features_manager": "Advanced Features Manager",
        # Integrations
        "integrations.api_key_manager": "API Key Manager",
        "integrations.voice_service": "Voice Service",
        "integrations.export_manager": "Export Manager",
        "integrations.notification_system": "Notification System",
        # Utils
        "utils.rate_limiter": "Rate Limiter",
        "utils.retry_helper": "Retry Helper",
        "utils.input_validation": "Input Validation",
        "utils.utils": "General Utils",
    }

    print("=" * 70)
    print("  Module Import Test")
    print("=" * 70)
    print(f"\nTesting {len(modules_to_test)} modules...\n")

    passed = []
    failed = []
    warnings = []

    for module_name, description in modules_to_test.items():
        try:
            # Capture warnings
            import warnings as warn_module

            with warn_module.catch_warnings(record=True) as w:
                warn_module.simplefilter("always")
                importlib.import_module(module_name)

                if w:
                    # Module imported but with warnings
                    warning_msgs = [str(warning.message) for warning in w]
                    warnings.append((module_name, description, warning_msgs))
                    print(f"⚠️  {description} ({module_name}) - with warnings")
                else:
                    passed.append((module_name, description))
                    print(f"✅ {description}")
        except Exception as e:
            failed.append((module_name, description, str(e)))
            print(f"❌ {description} ({module_name})")
            print(f"   Error: {str(e)[:100]}")

    # Summary
    print("\n" + "=" * 70)
    print("  Summary")
    print("=" * 70)

    print(f"\n✅ Passed: {len(passed)}/{len(modules_to_test)}")
    print(f"⚠️  Warnings: {len(warnings)}/{len(modules_to_test)}")
    print(f"❌ Failed: {len(failed)}/{len(modules_to_test)}")

    if warnings:
        print("\nModules with Warnings:")
        for module_name, description, warning_msgs in warnings:
            print(f"  ⚠️  {description}")
            for msg in warning_msgs[:2]:  # Show first 2 warnings
                print(f"     {msg[:80]}")

    if failed:
        print("\nFailed Modules:")
        for module_name, description, error in failed:
            print(f"  ❌ {description}")
            print(f"     {error[:80]}")

    # Overall status
    print("\n" + "=" * 70)

    if len(passed) == len(modules_to_test):
        print("✅ ALL MODULES IMPORT SUCCESSFULLY!")
        return 0
    elif len(failed) == 0:
        print("✅ All modules import (some with warnings)")
        print("⚠️  Warnings are usually non-critical")
        return 0
    else:
        success_rate = (len(passed) + len(warnings)) / len(modules_to_test) * 100
        print(f"⚠️  {success_rate:.1f}% of modules import successfully")
        print(f"   {len(failed)} module(s) need attention")
        return 1


if __name__ == "__main__":
    sys.exit(test_imports())
