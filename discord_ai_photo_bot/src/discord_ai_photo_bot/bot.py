"""Discord bot entrypoint wiring commands, payments, and generation."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Optional

import discord
from discord.ext import commands
import sentry_sdk
import uvicorn

from discord_ai_photo_bot.ai.generator import ReplicateGenerator, ReplicateLoraWorkflow
from discord_ai_photo_bot.commands.generate_pack import GeneratePack
from discord_ai_photo_bot.commands.photo_verification import PhotoVerification
from discord_ai_photo_bot.commands.studio import Studio
from discord_ai_photo_bot.config import Settings, load_settings
from discord_ai_photo_bot.database import Database
from discord_ai_photo_bot.jobs.queue import GenerationJob, JobQueue
from discord_ai_photo_bot.payments.bitcoin import BitcoinPaymentGateway
from discord_ai_photo_bot.server_manager import DiscordServerManager, ServerConfig
from discord_ai_photo_bot.storage.discord_storage import DiscordStorage
from discord_ai_photo_bot.webhook import create_webhook_app


logger = logging.getLogger(__name__)


class DiscordPhotoBot(commands.Bot):
    """Orchestrates command registration and job handling."""

    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.db = Database(settings.data_dir / "bot.db")
        self.payments = BitcoinPaymentGateway(settings)

        # Legacy generator (kept for compatibility)
        self.generator = ReplicateGenerator(api_token=settings.replicate_token)

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
        self.queue = JobQueue()

        # Payments/webhooks are disabled for now (free testing mode), but keep app available.
        self.webhook_app = create_webhook_app(settings, self.payments)
        self._webhook_server: Optional[uvicorn.Server] = None

        # Initialize server manager for role management
        server_config = ServerConfig(
            token=settings.discord_token,
            guild_id=int(settings.discord_guild_id),
        )
        self.server_manager = DiscordServerManager(server_config)

    async def setup_hook(self) -> None:
        # Connect server manager
        await self.server_manager.connect()
        logger.info("Server manager connected")

        # Create verification channel if it doesn't exist
        await self._ensure_verification_channel()

        cog = GeneratePack(
            bot=self,
            settings=self.settings,
            db=self.db,
            payments=self.payments,
            queue=self.queue,
            generation_handler=self.process_generation_job,
            server_manager=self.server_manager,
        )
        await self.add_cog(cog)

        # Premium studio cog (payments bypassed)
        await self.add_cog(
            Studio(
                bot=self,
                settings=self.settings,
                db=self.db,
                workflow=self.workflow,
                storage=self.storage,
            )
        )

        # Add photo verification cog (legacy)
        verification_cog = PhotoVerification(self, self.settings)
        await self.add_cog(verification_cog)

        # Register persistent views
        self.add_view(verification_cog.guide_view)

        await self.tree.sync()
        logger.info("Slash commands synced.")

        # Payments are off for now: do NOT start webhook server.
        if os.environ.get("ENABLE_WEBHOOK_SERVER", "").strip().lower() in ("1", "true", "yes"):
            webhook_port = int(os.environ.get("WEBHOOK_PORT", "8000"))
            config = uvicorn.Config(
                app=self.webhook_app,
                host="0.0.0.0",
                port=webhook_port,
                log_level="info",
            )
            self._webhook_server = uvicorn.Server(config)

            async def start_webhook():
                try:
                    await self._webhook_server.serve()
                except OSError as e:
                    if "address already in use" in str(e):
                        logger.warning(
                            f"Webhook port {webhook_port} already in use, skipping webhook server"
                        )
                    else:
                        logger.error(f"Failed to start webhook server: {e}")
                except Exception as e:
                    logger.error(f"Webhook server error: {e}")

            asyncio.create_task(start_webhook())
            logger.info(f"Webhook server starting on port {webhook_port}")

    async def process_generation_job(self, job: GenerationJob) -> None:
        """Handle a queued generation job."""

        output_dir = Path(self.settings.data_dir) / "generated" / job.invoice_id
        try:
            self.db.update_job_status(job.job_id, "running")
            generated = await self.generator.generate_batch(
                prompts=job.prompts,
                reference_images=job.reference_images,
                output_dir=output_dir,
            )
            self.db.update_job_status(
                job.job_id, "complete", output_paths=[str(path) for path in generated]
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Generation failed for job %s: %s", job.job_id, exc)
            self.db.update_job_status(job.job_id, "failed", output_paths=[])
            return

        try:
            user = await self.fetch_user(int(job.user_id))
            await self.storage.send_pack(
                channel=user,
                file_paths=generated,
                note="Your gesture photo pack is ready.",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to deliver pack for job %s: %s", job.job_id, exc)

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

    async def close(self) -> None:
        """Clean up resources on bot shutdown."""
        # Stop webhook server
        if self._webhook_server:
            self._webhook_server.should_exit = True
            logger.info("Webhook server shutdown initiated")
        
        # Stop job queue
        await self.queue.stop()
        
        await super().close()

    async def _ensure_verification_channel(self) -> None:
        """Ensure the photo-verification channel exists under LLAMA LLAMA CLUB category."""
        try:
            guild = self.get_guild(int(self.settings.discord_guild_id))
            if not guild:
                logger.warning("Guild not found, cannot create verification channel")
                return

            # Check if channel already exists
            existing_channel = discord.utils.get(guild.channels, name="photo-verification")
            if existing_channel:
                logger.info("Photo-verification channel already exists")
                return

            # Find the LLAMA LLAMA CLUB category
            category = discord.utils.get(guild.categories, id=1448815942435078355)
            if not category:
                logger.warning("LLAMA LLAMA CLUB category not found")
                return

            # Create the channel
            channel = await guild.create_text_channel(
                name="photo-verification",
                category=category,
                topic="AI-powered photo verification - upload photos and generate verification images"
            )
            logger.info(f"Created photo-verification channel: {channel.id}")

        except Exception as e:
            logger.error(f"Failed to create verification channel: {e}")


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





