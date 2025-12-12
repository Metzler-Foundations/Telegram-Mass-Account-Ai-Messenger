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
            title="AI Photo Studio • Quickstart",
            description=(
                f"**Start:** run `/studio` in {channel_hint}.\n\n"
                "**What happens**\n"
                "1) The bot creates a private thread for your session\n"
                "2) You upload **8–20** photos of the same person into the thread\n"
                "3) Click **Finish uploads & start training**\n"
                "4) After training succeeds, click **Generate pack (40)**\n"
                "5) Your ZIP is delivered via **DM**\n\n"
                "**Best results (photorealistic)**\n"
                "- No filters, no group photos\n"
                "- Face visible, good lighting, multiple angles\n"
                "- Mix: close-up + mid-shot + different expressions\n\n"
                "**Privacy**\n"
                "- Use only photos you have permission to use\n"
                "- Generated packs are delivered via DM"
            ),
            color=discord.Color.from_rgb(138, 43, 226),
        )
        embed.set_footer(text="Studio-only mode • Payments are currently disabled")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    settings = getattr(bot, "settings", None)
    if not settings:
        raise RuntimeError("Bot missing settings")
    await bot.add_cog(StudioHelp(bot, settings=settings))