"""Lightweight Bitcoin payment helper for invoice-style flows."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

import httpx

from discord_ai_photo_bot.config import Settings


@dataclass
class PaymentInvoice:
    """Represents a payment request to the user."""

    invoice_id: str
    address: str
    amount_btc: Decimal
    amount_usd: Decimal
    status: str = "pending"


class BitcoinPaymentGateway:
    """Responsible for quoting and verifying BTC payments."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._confirmed: set[str] = set()

    async def fetch_btc_price(self) -> Decimal:
        """Fetch BTC price in USD with retry logic."""

        urls = [
            self.settings.btc_price_api,
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            "https://api.coinbase.com/v2/exchange-rates?currency=BTC"
        ]

        last_error = None
        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()

                # Handle different API response formats
                if "bitcoin" in data and "usd" in data["bitcoin"]:
                    price = data["bitcoin"]["usd"]
                elif "data" in data and "rates" in data["data"] and "USD" in data["data"]["rates"]:
                    # Coinbase format
                    price = 1 / float(data["data"]["rates"]["USD"])
                else:
                    continue

                return Decimal(str(price))

            except Exception as e:
                last_error = e
                continue

        raise ValueError(f"Failed to fetch BTC price from all APIs. Last error: {last_error}")

    async def quote_amount(self, usd_amount: Decimal) -> Decimal:
        """Return BTC amount for the given USD value."""

        price_usd = await self.fetch_btc_price()
        btc_amount = usd_amount / price_usd
        return btc_amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)

    async def create_invoice(self, usd_amount: Decimal) -> PaymentInvoice:
        """Generate a payable invoice with a BTC amount."""

        btc_amount = await self.quote_amount(usd_amount)
        invoice_id = str(uuid.uuid4())
        address = self.settings.btc_receiver_address or "btc-address-not-configured"
        if not self.settings.btc_receiver_address:
            raise RuntimeError(
                "BTC_RECEIVER_ADDRESS missing. Provide a real address or integrate a "
                "payment backend to derive per-invoice addresses."
            )
        return PaymentInvoice(
            invoice_id=invoice_id,
            address=address,
            amount_btc=btc_amount,
            amount_usd=usd_amount,
        )

    async def await_confirmation(
        self, invoice_id: str, timeout_seconds: int, progress_callback: Optional[callable] = None
    ) -> bool:
        """Await confirmation signal with progress updates and better timeout handling."""

        waited = 0
        interval = 10  # Check every 10 seconds for better responsiveness
        max_consecutive_errors = 3
        consecutive_errors = 0

        while waited < timeout_seconds:
            try:
                if invoice_id in self._confirmed:
                    if progress_callback:
                        progress_callback(f"✅ Payment confirmed for {invoice_id}!")
                    return True

                # Send progress updates at key intervals
                if progress_callback:
                    remaining = timeout_seconds - waited
                    if remaining <= 60:  # Last minute
                        progress_callback(f"⏰ {remaining}s remaining - still waiting for payment...")
                    elif waited % 60 == 0 and waited > 0:  # Every minute
                        minutes_left = (timeout_seconds - waited) // 60
                        progress_callback(f"⏳ {minutes_left} minutes remaining - awaiting payment...")

                await asyncio.sleep(interval)
                waited += interval
                consecutive_errors = 0  # Reset error count on successful iteration

            except asyncio.CancelledError:
                # Handle cancellation gracefully
                if progress_callback:
                    progress_callback("❌ Payment monitoring cancelled")
                return False
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    if progress_callback:
                        progress_callback(f"❌ Too many errors monitoring payment: {e}")
                    return False
                # Continue waiting despite errors
                await asyncio.sleep(interval)
                waited += interval

        # Timeout reached
        if progress_callback:
            progress_callback(f"⏰ Payment timeout reached for invoice {invoice_id}")
        return False

    def mark_confirmed(self, invoice_id: str) -> None:
        """Mark an invoice as confirmed (e.g., from webhook)."""

        self._confirmed.add(invoice_id)






