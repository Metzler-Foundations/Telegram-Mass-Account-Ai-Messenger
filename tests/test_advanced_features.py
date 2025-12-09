#!/usr/bin/env python3
"""
Test script for advanced features.
Run this to verify features are working before full integration.
"""

import asyncio
import sys
from pathlib import Path

# Ensure imports work
try:
    from advanced_features_manager import AdvancedFeaturesManager, get_features_manager

    print("✅ Advanced features manager imported successfully")
except ImportError as e:
    print(f"❌ Failed to import advanced features manager: {e}")
    sys.exit(1)


# Test individual features
def test_feature_initialization():
    """Test that all features can be initialized."""
    print("\n=== Testing Feature Initialization ===")

    try:
        manager = AdvancedFeaturesManager(
            enabled_features=[
                "intelligence",
                "engagement",
                "discovery",
                "status",
                "shadowban",
                "network",
                "competitor",
                "media",
                "scheduler",
            ]
        )
        print("✅ All features initialized successfully")
        return manager
    except Exception as e:
        print(f"❌ Failed to initialize features: {e}")
        return None


def test_databases():
    """Test that database files are created."""
    print("\n=== Testing Database Creation ===")

    expected_dbs = [
        "intelligence.db",
        "engagement.db",
        "discovered_groups.db",
        "status_intelligence.db",
        "shadowban_monitor.db",
        "recovery_plans.db",
        "network.db",
        "competitor_intel.db",
        "media_intelligence.db",
        "scheduler.db",
        "conversation_analytics.db",
    ]

    for db in expected_dbs:
        if Path(db).exists():
            print(f"✅ {db} exists")
        else:
            print(f"⚠️  {db} not created yet (will be created on first use)")


def test_feature_apis():
    """Test basic API calls without Telegram client."""
    print("\n=== Testing Feature APIs ===")

    try:
        manager = AdvancedFeaturesManager()

        # Test engagement rule creation
        rule = manager.setup_engagement_rule(
            "Test Rule", "moderate", target_groups=[], keywords=["test"]
        )
        if rule:
            print(f"✅ Engagement rule created: {rule.rule_id}")
        else:
            print("⚠️  Engagement rule creation returned None")

        # Test high value targets (will be empty initially)
        targets = manager.get_high_value_targets(min_score=50.0, limit=10)
        print(f"✅ High value targets query: {len(targets)} users")

        # Test stats
        stats = manager.get_overall_stats()
        print(f"✅ Overall stats: {len(stats)} categories")

        # Test group discovery stats
        discovery_stats = (
            manager.group_discovery.get_discovery_stats() if manager.group_discovery else {}
        )
        print(f"✅ Discovery stats: {discovery_stats.get('total_discovered', 0)} groups")

        print("\n✅ All API tests passed!")
        return True

    except Exception as e:
        print(f"❌ API test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_dependencies():
    """Test that required dependencies are installed."""
    print("\n=== Testing Dependencies ===")

    deps = {
        "networkx": "Network analytics",
        "PIL": "Media processing (Pillow)",
        "pyrogram": "Telegram client",
        "sqlite3": "Database (built-in)",
    }

    for module, purpose in deps.items():
        try:
            if module == "PIL":
                import PIL  # noqa: F401
            else:
                __import__(module)
            print(f"✅ {module} - {purpose}")
        except ImportError:
            print(f"❌ {module} NOT INSTALLED - {purpose}")
            if module == "networkx":
                print("   Run: pip install networkx")
            elif module == "PIL":
                print("   Run: pip install Pillow")


async def test_with_telegram(api_id: str, api_hash: str, phone: str):
    """Test with actual Telegram connection (optional).

    Args:
        api_id: Telegram API ID
        api_hash: Telegram API hash
        phone: Phone number
    """
    print("\n=== Testing with Telegram (Optional) ===")

    try:
        from pyrogram import Client

        client = Client("test_session", api_id=api_id, api_hash=api_hash, phone_number=phone)
        await client.start()

        manager = get_features_manager()

        # Test getting your own user info
        me = await client.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username})")

        # Test intelligence gathering on yourself
        if manager.intelligence:
            intel = await manager.analyze_user(client, me.id, deep=False)
            if intel:
                print(f"✅ Intelligence gathered: Value score = {intel.value_score}")

        # Test status tracking
        if manager.status_tracker:
            profile = await manager.track_user_status(client, me.id)
            if profile:
                print(f"✅ Status tracked: {profile.current_status.value}")

        await client.stop()
        print("\n✅ Telegram integration test passed!")

    except Exception as e:
        print(f"❌ Telegram test failed: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Main test function."""
    print("=" * 60)
    print("Advanced Features Test Suite")
    print("=" * 60)

    # Test 1: Dependencies
    test_dependencies()

    # Test 2: Feature initialization
    manager = test_feature_initialization()
    if not manager:
        print("\n❌ Cannot proceed - initialization failed")
        return

    # Test 3: Databases
    test_databases()

    # Test 4: API calls
    if not test_feature_apis():
        print("\n⚠️  Some API tests failed, but features might still work")

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    print("✅ Basic tests completed")
    print("\nTo test with Telegram connection, run:")
    print("  python test_advanced_features.py --telegram")
    print("\nOr integrate with your main bot using:")
    print("  from advanced_features_manager import get_features_manager")
    print("  features = get_features_manager()")
    print("=" * 60)


if __name__ == "__main__":
    if "--telegram" in sys.argv:
        # Interactive Telegram test
        print("Telegram Integration Test")
        api_id = input("API ID: ")
        api_hash = input("API Hash: ")
        phone = input("Phone: ")
        asyncio.run(test_with_telegram(api_id, api_hash, phone))
    else:
        # Basic tests only
        main()
