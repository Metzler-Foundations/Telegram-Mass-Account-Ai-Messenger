"""User-facing help commands for the /studio-only bot."""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from discord_ai_photo_bot.config import Settings


class StudioHelp(commands.Cog):
    """Help surface for the premium /studio workflow."""

    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings

    @app_commands.command(
        name="help",
        description="How to use the AI Photo Studio (upload → train → generate → DM).",
    )
    async def help(self, interaction: discord.Interaction) -> None:
        guild = interaction.guild
        if not guild:
            await interaction.response.send_message(
                "Run `/help` inside the server (not in DMs).",
                ephemeral=True,
            )
            return

        channel_hint = "#photo-generation"
        if interaction.channel and getattr(interaction.channel, "name", None):
            if interaction.channel.name != "photo-generation":
                channel_hint = "#photo-generation (this command works anywhere, but /studio must be started there)"

        embed = discord.Embed(
            title="🎨 AI Photo Studio • Quickstart Guide",
            description=(
                f"**🚀 Ready to create AI photos?**\n\n"
                f"**Start:** run `/studio` in {channel_hint}.\n\n"
                "**✨ What you'll get:**\n"
                "• 40 unique AI-generated photos\n"
                "• Custom model trained on your photos\n"
                "• High-quality, photorealistic results\n\n"
                "**📋 Step-by-step**\n"
                "1) Bot creates your private studio thread\n"
                "2) Upload **5–15** photos of the same person\n"
                "3) Click **\"Finish uploads & start training\"**\n"
                "4) Training takes ~8 minutes (feel free to browse)\n"
                "5) Click **\"Generate pack (40)\"** when ready\n"
                "6) Receive your ZIP via **DM**\n\n"
                "**📸 Best photo tips**\n"
                "• Clear, well-lit photos work best\n"
                "• Face clearly visible in each photo\n"
                "• Different angles & expressions\n"
                "• No heavy filters or group photos\n\n"
                "**💡 Pro tips**\n"
                "• Sessions save automatically - come back anytime\n"
                "• Use only photos you have permission to use\n"
                "• More variety = better AI results"
            ),
            color=discord.Color.from_rgb(138, 43, 226),
        )
        embed.set_footer(text="🎯 Free during testing • Full ownership of generated images")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    settings = getattr(bot, "settings", None)
    if not settings:
        raise RuntimeError("Bot missing settings")
    await bot.add_cog(StudioHelp(bot, settings=settings))