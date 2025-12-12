"""Discord bot entrypoint wiring the premium /studio flow.

Legacy BTC/payment commands are intentionally disabled.
"""

from __future__ import annotations

import asyncio
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

        # Post/pin the studio guide in #photo-generation (best-effort).
        # IMPORTANT: setup_hook can run before caches are fully warm; run with retries after ready.
        asyncio.create_task(self._ensure_studio_guide_with_retries())


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


    async def _ensure_studio_guide_with_retries(self) -> None:
        """Run studio-guide posting after the bot is ready, with a few retries.

        Also enforces server structure:
        - ensure category "LLAMA LLAMA CLUB" (by ID) exists (create by name if missing)
        - ensure/move #photo-generation under that category

        This avoids a common failure mode where guild/channel caches are not ready during setup_hook.
        """
        try:
            await self.wait_until_ready()
        except Exception as exc:  # noqa: BLE001
            logger.warning("wait_until_ready failed: %s", exc)
            return

        # Retry a few times to allow guild/channel caches to populate.
        for attempt in range(1, 6):
            try:
                await self._ensure_llama_category_and_channel()
                posted = await self._ensure_studio_guide()
                if posted:
                    return
            except Exception as exc:  # noqa: BLE001
                logger.exception("Studio guide attempt %s failed: %s", attempt, exc)
            await asyncio.sleep(2.0 * attempt)

        logger.warning("Studio guide was not posted after retries.")

    async def _ensure_llama_category_and_channel(self) -> None:
        """Ensure #photo-generation is under the 'LLAMA LLAMA CLUB' category.

        Target category ID: 1448815942435078355 (preferred).
        If missing, create a category named 'LLAMA LLAMA CLUB' and log the new ID.
        """
        guild_id = int(self.settings.discord_guild_id)

        # Prefer cached guild, fall back to API fetch.
        guild = self.get_guild(guild_id)
        if not guild:
            try:
                guild = await self.fetch_guild(guild_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Unable to fetch guild %s for structure enforcement: %s", guild_id, exc)
                return

        # Fetch all channels for reliable lookup.
        try:
            channels = await guild.fetch_channels()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to fetch channels for guild %s: %s", guild_id, exc)
            return

        target_category_id = 1448815942435078355
        category = discord.utils.get(channels, id=target_category_id)

        if not category:
            # Fall back to category name, then create if missing.
            category = discord.utils.get(channels, name="LLAMA LLAMA CLUB")
            if not category:
                try:
                    # Need a cached Guild to create channels/categories
                    cached_guild = self.get_guild(guild_id)
                    if not cached_guild:
                        logger.warning("Guild cache not ready; cannot create category yet.")
                        return
                    category = await cached_guild.create_category(
                        name="LLAMA LLAMA CLUB",
                        reason="Ensure premium studio category exists",
                    )
                    logger.warning(
                        "Created category 'LLAMA LLAMA CLUB' with id=%s (update target id if you want it fixed).",
                        category.id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to create category 'LLAMA LLAMA CLUB': %s", exc)
                    return
            else:
                logger.warning(
                    "Category id=%s not found; using category by name 'LLAMA LLAMA CLUB' (id=%s).",
                    target_category_id,
                    getattr(category, "id", None),
                )

        # Find existing #photo-generation (by name) across fetched channels.
        photo_channel = discord.utils.get(channels, name="photo-generation")

        # If it doesn't exist, create it under the category.
        if not photo_channel:
            try:
                cached_guild = self.get_guild(guild_id)
                if not cached_guild:
                    logger.warning("Guild cache not ready; cannot create #photo-generation yet.")
                    return
                photo_channel = await cached_guild.create_text_channel(
                    name="photo-generation",
                    category=category if isinstance(category, discord.CategoryChannel) else None,
                    topic="Premium AI photo studio: use /studio here.",
                    reason="Ensure photo-generation channel exists for studio",
                )
                logger.info("Created #photo-generation under category id=%s", getattr(category, "id", None))
                return
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to create #photo-generation: %s", exc)
                return

        # If it exists but is not under the category, move it.
        try:
            current_cat_id = getattr(getattr(photo_channel, "category", None), "id", None)
            desired_cat_id = getattr(category, "id", None)
            if desired_cat_id and current_cat_id != desired_cat_id:
                await photo_channel.edit(
                    category=category,
                    reason="Move photo-generation under LLAMA LLAMA CLUB",
                )
                logger.info(
                    "Moved #photo-generation into category id=%s (was %s)",
                    desired_cat_id,
                    current_cat_id,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to move #photo-generation into category: %s", exc)

    async def _ensure_studio_guide(self) -> bool:
        """Ensure a pinned /studio onboarding guide exists in #photo-generation (best-effort).

        Returns True if the guide is confirmed pinned or posted+attempted pin, False otherwise.
        """
        try:
            guild_id = int(self.settings.discord_guild_id)
            guild = self.get_guild(guild_id)

            # Cache miss fallback: fetch guild + channels via API.
            if not guild:
                try:
                    guild = await self.fetch_guild(guild_id)
                    logger.info("Fetched guild %s via API for studio guide.", guild_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Guild %s not found (cache miss + fetch failed): %s", guild_id, exc)
                    return False

            try:
                channels = await guild.fetch_channels()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch channels for guild %s: %s", guild_id, exc)
                channels = []

            channel = discord.utils.get(channels, name="photo-generation")
            if not channel:
                # Best-effort fallback: try cached text_channels if available.
                cached_guild = self.get_guild(guild_id)
                if cached_guild:
                    channel = discord.utils.get(cached_guild.text_channels, name="photo-generation")

            if not channel:
                logger.warning("Channel #photo-generation not found in guild %s; skipping studio guide", guild_id)
                return False

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
                    logger.info("Studio guide already pinned in #%s (guild %s)", channel.name, guild_id)
                    return True

            # 2) If guide exists but got unpinned, re-pin it.
            async for msg in channel.history(limit=50):
                if _is_guide_message(msg):
                    try:
                        await msg.pin(reason="Re-pin studio onboarding guide")
                        logger.info("Re-pinned existing studio guide in #%s (guild %s)", channel.name, guild_id)
                        return True
                    except discord.Forbidden:
                        logger.warning("Missing permissions to pin messages in #%s (guild %s)", channel.name, guild_id)
                        return False

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
                logger.warning("Missing permissions to pin messages in #%s (guild %s)", channel.name, guild_id)
                return True  # posted even if pin failed
            logger.info("Posted and pinned studio guide in #%s (guild %s)", channel.name, guild_id)
            return True

        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed ensuring studio guide: %s", exc)
            return False


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





