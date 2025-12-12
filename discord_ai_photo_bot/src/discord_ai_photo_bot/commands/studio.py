"""Premium /studio flow for photorealistic identity training + generation.

This module intentionally bypasses payments for now (free testing mode).
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import tempfile
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image

from discord_ai_photo_bot.ai.generator import ReplicateLoraWorkflow
from discord_ai_photo_bot.config import Settings
from discord_ai_photo_bot.database import Database
from discord_ai_photo_bot.storage.discord_storage import DiscordStorage

logger = logging.getLogger(__name__)


MIN_REFS = 5
MAX_REFS = 15
DEFAULT_PACK_COUNT = 40

# Progress tracking constants
PROGRESS_UPDATE_INTERVAL = 30  # seconds
ESTIMATED_TRAINING_TIME = 480  # 8 minutes in seconds


@dataclass
class StudioSession:
    owner_user_id: int
    guild_id: int
    channel_id: int
    thread_id: int
    temp_dir: Path
    ref_paths: List[Path]
    dashboard_message_id: Optional[int] = None
    training_id: Optional[str] = None
    trained_model: Optional[str] = None  # typically "owner/name" on Replicate
    training_start_time: Optional[float] = None
    last_progress_update: Optional[float] = None
    progress_percentage: int = 0


def _sanitize_destination_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value[:48] or "user-model"


def _detect_largest_face_bbox(bgr_image) -> Optional[Tuple[int, int, int, int]]:
    """Return (x,y,w,h) for the largest detected face."""
    gray = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, 1.05, 3)
    if faces is None or len(faces) == 0:
        return None
    # pick largest area
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return int(x), int(y), int(w), int(h)


def _center_crop_square(img: Image.Image) -> Image.Image:
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return img.crop((left, top, left + side, top + side))


def _preprocess_reference_image(src_path: Path, dst_path: Path) -> Tuple[bool, str]:
    """Validate + crop a reference image with lenient requirements.

    Returns (accepted, reason). On accept, writes a processed image to dst_path.
    """
    try:
        img = cv2.imread(str(src_path))
        if img is None:
            return False, "unreadable image"
        h, w = img.shape[:2]

        # More lenient resolution requirements
        if w < 512 or h < 512:
            return False, "image too small (min 512px)"
        if w > 4096 or h > 4096:
            return False, "image too large (max 4096px)"

        # Try to detect face, but be more lenient
        bbox = _detect_largest_face_bbox(img)

        if bbox:
            # Face detected - crop around it
            x, y, bw, bh = bbox
            # Expand the face box to include head/shoulders
            pad = int(max(bw, bh) * 0.8)
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(w, x + bw + pad)
            y1 = min(h, y + bh + int(pad * 0.8))

            cropped = img[y0:y1, x0:x1]
            if cropped.size == 0:
                # Fallback to center crop if face crop fails
                pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
                pil = _center_crop_square(pil)
            else:
                pil = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        else:
            # No face detected - use center crop but still accept
            logger.warning("No face detected in %s, using center crop", src_path)
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            pil = _center_crop_square(pil)

        # Resize to standard size
        pil = pil.resize((1024, 1024), Image.LANCZOS)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        pil.save(dst_path, format="JPEG", quality=92, optimize=True)
        return True, "processed successfully"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Preprocess failed for %s: %s", src_path, exc)
        return False, "processing error - try a different image"

def _zip_dir(input_dir: Path) -> bytes:
    """Zip directory contents into bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(input_dir.glob("*")):
            if p.is_file():
                zf.write(p, arcname=p.name)
    buf.seek(0)
    return buf.read()


