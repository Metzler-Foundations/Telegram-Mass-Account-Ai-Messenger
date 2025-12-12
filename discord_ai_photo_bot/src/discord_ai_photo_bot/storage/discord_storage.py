"""Helpers to deliver generated images through Discord."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Iterable, Optional

import discord


class DiscordStorage:
    """Bundle generated assets and push them back to the user."""

    async def send_pack(
        self,
        channel: discord.abc.Messageable,
        file_paths: Iterable[Path],
        note: Optional[str] = None,
    ) -> None:
        """Zip files in-memory and send as a Discord attachment."""

        files_list = list(file_paths)
        if not files_list:
            await channel.send("No generated files to send.")
            return

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in files_list:
                archive.write(path, arcname=path.name)
        buffer.seek(0)

        await channel.send(
            content=note or "Here is your gesture photo pack.",
            file=discord.File(buffer, filename="ai_gesture_pack.zip"),
        )











