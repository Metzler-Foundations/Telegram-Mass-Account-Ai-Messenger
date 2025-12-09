#!/usr/bin/env python3
"""
Test script to verify Telegram authentication works
"""

import asyncio
import os
import sys

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram.telegram_client import TelegramClient


async def test_auth():
    """Test Telegram authentication"""
    print("🔍 Testing Telegram Authentication")
    print("=" * 50)

    # Check if credentials are provided
    if len(sys.argv) != 4:
        print("❌ Usage: python test_auth.py <api_id> <api_hash> <phone_number>")
        print("📝 Get credentials from: https://my.telegram.org")
        print("\nExample:")
        print("python test_auth.py 12345678 abc123def456 +1234567890")
        return

    api_id, api_hash, phone = sys.argv[1], sys.argv[2], sys.argv[3]

    print(f"📱 Phone: {phone}")
    print(f"🔑 API ID: {api_id}")
    print(f"🔐 API Hash: {api_hash[:8]}...")
    print("\n🔄 Connecting to Telegram...")

    # Create client
    client = TelegramClient(api_id, api_hash, phone)

    try:
        # Try to initialize (this will trigger authentication)
        success = await client.initialize()

        if success:
            print("✅ SUCCESS: Authenticated with Telegram!")
            print("📨 The client is now logged in and can receive/send messages")
            print("🤖 Auto-reply functionality is ready")

            # Keep it running briefly to show it's connected
            print("\n⏳ Client is running... (Ctrl+C to stop)")
            await client.run_forever()
        else:
            print("❌ FAILED: Could not authenticate")
            print("💡 Check your credentials and try again")

    except KeyboardInterrupt:
        print("\n👋 Stopped by user")
    except Exception as e:
        print(f"❌ ERROR: {e}")
    finally:
        await client.stop()


if __name__ == "__main__":
    asyncio.run(test_auth())
