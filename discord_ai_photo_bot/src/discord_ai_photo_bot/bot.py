"""Discord bot entrypoint wiring the premium /studio flow.

Legacy BTC/payment commands are intentionally disabled.
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands
import sentry_sdk

from discord_ai_photo_bot.ai.generator import ReplicateLoraWorkflow
from discord_ai_photo_bot.commands.help import StudioHelp
from discord_ai_photo_bot.commands.studio import DEFAULT_PACK_COUNT, MAX_REFS, MIN_REFS, Studio
from discord_ai_photo_bot.config import Settings, load_settings
from discord_ai_photo_bot.database import Database
from discord_ai_photo_bot.storage.discord_storage import DiscordStorage


logger = logging.getLogger(__name__)


class DiscordPhotoBot(commands.Bot):
    """Orchestrates command registration and job handling."""

    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True  # required to read attachment messages in studio threads
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.db = Database(settings.data_dir / "bot.db")

        # Premium LoRA workflow
        self.workflow = ReplicateLoraWorkflow(
            api_token=settings.replicate_token,
            training_model=settings.replicate_training_model,
            training_version=settings.replicate_training_version,
            training_params_json=settings.replicate_training_params_json,
            trigger_word=settings.replicate_trigger_word or "TOK",
            generation_params_json=settings.replicate_generation_params_json,
        )

        self.storage = DiscordStorage()

    async def setup_hook(self) -> None:
        # Premium studio cog (only user-facing surface)
        await self.add_cog(
            Studio(
                bot=self,
                settings=self.settings,
                db=self.db,
                workflow=self.workflow,
                storage=self.storage,
            )
        )
        await self.add_cog(StudioHelp(self, settings=self.settings))

        # Sync commands to the configured guild for immediate updates (no 1-hour global delay)
        guild_obj = discord.Object(id=int(self.settings.discord_guild_id))
        await self.tree.sync(guild=guild_obj)
        logger.info("Slash commands synced to guild %s.", self.settings.discord_guild_id)

        # Also sync globally so removed legacy commands eventually disappear everywhere.
        # This can take up to ~1 hour to propagate, but ensures clean command surface long-term.
        await self.tree.sync()
        logger.info("Slash commands synced globally.")

        # Post/pin the studio guide in #photo-generation (best-effort)
        await self._ensure_studio_guide()


    async def on_app_command_error(
        self, interaction: discord.Interaction, error: Exception
    ) -> None:
        """Send a concise error message and log the full trace."""

        logger.exception("Command error: %s", error)
        if interaction.response.is_done():
            await interaction.followup.send(
                "Something went wrong while processing your request. Please try again.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "Something went wrong while processing your request. Please try again.",
                ephemeral=True,
            )


    async def _ensure_studio_guide(self) -> None:
        """Ensure a pinned /studio onboarding guide exists in #photo-generation (best-effort)."""
        try:
            guild = self.get_guild(int(self.settings.discord_guild_id))
            if not guild:
                logger.warning("Guild not found, cannot post studio guide")
                return

            channel = discord.utils.get(guild.text_channels, name="photo-generation")
            if not channel:
                logger.warning("Channel #photo-generation not found; skipping studio guide")
                return

            guide_title = "AI Photo Studio • How it works"

            def _is_guide_message(msg: discord.Message) -> bool:
                if not self.user or msg.author.id != self.user.id:
                    return False
                if not msg.embeds:
                    return False
                return (msg.embeds[0].title or "").strip() == guide_title

            # 1) If already pinned, we're done.
            pins = await channel.pins()
            for msg in pins:
                if _is_guide_message(msg):
                    logger.info("Studio guide already pinned")
                    return

            # 2) If guide exists but got unpinned, re-pin it.
            async for msg in channel.history(limit=50):
                if _is_guide_message(msg):
                    try:
                        await msg.pin(reason="Re-pin studio onboarding guide")
                        logger.info("Re-pinned existing studio guide")
                    except discord.Forbidden:
                        logger.warning("Missing permissions to pin messages in #photo-generation")
                    return

            # 3) Otherwise, post a new guide and pin it.
            embed = discord.Embed(
                title=guide_title,
                description=(
                    "**Start here:** run `/studio` to begin.\n\n"
                    "**Flow**\n"
                    "1) Bot creates a private thread for you\n"
                    f"2) Upload **{MIN_REFS}–{MAX_REFS}** photos of the same person\n"
                    "3) Click **Finish uploads & start training**\n"
                    f"4) When training completes, click **Generate pack ({DEFAULT_PACK_COUNT})**\n"
                    "5) You receive a ZIP via DM\n\n"
                    "**Best reference photos**\n"
                    "- No filters, no group photos\n"
                    "- Face visible, good lighting, multiple angles\n"
                    "- Mix: close-up + mid-shot + different expressions\n\n"
                    "**Important**\n"
                    "- Use only photos you have permission to use\n"
                    "- Training can take several minutes"
                ),
                color=discord.Color.from_rgb(138, 43, 226),
            )
            embed.set_footer(text="Payments are currently disabled during testing.")

            guide_msg = await channel.send(embed=embed)
            try:
                await guide_msg.pin(reason="Studio onboarding guide")
            except discord.Forbidden:
                logger.warning("Missing permissions to pin messages in #photo-generation")
            logger.info("Posted studio guide in #photo-generation")

        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed ensuring studio guide: %s", exc)


def run_bot() -> None:
    """Entrypoint used by scripts or manual launching."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = load_settings()
    if not settings.discord_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required to run the bot.")

    # Initialize Sentry if DSN is provided
    if settings.sentry_dsn and settings.sentry_dsn.strip():
        sentry_sdk.init(dsn=settings.sentry_dsn)

    bot = DiscordPhotoBot(settings)
    bot.run(settings.discord_token)


if __name__ == "__main__":
    run_bot()





