"""Discord Server Management Utility.

This module provides comprehensive tools for managing a Discord server,
including creating channels, roles, categories, setting permissions,
sending messages, and more.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import discord
from discord import (
    CategoryChannel,
    Guild,
    Member,
    PermissionOverwrite,
    Role,
    TextChannel,
    VoiceChannel,
)
from discord.ext import commands

logger = logging.getLogger(__name__)


@dataclass
class ServerConfig:
    """Configuration for server management."""
    
    token: str
    guild_id: int
    application_id: Optional[int] = None


class DiscordServerManager:
    """Comprehensive Discord server management utility."""

    def __init__(self, config: ServerConfig) -> None:
        self.config = config
        self._bot: Optional[commands.Bot] = None
        self._guild: Optional[Guild] = None
        self._ready = asyncio.Event()

    async def _setup_bot(self) -> commands.Bot:
        """Create and configure the bot instance."""
        intents = discord.Intents.default()
        intents.guilds = True
        intents.guild_messages = True
        intents.message_content = True
        intents.members = True

        bot = commands.Bot(command_prefix="!", intents=intents)

        @bot.event
        async def on_ready():
            logger.info(f"Bot connected as {bot.user}")
            self._guild = bot.get_guild(self.config.guild_id)
            if not self._guild:
                logger.error(f"Could not find guild {self.config.guild_id}")
            else:
                logger.info(f"Connected to guild: {self._guild.name}")
            self._ready.set()

        return bot

    async def connect(self) -> None:
        """Connect the bot to Discord."""
        self._bot = await self._setup_bot()
        asyncio.create_task(self._bot.start(self.config.token))
        await self._ready.wait()

    async def disconnect(self) -> None:
        """Disconnect the bot."""
        if self._bot:
            await self._bot.close()

    @property
    def guild(self) -> Guild:
        """Get the connected guild."""
        if not self._guild:
            raise RuntimeError("Not connected to a guild")
        return self._guild

    @property
    def bot(self) -> commands.Bot:
        """Get the bot instance."""
        if not self._bot:
            raise RuntimeError("Bot not initialized")
        return self._bot

    # ==================== Server Info ====================

    async def get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive information about the server."""
        guild = self.guild
        return {
            "id": guild.id,
            "name": guild.name,
            "description": guild.description,
            "member_count": guild.member_count,
            "owner_id": guild.owner_id,
            "created_at": guild.created_at.isoformat(),
            "icon_url": str(guild.icon.url) if guild.icon else None,
            "banner_url": str(guild.banner.url) if guild.banner else None,
            "boost_level": guild.premium_tier,
            "boost_count": guild.premium_subscription_count,
            "features": guild.features,
            "verification_level": str(guild.verification_level),
            "channels": {
                "text": len([c for c in guild.channels if isinstance(c, TextChannel)]),
                "voice": len([c for c in guild.channels if isinstance(c, VoiceChannel)]),
                "categories": len([c for c in guild.channels if isinstance(c, CategoryChannel)]),
            },
            "roles_count": len(guild.roles),
            "emojis_count": len(guild.emojis),
        }

    async def list_channels(self) -> List[Dict[str, Any]]:
        """List all channels in the server."""
        channels = []
        for channel in self.guild.channels:
            channel_info = {
                "id": channel.id,
                "name": channel.name,
                "type": str(channel.type),
                "position": channel.position,
            }
            if hasattr(channel, "category") and channel.category:
                channel_info["category"] = channel.category.name
            if hasattr(channel, "topic"):
                channel_info["topic"] = channel.topic
            channels.append(channel_info)
        return sorted(channels, key=lambda x: x["position"])

    async def list_roles(self) -> List[Dict[str, Any]]:
        """List all roles in the server."""
        return [
            {
                "id": role.id,
                "name": role.name,
                "color": str(role.color),
                "position": role.position,
                "mentionable": role.mentionable,
                "hoisted": role.hoist,
                "permissions": role.permissions.value,
            }
            for role in sorted(self.guild.roles, key=lambda r: r.position, reverse=True)
        ]

    async def list_members(self, limit: int = 100) -> List[Dict[str, Any]]:
        """List members in the server."""
        members = []
        # Fetch all members if needed (this may require privileged intents)
        if not self.guild.chunked:
            await self.guild.chunk()
        
        member_list = list(self.guild.members)[:limit]
        for member in member_list:
            members.append({
                "id": member.id,
                "name": member.name,
                "display_name": member.display_name,
                "discriminator": member.discriminator,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "roles": [role.name for role in member.roles if role.name != "@everyone"],
                "bot": member.bot,
            })
        return members

    # ==================== Channel Management ====================

    async def create_text_channel(
        self,
        name: str,
        category: Optional[str] = None,
        topic: Optional[str] = None,
        slowmode: int = 0,
        nsfw: bool = False,
        overwrites: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> TextChannel:
        """Create a new text channel."""
        guild = self.guild
        
        category_obj = None
        if category:
            category_obj = discord.utils.get(guild.categories, name=category)
            if not category_obj:
                category_obj = await guild.create_category(category)

        permission_overwrites = {}
        if overwrites:
            permission_overwrites = await self._build_overwrites(overwrites)

        channel = await guild.create_text_channel(
            name=name,
            category=category_obj,
            topic=topic,
            slowmode_delay=slowmode,
            nsfw=nsfw,
            overwrites=permission_overwrites,
        )
        logger.info(f"Created text channel: {channel.name}")
        return channel

    async def create_voice_channel(
        self,
        name: str,
        category: Optional[str] = None,
        user_limit: int = 0,
        bitrate: int = 64000,
        overwrites: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> VoiceChannel:
        """Create a new voice channel."""
        guild = self.guild
        
        category_obj = None
        if category:
            category_obj = discord.utils.get(guild.categories, name=category)
            if not category_obj:
                category_obj = await guild.create_category(category)

        permission_overwrites = {}
        if overwrites:
            permission_overwrites = await self._build_overwrites(overwrites)

        channel = await guild.create_voice_channel(
            name=name,
            category=category_obj,
            user_limit=user_limit,
            bitrate=bitrate,
            overwrites=permission_overwrites,
        )
        logger.info(f"Created voice channel: {channel.name}")
        return channel

    async def create_category(
        self,
        name: str,
        overwrites: Optional[Dict[str, Dict[str, bool]]] = None,
    ) -> CategoryChannel:
        """Create a new category."""
        permission_overwrites = {}
        if overwrites:
            permission_overwrites = await self._build_overwrites(overwrites)

        category = await self.guild.create_category(
            name=name,
            overwrites=permission_overwrites,
        )
        logger.info(f"Created category: {category.name}")
        return category

    async def delete_channel(self, channel_name: str) -> bool:
        """Delete a channel by name."""
        channel = discord.utils.get(self.guild.channels, name=channel_name)
        if channel:
            await channel.delete()
            logger.info(f"Deleted channel: {channel_name}")
            return True
        logger.warning(f"Channel not found: {channel_name}")
        return False

    async def edit_channel(
        self,
        channel_name: str,
        new_name: Optional[str] = None,
        topic: Optional[str] = None,
        slowmode: Optional[int] = None,
        nsfw: Optional[bool] = None,
    ) -> Optional[TextChannel]:
        """Edit a text channel's properties."""
        channel = discord.utils.get(self.guild.text_channels, name=channel_name)
        if not channel:
            logger.warning(f"Channel not found: {channel_name}")
            return None

        kwargs = {}
        if new_name:
            kwargs["name"] = new_name
        if topic is not None:
            kwargs["topic"] = topic
        if slowmode is not None:
            kwargs["slowmode_delay"] = slowmode
        if nsfw is not None:
            kwargs["nsfw"] = nsfw

        if kwargs:
            await channel.edit(**kwargs)
            logger.info(f"Edited channel: {channel_name}")
        return channel

    async def edit_category(
        self,
        category_name: str,
        new_name: Optional[str] = None,
        position: Optional[int] = None,
    ) -> Optional[CategoryChannel]:
        """Edit a category's properties."""
        category = discord.utils.get(self.guild.categories, name=category_name)
        if not category:
            logger.warning(f"Category not found: {category_name}")
            return None

        kwargs = {}
        if new_name:
            kwargs["name"] = new_name
        if position is not None:
            kwargs["position"] = position

        if kwargs:
            await category.edit(**kwargs)
            logger.info(f"Edited category: {category_name}")
        return category

    async def edit_role(
        self,
        role_name: str,
        new_name: Optional[str] = None,
        color: Optional[str] = None,
        hoist: Optional[bool] = None,
        mentionable: Optional[bool] = None,
    ) -> Optional[Role]:
        """Edit a role's properties."""
        role = discord.utils.get(self.guild.roles, name=role_name)
        if not role:
            logger.warning(f"Role not found: {role_name}")
            return None

        kwargs = {}
        if new_name:
            kwargs["name"] = new_name
        if color:
            kwargs["color"] = discord.Color(int(color.lstrip("#"), 16))
        if hoist is not None:
            kwargs["hoist"] = hoist
        if mentionable is not None:
            kwargs["mentionable"] = mentionable

        if kwargs:
            await role.edit(**kwargs)
            logger.info(f"Edited role: {role_name}")
        return role

    async def upload_emoji(self, name: str, image_path: str) -> Optional[discord.Emoji]:
        """Upload a custom emoji."""
        with open(image_path, "rb") as f:
            image_bytes = f.read()
        emoji = await self.guild.create_custom_emoji(name=name, image=image_bytes)
        logger.info(f"Uploaded emoji: {name}")
        return emoji

    async def set_verification_level(self, level: str) -> None:
        """Set the server verification level."""
        verification_level = getattr(discord.VerificationLevel, level.lower())
        await self.guild.edit(verification_level=verification_level)
        logger.info(f"Set verification level to: {level}")

    # ==================== Role Management ====================

    async def create_role(
        self,
        name: str,
        color: Optional[str] = None,
        hoist: bool = False,
        mentionable: bool = False,
        permissions: Optional[List[str]] = None,
    ) -> Role:
        """Create a new role."""
        color_value = discord.Color.default()
        if color:
            color_value = discord.Color(int(color.lstrip("#"), 16))

        perms = discord.Permissions.none()
        if permissions:
            for perm in permissions:
                if hasattr(perms, perm):
                    setattr(perms, perm, True)

        role = await self.guild.create_role(
            name=name,
            color=color_value,
            hoist=hoist,
            mentionable=mentionable,
            permissions=perms,
        )
        logger.info(f"Created role: {role.name}")
        return role

    async def delete_role(self, role_name: str) -> bool:
        """Delete a role by name."""
        role = discord.utils.get(self.guild.roles, name=role_name)
        if role:
            await role.delete()
            logger.info(f"Deleted role: {role_name}")
            return True
        logger.warning(f"Role not found: {role_name}")
        return False

    async def assign_role(self, member_id: int, role_name: str) -> bool:
        """Assign a role to a member."""
        member = self.guild.get_member(member_id)
        if not member:
            logger.warning(f"Member not found: {member_id}")
            return False

        role = discord.utils.get(self.guild.roles, name=role_name)
        if not role:
            logger.warning(f"Role not found: {role_name}")
            return False

        await member.add_roles(role)
        logger.info(f"Assigned role {role_name} to {member.name}")
        return True

    async def remove_role(self, member_id: int, role_name: str) -> bool:
        """Remove a role from a member."""
        member = self.guild.get_member(member_id)
        if not member:
            logger.warning(f"Member not found: {member_id}")
            return False

        role = discord.utils.get(self.guild.roles, name=role_name)
        if not role:
            logger.warning(f"Role not found: {role_name}")
            return False

        await member.remove_roles(role)
        logger.info(f"Removed role {role_name} from {member.name}")
        return True

    # ==================== Messaging ====================

    async def send_message(
        self,
        channel_name: str,
        content: Optional[str] = None,
        embed: Optional[Dict[str, Any]] = None,
    ) -> Optional[discord.Message]:
        """Send a message to a channel."""
        channel = discord.utils.get(self.guild.text_channels, name=channel_name)
        if not channel:
            logger.warning(f"Channel not found: {channel_name}")
            return None

        embed_obj = None
        if embed:
            embed_obj = discord.Embed(
                title=embed.get("title"),
                description=embed.get("description"),
                color=discord.Color(int(embed.get("color", "0x000000").lstrip("#"), 16))
                if embed.get("color")
                else discord.Color.blue(),
            )
            for field in embed.get("fields", []):
                embed_obj.add_field(
                    name=field["name"],
                    value=field["value"],
                    inline=field.get("inline", False),
                )
            if embed.get("footer"):
                embed_obj.set_footer(text=embed["footer"])
            if embed.get("thumbnail"):
                embed_obj.set_thumbnail(url=embed["thumbnail"])
            if embed.get("image"):
                embed_obj.set_image(url=embed["image"])

        message = await channel.send(content=content, embed=embed_obj)
        logger.info(f"Sent message to {channel_name}")
        return message

    async def send_dm(
        self,
        user_id: int,
        content: Optional[str] = None,
        embed: Optional[Dict[str, Any]] = None,
    ) -> Optional[discord.Message]:
        """Send a direct message to a user."""
        user = await self.bot.fetch_user(user_id)
        if not user:
            logger.warning(f"User not found: {user_id}")
            return None

        embed_obj = None
        if embed:
            embed_obj = discord.Embed(
                title=embed.get("title"),
                description=embed.get("description"),
                color=discord.Color.blue(),
            )

        try:
            message = await user.send(content=content, embed=embed_obj)
            logger.info(f"Sent DM to user {user_id}")
            return message
        except discord.Forbidden:
            logger.warning(f"Cannot DM user {user_id} - DMs disabled")
            return None

    async def get_recent_messages(
        self,
        channel_name: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent messages from a channel."""
        channel = discord.utils.get(self.guild.text_channels, name=channel_name)
        if not channel:
            logger.warning(f"Channel not found: {channel_name}")
            return []

        messages = []
        async for message in channel.history(limit=limit):
            messages.append({
                "id": message.id,
                "content": message.content,
                "author": message.author.name,
                "author_id": message.author.id,
                "created_at": message.created_at.isoformat(),
                "attachments": [a.url for a in message.attachments],
                "embeds": len(message.embeds),
            })
        return messages

    async def delete_messages(
        self,
        channel_name: str,
        message_ids: List[int],
    ) -> int:
        """Delete specific messages from a channel."""
        channel = discord.utils.get(self.guild.text_channels, name=channel_name)
        if not channel:
            logger.warning(f"Channel not found: {channel_name}")
            return 0

        deleted = 0
        for msg_id in message_ids:
            try:
                message = await channel.fetch_message(msg_id)
                await message.delete()
                deleted += 1
            except discord.NotFound:
                continue
        logger.info(f"Deleted {deleted} messages from {channel_name}")
        return deleted

    async def purge_channel(
        self,
        channel_name: str,
        limit: int = 100,
    ) -> int:
        """Purge messages from a channel."""
        channel = discord.utils.get(self.guild.text_channels, name=channel_name)
        if not channel:
            logger.warning(f"Channel not found: {channel_name}")
            return 0

        deleted = await channel.purge(limit=limit)
        logger.info(f"Purged {len(deleted)} messages from {channel_name}")
        return len(deleted)

    # ==================== Permission Management ====================

    async def set_channel_permissions(
        self,
        channel_name: str,
        target_name: str,
        target_type: str,  # "role" or "member"
        permissions: Dict[str, bool],
    ) -> bool:
        """Set permission overwrites for a channel."""
        channel = discord.utils.get(self.guild.channels, name=channel_name)
        if not channel:
            logger.warning(f"Channel not found: {channel_name}")
            return False

        if target_type == "role":
            target = discord.utils.get(self.guild.roles, name=target_name)
        else:
            # For members, search by name or display name
            target = discord.utils.find(
                lambda m: m.name == target_name or m.display_name == target_name,
                self.guild.members
            )

        if not target:
            logger.warning(f"{target_type} not found: {target_name}")
            return False

        overwrite = PermissionOverwrite()
        for perm, value in permissions.items():
            if hasattr(overwrite, perm):
                setattr(overwrite, perm, value)

        await channel.set_permissions(target, overwrite=overwrite)
        logger.info(f"Set permissions for {target_name} in {channel_name}")
        return True

    async def _build_overwrites(
        self,
        overwrites: Dict[str, Dict[str, bool]],
    ) -> Dict[Union[Role, Member], PermissionOverwrite]:
        """Build permission overwrites from a dict specification."""
        result = {}
        for target_name, perms in overwrites.items():
            target = discord.utils.get(self.guild.roles, name=target_name)
            if not target:
                # For members, search by name or display name
                target = discord.utils.find(
                    lambda m: m.name == target_name or m.display_name == target_name,
                    self.guild.members
                )
            if target:
                overwrite = PermissionOverwrite()
                for perm, value in perms.items():
                    if hasattr(overwrite, perm):
                        setattr(overwrite, perm, value)
                result[target] = overwrite
        return result

    # ==================== Server Settings ====================

    async def set_server_name(self, name: str) -> None:
        """Change the server name."""
        await self.guild.edit(name=name)
        logger.info(f"Changed server name to: {name}")

    async def set_server_description(self, description: str) -> None:
        """Change the server description."""
        await self.guild.edit(description=description)
        logger.info("Updated server description")

    async def set_server_icon(self, icon_path: str) -> None:
        """Change the server icon."""
        with open(icon_path, "rb") as f:
            icon_bytes = f.read()
        await self.guild.edit(icon=icon_bytes)
        logger.info("Updated server icon")

    # ==================== Utility ====================

    async def export_server_structure(self, output_path: str) -> None:
        """Export the entire server structure to a JSON file."""
        structure = {
            "server_info": await self.get_server_info(),
            "channels": await self.list_channels(),
            "roles": await self.list_roles(),
            "exported_at": datetime.utcnow().isoformat(),
        }
        
        with open(output_path, "w") as f:
            json.dump(structure, f, indent=2)
        logger.info(f"Exported server structure to {output_path}")

    async def setup_standard_server(self) -> Dict[str, Any]:
        """Set up a standard server structure with common channels."""
        created = {"categories": [], "channels": [], "roles": []}

        # Create roles
        roles_to_create = [
            {"name": "Admin", "color": "#e74c3c", "hoist": True, "permissions": ["administrator"]},
            {"name": "Moderator", "color": "#3498db", "hoist": True, "permissions": ["kick_members", "ban_members", "manage_messages"]},
            {"name": "Member", "color": "#2ecc71", "hoist": False},
            {"name": "Bot", "color": "#9b59b6", "hoist": True},
        ]

        for role_config in roles_to_create:
            try:
                role = await self.create_role(**role_config)
                created["roles"].append(role.name)
            except Exception as e:
                logger.error(f"Failed to create role {role_config['name']}: {e}")

        # Create categories and channels
        categories = [
            {
                "name": "📢 Information",
                "channels": [
                    {"name": "welcome", "topic": "Welcome to the server! Read the rules."},
                    {"name": "rules", "topic": "Server rules and guidelines"},
                    {"name": "announcements", "topic": "Important announcements"},
                ],
            },
            {
                "name": "💬 General",
                "channels": [
                    {"name": "general-chat", "topic": "General discussion"},
                    {"name": "off-topic", "topic": "Random discussions"},
                    {"name": "introductions", "topic": "Introduce yourself!"},
                ],
            },
            {
                "name": "🤖 Bot Commands",
                "channels": [
                    {"name": "bot-commands", "topic": "Use bot commands here"},
                    {"name": "photo-generation", "topic": "Generate AI photo packs here"},
                ],
            },
            {
                "name": "🔊 Voice",
                "voice_channels": [
                    {"name": "General Voice"},
                    {"name": "Gaming"},
                    {"name": "Music"},
                ],
            },
            {
                "name": "🔒 Staff Only",
                "channels": [
                    {"name": "staff-chat", "topic": "Staff discussion"},
                    {"name": "mod-logs", "topic": "Moderation logs"},
                ],
            },
        ]

        for cat_config in categories:
            try:
                category = await self.create_category(cat_config["name"])
                created["categories"].append(category.name)

                for ch_config in cat_config.get("channels", []):
                    channel = await self.create_text_channel(
                        name=ch_config["name"],
                        category=cat_config["name"],
                        topic=ch_config.get("topic"),
                    )
                    created["channels"].append(channel.name)

                for vc_config in cat_config.get("voice_channels", []):
                    channel = await self.create_voice_channel(
                        name=vc_config["name"],
                        category=cat_config["name"],
                    )
                    created["channels"].append(channel.name)

            except Exception as e:
                logger.error(f"Failed to create category {cat_config['name']}: {e}")

        logger.info(f"Standard server setup complete: {created}")
        return created

    async def reorganize_channels_professional(self) -> Dict[str, Any]:
        """
        Reorganize all channels into a professional, top-tier structure.
        This method organizes existing channels and creates missing ones with proper hierarchy.
        """
        logger.info("Starting professional channel reorganization...")
        results = {
            "categories_created": [],
            "channels_organized": [],
            "channels_renamed": [],
            "channels_moved": [],
            "topics_updated": [],
            "channels_categorized": [],
        }

        # Professional category structure with proper ordering
        professional_structure = [
            {
                "name": "📌 ESSENTIALS",
                "position": 0,
                "channels": [
                    {"name": "start-here", "topic": "👋 Welcome! Read this first to get started and understand our community.", "slowmode": 0},
                    {"name": "rules", "topic": "📜 Server rules and guidelines. Please read before participating.", "slowmode": 0},
                    {"name": "announcements", "topic": "📢 Important server announcements and updates.", "slowmode": 0},
                    {"name": "server-info", "topic": "ℹ️ General information about the server, features, and resources.", "slowmode": 0},
                ],
                "keywords": ["welcome", "start", "rules", "rule", "announcement", "info", "information", "server-info", "guide", "getting-started"],
            },
            {
                "name": "💬 COMMUNITY",
                "position": 1,
                "channels": [
                    {"name": "general", "topic": "💭 General discussion and community chat. Keep it friendly!", "slowmode": 0},
                    {"name": "introductions", "topic": "👋 Introduce yourself to the community! Tell us about you.", "slowmode": 5},
                    {"name": "showcase", "topic": "✨ Share your creations, projects, and achievements!", "slowmode": 0},
                    {"name": "off-topic", "topic": "🎲 Random discussions and casual conversation.", "slowmode": 0},
                ],
                "keywords": ["general", "chat", "discussion", "introduce", "introduction", "showcase", "show", "off-topic", "random", "lounge", "community", "wins", "check-in", "media", "networking", "events", "achievement", "gallery", "ask", "anything", "manifesto"],
            },
            {
                "name": "🎨 AI PHOTO GENERATION",
                "position": 2,
                "channels": [
                    {"name": "generate-pack", "topic": "🤖 Use /generate_pack to create your AI photo pack. Payment required.", "slowmode": 0},
                    {"name": "upload-references", "topic": "📸 Upload your reference photos here after payment confirmation.", "slowmode": 0},
                    {"name": "generated-packs", "topic": "📦 View and share your generated photo packs.", "slowmode": 0},
                    {"name": "generation-help", "topic": "❓ Need help with photo generation? Ask here!", "slowmode": 0},
                ],
                "keywords": ["generate", "photo", "pack", "ai", "upload", "reference", "generation", "image", "picture", "photo-generation", "bot-commands", "bot", "command", "avatar", "fine-tuning", "model", "deepfake"],
            },
            {
                "name": "💼 SUPPORT & HELP",
                "position": 3,
                "channels": [
                    {"name": "support", "topic": "🆘 Get help with technical issues, payments, or general questions.", "slowmode": 0},
                    {"name": "faq", "topic": "❓ Frequently asked questions and answers.", "slowmode": 0},
                    {"name": "suggestions", "topic": "💡 Share your ideas and suggestions to improve the server.", "slowmode": 0},
                    {"name": "bug-reports", "topic": "🐛 Report bugs or issues you've encountered.", "slowmode": 0},
                ],
                "keywords": ["support", "help", "faq", "question", "suggestion", "bug", "report", "issue", "ticket", "assistance"],
            },
            {
                "name": "🎮 VOICE",
                "position": 4,
                "voice_channels": [
                    {"name": "General", "user_limit": 0},
                    {"name": "Gaming", "user_limit": 0},
                    {"name": "AFK", "user_limit": 0},
                ],
                "strict_keywords": [],
            },
            {
                "name": "🔒 STAFF",
                "position": 5,
                "channels": [
                    {"name": "staff-lounge", "topic": "👥 Staff discussion and coordination.", "slowmode": 0},
                    {"name": "mod-logs", "topic": "📋 Moderation logs and audit trail.", "slowmode": 0},
                    {"name": "admin-commands", "topic": "⚙️ Administrative commands and tools.", "slowmode": 0},
                ],
                "keywords": ["staff", "admin", "mod", "moderator", "log", "command", "management", "team"],
            },
        ]

        # Step 1: Create/Organize Categories
        category_map = {}
        for cat_config in professional_structure:
            cat_name = cat_config["name"]
            try:
                # Check if category exists
                existing_cat = discord.utils.get(self.guild.categories, name=cat_name)
                if existing_cat:
                    category_map[cat_name] = existing_cat
                    # Update position if needed
                    if existing_cat.position != cat_config["position"]:
                        await existing_cat.edit(position=cat_config["position"])
                        logger.info(f"Updated position for category: {cat_name}")
                else:
                    category = await self.create_category(cat_name)
                    category_map[cat_name] = category
                    results["categories_created"].append(cat_name)
                    # Set position
                    await category.edit(position=cat_config["position"])
                    logger.info(f"Created category: {cat_name}")
            except Exception as e:
                logger.error(f"Error with category {cat_name}: {e}")

        # Step 2: Organize Text Channels - Ensure essential channels exist and are organized
        for cat_config in professional_structure:
            cat_name = cat_config["name"]
            category = category_map.get(cat_name)
            if not category:
                continue

            for ch_config in cat_config.get("channels", []):
                ch_name = ch_config["name"]
                try:
                    # Check if channel exists (case-insensitive)
                    existing_ch = None
                    for ch in self.guild.text_channels:
                        if ch.name.lower() == ch_name.lower():
                            existing_ch = ch
                            break
                    
                    if existing_ch:
                        # Channel exists - update it
                        updates = {}
                        
                        # Move to category if not already there
                        if existing_ch.category != category:
                            updates["category"] = category
                            results["channels_moved"].append(ch_name)
                        
                        # Update topic if different
                        if existing_ch.topic != ch_config.get("topic"):
                            updates["topic"] = ch_config.get("topic")
                            results["topics_updated"].append(ch_name)
                        
                        # Update slowmode if specified
                        if "slowmode" in ch_config and existing_ch.slowmode_delay != ch_config["slowmode"]:
                            updates["slowmode_delay"] = ch_config["slowmode"]
                        
                        # Rename if needed (normalize to expected name)
                        if existing_ch.name != ch_name:
                            updates["name"] = ch_name
                        
                        if updates:
                            await existing_ch.edit(**updates)
                            logger.info(f"Updated channel: {existing_ch.name} -> {ch_name}")
                            results["channels_organized"].append(ch_name)
                    else:
                        # Create new channel
                        channel = await self.create_text_channel(
                            name=ch_name,
                            category=cat_name,
                            topic=ch_config.get("topic"),
                            slowmode=ch_config.get("slowmode", 0),
                        )
                        results["channels_organized"].append(ch_name)
                        logger.info(f"Created channel: {ch_name}")
                except Exception as e:
                    logger.error(f"Error with channel {ch_name}: {e}")

        # Step 3: Organize Voice Channels
        for cat_config in professional_structure:
            cat_name = cat_config["name"]
            category = category_map.get(cat_name)
            if not category:
                continue

            for vc_config in cat_config.get("voice_channels", []):
                vc_name = vc_config["name"]
                try:
                    existing_vc = discord.utils.get(self.guild.voice_channels, name=vc_name)
                    
                    if existing_vc:
                        # Update existing voice channel
                        updates = {}
                        if existing_vc.category != category:
                            updates["category"] = category
                        if "user_limit" in vc_config and existing_vc.user_limit != vc_config["user_limit"]:
                            updates["user_limit"] = vc_config["user_limit"]
                        
                        if updates:
                            await existing_vc.edit(**updates)
                            logger.info(f"Updated voice channel: {vc_name}")
                            results["channels_organized"].append(vc_name)
                    else:
                        # Create new voice channel
                        channel = await self.create_voice_channel(
                            name=vc_name,
                            category=cat_name,
                            user_limit=vc_config.get("user_limit", 0),
                        )
                        results["channels_organized"].append(vc_name)
                        logger.info(f"Created voice channel: {vc_name}")
                except Exception as e:
                    logger.error(f"Error with voice channel {vc_name}: {e}")

        # Step 4: CLEAN ORGANIZATION - Only keep essential channels visible
        # Get all channels that should be in main categories
        all_organized_channel_names = set()
        essential_channel_map = {}  # Map channel names to their categories
        
        for cat_config in professional_structure:
            cat_name = cat_config["name"]
            # Add defined channels
            for ch_config in cat_config.get("channels", []):
                ch_name = ch_config["name"]
                all_organized_channel_names.add(ch_name)
                essential_channel_map[ch_name] = cat_name
            for vc_config in cat_config.get("voice_channels", []):
                vc_name = vc_config["name"]
                all_organized_channel_names.add(vc_name)
                essential_channel_map[vc_name] = cat_name

        def find_category_for_channel(channel_name: str, is_voice: bool = False) -> Optional[str]:
            """Find category only for exact matches - keep it clean and minimal."""
            channel_lower = channel_name.lower().strip()
            
            # Skip if already organized
            if channel_name in all_organized_channel_names:
                return None
            
            # Voice channels go to voice category
            if is_voice:
                return "🎮 VOICE"
            
            # EXACT matching only - keep structure minimal and professional
            for cat_config in professional_structure:
                if cat_config["name"] == "🎮 VOICE":
                    continue
                
                exact_matches = cat_config.get("exact_matches", [])
                for match in exact_matches:
                    # Exact match or channel name contains the match
                    if match.lower() == channel_lower or match.lower() in channel_lower:
                        return cat_config["name"]
            
            # If no match, return None (will go to archive for clean structure)
            return None

        # Categorize text channels - ONLY essential ones
        for channel in self.guild.text_channels:
            try:
                # Skip if already in correct category
                if channel.category and channel.category.name in category_map:
                    continue
                
                # Check if this is an essential channel (exact name match)
                if channel.name in essential_channel_map:
                    target_category_name = essential_channel_map[channel.name]
                    target_category = category_map.get(target_category_name)
                    if target_category:
                        await channel.edit(category=target_category)
                        results["channels_categorized"].append(f"{channel.name} -> {target_category_name}")
                        logger.info(f"Categorized essential channel: {channel.name} -> {target_category_name}")
                        continue
                
                # Try keyword matching for close matches
                target_category_name = find_category_for_channel(channel.name, is_voice=False)
                if target_category_name:
                    target_category = category_map.get(target_category_name)
                    if target_category and channel.category != target_category:
                        await channel.edit(category=target_category)
                        results["channels_categorized"].append(f"{channel.name} -> {target_category_name}")
                        logger.info(f"Categorized channel: {channel.name} -> {target_category_name}")
            except Exception as e:
                logger.error(f"Error categorizing channel {channel.name}: {e}")

        # Categorize all voice channels
        for channel in self.guild.voice_channels:
            try:
                # Skip if already in correct category
                if channel.category and channel.category.name == "🎮 VOICE":
                    continue
                
                target_category = category_map.get("🎮 VOICE")
                if target_category and channel.category != target_category:
                    await channel.edit(category=target_category)
                    results["channels_categorized"].append(f"{channel.name} -> VOICE")
                    logger.info(f"Categorized voice channel: {channel.name}")
            except Exception as e:
                logger.error(f"Error categorizing voice channel {channel.name}: {e}")

        # Step 5: Archive truly orphaned channels (only if they don't fit anywhere)
        # Only archive channels that couldn't be categorized
        archive_cat = None
        uncategorized_channels = []
        
        for channel in list(self.guild.text_channels) + list(self.guild.voice_channels):
            try:
                # Skip system channels
                if hasattr(channel, "type") and channel.type in [discord.ChannelType.category]:
                    continue
                
                # Skip if channel is now in a proper category
                if channel.category and channel.category.name in category_map:
                    continue
                
                # Skip channels that are in the organized list (they should stay where they are)
                if channel.name in all_organized_channel_names:
                    continue
                
                # This channel couldn't be categorized - mark for archiving
                uncategorized_channels.append(channel)
            except Exception as e:
                logger.error(f"Error checking channel {channel.name}: {e}")
        
        # Only create archive and move channels if we have truly orphaned ones
        if uncategorized_channels:
            try:
                archive_cat = discord.utils.get(self.guild.categories, name="📦 ARCHIVE")
                if not archive_cat:
                    archive_cat = await self.create_category("📦 ARCHIVE")
                    await archive_cat.edit(position=99)
                    results["categories_created"].append("📦 ARCHIVE")
                
                # Archive only truly uncategorized channels
                for channel in uncategorized_channels:
                    try:
                        # Double-check it's not in a proper category now
                        if channel.category and channel.category.name in category_map:
                            continue
                        
                        await channel.edit(category=archive_cat)
                        results["channels_moved"].append(f"{channel.name} -> ARCHIVE")
                        logger.info(f"Archived channel: {channel.name}")
                    except Exception as e:
                        logger.error(f"Error archiving channel {channel.name}: {e}")
            except Exception as e:
                logger.error(f"Error setting up archive: {e}")

        logger.info("Professional channel reorganization complete!")
        return results

    async def apply_professional_naming(self) -> Dict[str, Any]:
        """
        Apply professional naming conventions to all channels.
        Converts names like 'general-chat' to 'general', removes hyphens, etc.
        """
        results = {"renamed": [], "errors": []}
        
        # Professional naming mappings (old_name -> new_name)
        naming_map = {
            "general-chat": "general",
            "off-topic": "off-topic",  # Keep as is, common convention
            "bot-commands": "bot-commands",  # Keep as is
            "photo-generation": "generate-pack",
            "staff-chat": "staff-lounge",
            "mod-logs": "mod-logs",  # Keep as is
        }
        
        for old_name, new_name in naming_map.items():
            try:
                channel = discord.utils.get(self.guild.text_channels, name=old_name)
                if channel and channel.name != new_name:
                    await channel.edit(name=new_name)
                    results["renamed"].append(f"{old_name} -> {new_name}")
                    logger.info(f"Renamed channel: {old_name} -> {new_name}")
            except Exception as e:
                results["errors"].append(f"{old_name}: {str(e)}")
                logger.error(f"Error renaming {old_name}: {e}")
        
        return results


# ==================== CLI Interface ====================

async def run_manager_cli():
    """Run an interactive CLI for server management."""
    import sys
    
    token = os.environ.get("DISCORD_BOT_TOKEN")
    guild_id = os.environ.get("DISCORD_GUILD_ID")
    
    if not token or not guild_id:
        print("Error: Set DISCORD_BOT_TOKEN and DISCORD_GUILD_ID environment variables")
        sys.exit(1)
    
    config = ServerConfig(token=token, guild_id=int(guild_id))
    manager = DiscordServerManager(config)
    
    print("Connecting to Discord...")
    await manager.connect()
    print(f"Connected to: {manager.guild.name}")
    
    while True:
        print("\n=== Discord Server Manager ===")
        print("1. Server Info")
        print("2. List Channels")
        print("3. List Roles")
        print("4. List Members")
        print("5. Create Text Channel")
        print("6. Create Role")
        print("7. Send Message")
        print("8. Export Structure")
        print("9. Setup Standard Server")
        print("10. Reorganize Channels (Professional)")
        print("11. Apply Professional Naming")
        print("0. Exit")
        
        choice = input("\nChoice: ").strip()
        
        try:
            if choice == "1":
                info = await manager.get_server_info()
                print(json.dumps(info, indent=2))
            elif choice == "2":
                channels = await manager.list_channels()
                for ch in channels:
                    print(f"  {ch['type']:15} | {ch['name']}")
            elif choice == "3":
                roles = await manager.list_roles()
                for role in roles:
                    print(f"  {role['position']:2} | {role['name']}")
            elif choice == "4":
                members = await manager.list_members()
                for m in members:
                    roles = ", ".join(m["roles"]) if m["roles"] else "None"
                    print(f"  {m['name']} ({m['display_name']}) - Roles: {roles}")
            elif choice == "5":
                name = input("Channel name: ")
                category = input("Category (optional): ") or None
                topic = input("Topic (optional): ") or None
                await manager.create_text_channel(name, category, topic)
                print(f"Created channel: {name}")
            elif choice == "6":
                name = input("Role name: ")
                color = input("Color (hex, e.g. #ff0000): ") or None
                await manager.create_role(name, color)
                print(f"Created role: {name}")
            elif choice == "7":
                channel = input("Channel name: ")
                content = input("Message: ")
                await manager.send_message(channel, content)
                print("Message sent!")
            elif choice == "8":
                path = input("Output path: ") or "server_structure.json"
                await manager.export_server_structure(path)
                print(f"Exported to {path}")
            elif choice == "9":
                confirm = input("This will create standard channels/roles. Continue? (y/n): ")
                if confirm.lower() == "y":
                    result = await manager.setup_standard_server()
                    print(f"Created: {result}")
            elif choice == "10":
                confirm = input("This will reorganize all channels professionally. Continue? (y/n): ")
                if confirm.lower() == "y":
                    result = await manager.reorganize_channels_professional()
                    print("\n=== Reorganization Results ===")
                    print(f"Categories created: {len(result['categories_created'])}")
                    print(f"Channels organized: {len(result['channels_organized'])}")
                    print(f"Channels moved: {len(result['channels_moved'])}")
                    print(f"Topics updated: {len(result['topics_updated'])}")
                    print(f"\nDetails: {json.dumps(result, indent=2)}")
            elif choice == "11":
                confirm = input("This will apply professional naming to channels. Continue? (y/n): ")
                if confirm.lower() == "y":
                    result = await manager.apply_professional_naming()
                    print(f"\nRenamed: {result['renamed']}")
                    if result['errors']:
                        print(f"Errors: {result['errors']}")
            elif choice == "0":
                break
        except Exception as e:
            print(f"Error: {e}")
    
    await manager.disconnect()
    print("Disconnected.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_manager_cli())



