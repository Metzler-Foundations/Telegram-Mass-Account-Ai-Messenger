#!/usr/bin/env python3
"""
Test script to verify official Telegram API credentials work
"""

import asyncio
import sys
import os

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.telegram_client import TelegramClient
from ai.gemini_service import GeminiService


async def test_official_api():
    """Test connection with Telegram API credentials from environment"""
    import os

    print("🧪 Testing Telegram API Credentials")
    print("=" * 50)

    # Get API credentials from environment variables (REQUIRED)
    API_ID = os.getenv("TELEGRAM_API_ID", "")
    API_HASH = os.getenv("TELEGRAM_API_HASH", "")

    if not API_ID or not API_HASH:
        print("❌ Error: TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables are required")
        print("📝 Set them before running:")
        print("   export TELEGRAM_API_ID='your_api_id'")
        print("   export TELEGRAM_API_HASH='your_api_hash'")
        print("🔗 Get credentials from: https://my.telegram.org/apps")
        return

    # Check if phone number is provided
    if len(sys.argv) != 2:
        print("❌ Usage: python test_official_api.py <phone_number>")
        print("📱 Example: python test_official_api.py +1234567890")
        return

    phone = sys.argv[1]

    print(f"📱 Phone: {phone}")
    print(f"🔑 API ID: {API_ID[:4]}*** (from env)")
    print(f"🔐 API Hash: {API_HASH[:8]}*** (from env)")
    print("\n🚀 Connecting to Telegram...")
    print("📋 Using credentials from environment variables...")

    # Create client with credentials from environment
    client = TelegramClient(API_ID, API_HASH, phone)

    try:
        # Try to initialize (this will trigger authentication)
        success = await client.initialize()
        if success:
            print("✅ SUCCESS: Connected with official Telegram API!")
            print("📱 This client appears identical to official Telegram Desktop")
            print("🤖 Ready for AI auto-reply functionality")

            # Keep it running briefly
            print("\n⏳ Client active... (Ctrl+C to stop)")
            await client.run_forever()
        else:
            print("❌ Authentication failed - check your phone number")

    except KeyboardInterrupt:
        print("\n👋 Stopped by user")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(test_official_api())
