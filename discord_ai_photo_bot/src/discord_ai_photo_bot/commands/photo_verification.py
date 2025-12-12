"""Photo verification commands for Discord bot."""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import discord
import openai
from discord import app_commands
from discord.ext import commands
from PIL import Image

from discord_ai_photo_bot.config import Settings

logger = logging.getLogger(__name__)

VERIFICATION_ACTIONS = [
    "Touch Nose",
    "Wink Left Eye",
    "Smile Widely",
    "Raise Eyebrows",
    "Stick Out Tongue"
]


class PhotoVerification(commands.Cog):
    """Handles photo verification commands."""

    def __init__(self, bot: commands.Bot, settings: Settings) -> None:
        self.bot = bot
        self.settings = settings
        self.user_sessions: Dict[int, Dict] = {}
        self.openai_client = openai.OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.guide_view = GuideView(self)

    @app_commands.command(name="start", description="Start photo verification process")
    async def start_verification(self, interaction: discord.Interaction) -> None:
        """Start the photo verification process."""
        user_id = interaction.user.id

        # Check if user already has an active session
        if user_id in self.user_sessions:
            await interaction.response.send_message(
                "You already have an active verification session. Please complete it first.",
                ephemeral=True
            )
            return

        # Initialize session
        self.user_sessions[user_id] = {
            "images": [],
            "action": None,
            "temp_dir": tempfile.mkdtemp()
        }

        embed = discord.Embed(
            title="Photo Verification",
            description="Please upload 3-5 photos of the same person. All photos must be clear and show the person's face.",
            color=0x00ff00
        )
        embed.add_field(
            name="Requirements",
            value="- JPG or PNG format\n- Max 10MB per image\n- Face must be clearly visible\n- Same person in all photos",
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle image uploads for verification."""
        if message.author.bot or not message.attachments:
            return

        # Only process in DMs
        if message.channel.type != discord.ChannelType.private:
            return

        user_id = message.author.id
        if user_id not in self.user_sessions:
            return

        session = self.user_sessions[user_id]
        if len(session["images"]) >= 5:
            await message.reply("You have already uploaded the maximum of 5 images. Please wait for processing.")
            return

        for attachment in message.attachments:
            if not self._validate_image_attachment(attachment):
                await message.reply(f"Invalid image: {attachment.filename}. Please upload JPG or PNG files under 10MB.")
                continue

            # Download and validate image
            try:
                image_data = await attachment.read()
                image_path = Path(session["temp_dir"]) / f"{attachment.filename}"
                with open(image_path, "wb") as f:
                    f.write(image_data)

                # Check for face
                if not self._has_face(str(image_path)):
                    await message.reply(f"No face detected in {attachment.filename}. Please upload a clear photo of a face.")
                    image_path.unlink()
                    continue

                session["images"].append(str(image_path))
                await message.add_reaction("✅")

            except Exception as e:
                logger.error(f"Error processing image {attachment.filename}: {e}")
                await message.reply(f"Error processing {attachment.filename}. Please try again.")

        # Check if ready for action selection
        if len(session["images"]) >= 3:
            dm = await message.author.create_dm()
            await self._send_action_selection(dm, user_id)

    def _validate_image_attachment(self, attachment: discord.Attachment) -> bool:
        """Validate image attachment."""
        if attachment.size > 10 * 1024 * 1024:  # 10MB
            return False
        if attachment.content_type not in ["image/jpeg", "image/png"]:
            return False
        return True

    def _has_face(self, image_path: str) -> bool:
        """Check if image contains a face."""
        try:
            image = cv2.imread(image_path)
            if image is None:
                logger.warning(f"Failed to load image: {image_path}")
                return False

            logger.info(f"Image loaded: {image.shape}")
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
            faces = face_cascade.detectMultiScale(gray, 1.05, 3)
            logger.info(f"Faces detected: {len(faces)}")
            return len(faces) > 0
        except Exception as e:
            logger.error(f"Face detection error: {e}")
            return False

    async def _send_action_selection(self, channel: discord.TextChannel, user_id: int) -> None:
        """Send action selection buttons."""
        embed = discord.Embed(
            title="Choose Verification Action",
            description="Select the action you want the AI to generate for your photos:",
            color=0x00ff00
        )

        view = ActionSelectionView(self, user_id)
        await channel.send(embed=embed, view=view)

    async def _generate_verification_image(self, user_id: int, action: str) -> Optional[str]:
        """Generate verification image using AI."""
        session = self.user_sessions.get(user_id)
        if not session or not session["images"]:
            return None

        if not self.openai_client:
            return None

        try:
            # Analyze first image for description
            with open(session["images"][0], "rb") as f:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Describe this person's appearance in detail: age, gender, ethnicity, hair color/style, eye color, facial features, clothing if visible. Be very specific."},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{self._encode_image(f)}"}}
                            ]
                        }
                    ],
                    max_tokens=300
                )
                description = response.choices[0].message.content

            # Generate image with DALL-E
            prompt = f"A realistic photo of {description} performing the action: {action.lower()}. High quality, photorealistic, same person as in the reference."
            
            image_response = self.openai_client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1
            )

            image_url = image_response.data[0].url

            # Download the image
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url)
                image_path = Path(session["temp_dir"]) / f"generated_{action.lower().replace(' ', '_')}.png"
                with open(image_path, "wb") as f:
                    f.write(response.content)

            return str(image_path)

        except Exception as e:
            logger.error(f"AI generation error: {e}")
            return None

    def _encode_image(self, file) -> str:
        """Encode image to base64."""
        import base64
        return base64.b64encode(file.read()).decode('utf-8')

    async def send_guide_message(self) -> None:
        """Send the guide message with button to ai-model-creation channel."""
        try:
            guild = self.bot.get_guild(int(self.settings.discord_guild_id))
            if not guild:
                return
            channel = guild.get_channel(1448815945563902063)  # ai-model-creation
            if not channel:
                return

            embed = discord.Embed(
                title="AI Photo Verification",
                description="Click the button below to start the photo verification process. This will guide you through uploading photos and generating AI verification images.",
                color=0x00ff00
            )
            embed.add_field(
                name="Step-by-Step Process",
                value="1. Click 'Start Photo Verification'\n2. Upload 3-5 clear photos of the same person\n3. Wait for validation (face detection)\n4. Choose your verification action\n5. Receive AI-generated verification image",
                inline=False
            )
            embed.set_footer(text="All uploads are processed securely and deleted after use.")

            view = GuideView(self)
            await channel.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"Failed to send guide message: {e}")

    async def start_verification_process(self, interaction: discord.Interaction) -> None:
        """Start the verification process from button click."""
        user_id = interaction.user.id

        # Check if user already has an active session
        if user_id in self.user_sessions:
            await interaction.response.send_message(
                "You already have an active verification session. Please complete it first.",
                ephemeral=True
            )
            return

        # Initialize session
        self.user_sessions[user_id] = {
            "images": [],
            "action": None,
            "temp_dir": tempfile.mkdtemp()
        }

        # Create DM channel
        dm = await interaction.user.create_dm()

        embed = discord.Embed(
            title="Photo Verification Started",
            description="Please upload 3-5 photos of the same person. All photos must be clear and show the person's face.",
            color=0x00ff00
        )
        embed.add_field(
            name="Requirements",
            value="- JPG or PNG format\n- Max 10MB per image\n- Face must be clearly visible\n- Same person in all photos",
            inline=False
        )
        embed.add_field(
            name="Next Step",
            value="Upload your photos in this DM. The bot will validate and process them.",
            inline=False
        )

        await dm.send(embed=embed)
        await interaction.response.send_message("Check your DMs to continue the verification process!", ephemeral=True)

    async def _cleanup_session(self, user_id: int) -> None:
        """Clean up user session."""
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            temp_dir = Path(session["temp_dir"])
            try:
                for file in temp_dir.glob("*"):
                    file.unlink()
                temp_dir.rmdir()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
            del self.user_sessions[user_id]


class ActionSelectionView(discord.ui.View):
    """View for action selection buttons."""

    def __init__(self, cog: PhotoVerification, user_id: int) -> None:
        super().__init__(timeout=300)  # 5 minutes
        self.cog = cog
        self.user_id = user_id

        for action in VERIFICATION_ACTIONS:
            button = ActionButton(action, cog, user_id)
            self.add_item(button)

    async def on_timeout(self) -> None:
        """Handle timeout."""
        await self.cog._cleanup_session(self.user_id)


class ActionButton(discord.ui.Button):
    """Button for selecting verification action."""

    def __init__(self, action: str, cog: PhotoVerification, user_id: int) -> None:
        super().__init__(label=action, style=discord.ButtonStyle.primary)
        self.action = action
        self.cog = cog
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction) -> None:
        """Handle button click."""
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your verification session.", ephemeral=True)
            return

        await interaction.response.defer()

        # Disable all buttons
        for item in self.view.children:
            item.disabled = True
        await interaction.edit_original_response(view=self.view)

        # Generate image
        image_path = await self.cog._generate_verification_image(self.user_id, self.action)

        # Send to DM
        dm = await interaction.user.create_dm()
        if image_path:
            file = discord.File(image_path, filename=f"verification_{self.action.lower().replace(' ', '_')}.png")
            embed = discord.Embed(
                title=f"Verification: {self.action}",
                description="Here is your AI-generated verification image!",
                color=0x00ff00
            )
            await dm.send(embed=embed, file=file)
        else:
            await dm.send("Sorry, there was an error generating your verification image. Please try again.")

        # Cleanup
        await self.cog._cleanup_session(self.user_id)


class GuideView(discord.ui.View):
    """Persistent view for the guide message."""

    def __init__(self, cog: PhotoVerification):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Start Photo Verification", style=discord.ButtonStyle.primary, custom_id="start_verification")
    async def start_verification(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start the verification process."""
        await self.cog.start_verification_process(interaction)


async def setup(bot: commands.Bot) -> None:
    """Setup the cog."""
    # Get settings - assuming it's available in bot.settings
    settings = getattr(bot, 'settings', None)
    if settings:
        cog = PhotoVerification(bot, settings)
        await bot.add_cog(cog)
        
        # Send guide message to ai-model-creation channel
        await cog.send_guide_message()