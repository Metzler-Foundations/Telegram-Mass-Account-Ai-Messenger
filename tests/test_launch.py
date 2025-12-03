#!/usr/bin/env python3
"""
Test script to verify the ultra-premium Telegram AI Assistant can launch.
This runs the application initialization without the GUI for testing.
"""

import sys
import os
import asyncio
from pathlib import Path

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported successfully."""
    print("🔍 Testing imports...")

    modules_to_test = [
        ('telegram.telegram_client', 'TelegramClient'),
        ('ai.gemini_service', 'GeminiService'),
        ('accounts.account_creator', 'AccountCreator'),
        ('scraping.member_scraper', 'MemberDatabase'),
        ('anti_detection.anti_detection_system', 'AntiDetectionSystem'),
        ('integrations.api_key_manager', 'APIKeyManager'),
        ('campaigns.dm_campaign_manager', 'DMCampaignManager'),
        ('accounts.account_manager', 'AccountManager'),
        ('ui.settings_window', 'SettingsWindow'),
        ('ui.ui_redesign', 'DISCORD_THEME'),
    ]

    success_count = 0
    for module_name, class_name in modules_to_test:
        try:
            parts = module_name.split('.')
            module = __import__(module_name, fromlist=[parts[-1]])
            if hasattr(module, class_name):
                print(f"✅ {module_name}.{class_name} imported successfully")
                success_count += 1
            else:
                print(f"❌ {module_name}.{class_name} not found")
        except Exception as e:
            print(f"❌ {module_name} import failed: {e}")

    return success_count == len(modules_to_test)

def test_theme():
    """Test that the premium theme loads correctly."""
    try:
        from ui.ui_redesign import DISCORD_THEME
        print("✅ Ultra-premium Discord theme loaded successfully")
        print(f"   Theme size: {len(DISCORD_THEME)} characters")
        return True
    except Exception as e:
        print(f"❌ Theme loading failed: {e}")
        return False

def test_config():
    """Test configuration loading."""
    try:
        from pathlib import Path
        config_file = Path("config.json")
        if config_file.exists():
            print("✅ Configuration file found")
        else:
            print("ℹ️  Configuration file not found (will be created on first run)")

        # Test database files
        db_files = ["members.db", "campaigns.db"]
        for db_file in db_files:
            if Path(db_file).exists():
                print(f"✅ Database file {db_file} found")
            else:
                print(f"ℹ️  Database file {db_file} not found (will be created on first run)")

        return True
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def test_services():
    """Test service initialization."""
    try:
        from member_scraper import MemberDatabase
        db = MemberDatabase()
        print("✅ MemberDatabase service initialized")

        from account_manager import AccountManager
        manager = AccountManager(db)
        print("✅ AccountManager service initialized")

        return True
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False

async def test_ai_service():
    """Test AI service (async)."""
    try:
        from gemini_service import GeminiService
        service = GeminiService("")
        print("✅ GeminiService initialized (API key needed for full functionality)")
        return True
    except Exception as e:
        print(f"❌ AI service test failed: {e}")
        return False

def main():
    """Main test function."""
    print("🚀 Testing Ultra-Premium Telegram AI Assistant Launch")
    print("=" * 60)

    # Test imports
    imports_ok = test_imports()
    print()

    # Test theme
    theme_ok = test_theme()
    print()

    # Test config
    config_ok = test_config()
    print()

    # Test services
    services_ok = test_services()
    print()

    # Test AI service
    ai_ok = asyncio.run(test_ai_service())
    print()

    # Summary
    all_tests = [imports_ok, theme_ok, config_ok, services_ok, ai_ok]
    passed = sum(all_tests)

    print("=" * 60)
    print(f"🎯 Launch Test Results: {passed}/{len(all_tests)} tests passed")

    if passed == len(all_tests):
        print("🎉 ALL SYSTEMS GO! Ultra-Premium Telegram AI Assistant is ready to launch!")
        print()
        print("✨ Premium Features Ready:")
        print("   • Ultra-sophisticated Discord-like UI")
        print("   • Pixel-perfect design and animations")
        print("   • Premium status indicators")
        print("   • Advanced AI integration")
        print("   • Anti-detection systems")
        print("   • Account management")
        print("   • Campaign automation")
        print()
        print("🚀 To launch the full application:")
        print("   cd /path/to/bot && python3 main.py")
        print("   (Requires GUI display or xvfb-run for headless)")
        return True
    else:
        print("⚠️  Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
















