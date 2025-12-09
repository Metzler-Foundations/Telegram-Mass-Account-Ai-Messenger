"""
Read Receipt Poller - Background task to poll and record message read receipts.

Features:
- Poll Telegram API for read receipts
- Update delivery analytics
- Batch processing for efficiency
- Configurable poll interval
"""

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class ReadReceiptPoller:
    """Poll for and record message read receipts."""

    def __init__(self, campaign_manager, delivery_analytics, poll_interval_minutes: int = 5):
        """
        Initialize read receipt poller.

        Args:
            campaign_manager: DMCampaignManager instance
            delivery_analytics: DeliveryAnalytics instance
            poll_interval_minutes: Minutes between polls
        """
        self.campaign_manager = campaign_manager
        self.delivery_analytics = delivery_analytics
        self.poll_interval = poll_interval_minutes * 60  # Convert to seconds
        self.is_running = False
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start polling for read receipts."""
        if self.is_running:
            return

        self.is_running = True
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info(f"✅ Read receipt poller started (interval: {self.poll_interval//60}min)")

    async def stop(self):
        """Stop polling."""
        self.is_running = False

        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        logger.info("🛑 Read receipt poller stopped")

    async def _poll_loop(self):
        """Main polling loop."""
        while self.is_running:
            try:
                await self._check_read_receipts()
                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Read receipt poll error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    async def _check_read_receipts(self):
        """Check for read receipts on recent messages."""
        try:
            # Get messages sent in last 24 hours that haven't been marked as read
            messages_to_check = self._get_unread_messages()

            if not messages_to_check:
                logger.debug("No messages to check for read receipts")
                return

            logger.info(f"Checking read receipts for {len(messages_to_check)} messages")

            # Get active clients from campaign manager's account manager
            if not hasattr(self.campaign_manager, "account_manager"):
                logger.debug("Account manager not available for read receipt checking")
                return

            account_manager = self.campaign_manager.account_manager
            if not account_manager or not hasattr(account_manager, "active_clients"):
                logger.debug("No active clients available for read receipt checking")
                return

            # Group messages by account for efficient checking
            messages_by_account = {}
            for msg in messages_to_check[:50]:  # Limit to 50 per cycle
                account_phone = msg["account_phone"]
                if account_phone not in messages_by_account:
                    messages_by_account[account_phone] = []
                messages_by_account[account_phone].append(msg)

            # Check read receipts for each account
            for account_phone, messages in messages_by_account.items():
                if account_phone not in account_manager.active_clients:
                    continue

                client = account_manager.active_clients[account_phone]
                pyrogram_client = client.client if hasattr(client, "client") else client

                if not pyrogram_client:
                    continue

                # Check each message
                for msg in messages[:10]:  # Limit per account
                    try:
                        user_id = msg["user_id"]
                        message_id = msg["message_id"]

                        # Get chat history to check message status
                        async for message in pyrogram_client.get_chat_history(user_id, limit=100):
                            if message.id == message_id:
                                # Check if message was read (outgoing messages show read status)
                                if hasattr(message, "read_date") and message.read_date:
                                    # Message was read!
                                    self.delivery_analytics.record_read_receipt(
                                        campaign_id=msg["campaign_id"],
                                        user_id=user_id,
                                        read_at=message.read_date,
                                    )
                                    logger.info(f"✓ Read receipt recorded for user {user_id}")
                                break

                        # Small delay to respect rate limits
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.debug(f"Error checking message {message_id}: {e}")

        except Exception as e:
            logger.error(f"Error checking read receipts: {e}")

    def _get_unread_messages(self, hours: int = 24) -> List[Dict]:
        """Get messages sent recently that haven't been marked as read."""
        try:
            cutoff = datetime.now() - timedelta(hours=hours)

            with sqlite3.connect(self.delivery_analytics.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT campaign_id, user_id, message_id, account_phone, sent_at
                    FROM delivery_events
                    WHERE sent_at >= ?
                    AND read_at IS NULL
                    AND status != 'failed'
                    ORDER BY sent_at DESC
                    LIMIT 100
                """,
                    (cutoff,),
                )

                return [dict(row) for row in cursor]

        except Exception as e:
            logger.error(f"Error getting unread messages: {e}")
            return []


# Singleton
_read_receipt_poller: Optional[ReadReceiptPoller] = None


def get_read_receipt_poller(campaign_manager=None, delivery_analytics=None) -> ReadReceiptPoller:
    """Get singleton read receipt poller."""
    global _read_receipt_poller
    if _read_receipt_poller is None and campaign_manager and delivery_analytics:
        _read_receipt_poller = ReadReceiptPoller(campaign_manager, delivery_analytics)
    return _read_receipt_poller
