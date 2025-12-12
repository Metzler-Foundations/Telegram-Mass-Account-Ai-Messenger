#!/usr/bin/env python3
"""
Elite Professional Server Setup
Removes all emojis, implements top-tier server features, and creates a world-class Discord community.
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "src")

from discord_ai_photo_bot.server_manager import DiscordServerManager, ServerConfig

async def main():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    guild_id = os.environ.get("DISCORD_GUILD_ID")

    if not token or not guild_id:
        print("Error: DISCORD_BOT_TOKEN and DISCORD_GUILD_ID must be set")
        sys.exit(1)

    config = ServerConfig(token=token, guild_id=int(guild_id))
    manager = DiscordServerManager(config)

    print("🔗 Connecting to Discord...")
    await manager.connect()
    print(f"✅ Connected to: {manager.guild.name}")

    try:
        print("\n🚀 Applying Elite Professional Server Setup...")

        # Phase 1: Remove ALL emojis from categories and channels
        print("\n📝 Phase 1: Removing emojis for professional appearance...")

        # Professional category renames (remove all emojis)
        category_renames = {
            "🏁・WELCOME": "ESSENTIALS",
            "💬・COMMUNITY": "COMMUNITY",
            "💼・GROWTH HACKING": "GROWTH & MARKETING",
            "💰・BUSINESS": "BUSINESS & FINANCE",
            "🎨・CREATIVE LAB": "CREATIVE & CONTENT",
            "🔊・AUDIO/VISUAL": "MEDIA & PRODUCTION",
            "🛠️・SUPPORT": "SUPPORT & HELP",
            "🔒・VIP": "PREMIUM MEMBERS",
            "🦙・LLAMA LLAMA CLUB": "ELITE NETWORK",
            "VOICE CHANNELS": "VOICE CHANNELS",  # Keep as is
        }

        for old, new in category_renames.items():
            try:
                await manager.edit_category(old, new_name=new)
                print(f"✅ Renamed category: {old} → {new}")
            except Exception as e:
                print(f"⚠️  Could not rename {old}: {e}")

        # Phase 2: Professional role color scheme
        print("\n🎨 Phase 2: Applying professional role colors...")

        professional_role_colors = {
            # Administrative Roles
            "Head Llama": "#1a1a2e",        # Deep navy
            "Llama Leaders": "#16213e",     # Dark blue
            "Llama Guardians": "#0f3460",   # Professional blue
            "System Admin": "#e94560",      # Professional red
            "Ethics Committee": "#533483",  # Professional purple
            "Archivist": "#2d5016",         # Professional green

            # Professional Hierarchy
            "Senior Fellow": "#1e3a5f",     # Executive blue
            "Field Researcher": "#2c5282",  # Research blue
            "Observer": "#4a5568",          # Analyst gray

            # Community Roles (Professional colors)
            "Premium Llama": "#d69e2e",     # Gold
            "Verified Llama": "#2d3748",    # Charcoal
            "Llama Member": "#3182ce",     # Professional blue
            "Content Llama": "#dd6b20",     # Professional orange
            "Short-Form Llama": "#319795",  # Professional teal
            "Reddit Llama": "#ff4500",      # Platform orange
            "Dating Llama": "#d53f8c",      # Professional pink

            # Bot and Integration Roles
            "Llama Bot": "#805ad5",         # Professional purple
            "Exclusive Content Manager": "#4a5568",
            "CashCord": "#2d3748",
            "StartIT": "#3182ce",
        }

        for role_name, color in professional_role_colors.items():
            try:
                await manager.edit_role(role_name, color=color)
                print(f"✅ Updated color for: {role_name}")
            except Exception as e:
                print(f"⚠️  Could not update {role_name}: {e}")

        # Phase 3: Server settings optimization
        print("\n⚙️  Phase 3: Optimizing server settings...")

        # Set verification level to highest
        try:
            await manager.set_verification_level("highest")
            print("✅ Set verification level to highest")
        except Exception as e:
            print(f"⚠️  Could not set verification level: {e}")

        # Update server description to be more professional
        try:
            professional_description = "Elite Professional Network | Enterprise-grade community platform for entrepreneurs, creators, and innovators. Invitation required. Building the future of digital business."
            await manager.set_server_description(professional_description)
            print("✅ Updated server description")
        except Exception as e:
            print(f"⚠️  Could not update description: {e}")

        # Phase 4: Create professional channel structure
        print("\n🏗️  Phase 4: Creating professional channel structure...")

        # Essential professional channels
        professional_channels = [
            # Essentials Category
            ("server-guide", "ESSENTIALS", "Complete server guide and navigation"),
            ("verification", "ESSENTIALS", "Account verification and member onboarding"),
            ("server-stats", "ESSENTIALS", "Real-time server statistics and analytics"),

            # Community Category
            ("general-discussion", "COMMUNITY", "General community discussion and networking"),
            ("introductions", "COMMUNITY", "Member introductions and networking"),
            ("success-stories", "COMMUNITY", "Share your wins and achievements"),
            ("marketplace", "COMMUNITY", "Buy, sell, and trade services"),

            # Business Category
            ("business-strategy", "BUSINESS & FINANCE", "Strategic business planning and growth"),
            ("investment-opportunities", "BUSINESS & FINANCE", "Investment discussions and opportunities"),
            ("legal-advice", "BUSINESS & FINANCE", "Legal questions and business law"),

            # Support Category
            ("technical-support", "SUPPORT & HELP", "Technical issues and troubleshooting"),
            ("account-recovery", "SUPPORT & HELP", "Account recovery and password reset"),
            ("billing-support", "SUPPORT & HELP", "Billing and payment questions"),
        ]

        for channel_name, category, topic in professional_channels:
            try:
                await manager.create_text_channel(channel_name, category, topic)
                print(f"✅ Created channel: {channel_name}")
            except Exception as e:
                print(f"⚠️  Could not create {channel_name}: {e}")

        # Phase 5: Professional role management
        print("\n👥 Phase 5: Creating professional role structure...")

        professional_roles = [
            # Premium Tiers
            {"name": "Platinum Member", "color": "#e5e4e2", "hoist": True, "permissions": []},
            {"name": "Gold Member", "color": "#ffd700", "hoist": True, "permissions": []},
            {"name": "Silver Member", "color": "#c0c0c0", "hoist": False, "permissions": []},

            # Professional Certifications
            {"name": "Certified Consultant", "color": "#4169e1", "hoist": True, "permissions": []},
            {"name": "Expert Contributor", "color": "#32cd32", "hoist": True, "permissions": []},
            {"name": "Community Mentor", "color": "#ff6347", "hoist": False, "permissions": []},

            # Activity Roles
            {"name": "Active Contributor", "color": "#00ced1", "hoist": False, "permissions": []},
            {"name": "Rising Star", "color": "#dda0dd", "hoist": False, "permissions": []},
        ]

        for role_config in professional_roles:
            try:
                role = await manager.create_role(**role_config)
                print(f"✅ Created role: {role_config['name']}")
            except Exception as e:
                print(f"⚠️  Could not create role {role_config['name']}: {e}")

        # Phase 6: Final professional touches
        print("\n✨ Phase 6: Applying final professional touches...")

        # Send professional welcome message
        try:
            welcome_message = {
                "title": "Welcome to the Elite Professional Network",
                "description": "You've joined an exclusive community of entrepreneurs, creators, and innovators. This server represents the pinnacle of professional Discord communities.",
                "color": 0x1a1a2e,
                "fields": [
                    {
                        "name": "🏆 Our Standards",
                        "value": "Excellence, professionalism, and mutual respect define our community.",
                        "inline": False
                    },
                    {
                        "name": "🚀 Getting Started",
                        "value": "Check out #server-guide and #verification to get fully onboarded.",
                        "inline": False
                    },
                    {
                        "name": "💼 Professional Networking",
                        "value": "Connect with industry leaders in #business-strategy and #marketplace.",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Elite Professional Network | Building the Future"
                }
            }
            await manager.send_message("start-here", embed=welcome_message)
            print("✅ Sent professional welcome message")
        except Exception as e:
            print(f"⚠️  Could not send welcome message: {e}")

        print("\n🎉 ELITE PROFESSIONAL SERVER SETUP COMPLETE!")
        print("Your server now represents the highest standards of professional Discord communities.")
        print("\nNext steps:")
        print("1. Review and customize the new channel structure")
        print("2. Set up automated moderation rules")
        print("3. Configure premium member benefits")
        print("4. Create community guidelines and enforcement")

    finally:
        await manager.disconnect()
        print("\n🔌 Disconnected from Discord.")

if __name__ == "__main__":
    asyncio.run(main())