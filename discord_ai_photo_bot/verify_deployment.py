#!/usr/bin/env python3
"""
🚀 Discord AI Photo Bot - Deployment Verification Script

This script verifies that all components are properly configured and working.
Run this after deployment to ensure everything is set up correctly.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def check_environment_variables():
    """Check all required environment variables."""
    print("🔍 Checking Environment Variables...")

    required_vars = [
        "DISCORD_BOT_TOKEN",
        "DISCORD_GUILD_ID",
        "REPLICATE_API_TOKEN",
        "REPLICATE_DESTINATION_OWNER",
        "PYTHONPATH"
    ]

    missing = []
    for var in required_vars:
        if not os.environ.get(var):
            missing.append(var)
        else:
            print(f"  ✅ {var}: {'*' * len(os.environ[var][:10])}...")

    if missing:
        print(f"  ❌ Missing: {', '.join(missing)}")
        return False

    print("  ✅ All required environment variables present")
    return True

def check_imports():
    """Check that all required modules can be imported."""
    print("\n🔍 Checking Python Imports...")

    try:
        import discord
        print(f"  ✅ discord.py: {discord.__version__}")

        import replicate
        print(f"  ✅ replicate: {replicate.__version__}")

        import cv2
        print("  ✅ opencv-python-headless: OK"

        import PIL
        print(f"  ✅ pillow: {PIL.__version__}")

        from discord_ai_photo_bot.config import load_settings
        print("  ✅ Bot configuration: OK"

        return True
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False

async def check_discord_bot():
    """Check Discord bot connectivity."""
    print("\n🔍 Checking Discord Bot...")

    try:
        from discord_ai_photo_bot.config import load_settings
        settings = load_settings()

        import discord
        intents = discord.Intents.default()
        intents.message_content = True

        bot = discord.Client(intents=intents)

        @bot.event
        async def on_ready():
            print(f"  ✅ Bot connected as: {bot.user}")
            print(f"  ✅ Guilds: {len(bot.guilds)}")
            await bot.close()

        await bot.start(settings.discord_token)
        return True

    except Exception as e:
        print(f"  ❌ Discord bot error: {e}")
        return False

async def check_replicate_api():
    """Check Replicate API connectivity."""
    print("\n🔍 Checking Replicate API...")

    try:
        from discord_ai_photo_bot.config import load_settings
        settings = load_settings()

        import replicate
        client = replicate.Client(api_token=settings.replicate_token)

        # Test API access
        models = await client.models.async_list()
        print(f"  ✅ Replicate API: Connected (found {len(list(models))} models)")

        return True

    except Exception as e:
        print(f"  ❌ Replicate API error: {e}")
        return False

def check_database():
    """Check database connectivity."""
    print("\n🔍 Checking Database...")

    try:
        from discord_ai_photo_bot.database import Database
        from discord_ai_photo_bot.config import load_settings

        settings = load_settings()
        db = Database(settings.data_dir / "test.db")

        # Test basic operations
        db.ensure_user("test_user", "Test User")
        user = db._connect().execute("SELECT * FROM users WHERE user_id = ?", ("test_user",)).fetchone()

        if user:
            print("  ✅ Database: Connected and functional")
            return True
        else:
            print("  ❌ Database: Connection failed")
            return False

    except Exception as e:
        print(f"  ❌ Database error: {e}")
        return False

async def main():
    """Run all verification checks."""
    print("🚀 Discord AI Photo Bot - Deployment Verification")
    print("=" * 55)

    checks = [
        ("Environment Variables", check_environment_variables),
        ("Python Imports", check_imports),
        ("Database", check_database),
        ("Discord Bot", check_discord_bot),
        ("Replicate API", check_replicate_api),
    ]

    results = []
    for name, check_func in checks:
        try:
            if asyncio.iscoroutinefunction(check_func):
                result = await check_func()
            else:
                result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ {name}: Exception - {e}")
            results.append((name, False))

    print("\n" + "=" * 55)
    print("📊 VERIFICATION RESULTS:")

    all_passed = True
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
        if not result:
            all_passed = False

    print("\n" + "=" * 55)

    if all_passed:
        print("🎉 ALL CHECKS PASSED!")
        print("Your Discord AI Photo Bot is fully configured and ready to deploy.")
        print("\nNext steps:")
        print("1. Run: ./deploy_to_railway.sh")
        print("2. Or manually set variables in Railway dashboard")
        print("3. Push to trigger deployment")
        print("4. Test /help and /studio commands")
    else:
        print("❌ SOME CHECKS FAILED!")
        print("Please fix the failed checks before deploying.")
        print("See COMPREHENSIVE_SETUP.md for detailed instructions.")

    return all_passed

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)