class StudioDashboardView(discord.ui.View):
    def __init__(self, cog: "Studio", session_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.session_id = session_id

    @discord.ui.button(
        label="📸 Finish uploads & start training",
        style=discord.ButtonStyle.primary,
        custom_id="studio_start_training",
    )
    async def start_training(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog._start_training(interaction, self.session_id)

    @discord.ui.button(
        label="🎨 Generate pack (40)",
        style=discord.ButtonStyle.success,
        custom_id="studio_generate_pack",
    )
    async def generate_pack(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog._generate_pack(interaction, self.session_id, DEFAULT_PACK_COUNT)

    @discord.ui.button(
        label="❓ Help & Tips",
        style=discord.ButtonStyle.secondary,
        custom_id="studio_help",
    )
    async def show_help(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        session = self.cog._sessions_by_thread.get(self.session_id)
        if not session:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return

        uploads = len(session.ref_paths)
        help_embed = discord.Embed(
            title="💡 AI Photo Studio Help",
            color=discord.Color.from_rgb(138, 43, 226),
        )

        if uploads < MIN_REFS:
            help_embed.description = f"**You have {uploads} photos uploaded**\n\n📸 **Next step:** Upload {MIN_REFS - uploads} more photos\n\n💡 **Tips:**\n• Use clear, well-lit photos\n• Show different angles\n• Make sure faces are visible\n• Avoid group photos"
        elif not session.training_id:
            help_embed.description = f"**Ready to train!** ({uploads} photos uploaded)\n\n🚀 **Click \"Finish uploads & start training\"**\n\n⏱️ **Training takes about 8 minutes**\n\n💡 **Pro tip:** You can leave and come back - your session is saved!"
        elif not session.trained_model:
            help_embed.description = f"**Training in progress...** ({session.progress_percentage}%)\n\n⏳ **This usually takes 6-10 minutes**\n\n💡 **Feel free to:**\n• Browse other channels\n• Grab a coffee\n• Come back when you get a notification"
        else:
            help_embed.description = "**Training complete!**\n\n🎨 **Click \"Generate pack (40)\" to create your AI photos**\n\n📩 **You'll receive a ZIP file via DM**\n\n💡 **What you get:** 40 unique AI-generated photos based on your reference images"

        await interaction.response.send_message(embed=help_embed, ephemeral=True)

    @discord.ui.button(
        label="❌ Cancel session",
        style=discord.ButtonStyle.danger,
        custom_id="studio_cancel_session",
    )
    async def cancel_session(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog._cancel_session(interaction, self.session_id)


class Studio(commands.Cog):
    """Premium guided studio flow in #photo-generation (thread-based)."""

    def __init__(
        self,
        bot: commands.Bot,
        settings: Settings,
        db: Database,
        workflow: ReplicateLoraWorkflow,
        storage: DiscordStorage,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.db = db
        self.workflow = workflow
        self.storage = storage

        self._sessions_by_thread: Dict[int, StudioSession] = {}

    async def _save_session(self, session: StudioSession) -> None:
        """Save session state to database for recovery."""
        try:
            # Save session metadata
            self.db.save_studio_session(
                thread_id=str(session.thread_id),
                user_id=str(session.owner_user_id),
                guild_id=str(session.guild_id),
                channel_id=str(session.channel_id),
                temp_dir=str(session.temp_dir),
                ref_paths=[str(p) for p in session.ref_paths],
                training_id=session.training_id,
                trained_model=session.trained_model,
                training_start_time=session.training_start_time,
                progress_percentage=session.progress_percentage,
                dashboard_message_id=session.dashboard_message_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to save session state: %s", exc)

    async def _load_session(self, thread_id: int) -> Optional[StudioSession]:
        """Load session state from database."""
        try:
            session_data = self.db.get_studio_session(str(thread_id))
            if not session_data:
                return None

            session = StudioSession(
                owner_user_id=int(session_data["user_id"]),
                guild_id=int(session_data["guild_id"]),
                channel_id=int(session_data["channel_id"]),
                thread_id=thread_id,
                temp_dir=Path(session_data["temp_dir"]),
                ref_paths=[Path(p) for p in session_data.get("ref_paths", [])],
                training_id=session_data.get("training_id"),
                trained_model=session_data.get("trained_model"),
                training_start_time=session_data.get("training_start_time"),
                progress_percentage=session_data.get("progress_percentage", 0),
                dashboard_message_id=session_data.get("dashboard_message_id"),
            )
            return session
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load session state: %s", exc)
            return None

    @app_commands.command(
        name="studio",
        description="Start a premium photo studio session (upload 5–15 refs, train, generate).",
    )
    async def studio(self, interaction: discord.Interaction) -> None:
        if not interaction.guild or not interaction.channel:
            await interaction.response.send_message(
                "Run this in the server inside #photo-generation.", ephemeral=True
            )
            return

        # Enforce channel name for now (premium vibe + containment)
        if interaction.channel.name != "photo-generation":
            await interaction.response.send_message(
                "Use this command in #photo-generation.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Check if user already has an active session
        existing_session = None
        for session in self._sessions_by_thread.values():
            if session.owner_user_id == interaction.user.id:
                existing_session = session
                break

        if existing_session:
            # Try to restore the existing session
            thread = self.bot.get_channel(existing_session.thread_id)
            if isinstance(thread, discord.Thread):
                await interaction.followup.send(
                    f"You already have an active session: {thread.mention}\n"
                    "Continue there or cancel it first to start a new one.",
                    ephemeral=True
                )
                return
            else:
                # Thread doesn't exist, clean up
                self._sessions_by_thread.pop(existing_session.thread_id, None)
                self.db.delete_studio_session(str(existing_session.thread_id))

        # Create a private thread (invitable=False means only people with access can view)
        thread = await interaction.channel.create_thread(
            name=f"studio-{interaction.user.name}-{interaction.user.id}",
            type=discord.ChannelType.private_thread,
            invitable=False,
            auto_archive_duration=1440,  # 24h
            reason="AI photo studio session",
        )

        temp_dir = Path(tempfile.mkdtemp(prefix="studio_"))
        session = StudioSession(
            owner_user_id=interaction.user.id,
            guild_id=interaction.guild.id,
            channel_id=interaction.channel.id,
            thread_id=thread.id,
            temp_dir=temp_dir,
            ref_paths=[],
        )
        self._sessions_by_thread[thread.id] = session

        embed = discord.Embed(
            title="🎨 AI Photo Studio • Session Started!",
            description=(
                f"**Your private thread:** {thread.mention}\n\n"
                f"📸 **Step 1:** Upload **{MIN_REFS}–{MAX_REFS}** photos of the same person\n"
                "💡 **Tips for best results:**\n"
                "• Clear, well-lit photos\n"
                "• Different angles & expressions\n"
                "• Face clearly visible\n"
                "• No heavy filters\n\n"
                "✅ **Step 2:** Click \"Finish uploads & start training\" when ready\n"
                "⏳ **Step 3:** Wait for AI training (about 8 minutes)\n"
                "🎉 **Step 4:** Generate your custom AI photos!\n\n"
                "*You own all generated images • Private session*"
            ),
            color=discord.Color.from_rgb(138, 43, 226),
        )
        embed.set_footer(text="💡 Click \"Help & Tips\" for guidance at any time")

        view = StudioDashboardView(self, session_id=thread.id)
        msg = await thread.send(embed=embed, view=view)
        session.dashboard_message_id = msg.id

        # Save session to database
        await self._save_session(session)

        await interaction.followup.send(
            f"🎨 Studio session created: {thread.mention}\n"
            f"Upload {MIN_REFS}-{MAX_REFS} photos there to get started!",
            ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.attachments:
            return
        if not isinstance(message.channel, discord.Thread):
            return

        session = self._sessions_by_thread.get(message.channel.id)

        # Try to load session from database if not in memory
        if not session:
            session = await self._load_session(message.channel.id)
            if session:
                self._sessions_by_thread[message.channel.id] = session
                # Resume training polling if training was in progress
                if session.training_id and not session.trained_model:
                    asyncio.create_task(self._poll_training(session))

        if not session:
            return
        if message.author.id != session.owner_user_id:
            return

        # Save attachments
        for att in message.attachments:
            if len(session.ref_paths) >= MAX_REFS:
                await message.reply(
                    f"Max {MAX_REFS} photos reached. Click **\"Finish uploads & start training\"**."
                )
                return
            if not (att.content_type or "").startswith("image/"):
                continue

            dst = session.temp_dir / "raw" / f"{len(session.ref_paths):02d}_{att.filename}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                await att.save(dst)
                session.ref_paths.append(dst)
                await message.add_reaction("✅")
                # Save session state after each upload
                await self._save_session(session)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed saving attachment: %s", exc)
                await message.reply(f"Failed saving `{att.filename}` - try uploading again")

        await self._update_dashboard(session)

    async def _update_dashboard(self, session: StudioSession, note: Optional[str] = None) -> None:
        thread = self.bot.get_channel(session.thread_id)
        if not isinstance(thread, discord.Thread):
            return
        if not session.dashboard_message_id:
            return

        try:
            msg = await thread.fetch_message(session.dashboard_message_id)
        except Exception:  # noqa: BLE001
            return

        embed = msg.embeds[0] if msg.embeds else discord.Embed(title="AI Photo Studio • Session Dashboard")
        # Update fields
        uploads = len(session.ref_paths)
        status = note or ("Ready to train ✅" if uploads >= MIN_REFS else "Waiting for uploads…")

        embed.clear_fields()
        embed.add_field(name="Status", value=status, inline=False)
        embed.add_field(name="Uploads", value=f"{uploads}/{MIN_REFS} refs", inline=True)

        # Enhanced training status with progress
        if session.trained_model:
            training_status = "Succeeded ✅"
        elif session.training_id:
            if session.progress_percentage > 0:
                training_status = f"In progress… {session.progress_percentage}%"
            else:
                training_status = "In progress…"
        else:
            training_status = "Not started"

        embed.add_field(name="Training", value=training_status, inline=True)
        embed.add_field(name="Generation", value="Ready" if session.trained_model else "Locked", inline=True)
        await msg.edit(embed=embed, view=StudioDashboardView(self, session_id=session.thread_id))

    async def _update_progress(self, session: StudioSession) -> None:
        """Update training progress with time-based estimation."""
        import time

        if not session.training_start_time:
            return

        elapsed = time.time() - session.training_start_time
        # Estimate progress based on elapsed time (training typically takes 6-10 minutes)
        estimated_progress = min(95, int((elapsed / ESTIMATED_TRAINING_TIME) * 100))

        # Only update if progress changed significantly or enough time has passed
        if (estimated_progress != session.progress_percentage and
            (not session.last_progress_update or
             time.time() - session.last_progress_update >= PROGRESS_UPDATE_INTERVAL)):

            session.progress_percentage = estimated_progress
            session.last_progress_update = time.time()

            progress_msg = f"Training in progress… {estimated_progress}% complete"
            if estimated_progress < 30:
                progress_msg += " (setting up model)"
            elif estimated_progress < 70:
                progress_msg += " (training in progress)"
            else:
                progress_msg += " (finalizing model)"

            await self._update_dashboard(session, progress_msg)

    async def _start_training(self, interaction: discord.Interaction, session_id: int) -> None:
        session = self._sessions_by_thread.get(session_id)
        if not session:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if interaction.user.id != session.owner_user_id:
            await interaction.response.send_message("This is not your session.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        if session.training_id or session.trained_model:
            await interaction.followup.send("Training already started for this session.", ephemeral=True)
            return

        if len(session.ref_paths) < MIN_REFS:
            await interaction.followup.send(
                f"Upload at least {MIN_REFS} photos before training.", ephemeral=True
            )
            return
        if len(session.ref_paths) > MAX_REFS:
            await interaction.followup.send(
                f"Please keep uploads under {MAX_REFS}.", ephemeral=True
            )
            return

        processed_dir = session.temp_dir / "processed"
        accepted = 0
        rejected: List[str] = []
        for idx, src in enumerate(session.ref_paths):
            dst = processed_dir / f"ref_{idx:02d}.jpg"
            ok, reason = _preprocess_reference_image(src, dst)
            if ok:
                accepted += 1
            else:
                rejected.append(f"{src.name}: {reason}")

        if accepted < MIN_REFS:
            helpful_tips = (
                f"💡 **Tips to fix this:**\n"
                f"• Upload more photos (you have {accepted} good ones, need {MIN_REFS})\n"
                f"• Make sure faces are clearly visible\n"
                f"• Use better lighting\n"
                f"• Try different angles\n"
                f"• Avoid heavy filters or group photos"
            )
            await interaction.followup.send(
                f"❌ Only {accepted} photos passed validation (need at least {MIN_REFS}).\n\n{helpful_tips}\n\n"
                f"Upload more photos to your thread and try again!",
                ephemeral=True,
            )
            await self._update_dashboard(session, note=f"❌ Need {MIN_REFS} good photos (have {accepted})")
            return

        dataset_zip_bytes = _zip_dir(processed_dir)
        dataset_zip_path = session.temp_dir / "dataset.zip"
        dataset_zip_path.write_bytes(dataset_zip_bytes)

        # Determine destination model name on Replicate (required)
        dest_owner = self.settings.replicate_destination_owner
        if not dest_owner:
            await interaction.followup.send(
                "Missing REPLICATE_DESTINATION_OWNER in env. Set it to your Replicate username.",
                ephemeral=True,
            )
            return
        dest_name = _sanitize_destination_name(f"{interaction.user.name}-{interaction.user.id}")
        destination = f"{dest_owner}/{dest_name}"

        await self._update_dashboard(session, note="Training starting…")

        try:
            training = await self.workflow.start_training(
                dataset_zip_path=dataset_zip_path,
                destination=destination,
                trigger_word=self.settings.replicate_trigger_word or "TOK",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Training start failed: %s", exc)
            await interaction.followup.send(f"Training failed to start: {exc}", ephemeral=True)
            await self._update_dashboard(session, note="Training failed ❌")
            return

        session.training_id = training.id
        session.training_start_time = time.time()
        session.progress_percentage = 0
        session.last_progress_update = time.time()

        self.db.upsert_training_job(
            training_id=training.id,
            user_id=str(session.owner_user_id),
            thread_id=str(session.thread_id),
            destination=destination,
            status=training.status,
        )

        await self._update_dashboard(session, "Training started… 0% complete")
        await self._save_session(session)  # Save session state
        asyncio.create_task(self._poll_training(session))

        summary = f"Accepted {accepted} refs. Rejected {len(rejected)}."
        await interaction.followup.send(f"Training started ✅ {summary}", ephemeral=True)

    async def _poll_training(self, session: StudioSession) -> None:
        # Poll status until finished
        try:
            while True:
                if not session.training_id:
                    return

                # Update progress before checking status
                await self._update_progress(session)

                training = await self.workflow.get_training(session.training_id)
                self.db.update_training_status(training.id, training.status, training.error, training.logs)

                if training.status in ("succeeded", "failed", "canceled"):
                    if training.status == "succeeded":
                        # destination is persisted in db; set trained_model to destination for now
                        record = self.db.get_training_job(training.id)
                        if record:
                            session.trained_model = record["destination"]
                        session.progress_percentage = 100
                        await self._update_dashboard(session, note="Training succeeded ✅")
                        # notify thread
                        thread = self.bot.get_channel(session.thread_id)
                        if isinstance(thread, discord.Thread):
                            await thread.send("🎉 Training completed! You can now click **\"Generate pack (40)\"** to create your AI photos.")
                    else:
                        await self._update_dashboard(session, note=f"Training {training.status} ❌")
                        thread = self.bot.get_channel(session.thread_id)
                        if isinstance(thread, discord.Thread):
                            error_msg = training.error or "Unknown error occurred"
                            await thread.send(f"❌ Training failed: **{training.status}**\n`{error_msg}`\n\n💡 Try uploading different photos or contact support if this persists.")
                    return

                await asyncio.sleep(15)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Training poll failed: %s", exc)
            await self._update_dashboard(session, note="Training error ❌")

    async def _generate_pack(self, interaction: discord.Interaction, session_id: int, count: int) -> None:
        session = self._sessions_by_thread.get(session_id)
        if not session:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if interaction.user.id != session.owner_user_id:
            await interaction.response.send_message("This is not your session.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        if not session.trained_model:
            await interaction.followup.send("Training must finish before generation.", ephemeral=True)
            return

        # Simple defaults; we’ll expand to presets later
        prompts = [
            f"Ultra photorealistic portrait photo of {self.settings.replicate_trigger_word or 'TOK'}; natural skin texture; realistic lighting; shallow depth of field"
            for _ in range(count)
        ]

        output_dir = session.temp_dir / "generated"
        output_dir.mkdir(parents=True, exist_ok=True)

        await self._update_dashboard(session, note="Generating…")

        try:
            paths = await self.workflow.generate_batch(
                trained_model=session.trained_model,
                prompts=prompts,
                output_dir=output_dir,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Generation failed: %s", exc)
            await interaction.followup.send(f"Generation failed: {exc}", ephemeral=True)
            await self._update_dashboard(session, note="Generation failed ❌")
            return

        # Deliver via DM
        try:
            user = await self.bot.fetch_user(session.owner_user_id)
            await self.storage.send_pack(
                channel=user,
                file_paths=paths,
                note="Your photo pack is ready.",
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("DM delivery failed: %s", exc)

        # Notify in thread
        thread = self.bot.get_channel(session.thread_id)
        if isinstance(thread, discord.Thread):
            await thread.send("Pack delivered via DM ✅")

        await interaction.followup.send("Delivered via DM ✅", ephemeral=True)
        await self._update_dashboard(session, note="Completed ✅ (delivered via DM)")

    async def _cancel_session(self, interaction: discord.Interaction, session_id: int) -> None:
        session = self._sessions_by_thread.get(session_id)
        if not session:
            await interaction.response.send_message("Session not found.", ephemeral=True)
            return
        if interaction.user.id != session.owner_user_id:
            await interaction.response.send_message("This is not your session.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        # Best-effort cleanup
        try:
            if session.temp_dir.exists():
                for p in session.temp_dir.rglob("*"):
                    try:
                        if p.is_file():
                            p.unlink()
                    except Exception:
                        pass
                for p in sorted(session.temp_dir.glob("**/*"), reverse=True):
                    try:
                        if p.is_dir():
                            p.rmdir()
                    except Exception:
                        pass
                try:
                    session.temp_dir.rmdir()
                except Exception:
                    pass
        except Exception:
            pass

        # Clean up from database
        self.db.delete_studio_session(str(session.thread_id))
        self._sessions_by_thread.pop(session.thread_id, None)
        await interaction.followup.send("Session cancelled and cleaned up.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    settings = getattr(bot, "settings", None)
    db = getattr(bot, "db", None)
    workflow = getattr(bot, "workflow", None)
    storage = getattr(bot, "storage", None)

    if not settings or not db or not workflow or not storage:
        raise RuntimeError("Bot missing required attributes for Studio cog")

    await bot.add_cog(Studio(bot, settings=settings, db=db, workflow=workflow, storage=storage))