#!/usr/bin/env python3
"""Discord Server Management CLI.

Non-interactive commands for managing your Discord server.
Usage: python manage_server.py <command> [options]

Commands:
  info                    - Show server information
  channels                - List all channels
  roles                   - List all roles
  members [--limit N]     - List members
  create-channel <name> [--category CAT] [--topic TOPIC]
  create-voice <name> [--category CAT]
  create-role <name> [--color HEX] [--hoist]
  delete-channel <name>
  delete-role <name>
  send <channel> <message>
  export [--output FILE]
  setup-standard          - Create standard server structure
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from dotenv import load_dotenv


async def main():
    # Load environment
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    
    parser = argparse.ArgumentParser(description="Discord Server Management CLI")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Info command
    subparsers.add_parser("info", help="Show server information")
    
    # List commands
    subparsers.add_parser("channels", help="List all channels")
    subparsers.add_parser("roles", help="List all roles")
    
    members_parser = subparsers.add_parser("members", help="List members")
    members_parser.add_argument("--limit", type=int, default=100, help="Max members to fetch")
    
    # Create commands
    create_channel = subparsers.add_parser("create-channel", help="Create a text channel")
    create_channel.add_argument("name", help="Channel name")
    create_channel.add_argument("--category", "-c", help="Category name")
    create_channel.add_argument("--topic", "-t", help="Channel topic")
    create_channel.add_argument("--slowmode", "-s", type=int, default=0, help="Slowmode seconds")
    
    create_voice = subparsers.add_parser("create-voice", help="Create a voice channel")
    create_voice.add_argument("name", help="Channel name")
    create_voice.add_argument("--category", "-c", help="Category name")
    create_voice.add_argument("--limit", type=int, default=0, help="User limit")
    
    create_category = subparsers.add_parser("create-category", help="Create a category")
    create_category.add_argument("name", help="Category name")
    
    create_role = subparsers.add_parser("create-role", help="Create a role")
    create_role.add_argument("name", help="Role name")
    create_role.add_argument("--color", help="Hex color (e.g., #ff0000)")
    create_role.add_argument("--hoist", action="store_true", help="Display separately")
    create_role.add_argument("--mentionable", action="store_true", help="Allow mentions")
    
    # Delete commands
    delete_channel = subparsers.add_parser("delete-channel", help="Delete a channel")
    delete_channel.add_argument("name", help="Channel name")
    
    delete_role = subparsers.add_parser("delete-role", help="Delete a role")
    delete_role.add_argument("name", help="Role name")
    
    # Message commands
    send_parser = subparsers.add_parser("send", help="Send a message")
    send_parser.add_argument("channel", help="Channel name")
    send_parser.add_argument("message", help="Message content")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export server structure")
    export_parser.add_argument("--output", "-o", default="server_export.json", help="Output file")
    
    # Setup command
    subparsers.add_parser("setup-standard", help="Set up standard server structure")
    
    # Edit channel
    edit_channel = subparsers.add_parser("edit-channel", help="Edit a channel")
    edit_channel.add_argument("name", help="Channel name")
    edit_channel.add_argument("--new-name", help="New channel name")
    edit_channel.add_argument("--topic", help="New topic")
    edit_channel.add_argument("--slowmode", type=int, help="Slowmode seconds")
    
    # Purge messages
    purge_parser = subparsers.add_parser("purge", help="Purge messages from channel")
    purge_parser.add_argument("channel", help="Channel name")
    purge_parser.add_argument("--limit", type=int, default=100, help="Number of messages")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    
    # Check environment
    token = os.environ.get("DISCORD_BOT_TOKEN")
    guild_id = os.environ.get("DISCORD_GUILD_ID")
    
    if not token or not guild_id:
        print("Error: DISCORD_BOT_TOKEN and DISCORD_GUILD_ID must be set")
        print("Run 'python setup_discord.py' to configure, or set environment variables")
        sys.exit(1)
    
    # Import after env is loaded
    from discord_ai_photo_bot.server_manager import DiscordServerManager, ServerConfig
    
    config = ServerConfig(token=token, guild_id=int(guild_id))
    manager = DiscordServerManager(config)
    
    print("Connecting to Discord...", file=sys.stderr)
    await manager.connect()
    print(f"Connected to: {manager.guild.name}", file=sys.stderr)
    
    try:
        # Execute command
        if args.command == "info":
            info = await manager.get_server_info()
            print(json.dumps(info, indent=2))
            
        elif args.command == "channels":
            channels = await manager.list_channels()
            for ch in channels:
                cat = f" [{ch.get('category', 'No Category')}]" if ch.get('category') else ""
                print(f"{ch['type']:15} | {ch['name']}{cat}")
                
        elif args.command == "roles":
            roles = await manager.list_roles()
            for role in roles:
                print(f"{role['position']:3} | {role['name']:20} | {role['color']}")
                
        elif args.command == "members":
            members = await manager.list_members(limit=args.limit)
            for m in members:
                roles = ", ".join(m["roles"]) if m["roles"] else "None"
                bot_tag = " [BOT]" if m["bot"] else ""
                print(f"{m['name']}{bot_tag} - Roles: {roles}")
                
        elif args.command == "create-channel":
            channel = await manager.create_text_channel(
                name=args.name,
                category=args.category,
                topic=args.topic,
                slowmode=args.slowmode,
            )
            print(f"Created text channel: #{channel.name} (ID: {channel.id})")
            
        elif args.command == "create-voice":
            channel = await manager.create_voice_channel(
                name=args.name,
                category=args.category,
                user_limit=args.limit,
            )
            print(f"Created voice channel: 🔊 {channel.name} (ID: {channel.id})")
            
        elif args.command == "create-category":
            category = await manager.create_category(name=args.name)
            print(f"Created category: {category.name} (ID: {category.id})")
            
        elif args.command == "create-role":
            role = await manager.create_role(
                name=args.name,
                color=args.color,
                hoist=args.hoist,
                mentionable=args.mentionable,
            )
            print(f"Created role: @{role.name} (ID: {role.id})")
            
        elif args.command == "delete-channel":
            success = await manager.delete_channel(args.name)
            if success:
                print(f"Deleted channel: {args.name}")
            else:
                print(f"Channel not found: {args.name}")
                sys.exit(1)
                
        elif args.command == "delete-role":
            success = await manager.delete_role(args.name)
            if success:
                print(f"Deleted role: {args.name}")
            else:
                print(f"Role not found: {args.name}")
                sys.exit(1)
                
        elif args.command == "send":
            message = await manager.send_message(args.channel, args.message)
            if message:
                print(f"Sent message to #{args.channel} (ID: {message.id})")
            else:
                print(f"Channel not found: {args.channel}")
                sys.exit(1)
                
        elif args.command == "export":
            await manager.export_server_structure(args.output)
            print(f"Exported server structure to: {args.output}")
            
        elif args.command == "setup-standard":
            print("Setting up standard server structure...")
            result = await manager.setup_standard_server()
            print(f"\nCreated:")
            print(f"  Categories: {', '.join(result['categories'])}")
            print(f"  Channels: {', '.join(result['channels'])}")
            print(f"  Roles: {', '.join(result['roles'])}")
            
        elif args.command == "edit-channel":
            channel = await manager.edit_channel(
                channel_name=args.name,
                new_name=args.new_name,
                topic=args.topic,
                slowmode=args.slowmode,
            )
            if channel:
                print(f"Edited channel: #{channel.name}")
            else:
                print(f"Channel not found: {args.name}")
                sys.exit(1)
                
        elif args.command == "purge":
            count = await manager.purge_channel(args.channel, args.limit)
            print(f"Purged {count} messages from #{args.channel}")
            
    finally:
        await manager.disconnect()


if __name__ == "__main__":
    asyncio.run(main())









