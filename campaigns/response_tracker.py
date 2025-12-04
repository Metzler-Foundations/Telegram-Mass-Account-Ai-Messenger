"""
Response Tracker - Detect and track user responses to campaign messages.

Features:
- Listen for incoming messages
- Match responses to campaign sends
- Update delivery analytics
- Track response patterns
- Calculate response times
"""

import logging
import asyncio
from typing import Dict, Optional, Set
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import Message

logger = logging.getLogger(__name__)


class ResponseTracker:
    """Track user responses to campaign messages."""
    
    def __init__(self, campaign_manager, delivery_analytics):
        """
        Initialize response tracker.
        
        Args:
            campaign_manager: DMCampaignManager instance
            delivery_analytics: DeliveryAnalytics instance
        """
        self.campaign_manager = campaign_manager
        self.delivery_analytics = delivery_analytics
        self.is_running = False
        self._client: Optional[Client] = None
    
    async def start(self, client: Client):
        """
        Start tracking responses.
        
        Args:
            client: Pyrogram client to listen on
        """
        if self.is_running:
            return
        
        self._client = client
        self.is_running = True
        
        # Register message handler
        @client.on_message(filters.private & filters.incoming)
        async def handle_incoming_message(client: Client, message: Message):
            await self._process_incoming_message(message)
        
        logger.info("✅ Response tracker started")
    
    async def stop(self):
        """Stop tracking responses."""
        self.is_running = False
        logger.info("🛑 Response tracker stopped")
    
    async def _process_incoming_message(self, message: Message):
        """Process an incoming message to detect campaign responses."""
        if not message.from_user:
            return
        
        try:
            user_id = message.from_user.id
            
            # Check if this user was targeted by any active campaign
            campaign_user_mapping = await self._find_campaign_for_user(user_id)
            
            if campaign_user_mapping:
                for campaign_id, account_phone in campaign_user_mapping:
                    # Record response in delivery analytics
                    self.delivery_analytics.record_response(
                        campaign_id=campaign_id,
                        user_id=user_id,
                        replied_at=message.date or datetime.now()
                    )
                    
                    logger.info(
                        f"✓ Recorded response from user {user_id} "
                        f"to campaign {campaign_id} (sent from {account_phone})"
                    )
                    
                    # Also track in campaign manager if needed
                    # Update conversation analytics, etc.
                    
        except Exception as e:
            logger.error(f"Error processing incoming message for response tracking: {e}")
    
    async def _find_campaign_for_user(self, user_id: int) -> list:
        """
        Find which campaigns targeted this user.
        
        Args:
            user_id: User ID to search for
            
        Returns:
            List of (campaign_id, account_phone) tuples
        """
        try:
            import sqlite3
            results = []
            
            with sqlite3.connect(self.campaign_manager.db_path) as conn:
                conn.row_factory = sqlite3.Row
                
                # Find campaigns that sent to this user in last 7 days
                cutoff = datetime.now() - timedelta(days=7)
                
                cursor = conn.execute('''
                    SELECT DISTINCT campaign_id, account_phone
                    FROM campaign_messages
                    WHERE user_id = ? 
                    AND status = 'sent'
                    AND sent_at >= ?
                    AND sent_at IS NOT NULL
                ''', (user_id, cutoff))
                
                for row in cursor:
                    results.append((row['campaign_id'], row['account_phone']))
            
            return results
            
        except Exception as e:
            logger.error(f"Error finding campaign for user: {e}")
            return []


# Singleton
_response_tracker: Optional[ResponseTracker] = None


def get_response_tracker(campaign_manager=None, delivery_analytics=None) -> ResponseTracker:
    """Get singleton response tracker."""
    global _response_tracker
    if _response_tracker is None and campaign_manager and delivery_analytics:
        _response_tracker = ResponseTracker(campaign_manager, delivery_analytics)
    return _response_tracker





