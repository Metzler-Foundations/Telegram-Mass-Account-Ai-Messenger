#!/usr/bin/env python3
"""
Quick Connection Test Script for Discord AI Photo Bot

Usage:
    1. Set your environment variables:
       export DISCORD_BOT_TOKEN="your_token_here"
       export DISCORD_GUILD_ID="your_guild_id_here"
       export REPLICATE_API_TOKEN="your_replicate_token_here"
       export REPLICATE_DESTINATION_OWNER="your_username_here"
    
    2. Run this script:
       python test_connections.py
"""

import asyncio
import os
import sys

def test_environment_variables():
    """Check if required environment variables are set."""
    print("\n🔍 Checking Environment Variables...")
    
    required = {
        "DISCORD_BOT_TOKEN": os.environ.get("DISCORD_BOT_TOKEN", ""),
        "DISCORD_GUILD_ID": os.environ.get("DISCORD_GUILD_ID", ""),
        "REPLICATE_API_TOKEN": os.environ.get("REPLICATE_API_TOKEN", ""),
        "REPLICATE_DESTINATION_OWNER": os.environ.get("REPLICATE_DESTINATION_OWNER", ""),
    }
    
    all_set = True
    for key, value in required.items():
        if value and value not in ["", "your_token_here", "your_guild_id_here", "your_replicate_token_here", "your_username_here"]:
            # Mask the value for security
            masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
            print(f"  ✅ {key}: {masked}")
        else:
            print(f"  ❌ {key}: NOT SET or placeholder")
            all_set = False
    
    return all_set, required


async def test_discord_connection(token: str, guild_id: str):
    """Test Discord bot connection."""
    print("\n🔍 Testing Discord Connection...")
    
    if not token:
        print("  ❌ No Discord token provided")
        return False
    
    try:
        import discord
        
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        connected = asyncio.Event()
        result = {"success": False, "message": ""}
        
        @client.event
        async def on_ready():
            result["success"] = True
            result["message"] = f"Connected as {client.user} (ID: {client.user.id})"
            result["guilds"] = len(client.guilds)
            
            # Check if we can access the target guild
            target_guild = client.get_guild(int(guild_id)) if guild_id else None
            if target_guild:
                result["target_guild"] = target_guild.name
            
            connected.set()
        
        @client.event
        async def on_error(event, *args, **kwargs):
            result["message"] = f"Error in {event}"
            connected.set()
        
        # Start bot with timeout
        async def run_with_timeout():
            try:
                await asyncio.wait_for(client.start(token), timeout=15)
            except asyncio.TimeoutError:
                pass
            except discord.LoginFailure as e:
                result["message"] = f"Login failed: {e}"
                connected.set()
            except Exception as e:
                result["message"] = f"Error: {e}"
                connected.set()
        
        # Run in background
        task = asyncio.create_task(run_with_timeout())
        
        # Wait for connection or timeout
        try:
            await asyncio.wait_for(connected.wait(), timeout=20)
        except asyncio.TimeoutError:
            result["message"] = "Connection timeout"
        
        # Close the client
        await client.close()
        
        if result["success"]:
            print(f"  ✅ {result['message']}")
            print(f"  ✅ Connected to {result.get('guilds', 0)} guild(s)")
            if "target_guild" in result:
                print(f"  ✅ Target guild found: {result['target_guild']}")
            else:
                print(f"  ⚠️  Target guild {guild_id} not found (bot may not be invited)")
            return True
        else:
            print(f"  ❌ {result['message']}")
            return False
            
    except ImportError:
        print("  ❌ discord.py not installed. Run: pip install discord.py")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def test_replicate_connection(token: str, owner: str):
    """Test Replicate API connection."""
    print("\n🔍 Testing Replicate Connection...")
    
    if not token:
        print("  ❌ No Replicate token provided")
        return False
    
    try:
        import replicate
        
        client = replicate.Client(api_token=token)
        
        # Test by getting account info
        try:
            # Try to list models (simple API call)
            models = client.models.list()
            # Just check if we can iterate (don't need to fetch all)
            first_model = next(iter(models), None)
            print(f"  ✅ Replicate API connected successfully")
            print(f"  ✅ Destination owner: {owner}")
            return True
        except replicate.exceptions.ReplicateError as e:
            print(f"  ❌ Replicate API error: {e}")
            return False
            
    except ImportError:
        print("  ❌ replicate not installed. Run: pip install replicate")
        return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


async def main():
    print("=" * 60)
    print("  Discord AI Photo Bot - Connection Test")
    print("=" * 60)
    
    # Check environment variables
    env_ok, env_vars = test_environment_variables()
    
    if not env_ok:
        print("\n⚠️  Some environment variables are missing!")
        print("Set them with:")
        print('  export DISCORD_BOT_TOKEN="your_token"')
        print('  export DISCORD_GUILD_ID="your_guild_id"')
        print('  export REPLICATE_API_TOKEN="your_replicate_token"')
        print('  export REPLICATE_DESTINATION_OWNER="your_username"')
        print("\nContinuing with available values...\n")
    
    results = []
    
    # Test Discord
    discord_ok = await test_discord_connection(
        env_vars["DISCORD_BOT_TOKEN"],
        env_vars["DISCORD_GUILD_ID"]
    )
    results.append(("Discord Bot", discord_ok))
    
    # Test Replicate
    replicate_ok = await test_replicate_connection(
        env_vars["REPLICATE_API_TOKEN"],
        env_vars["REPLICATE_DESTINATION_OWNER"]
    )
    results.append(("Replicate API", replicate_ok))
    
    # Summary
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    
    if all_passed:
        print("🎉 All connections successful!")
        print("\nYour bot is ready to deploy to Railway.")
        print("Next steps:")
        print("1. Ensure these same variables are set in Railway")
        print("2. Deploy with: railway up")
        print("3. Test /studio command in Discord")
    else:
        print("❌ Some connections failed.")
        print("Please fix the issues above before deploying.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))