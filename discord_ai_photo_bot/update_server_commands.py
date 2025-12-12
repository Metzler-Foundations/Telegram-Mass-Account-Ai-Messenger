#!/usr/bin/env python3
"""Update Discord server with command documentation.

This script posts/updates command documentation in the server channels:
- #club-info: Full command reference
- #photo-generation: Studio guide (already handled by bot)

Usage:
    cd discord_ai_photo_bot
    PYTHONPATH=./src python update_server_commands.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import discord
from dotenv import load_dotenv


# Load environment
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


COMMANDS_EMBED = discord.Embed(
    title="🤖 Bot Commands Reference",
    description=(
        "**Welcome to the AI Photo Studio!**\n\n"
        "This bot creates photorealistic AI photos from your reference images using "
        "advanced LoRA training technology.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    ),
    color=discord.Color.from_rgb(138, 43, 226),  # Purple
)

COMMANDS_EMBED.add_field(
    name="📸 `/studio`",
    value=(
        "**Start a premium photo studio session**\n"
        "• Creates a private thread for your session\n"
        "• Upload 8-20 reference photos\n"
        "• AI trains a custom model on your photos\n"
        "• Generates 40 photorealistic images\n"
        "• Delivers ZIP via DM\n\n"
        "**Where:** `#photo-generation` channel only\n"
        "**Time:** Training ~5-15 min, Generation ~5-10 min"
    ),
    inline=False,
)

COMMANDS_EMBED.add_field(
    name="❓ `/help`",
    value=(
        "**Show the quickstart guide**\n"
        "• Step-by-step instructions\n"
        "• Best practices for reference photos\n"
        "• Tips for best results\n\n"
        "**Where:** Any channel"
    ),
    inline=False,
)

COMMANDS_EMBED.add_field(
    name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    value="**📋 How `/studio` Works**",
    inline=False,
)

COMMANDS_EMBED.add_field(
    name="Step 1: Start Session",
    value="Run `/studio` in `#photo-generation`\nBot creates a private thread",
    inline=True,
)

COMMANDS_EMBED.add_field(
    name="Step 2: Upload Photos",
    value="Upload 8-20 clear photos\nSame person, different angles",
    inline=True,
)

COMMANDS_EMBED.add_field(
    name="Step 3: Train Model",
    value="Click 'Finish uploads'\nAI trains on your photos",
    inline=True,
)

COMMANDS_EMBED.add_field(
    name="Step 4: Generate Pack",
    value="Click 'Generate pack (40)'\nAI creates 40 new photos",
    inline=True,
)

COMMANDS_EMBED.add_field(
    name="Step 5: Receive ZIP",
    value="Photos delivered via DM\nDownload your pack!",
    inline=True,
)

COMMANDS_EMBED.add_field(
    name="⚡ Quick Tips",
    value="Use high-quality photos",
    inline=True,
)

COMMANDS_EMBED.add_field(
    name="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    value="**📷 Best Reference Photos**",
    inline=False,
)

COMMANDS_EMBED.add_field(
    name="✅ DO",
    value=(
        "• Clear, well-lit photos\n"
        "• Face visible in all shots\n"
        "• Multiple angles (front, side, 3/4)\n"
        "• Different expressions\n"
        "• Mix of close-up and mid-shot\n"
        "• Natural lighting preferred"
    ),
    inline=True,
)

COMMANDS_EMBED.add_field(
    name="❌ DON'T",
    value=(
        "• No heavy filters\n"
        "• No group photos\n"
        "• No blurry images\n"
        "• No extreme angles\n"
        "• No sunglasses/masks\n"
        "• No low resolution"
    ),
    inline=True,
)

COMMANDS_EMBED.set_footer(
    text="💡 Payments are currently disabled during testing • Studio mode is FREE"
)


WELCOME_EMBED = discord.Embed(
    title="🦙 Welcome to Llama Llama Club",
    description=(
        "**Your AI Photo Generation Hub**\n\n"
        "This is the premium section of the server where you can:\n\n"
        "🎨 **Create AI Photos** - Generate photorealistic images\n"
        "🤖 **Train Custom Models** - AI learns from your photos\n"
        "📦 **Get Photo Packs** - 40 images delivered via DM\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "**🚀 Get Started:**\n"
        "1. Go to `#photo-generation`\n"
        "2. Run `/studio`\n"
        "3. Follow the bot's instructions\n\n"
        "**📖 Need Help?**\n"
        "Run `/help` anywhere in the server"
    ),
    color=discord.Color.from_rgb(255, 107, 107),  # Coral
)

WELCOME_EMBED.add_field(
    name="📍 Channel Guide",
    value=(
        "`#photo-generation` - Start AI sessions here\n"
        "`#ai-model-creation` - Learn about AI models\n"
        "`#club-info` - Commands & documentation\n"
        "`#automation-bots` - Bot discussions"
    ),
    inline=False,
)


async def update_server():
    """Connect to Discord and update server channels."""
    token = os.environ.get("DISCORD_BOT_TOKEN")
    guild_id = os.environ.get("DISCORD_GUILD_ID")

    if not token or not guild_id:
        print("Error: DISCORD_BOT_TOKEN and DISCORD_GUILD_ID must be set")
        print("Run 'python setup_discord.py' to configure")
        sys.exit(1)

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f"Connected as {client.user}")

        guild = client.get_guild(int(guild_id))
        if not guild:
            print(f"Guild {guild_id} not found")
            await client.close()
            return

        print(f"Found guild: {guild.name}")

        # Find channels
        club_info_channel = discord.utils.get(guild.text_channels, name="📋・club-info")
        photo_gen_channel = discord.utils.get(guild.text_channels, name="photo-generation")

        # Update #club-info with commands reference
        if club_info_channel:
            print(f"Updating #{club_info_channel.name}...")

            # Check for existing bot messages
            bot_messages = []
            async for msg in club_info_channel.history(limit=50):
                if msg.author == client.user:
                    bot_messages.append(msg)

            # Delete old bot messages
            for msg in bot_messages:
                try:
                    await msg.delete()
                    print(f"  Deleted old message: {msg.id}")
                except Exception as e:
                    print(f"  Could not delete message: {e}")

            # Post new embeds
            await club_info_channel.send(embed=WELCOME_EMBED)
            print("  Posted welcome embed")

            await club_info_channel.send(embed=COMMANDS_EMBED)
            print("  Posted commands embed")

            # Try to pin the commands message
            async for msg in club_info_channel.history(limit=5):
                if msg.author == client.user and msg.embeds:
                    if msg.embeds[0].title == "🤖 Bot Commands Reference":
                        try:
                            await msg.pin()
                            print("  Pinned commands message")
                        except Exception as e:
                            print(f"  Could not pin: {e}")
                        break
        else:
            print("Channel #club-info not found")
            # Try alternative name
            club_info_channel = discord.utils.get(guild.text_channels, name="club-info")
            if club_info_channel:
                print(f"Found #{club_info_channel.name} (without emoji)")
                await club_info_channel.send(embed=WELCOME_EMBED)
                await club_info_channel.send(embed=COMMANDS_EMBED)
                print("  Posted embeds")

        # Check #photo-generation
        if photo_gen_channel:
            print(f"Found #{photo_gen_channel.name}")
            print("  (Studio guide is auto-posted by bot on startup)")
        else:
            print("Channel #photo-generation not found")

        print("\n✅ Server update complete!")
        print("\nNext steps:")
        print("1. Start the bot: PYTHONPATH=./src python -m discord_ai_photo_bot.bot")
        print("2. The bot will auto-post the studio guide in #photo-generation")
        print("3. Users can now see commands in #club-info")

        await client.close()

    await client.start(token)


if __name__ == "__main__":
    print("Discord Server Command Documentation Updater")
    print("=" * 50)
    asyncio.run(update_server())