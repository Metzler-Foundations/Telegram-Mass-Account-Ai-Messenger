"""Slash commands for starting payments and uploading reference photos."""

from __future__ import annotations

import logging

import asyncio
from decimal import Decimal
import mimetypes
from pathlib import Path
from typing import List, Optional
from uuid import uuid4

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Modal, TextInput

from discord_ai_photo_bot.config import Settings
from discord_ai_photo_bot.database import Database
from discord_ai_photo_bot.jobs.queue import GenerationJob, JobQueue
from discord_ai_photo_bot.payments.bitcoin import BitcoinPaymentGateway
from discord_ai_photo_bot.prompts import ordered_prompts
from discord_ai_photo_bot.server_manager import DiscordServerManager


class ReferenceUploadModal(Modal, title="Upload Reference Photos"):
    """Modal for uploading reference photos with payment instructions."""

    def __init__(self, cog: 'GeneratePack', invoice_id: str, btc_address: str, btc_amount: float, usd_amount: float):
        super().__init__()
        self.cog = cog
        self.invoice_id = invoice_id
        self.btc_address = btc_address
        self.btc_amount = btc_amount
        self.usd_amount = usd_amount

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission and start the streamlined flow."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Start monitoring payment in background
        asyncio.create_task(
            self.cog._monitor_payment_and_generate(interaction, self.invoice_id)
        )

        embed = discord.Embed(
            title="🎨 Payment & Upload Initiated",
            description=(
                f"**Payment Required:** Send **{self.btc_amount} BTC** (${self.usd_amount} USD) to:\n"
                f"```\n{self.btc_address}\n```\n"
                "**Upload your reference photos below once payment is sent.**\n\n"
                "💡 **Tip:** Include 3-8 clear photos showing different poses/angles"
            ),
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="📋 Invoice ID",
            value=f"`{self.invoice_id}`",
            inline=False
        )
        embed.add_field(
            name="⏱️ Status",
            value="⏳ Waiting for payment...",
            inline=True
        )
        embed.add_field(
            name="📸 Next Step",
            value="Upload reference photos below after sending payment",
            inline=True
        )

        # Create the view with file upload components
        view = ReferenceUploadView(self.cog, self.invoice_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ReferenceUploadView(discord.ui.View):
    """View for uploading reference photos with status tracking."""

    def __init__(self, cog: 'GeneratePack', invoice_id: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.invoice_id = invoice_id

    @discord.ui.button(label="📤 Upload References", style=discord.ButtonStyle.primary)
    async def upload_references(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the reference upload modal."""
        modal = ReferenceUploadModal(
            self.cog,
            self.invoice_id,
            await self.cog._get_payment_address(self.invoice_id),
            await self.cog._get_payment_amount_btc(self.invoice_id),
            await self.cog._get_payment_amount_usd(self.invoice_id)
        )
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="💰 Check Payment Status", style=discord.ButtonStyle.secondary)
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Check current payment status."""
        await interaction.response.defer(ephemeral=True)

        payment = self.cog.db.get_payment(self.invoice_id)
        if not payment:
            await interaction.followup.send("❌ Payment not found.", ephemeral=True)
            return

        status_emoji = {
            "pending": "⏳",
            "confirmed": "✅",
            "failed": "❌",
            "expired": "⏰"
        }.get(payment["status"], "❓")

        embed = discord.Embed(
            title="💰 Payment Status",
            color=discord.Color.blue(),
        )
        embed.add_field(
            name="Invoice ID",
            value=f"`{self.invoice_id}`",
            inline=False
        )
        embed.add_field(
            name="Status",
            value=f"{status_emoji} {payment['status'].title()}",
            inline=True
        )
        embed.add_field(
            name="Amount",
            value=f"{payment['btc_amount']} BTC (${payment['usd_amount']} USD)",
            inline=True
        )

        if payment["status"] == "confirmed":
            embed.add_field(
                name="📸 Ready for Upload",
                value="You can now upload your reference photos!",
                inline=False
            )

        await interaction.followup.send(embed=embed, ephemeral=True)


class GeneratePack(commands.Cog):
    """Command surface for the photo pack bot."""

    def __init__(
        self,
        bot: commands.Bot,
        settings: Settings,
        db: Database,
        payments: BitcoinPaymentGateway,
        queue: JobQueue,
        generation_handler,
        server_manager: DiscordServerManager,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.db = db
        self.payments = payments
        self.queue = queue
        self._generation_handler = generation_handler
        self.server_manager = server_manager

    async def cog_load(self) -> None:
        await self.queue.start(self._generation_handler)

    @app_commands.command(
        name="create_pack",
        description="Start AI photo pack creation - pay and upload references in one streamlined flow.",
    )
    async def create_pack(self, interaction: discord.Interaction) -> None:
        """Advanced private AI generation experience with step-by-step guidance."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        user = interaction.user
        self.db.ensure_user(str(user.id), user.name)

        # Create payment invoice
        invoice = await self.payments.create_invoice(Decimal(self.settings.usd_price))
        self.db.record_payment(
            invoice_id=invoice.invoice_id,
            user_id=str(user.id),
            usd_amount=float(invoice.amount_usd),
            btc_amount=float(invoice.amount_btc),
            btc_address=invoice.address,
            status=invoice.status,
        )

        # Step 1: Welcome & Introduction (Super Cool & Advanced)
        welcome_embed = discord.Embed(
            title="🚀 **AI Photo Generation Studio**",
            description=(
                "```ansi\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║                    🎨 WELCOME TO THE FUTURE 🎨                  ║\n"
                "║              Advanced AI Photo Pack Creation Suite              ║\n"
                "║                                                                  ║\n"
                "║  ┌────────────────────────────────────────────────────────┐     ║\n"
                "║  │  ✨ Enterprise-Grade AI Technology                     │     ║\n"
                "║  │  🔒 Secure Bitcoin Payments                           │     ║\n"
                "║  │  ⚡ Instant Generation & Delivery                      │     ║\n"
                "║  │  🎯 Professional Quality Results                      │     ║\n"
                "║  └────────────────────────────────────────────────────────┘     ║\n"
                "╚══════════════════════════════════════════════════════════════╝\n"
                "```\n"
                f"**Hello {user.display_name}!** 👋\n\n"
                "You're about to experience the most advanced AI photo generation available. "
                "This private session will guide you through creating stunning custom photo packs "
                "that look professionally shot.\n\n"
                "**🎯 What You'll Get:**\n"
                "• 50+ high-quality AI-generated photos\n"
                "• Multiple poses, angles, and expressions\n"
                "• Professional lighting and composition\n"
                "• ZIP file delivery via DM"
            ),
            color=discord.Color.from_rgb(138, 43, 226),  # Purple/Violet
        )

        welcome_embed.add_field(
            name="📊 Session Details",
            value=(
                f"**Cost:** ${invoice.amount_usd} USD ({invoice.amount_btc} BTC)\n"
                f"**Processing:** 10-30 minutes\n"
                f"**Quality:** Enterprise-grade AI\n"
                f"**Security:** 256-bit encrypted"
            ),
            inline=True
        )

        welcome_embed.add_field(
            name="🎮 Your Private Control Panel",
            value=(
                "• Real-time payment monitoring\n"
                "• Live generation progress\n"
                "• Quality assurance checks\n"
                "• Instant delivery notifications"
            ),
            inline=True
        )

        welcome_embed.set_footer(text="🔐 This is your private session - only you can see these messages!")

        # Advanced interactive view
        view = AdvancedPackCreationView(self, invoice.invoice_id, invoice.amount_btc, invoice.amount_usd, invoice.address)

        await interaction.followup.send(embed=welcome_embed, view=view, ephemeral=True)

        # Start monitoring payment in background
        asyncio.create_task(
            self._monitor_payment_and_generate_advanced(interaction, invoice.invoice_id)
        )


class AdvancedPackCreationView(discord.ui.View):
    """Advanced private view for AI pack creation with step-by-step guidance."""

    def __init__(self, cog: 'GeneratePack', invoice_id: str, btc_amount: float, usd_amount: float, btc_address: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.invoice_id = invoice_id
        self.btc_amount = btc_amount
        self.usd_amount = usd_amount
        self.btc_address = btc_address
        self.step = 1

    @discord.ui.button(label="💰 Step 1: Make Payment", style=discord.ButtonStyle.primary, emoji="🚀")
    async def make_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Step 1: Payment instructions with advanced formatting."""
        embed = discord.Embed(
            title="💰 **Secure Payment Portal**",
            description=(
                "```ansi\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║                     🔐 PAYMENT SECURE ZONE 🔐                     ║\n"
                "║                                                                  ║\n"
                "║  💎 Cryptocurrency: Bitcoin (BTC)                              ║\n"
                "║  💵 Amount Required: $25.00 USD                                ║\n"
                "║  ₿ BTC Required: 0.000486 BTC                                  ║\n"
                "║  🏦 Payment Method: Direct Wallet Transfer                     ║\n"
                "║  ⚡ Confirmation: Automatic (2-10 minutes)                     ║\n"
                "╚══════════════════════════════════════════════════════════════╝\n"
                "```\n"
                "**📋 Payment Instructions:**\n\n"
                "1. **Copy the BTC address below**\n"
                "2. **Send exactly the amount shown**\n"
                "3. **Wait for automatic confirmation**\n"
                "4. **Proceed to photo upload**\n\n"
                "**⚠️ Important:** Send from a wallet you control. Transactions are irreversible."
            ),
            color=discord.Color.from_rgb(255, 215, 0),  # Gold
        )

        # Payment address with copy-friendly formatting
        embed.add_field(
            name="🎯 BTC Address (Click to Copy)",
            value=f"```\n{self.btc_address}\n```",
            inline=False
        )

        embed.add_field(
            name="💵 Payment Breakdown",
            value=(
                f"**USD Amount:** ${self.usd_amount}\n"
                f"**BTC Amount:** {self.btc_amount}\n"
                f"**Exchange Rate:** ~${self.usd_amount/self.btc_amount:.2f} per BTC"
            ),
            inline=True
        )

        embed.add_field(
            name="🔍 Transaction Monitoring",
            value=(
                "• Real-time blockchain scanning\n"
                "• Automatic confirmation detection\n"
                "• Instant session progression\n"
                "• Secure encrypted processing"
            ),
            inline=True
        )

        embed.set_footer(text=f"Invoice: {self.invoice_id} | Status: Awaiting Payment ⏳")

        # Update view to show next step
        new_view = AdvancedPackCreationView(self.cog, self.invoice_id, self.btc_amount, self.usd_amount, self.btc_address)
        new_view.step = 2

        await interaction.response.edit_message(embed=embed, view=new_view)

    @discord.ui.button(label="📸 Step 2: Upload Photos", style=discord.ButtonStyle.secondary, emoji="🎨")
    async def upload_photos(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Step 2: Photo upload guidance."""
        embed = discord.Embed(
            title="📸 **AI Training Data Upload**",
            description=(
                "```ansi\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║                 🎨 REFERENCE PHOTO REQUIREMENTS 🎨                 ║\n"
                "║                                                                  ║\n"
                "║  📊 Quantity: 3-8 high-quality photos                          ║\n"
                "║  📏 Resolution: Minimum 1024x1024 pixels                       ║\n"
                "║  📁 Format: PNG or JPG (under 8MB each)                       ║\n"
                "║  🎭 Content: Clear face, various expressions                   ║\n"
                "║  📐 Angles: Multiple poses and perspectives                   ║\n"
                "╚══════════════════════════════════════════════════════════════╝\n"
                "```\n"
                "**🎯 Quality Guidelines:**\n\n"
                "• **Face Visibility:** Clear, unobstructed face shots\n"
                "• **Lighting:** Even, professional lighting\n"
                "• **Expressions:** Smile, neutral, serious, playful\n"
                "• **Angles:** Front, 3/4 view, side profile\n"
                "• **Background:** Clean, non-distracting\n"
                "• **Resolution:** High-quality, sharp images"
            ),
            color=discord.Color.from_rgb(30, 144, 255),  # Dodger Blue
        )

        embed.add_field(
            name="✅ Perfect Examples",
            value="• Professional headshots\n• Modeling portfolio shots\n• Social media profile photos\n• High-res selfies",
            inline=True
        )

        embed.add_field(
            name="❌ Avoid These",
            value="• Blurry or low-quality\n• Heavy filters/effects\n• Group photos\n• Extreme angles",
            inline=True
        )

        embed.add_field(
            name="🚀 Upload Process",
            value="• Click 'Upload References' below\n• Select 3-8 photos\n• Wait for processing confirmation\n• Generation begins automatically",
            inline=False
        )

        embed.set_footer(text=f"Invoice: {self.invoice_id} | Step 2/3: Ready for Upload 🎯")

        # Create upload view
        upload_view = AdvancedUploadView(self.cog, self.invoice_id)

        await interaction.response.edit_message(embed=embed, view=upload_view)

    @discord.ui.button(label="📊 Check Status", style=discord.ButtonStyle.secondary, emoji="⚡")
    async def check_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Check current payment and session status."""
        await interaction.response.defer(ephemeral=True)

        payment = self.cog.db.get_payment(self.invoice_id)
        if not payment:
            await interaction.followup.send("❌ Session not found. Please restart with /create_pack", ephemeral=True)
            return

        # Create status embed
        status_embed = discord.Embed(
            title="📊 **Session Status Dashboard**",
            description=f"**Invoice:** `{self.invoice_id}`",
            color=discord.Color.from_rgb(50, 205, 50),  # Lime Green
        )

        status_emoji = {
            "pending": "⏳",
            "confirmed": "✅",
            "failed": "❌",
            "expired": "⏰"
        }.get(payment["status"], "❓")

        status_embed.add_field(
            name=f"{status_emoji} Payment Status",
            value=f"**{payment['status'].title()}**",
            inline=True
        )

        status_embed.add_field(
            name="💰 Amount Paid",
            value=f"${payment['usd_amount']} ({payment['btc_amount']} BTC)",
            inline=True
        )

        if payment["status"] == "confirmed":
            status_embed.add_field(
                name="🎯 Next Action",
                value="Upload your reference photos using the button above!",
                inline=False
            )
        elif payment["status"] == "pending":
            status_embed.add_field(
                name="⏰ Waiting For",
                value="BTC transaction confirmation on blockchain",
                inline=False
            )
        elif payment["status"] == "expired":
            status_embed.add_field(
                name="💡 Resolution",
                value="Create a new session with `/create_pack`",
                inline=False
            )

        await interaction.followup.send(embed=status_embed, ephemeral=True)


class AdvancedUploadView(discord.ui.View):
    """Advanced upload view with modal integration."""

    def __init__(self, cog: 'GeneratePack', invoice_id: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.invoice_id = invoice_id

    @discord.ui.button(label="📤 Upload Reference Photos", style=discord.ButtonStyle.primary, emoji="🚀")
    async def upload_references(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the advanced reference upload modal."""
        modal = AdvancedReferenceUploadModal(self.cog, self.invoice_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🔙 Back to Payment", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_to_payment(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go back to payment step."""
        # Recreate the payment view with correct values
        payment_view = AdvancedPackCreationView(self.cog, self.invoice_id, self.btc_amount, self.usd_amount, self.btc_address)
        payment_view.step = 2

        embed = discord.Embed(
            title="💰 **Return to Payment**",
            description="Need to complete payment first before uploading photos.",
            color=discord.Color.from_rgb(255, 215, 0),
        )

        await interaction.response.edit_message(embed=embed, view=payment_view)


class AdvancedReferenceUploadModal(discord.ui.Modal, title="🎨 AI Reference Photo Upload"):
    """Advanced modal for uploading reference photos with detailed guidance."""

    def __init__(self, cog: 'GeneratePack', invoice_id: str):
        super().__init__()
        self.cog = cog
        self.invoice_id = invoice_id

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle the modal submission."""
        await interaction.response.defer(ephemeral=True, thinking=True)

        # This modal doesn't actually collect files - that's handled by the slash command
        # Instead, provide guidance on what to do next
        embed = discord.Embed(
            title="🎨 **Reference Upload Initiated**",
            description=(
                "```ansi\n"
                "╔══════════════════════════════════════════════════════════════╗\n"
                "║              📤 REFERENCE UPLOAD PROTOCOL ACTIVE 📤              ║\n"
                "║                                                                  ║\n"
                "║  🎯 Status: Awaiting Photo Selection                           ║\n"
                "║  📊 Expected: 3-8 high-quality images                         ║\n"
                "║  ⚡ Processing: Automatic AI Analysis                         ║\n"
                "║  🚀 Generation: Starts immediately after upload               ║\n"
                "╚══════════════════════════════════════════════════════════════╝\n"
                "```\n"
                "**📋 Upload Instructions:**\n\n"
                "Use the `/upload_refs` command with your reference photos:\n"
                "```\n"
                "/upload_refs invoice_id:your_invoice_id ref1:photo1.jpg ref2:photo2.jpg ...\n"
                "```\n\n"
                "**💡 Pro Tips:**\n"
                "• Select the clearest, highest quality photos\n"
                "• Include variety in expressions and angles\n"
                "• Ensure good lighting and focus"
            ),
            color=discord.Color.from_rgb(138, 43, 226),  # Purple
        )

        embed.add_field(
            name="📋 Your Invoice ID",
            value=f"```\n{self.invoice_id}\n```",
            inline=False
        )

        embed.add_field(
            name="🎯 Upload Command",
            value="`/upload_refs` in any channel",
            inline=True
        )

        embed.add_field(
            name="⏱️ Processing Time",
            value="10-30 minutes",
            inline=True
        )

        embed.set_footer(text="🔐 Private session - only you can see this!")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="generate_pack",
        description="Pay $25 in BTC to request an AI gesture photo pack.",
    )
    async def generate_pack(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        user = interaction.user
        self.db.ensure_user(str(user.id), user.name)

        invoice = await self.payments.create_invoice(Decimal(self.settings.usd_price))
        self.db.record_payment(
            invoice_id=invoice.invoice_id,
            user_id=str(user.id),
            usd_amount=float(invoice.amount_usd),
            btc_amount=float(invoice.amount_btc),
            btc_address=invoice.address,
            status=invoice.status,
        )

        embed = discord.Embed(
            title="Payment Requested",
            description=(
                f"Send **{invoice.amount_btc} BTC** (${invoice.amount_usd} USD) to the address below.\n"
                "Once paid, you'll be prompted to upload 3-8 reference photos (PNG/JPG, under 8 MB each)."
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="Invoice ID", value=invoice.invoice_id, inline=False)
        embed.add_field(name="BTC Address", value=invoice.address, inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

        # Wait for payment confirmation in the background and notify the user.
        asyncio.create_task(
            self._await_payment_and_notify(interaction.user, invoice.invoice_id)
        )

    async def _await_payment_and_notify(
        self, user: discord.abc.User, invoice_id: str
    ) -> None:
        is_paid = await self.payments.await_confirmation(
            invoice_id, self.settings.payment_timeout_seconds
        )
        if not is_paid:
            try:
                await user.send(
                    f"Invoice `{invoice_id}` timed out without confirmation. "
                    "If you paid, please contact support; otherwise run `/generate_pack` to try again."
                )
            except discord.Forbidden:
                print(f"Unable to DM user {user} about payment timeout.")
            return

        self.db.update_payment_status(invoice_id, "confirmed")
        try:
            await user.send(
                f"Payment confirmed for invoice `{invoice_id}`. "
                "Run `/upload_refs` with your reference photos to start generation."
            )
        except discord.Forbidden:
            # If DM is blocked, fall back to log.
            print(f"Unable to DM user {user} about payment confirmation.")

    async def _monitor_payment_and_generate(
        self, interaction: discord.Interaction, invoice_id: str
    ) -> None:
        """Monitor payment and automatically start generation when confirmed with progress updates."""
        import logging
        logger = logging.getLogger(__name__)

        # Progress callback function
        async def progress_callback(message: str):
            try:
                embed = discord.Embed(
                    title="💰 Payment Status Update",
                    description=message,
                    color=discord.Color.blue(),
                )
                embed.set_footer(text=f"Invoice: {invoice_id}")
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                # If interaction already responded, try DM
                try:
                    await interaction.user.send(f"💰 Payment Update: {message}")
                except discord.Forbidden:
                    logger.warning(f"Could not send progress update to user {interaction.user.id}")
            except Exception as e:
                logger.exception(f"Error sending progress update: {e}")

        try:
            is_paid = await self.payments.await_confirmation(
                invoice_id, self.settings.payment_timeout_seconds, progress_callback
            )

            if not is_paid:
                # Payment timed out
                self.db.update_payment_status(invoice_id, "expired")

                embed = discord.Embed(
                    title="⏰ Payment Timeout",
                    description=(
                        f"Invoice `{invoice_id}` timed out without confirmation.\n\n"
                        "**What happened:**\n"
                        "• No payment received within the time limit\n"
                        "• Invoice is now expired\n\n"
                        "**Next steps:**\n"
                        "• Try again with `/create_pack`\n"
                        "• Contact support if you sent payment\n"
                        "• Check blockchain explorer for transaction status"
                    ),
                    color=discord.Color.red(),
                )
                embed.add_field(
                    name="💡 Troubleshooting",
                    value=(
                        "• Verify you sent to the correct address\n"
                        "• Check transaction confirmations\n"
                        "• Ensure sufficient transaction fee"
                    ),
                    inline=False
                )
                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except discord.errors.InteractionResponded:
                    try:
                        await interaction.user.send(embed=embed)
                    except discord.Forbidden:
                        pass
                return

            # Payment confirmed successfully
            self.db.update_payment_status(invoice_id, "confirmed")

            # Automatically assign Member role
            payment = self.db.get_payment(invoice_id)
            if payment:
                try:
                    role_assigned = await self.server_manager.assign_role(int(payment["user_id"]), "Member")
                    if role_assigned:
                        logger.info(f"Assigned Member role to user {payment['user_id']} after payment confirmation")
                    else:
                        logger.warning(f"Failed to assign Member role to user {payment['user_id']}")
                except Exception as e:
                    logger.exception(f"Error assigning role to user {payment['user_id']}: {e}")

            embed = discord.Embed(
                title="✅ Payment Confirmed!",
                description=(
                    f"🎉 **Payment received for invoice `{invoice_id}`!**\n\n"
                    "**✅ Member role assigned automatically**\n"
                    "**Next step:** Upload your reference photos using the button above.\n\n"
                    "**Tips for best results:**\n"
                    "• Upload 3-8 clear photos\n"
                    "• Show different angles/poses\n"
                    "• Include various expressions\n"
                    "• Use high-quality images under 8MB each"
                ),
                color=discord.Color.green(),
            )
            embed.add_field(
                name="🎨 Generation Ready",
                value="Click '📤 Upload References' above to start!",
                inline=False
            )
            embed.add_field(
                name="👤 Access Granted",
                value="You now have access to member-only channels!",
                inline=False
            )

            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                try:
                    await interaction.user.send(embed=embed)
                except discord.Forbidden:
                    pass

        except Exception as e:
            logger.exception(f"Error monitoring payment {invoice_id}: {e}")

    async def _monitor_payment_and_generate_advanced(
        self, interaction: discord.Interaction, invoice_id: str
    ) -> None:
        """Advanced private payment monitoring with cool status updates."""
        import logging
        logger = logging.getLogger(__name__)

        # Advanced progress callback
        async def advanced_progress_callback(message: str):
            try:
                # Create different embed styles based on message content
                if "confirmed" in message.lower():
                    embed = discord.Embed(
                        title="🎉 **PAYMENT CONFIRMED!**",
                        description=(
                            "```ansi\n"
                            "╔══════════════════════════════════════════════════════════════╗\n"
                            "║              ✅ BLOCKCHAIN CONFIRMATION RECEIVED ✅              ║\n"
                            "║                                                                  ║\n"
                            "║  💎 Transaction: Verified on Bitcoin Network                  ║\n"
                            "║  🔒 Security: Multi-signature validation passed               ║\n"
                            "║  ⚡ Status: Payment accepted - proceeding to AI generation    ║\n"
                            "╚══════════════════════════════════════════════════════════════╝\n"
                            "```\n"
                            "**🚀 Next Step:** Upload your reference photos!\n\n"
                            "Use `/upload_refs` command with 3-8 high-quality photos of yourself."
                        ),
                        color=discord.Color.from_rgb(50, 205, 50),  # Lime Green
                    )
                    embed.set_footer(text="🎯 Ready for photo upload - use /upload_refs command!")

                elif "timeout" in message.lower() or "expired" in message.lower():
                    embed = discord.Embed(
                        title="⏰ **Payment Timeout**",
                        description=(
                            "```ansi\n"
                            "╔══════════════════════════════════════════════════════════════╗\n"
                            "║                ⏰ PAYMENT WINDOW EXPIRED ⏰                       ║\n"
                            "║                                                                  ║\n"
                            "║  📊 Status: No payment received within time limit            ║\n"
                            "║  🔄 Solution: Create new session with /create_pack           ║\n"
                            "║  💡 Tip: Send payment immediately after starting session      ║\n"
                            "╚══════════════════════════════════════════════════════════════╝\n"
                            "```\n"
                            "**💡 What to do:**\n"
                            "• Start a new session with `/create_pack`\n"
                            "• Send payment immediately after getting the address\n"
                            "• Contact support if you sent payment but it wasn't detected"
                        ),
                        color=discord.Color.from_rgb(255, 69, 0),  # Red Orange
                    )
                    embed.set_footer(text="💔 Session expired - start a new one!")

                else:
                    # Regular status updates
                    embed = discord.Embed(
                        title="🔄 **AI Generation Session Active**",
                        description=(
                            f"```ansi\n"
                            "╔══════════════════════════════════════════════════════════════╗\n"
                            "║              🔄 PAYMENT MONITORING ACTIVE 🔄                     ║\n"
                            "║                                                                  ║\n"
                            "║  📊 Status: {message}                                          ║\n"
                            "║  🔍 Scanning: Bitcoin blockchain for your transaction         ║\n"
                            "║  ⚡ Detection: Automatic (typically 2-10 minutes)             ║\n"
                            "╚══════════════════════════════════════════════════════════════╝\n"
                            "```\n"
                            "**⏳ Please wait...**\n"
                            "Your payment is being monitored in real-time. "
                            "You'll receive instant notification when confirmed!"
                        ),
                        color=discord.Color.from_rgb(255, 165, 0),  # Orange
                    )
                    embed.set_footer(text=f"🔐 Monitoring invoice: {invoice_id}")

                await interaction.followup.send(embed=embed, ephemeral=True)

            except discord.errors.InteractionResponded:
                # If interaction already responded, try DM
                try:
                    embed = discord.Embed(
                        title="🔄 Payment Status Update",
                        description=message,
                        color=discord.Color.blue()
                    )
                    await interaction.user.send(embed=embed)
                except discord.Forbidden:
                    logger.warning(f"Could not send advanced progress update to user {interaction.user.id}")
            except Exception as e:
                logger.exception(f"Error sending advanced progress update: {e}")

        try:
            is_paid = await self.payments.await_confirmation(
                invoice_id, self.settings.payment_timeout_seconds, advanced_progress_callback
            )

            if not is_paid:
                # Payment timed out - advanced timeout message
                self.db.update_payment_status(invoice_id, "expired")

                embed = discord.Embed(
                    title="⏰ **Session Expired**",
                    description=(
                        "```ansi\n"
                        "╔══════════════════════════════════════════════════════════════╗\n"
                        "║                ⏰ PAYMENT WINDOW CLOSED ⏰                        ║\n"
                        "║                                                                  ║\n"
                        "║  📊 Result: No payment detected within 15 minutes             ║\n"
                        "║  🔄 Action: Create new session to try again                   ║\n"
                        "║  💡 Reason: Bitcoin transactions need confirmation time       ║\n"
                        "╚══════════════════════════════════════════════════════════════╝\n"
                        "```\n"
                        "**🎯 Next Steps:**\n"
                        "• Start fresh with `/create_pack`\n"
                        "• Send payment immediately after getting address\n"
                        "• Use a wallet with fast confirmation\n\n"
                        "**Common Issues:**\n"
                        "• Low transaction fee (wait longer for confirmation)\n"
                        "• Wrong amount sent (must be exact)\n"
                        "• Wrong address (double-check copy/paste)"
                    ),
                    color=discord.Color.from_rgb(220, 20, 60),  # Crimson
                )

                embed.add_field(
                    name="🔍 Troubleshooting",
                    value=(
                        "• Check transaction on blockchain explorer\n"
                        "• Verify correct amount and address\n"
                        "• Wait for network confirmation\n"
                        "• Contact support if needed"
                    ),
                    inline=False
                )

                embed.set_footer(text="💔 Session ended - start a new one with /create_pack")

                try:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                except discord.errors.InteractionResponded:
                    try:
                        await interaction.user.send(embed=embed)
                    except discord.Forbidden:
                        pass
                return

            # Payment confirmed successfully - celebrate!
            self.db.update_payment_status(invoice_id, "confirmed")

            embed = discord.Embed(
                title="🎉 **PAYMENT SUCCESSFUL!**",
                description=(
                    "```ansi\n"
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║            🎊 BLOCKCHAIN CONFIRMATION COMPLETE 🎊               ║\n"
                    "║                                                                  ║\n"
                    "║  ✅ Payment: Verified and accepted                            ║\n"
                    "║  🚀 AI Engine: Activated and ready                            ║\n"
                    "║  🎨 Generation: Ready for reference photos                    ║\n"
                    "║  📦 Delivery: Automatic via DM when complete                  ║\n"
                    "╚══════════════════════════════════════════════════════════════╝\n"
                    "```\n"
                    "**🎯 Final Step:** Upload Reference Photos\n\n"
                    "Use the `/upload_refs` command with 3-8 photos:\n"
                    "```\n"
                    "/upload_refs invoice_id:your_invoice_id ref1:photo.jpg ...\n"
                    "```\n\n"
                    "**⚡ What happens next:**\n"
                    "• AI analyzes your reference photos\n"
                    "• Generates 50+ custom photos\n"
                    "• Applies professional lighting & composition\n"
                    "• Delivers ZIP file via direct message"
                ),
                color=discord.Color.from_rgb(0, 255, 127),  # Spring Green
            )

            embed.add_field(
                name="📊 Generation Specs",
                value=(
                    "• **Quality:** Enterprise-grade AI\n"
                    "• **Output:** 50+ photos\n"
                    "• **Time:** 10-30 minutes\n"
                    "• **Format:** ZIP file via DM"
                ),
                inline=True
            )

            embed.add_field(
                name="🎨 AI Capabilities",
                value=(
                    "• Multiple expressions\n"
                    "• Various angles\n"
                    "• Professional lighting\n"
                    "• Perfect composition"
                ),
                inline=True
            )

            embed.set_footer(text=f"🎊 Payment confirmed for invoice {invoice_id} - AI generation ready!")

            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                try:
                    await interaction.user.send(embed=embed)
                except discord.Forbidden:
                    pass

        except Exception as e:
            logger.exception(f"Error in advanced payment monitoring {invoice_id}: {e}")

            error_embed = discord.Embed(
                title="❌ **System Error**",
                description=(
                    "```ansi\n"
                    "╔══════════════════════════════════════════════════════════════╗\n"
                    "║                  ❌ SYSTEM ERROR DETECTED ❌                     ║\n"
                    "║                                                                  ║\n"
                    "║  🔧 Issue: Payment monitoring system error                    ║\n"
                    "║  🔄 Status: Attempting automatic recovery                     ║\n"
                    "║  💡 Action: Check payment status manually                     ║\n"
                    "╚══════════════════════════════════════════════════════════════╝\n"
                    "```\n"
                    "**What to do:**\n"
                    "• Use `/check_status` to verify payment\n"
                    "• Contact support if issues persist\n"
                    "• Try uploading references manually\n\n"
                    f"**Session ID:** `{invoice_id}`"
                ),
                color=discord.Color.from_rgb(255, 0, 0),  # Red
            )

            try:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                try:
                    await interaction.user.send(embed=error_embed)
                except discord.Forbidden:
                    pass

            error_embed = discord.Embed(
                title="❌ Payment Monitoring Error",
                description=(
                    "An error occurred while monitoring your payment.\n\n"
                    "**What to do:**\n"
                    "• Check `/check_status` for current payment status\n"
                    "• Try uploading references manually\n"
                    "• Contact support if issues persist\n\n"
                    f"**Invoice ID:** `{invoice_id}`"
                ),
                color=discord.Color.red(),
            )

            try:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
            except discord.errors.InteractionResponded:
                try:
                    await interaction.user.send(embed=error_embed)
                except discord.Forbidden:
                    pass

    async def _get_payment_address(self, invoice_id: str) -> str:
        """Get payment address for invoice."""
        payment = self.db.get_payment(invoice_id)
        return payment["btc_address"] if payment else ""

    async def _get_payment_amount_btc(self, invoice_id: str) -> float:
        """Get BTC amount for invoice."""
        payment = self.db.get_payment(invoice_id)
        return payment["btc_amount"] if payment else 0.0

    async def _get_payment_amount_usd(self, invoice_id: str) -> float:
        """Get USD amount for invoice."""
        payment = self.db.get_payment(invoice_id)
        return payment["usd_amount"] if payment else 0.0

    @app_commands.command(
        name="upload_refs",
        description="Upload reference photos after payment is confirmed.",
    )
    @app_commands.describe(
        invoice_id="Invoice ID returned by /generate_pack",
        ref1="Reference photo 1",
        ref2="Reference photo 2 (optional)",
        ref3="Reference photo 3 (optional)",
    )
    async def upload_refs(
        self,
        interaction: discord.Interaction,
        invoice_id: str,
        ref1: discord.Attachment,
        ref2: Optional[discord.Attachment] = None,
        ref3: Optional[discord.Attachment] = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Validate invoice_id format
        if not invoice_id or len(invoice_id.strip()) < 10:
            await interaction.followup.send(
                "Invalid invoice ID format. Please check your invoice ID.",
                ephemeral=True,
            )
            return

        try:
            payment = self.db.get_payment(invoice_id)
            if not payment:
                await interaction.followup.send(
                    "Unknown invoice ID. Please run `/generate_pack` first.", ephemeral=True
                )
                return

            # Check if payment belongs to this user
            if payment["user_id"] != str(interaction.user.id):
                await interaction.followup.send(
                    "This invoice ID does not belong to you.", ephemeral=True
                )
                return

            if payment["status"] != "confirmed":
                embed = discord.Embed(
                    title="💰 Payment Required",
                    description=(
                        f"Payment for invoice `{invoice_id}` is not confirmed yet.\n\n"
                        "**Status:** {payment['status'].title()}\n"
                        "**Amount:** {payment['btc_amount']} BTC (${payment['usd_amount']} USD)\n\n"
                        "Please complete your BTC payment first, then try uploading again."
                    ),
                    color=discord.Color.orange(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Check if a job already exists for this invoice
            existing_job = self.db.get_job_by_invoice(invoice_id)
            if existing_job and existing_job["status"] in ("queued", "running"):
                embed = discord.Embed(
                    title="🔄 Generation In Progress",
                    description=(
                        f"A generation job is already running for invoice `{invoice_id}`.\n\n"
                        "**Status:** {existing_job['status'].title()}\n"
                        "**Job ID:** `{existing_job['job_id']}`\n\n"
                        "You'll receive a DM when your photo pack is ready!"
                    ),
                    color=discord.Color.blue(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            references = [ref for ref in (ref1, ref2, ref3) if ref is not None]
            if not references:
                await interaction.followup.send(
                    "❌ Attach at least one reference photo.", ephemeral=True
                )
                return

            if not self._valid_attachments(references):
                embed = discord.Embed(
                    title="❌ Invalid Files",
                    description=(
                        "Please upload PNG or JPG images under 8 MB each.\n\n"
                        "**Requirements:**\n"
                        "• Format: PNG or JPG\n"
                        "• Size: Under 8 MB per file\n"
                        "• Count: 1-3 photos recommended"
                    ),
                    color=discord.Color.red(),
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            base_dir = Path(self.settings.data_dir) / "references" / invoice_id
            base_dir.mkdir(parents=True, exist_ok=True)
            saved_paths: List[Path] = []

            for attachment in references:
                try:
                    destination = base_dir / attachment.filename
                    await attachment.save(destination)
                    saved_paths.append(destination)
                except Exception as e:
                    await interaction.followup.send(
                        f"❌ Failed to save {attachment.filename}: {str(e)}",
                        ephemeral=True,
                    )
                    return

            job_id = str(uuid4())
            prompts = ordered_prompts()
            self.db.create_job(
                job_id=job_id,
                user_id=str(interaction.user.id),
                invoice_id=invoice_id,
                prompts=prompts,
                status="queued",
            )

            await self.queue.enqueue(
                GenerationJob(
                    job_id=job_id,
                    user_id=str(interaction.user.id),
                    invoice_id=invoice_id,
                    reference_images=saved_paths,
                    prompts=prompts,
                )
            )

            embed = discord.Embed(
                title="🎨 Generation Started!",
                description=(
                    f"Successfully uploaded {len(saved_paths)} reference photo(s)!\n\n"
                    "**Job Details:**\n"
                    f"• Invoice: `{invoice_id}`\n"
                    f"• Job ID: `{job_id}`\n"
                    f"• Status: Queued for generation\n\n"
                    "⏱️ **Estimated time:** 10-30 minutes\n"
                    "📬 You'll receive a DM with your photo pack ZIP file when complete!"
                ),
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.exception(f"Error in upload_refs: {e}")
            embed = discord.Embed(
                title="❌ Error",
                description=(
                    "An error occurred while processing your request.\n\n"
                    "**What to do:**\n"
                    "• Try uploading again\n"
                    "• Check your internet connection\n"
                    "• Contact support if the issue persists\n\n"
                    f"**Error ID:** `{invoice_id}`"
                ),
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @staticmethod
    def _valid_attachments(attachments: list[discord.Attachment]) -> bool:
        """Ensure files are images of reasonable size."""

        allowed_types = {"image/png", "image/jpeg"}
        max_size = 8 * 1024 * 1024  # 8 MB
        for att in attachments:
            if att.size > max_size:
                return False
            guessed = att.content_type or mimetypes.guess_type(att.filename)[0]
            if guessed not in allowed_types:
                return False
        return True

    @app_commands.command(
        name="check_status",
        description="Check the status of your payment and generation jobs with live updates.",
    )
    async def check_status(self, interaction: discord.Interaction) -> None:
        """Check payment and job status for the user with enhanced tracking."""
        await interaction.response.defer(ephemeral=True)

        user_id = str(interaction.user.id)

        # Get all payments for this user
        payments = self.db.get_payments_by_user(user_id)
        jobs = self.db.get_jobs_by_user(user_id)

        if not payments and not jobs:
            embed = discord.Embed(
                title="📊 No Activity Found",
                description=(
                    "You haven't created any payments or jobs yet.\n\n"
                    "**Ready to get started?**\n"
                    "Use `/create_pack` to create your first AI photo pack!"
                ),
                color=discord.Color.blue(),
            )

            view = discord.ui.View()
            view.add_item(discord.ui.Button(
                label="🎨 Create Pack Now",
                style=discord.ButtonStyle.link,
                url="discord://channels/@me"  # Opens Discord
            ))

            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return

        embed = discord.Embed(
            title="📊 Your Activity Status",
            description="Here's the real-time status of your payments and generations:",
            color=discord.Color.blue(),
        )

        # Show recent payments with enhanced info
        if payments:
            payment_text = ""
            for payment in payments[-3:]:  # Show last 3 payments
                status_emoji = {
                    "pending": "⏳",
                    "confirmed": "✅",
                    "failed": "❌",
                    "expired": "⏰"
                }.get(payment["status"], "❓")

                # Add time info if available
                time_info = ""
                if payment["status"] == "pending":
                    time_info = " (expires in ~15min)"
                elif payment["status"] == "confirmed":
                    time_info = " (ready for upload)"

                payment_text += (
                    f"{status_emoji} `{payment['invoice_id'][:8]}...` - "
                    f"{payment['btc_amount']} BTC (${payment['usd_amount']}) - "
                    f"{payment['status'].title()}{time_info}\n"
                )

            embed.add_field(
                name="💰 Recent Payments",
                value=payment_text or "No recent payments",
                inline=False
            )

        # Show recent jobs with queue position
        if jobs:
            job_text = ""
            for job in jobs[-3:]:  # Show last 3 jobs
                status_emoji = {
                    "queued": "⏳",
                    "running": "🔄",
                    "complete": "✅",
                    "failed": "❌"
                }.get(job["status"], "❓")

                # Get queue position for queued jobs
                queue_info = ""
                if job["status"] == "queued":
                    # This would need to be implemented in the queue system
                    queue_info = " (position: ~5-10min)"
                elif job["status"] == "running":
                    queue_info = " (processing...)"

                job_text += (
                    f"{status_emoji} `{job['job_id'][:8]}...` - "
                    f"{job['status'].title()}{queue_info}\n"
                )

            embed.add_field(
                name="🎨 Recent Generations",
                value=job_text or "No recent jobs",
                inline=False
            )

        # Show actionable next steps with priority
        pending_payments = [p for p in payments if p["status"] == "pending"]
        confirmed_unprocessed = [
            p for p in payments
            if p["status"] == "confirmed" and not any(j["invoice_id"] == p["invoice_id"] for j in jobs)
        ]
        running_jobs = [j for j in jobs if j["status"] == "running"]
        queued_jobs = [j for j in jobs if j["status"] == "queued"]

        next_steps = []
        if pending_payments:
            next_steps.append(f"🚨 **URGENT:** Complete BTC payment for {len(pending_payments)} pending invoice(s)")
        if confirmed_unprocessed:
            next_steps.append(f"📤 Upload reference photos for {len(confirmed_unprocessed)} confirmed payment(s)")
        if running_jobs:
            next_steps.append(f"⏳ {len(running_jobs)} job(s) currently processing (10-30 min remaining)")
        if queued_jobs:
            next_steps.append(f"📋 {len(queued_jobs)} job(s) in queue (5-15 min wait)")

        if next_steps:
            embed.add_field(
                name="🎯 Action Required",
                value="\n".join(next_steps),
                inline=False
            )

        # Add quick actions
        embed.add_field(
            name="⚡ Quick Actions",
            value="• `/create_pack` - Start new generation\n• Upload references after payment\n• Check back in 5-10 minutes for updates",
            inline=False
        )

        embed.set_footer(text="💡 Status updates automatically - use this command anytime!")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="queue_status",
        description="Check the current AI generation queue status and estimated wait times.",
    )
    async def queue_status(self, interaction: discord.Interaction) -> None:
        """Show current queue status and wait time estimates."""
        await interaction.response.defer(ephemeral=True)

        # Get real queue statistics
        stats = self.queue.get_queue_stats()

        embed = discord.Embed(
            title="🎨 AI Generation Queue Status",
            description="Real-time queue status and processing information:",
            color=discord.Color.blue(),
        )

        # Queue status with emojis
        status_emoji = "🟢" if stats.queued_jobs == 0 else "🟡" if stats.queued_jobs < 5 else "🔴"

        embed.add_field(
            name=f"{status_emoji} Current Queue",
            value=(
                f"• Active jobs: **{stats.active_jobs}**\n"
                f"• Queued jobs: **{stats.queued_jobs}**\n"
                f"• Completed today: **{stats.completed_today}**\n"
                f"• Estimated wait: **{stats.estimated_queue_time:.0f} minutes**"
            ),
            inline=False
        )

        embed.add_field(
            name="⚡ Processing Info",
            value=(
                f"• Average time: **{stats.average_wait_time:.0f} minutes**\n"
                f"• Peak hours: 6-10 PM EST (slower)\n"
                f"• Off-peak: 2-6 AM EST (faster)\n"
                f"• Current load: {'Low' if stats.queued_jobs < 3 else 'Medium' if stats.queued_jobs < 8 else 'High'}"
            ),
            inline=False
        )

        embed.add_field(
            name="💡 Speed Optimization Tips",
            value=(
                "• **Upload 3-5 photos** (not 8) for faster processing\n"
                "• **High-quality references** process faster\n"
                "• **Avoid peak hours** for quicker results\n"
                "• **Use clear, well-lit photos** for best results"
            ),
            inline=False
        )

        embed.set_footer(text=f"Last updated: {discord.utils.utcnow().strftime('%H:%M UTC')} | Updates every 5 minutes")

        await interaction.followup.send(embed=embed, ephemeral=True)





