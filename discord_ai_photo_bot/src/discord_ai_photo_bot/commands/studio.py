"""Premium /studio flow for photorealistic identity training + generation.

This module intentionally bypasses payments for now (free testing mode).
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import tempfile
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


MIN_REFS = 8
MAX_REFS = 20
DEFAULT_PACK_COUNT = 40


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
    """Validate + crop a reference image.

    Returns (accepted, reason). On accept, writes a processed image to dst_path.
    """
    try:
        img = cv2.imread(str(src_path))
        if img is None:
            return False, "unreadable image"
        h, w = img.shape[:2]
        if w < 768 or h < 768:
            return False, "resolution too low (min 768px)"
        bbox = _detect_largest_face_bbox(img)
        if not bbox:
            return False, "no face detected"

        x, y, bw, bh = bbox
        # Expand the face box to include head/shoulders
        pad = int(max(bw, bh) * 0.8)
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + bw + pad)
        y1 = min(h, y + bh + int(pad * 0.8))

        cropped = img[y0:y1, x0:x1]
        if cropped.size == 0:
            return False, "bad crop"

        pil = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        pil = _center_crop_square(pil).resize((1024, 1024), Image.LANCZOS)
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        pil.save(dst_path, format="JPEG", quality=92, optimize=True)
        return True, "ok"
    except Exception as exc:  # noqa: BLE001
        logger.exception("Preprocess failed for %s: %s", src_path, exc)
        return False, "preprocess error"


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
        label="Finish uploads & start training",
        style=discord.ButtonStyle.primary,
        custom_id="studio_start_training",
    )
    async def start_training(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog._start_training(interaction, self.session_id)

    @discord.ui.button(
        label="Generate pack (40)",
        style=discord.ButtonStyle.success,
        custom_id="studio_generate_pack",
    )
    async def generate_pack(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ) -> None:
        await self.cog._generate_pack(interaction, self.session_id, DEFAULT_PACK_COUNT)

    @discord.ui.button(
        label="Cancel session",
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

    @app_commands.command(
        name="studio",
        description="Start a premium photo studio session (upload 10–20 refs, train, generate).",
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
            title="AI Photo Studio • Session Dashboard",
            description=(
                f"Thread: {thread.mention}\n\n"
                f"Upload **{MIN_REFS}–{MAX_REFS}** photos of the same person.\n"
                "Best results: 10–20 clear, well-lit photos with different angles.\n\n"
                "**Rules**\n"
                "- No filters, no group photos\n"
                "- Face visible, good lighting\n"
                "- You must have permission to use these photos"
            ),
            color=discord.Color.from_rgb(138, 43, 226),
        )
        embed.add_field(name="Status", value="Waiting for uploads…", inline=False)
        embed.add_field(name="Uploads", value="0 refs", inline=True)
        embed.add_field(name="Training", value="Not started", inline=True)
        embed.add_field(name="Generation", value="Not started", inline=True)
        embed.set_footer(text="When ready, click “Finish uploads & start training”")

        view = StudioDashboardView(self, session_id=thread.id)
        msg = await thread.send(embed=embed, view=view)
        session.dashboard_message_id = msg.id

        await interaction.followup.send(
            f"Studio session created: {thread.mention}", ephemeral=True
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.attachments:
            return
        if not isinstance(message.channel, discord.Thread):
            return

        session = self._sessions_by_thread.get(message.channel.id)
        if not session:
            return
        if message.author.id != session.owner_user_id:
            return

        # Save attachments
        for att in message.attachments:
            if len(session.ref_paths) >= MAX_REFS:
                await message.reply(
                    f"Max {MAX_REFS} photos reached. Click “Finish uploads & start training”."
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
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed saving attachment: %s", exc)
                await message.reply(f"Failed saving `{att.filename}`")

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
        embed.add_field(name="Uploads", value=f"{uploads} refs", inline=True)
        embed.add_field(
            name="Training",
            value="Succeeded ✅" if session.trained_model else ("In progress…" if session.training_id else "Not started"),
            inline=True,
        )
        embed.add_field(name="Generation", value="Ready" if session.trained_model else "Locked", inline=True)
        await msg.edit(embed=embed, view=StudioDashboardView(self, session_id=session.thread_id))

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
            await interaction.followup.send(
                f"Not enough usable photos after validation ({accepted}/{MIN_REFS}). "
                "Upload clearer photos and try again.",
                ephemeral=True,
            )
            await self._update_dashboard(session, note="Validation failed ❌ (need more good refs)")
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
        self.db.upsert_training_job(
            training_id=training.id,
            user_id=str(session.owner_user_id),
            thread_id=str(session.thread_id),
            destination=destination,
            status=training.status,
        )

        asyncio.create_task(self._poll_training(session))

        summary = f"Accepted {accepted} refs. Rejected {len(rejected)}."
        await interaction.followup.send(f"Training started ✅ {summary}", ephemeral=True)

    async def _poll_training(self, session: StudioSession) -> None:
        # Poll status until finished
        try:
            while True:
                if not session.training_id:
                    return
                training = await self.workflow.get_training(session.training_id)
                self.db.update_training_status(training.id, training.status, training.error, training.logs)

                if training.status in ("succeeded", "failed", "canceled"):
                    if training.status == "succeeded":
                        # destination is persisted in db; set trained_model to destination for now
                        record = self.db.get_training_job(training.id)
                        if record:
                            session.trained_model = record["destination"]
                        await self._update_dashboard(session, note="Training succeeded ✅")
                        # notify thread
                        thread = self.bot.get_channel(session.thread_id)
                        if isinstance(thread, discord.Thread):
                            await thread.send("Training completed ✅ You can now click “Generate pack (40)”.")
                    else:
                        await self._update_dashboard(session, note=f"Training {training.status} ❌")
                        thread = self.bot.get_channel(session.thread_id)
                        if isinstance(thread, discord.Thread):
                            await thread.send(f"Training ended: **{training.status}**\n`{training.error or ''}`")
                    return

                await asyncio.sleep(15)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Training poll failed: %s", exc)

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

        self._sessions_by_thread.pop(session.thread_id, None)
        await interaction.followup.send("Session cancelled.", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    settings = getattr(bot, "settings", None)
    db = getattr(bot, "db", None)
    workflow = getattr(bot, "workflow", None)
    storage = getattr(bot, "storage", None)

    if not settings or not db or not workflow or not storage:
        raise RuntimeError("Bot missing required attributes for Studio cog")

    await bot.add_cog(Studio(bot, settings=settings, db=db, workflow=workflow, storage=storage))