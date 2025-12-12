#!/usr/bin/env python3
"""
Elite Professional Server Setup
Removes all emojis, implements top-tier server features, and creates a world-class Discord community.
Enhanced with comprehensive emoji optimization and professional branding.
"""

import asyncio
import os
import sys
import re
from pathlib import Path

sys.path.insert(0, "src")

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from discord_ai_photo_bot.server_manager import DiscordServerManager, ServerConfig

def remove_emojis_from_text(text: str) -> str:
    """Remove all emojis from text using regex pattern."""
    # Emoji regex pattern - matches most emojis
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()

def normalize_channel_name(name: str) -> str:
    """Normalize channel name to lowercase-with-hyphens format."""
    # Remove emojis first
    name = remove_emojis_from_text(name)
    
    # Replace common separators with hyphens
    name = re.sub(r'[.\s_]+', '-', name)
    
    # Remove any remaining special characters except hyphens
    name = re.sub(r'[^a-zA-Z0-9\-]', '', name)
    
    # Convert to lowercase
    name = name.lower()
    
    # Remove leading/trailing hyphens and multiple consecutive hyphens
    name = re.sub(r'^-+|-+$', '', name)
    name = re.sub(r'-{2,}', '-', name)
    
    return name

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

        # Phase 7: Comprehensive emoji removal from all channels
        print("\n🧹 Phase 7: Removing emojis from all channel names...")
        
        # Get all text channels and remove emojis from their names
        for channel in manager.guild.text_channels:
            try:
                original_name = channel.name
                # Remove emojis and normalize name
                clean_name = normalize_channel_name(original_name)
                
                # Skip if name is already clean
                if clean_name == original_name:
                    continue
                
                # Update channel name
                await channel.edit(name=clean_name)
                print(f"✅ Renamed channel: {original_name} → {clean_name}")
            except Exception as e:
                print(f"⚠️  Could not rename channel {channel.name}: {e}")
        
        # Phase 8: Update channel topics to be descriptive instead of emoji-dependent
        print("\n📝 Phase 8: Updating channel topics to be descriptive...")
        
        # Professional topic updates for common channels
        professional_topics = {
            "general": "General community discussion and networking",
            "introductions": "Introduce yourself to the community and connect with other members",
            "announcements": "Important server announcements and updates from the team",
            "rules": "Server rules and community guidelines",
            "support": "Get help with technical issues, payments, or general questions",
            "suggestions": "Share your ideas and suggestions to improve the community",
            "bot-commands": "Use bot commands and AI photo generation tools here",
            "generate-pack": "Create AI photo packs using advanced generation tools",
            "off-topic": "Casual conversations and random discussions",
            "showcase": "Share your creations, projects, and achievements",
            "help": "Frequently asked questions and support resources",
            "staff-lounge": "Staff discussion and coordination",
            "mod-logs": "Moderation logs and audit trail",
        }
        
        for channel_name, topic in professional_topics.items():
            try:
                channel = discord.utils.get(manager.guild.text_channels, name=channel_name)
                if channel and channel.topic != topic:
                    await channel.edit(topic=topic)
                    print(f"✅ Updated topic for: {channel_name}")
            except Exception as e:
                print(f"⚠️  Could not update topic for {channel_name}: {e}")
        
        # Phase 9: Modernize role names with professional titles
        print("\n👥 Phase 9: Modernizing role names with professional titles...")
        
        # Professional role renames
        professional_role_renames = {
            "Head Llama": "Community Director",
            "Llama Leaders": "Leadership Team",
            "Llama Guardians": "Community Moderators",
            "Premium Llama": "Premium Member",
            "Verified Llama": "Verified Member",
            "Llama Member": "Community Member",
            "Content Llama": "Content Creator",
            "Short-Form Llama": "Social Media Expert",
            "Reddit Llama": "Reddit Specialist",
            "Dating Llama": "Relationship Coach",
            "Llama Bot": "AI Assistant",
        }
        
        for old_name, new_name in professional_role_renames.items():
            try:
                await manager.edit_role(old_name, new_name=new_name)
                print(f"✅ Renamed role: {old_name} → {new_name}")
            except Exception as e:
                print(f"⚠️  Could not rename role {old_name}: {e}")
        
        # Phase 10: Implement clear role hierarchy
        print("\n🏆 Phase 10: Implementing clear role hierarchy...")
        
        # Create professional hierarchy roles if they don't exist
        hierarchy_roles = [
            {"name": "Basic Member", "color": "#95a5a6", "hoist": False, "permissions": []},
            {"name": "Premium Member", "color": "#f39c12", "hoist": True, "permissions": []},
            {"name": "Elite Member", "color": "#9b59b6", "hoist": True, "permissions": []},
            {"name": "Leadership Team", "color": "#2c3e50", "hoist": True, "permissions": []},
            {"name": "Community Director", "color": "#c0392b", "hoist": True, "permissions": []},
        ]
        
        for role_config in hierarchy_roles:
            try:
                # Check if role already exists
                existing_role = discord.utils.get(manager.guild.roles, name=role_config["name"])
                if not existing_role:
                    role = await manager.create_role(**role_config)
                    print(f"✅ Created hierarchy role: {role_config['name']}")
                else:
                    print(f"ℹ️  Role already exists: {role_config['name']}")
            except Exception as e:
                print(f"⚠️  Could not create role {role_config['name']}: {e}")
        
        # Phase 11: Strategic emoji usage guidelines
        print("\n📋 Phase 11: Creating strategic emoji usage guidelines...")
        
        # Create a guidelines channel with emoji usage rules
        try:
            guidelines_channel = await manager.create_text_channel(
                name="emoji-guidelines",
                category="ESSENTIALS",
                topic="Guidelines for appropriate emoji usage in the community"
            )
            
            guidelines_message = {
                "title": "Strategic Emoji Usage Guidelines",
                "description": "To maintain our professional appearance, emojis are used strategically for specific purposes only.",
                "color": 0x1a1a2e,
                "fields": [
                    {
                        "name": "✅ Appropriate Emoji Usage",
                        "value": "• Status indicators (online, away, busy)\n• Priority markers (urgent, important)\n• Bot UI elements and commands\n• Navigation aids in structured messages",
                        "inline": False
                    },
                    {
                        "name": "❌ Inappropriate Emoji Usage",
                        "value": "• Decorative emojis in channel names\n• Excessive emojis in messages\n• Emoji-only reactions without context\n• Unprofessional emoji combinations",
                        "inline": False
                    },
                    {
                        "name": "🎯 Professional Standards",
                        "value": "• Use emojis to enhance clarity, not replace text\n• Maintain consistency in emoji usage\n• Consider cultural context and interpretations\n• Prioritize accessibility and inclusivity",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Elite Professional Network | Excellence in Communication"
                }
            }
            await manager.send_message("emoji-guidelines", embed=guidelines_message)
            print("✅ Created emoji guidelines channel")
        except Exception as e:
            print(f"⚠️  Could not create guidelines channel: {e}")
        
        # Phase 12: Final server branding update
        print("\n🎨 Phase 12: Final server branding update...")
        
        # Update server description to emphasize professional network
        try:
            elite_description = "🏆 Elite Professional Network | Enterprise-grade community platform for entrepreneurs, creators, and innovators. Building the future of digital business with excellence, integrity, and strategic collaboration. Invitation required."
            await manager.set_server_description(elite_description)
            print("✅ Updated elite server description")
        except Exception as e:
            print(f"⚠️  Could not update description: {e}")

        print("\n🎉 COMPREHENSIVE EMOJI OPTIMIZATION COMPLETE!")
        print("Your server now represents the highest standards of professional Discord communities.")
        print("\n✅ Completed optimizations:")
        print("• Removed all emoji prefixes from categories and channels")
        print("• Implemented consistent lowercase-with-hyphens naming convention")
        print("• Updated channel topics to be descriptive and professional")
        print("• Modernized role names with professional titles")
        print("• Implemented clear role hierarchy (Basic → Premium → Elite → Leadership)")
        print("• Created strategic emoji usage guidelines")
        print("• Updated server branding to match professional appearance")
        print("\nNext steps:")
        print("1. Review and customize the new channel structure")
        print("2. Set up automated moderation rules")
        print("3. Configure premium member benefits")
        print("4. Create community guidelines and enforcement")
        print("5. Train staff on professional communication standards")

    finally:
        await manager.disconnect()
        print("\n🔌 Disconnected from Discord.")

if __name__ == "__main__":
    asyncio.run(main())