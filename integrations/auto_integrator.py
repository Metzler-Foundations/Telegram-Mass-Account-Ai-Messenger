"""
Auto-Integrator - Automatically applies advanced features to campaigns.

This module wraps existing campaign functionality to automatically:
- Analyze target intelligence before sending
- Prioritize high-value users
- Optimize send timing
- Auto-engage in groups
- Track everything
"""

import logging
import asyncio
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class AutoIntegrator:
    """Automatically integrates advanced features into campaigns."""
    
    def __init__(self, features_manager):
        """Initialize auto-integrator.
        
        Args:
            features_manager: AdvancedFeaturesManager instance
        """
        self.features = features_manager
        self.enabled = True
        logger.info("🤖 Auto-Integrator initialized - features will apply automatically")
    
    async def enhance_campaign_targets(self, client, target_user_ids: List[int], 
                                      prioritize_by_value: bool = True,
                                      min_value_score: float = 30.0) -> List[int]:
        """Automatically analyze and prioritize campaign targets.
        
        Args:
            client: Pyrogram client
            target_user_ids: Original target list
            prioritize_by_value: Whether to sort by value score
            min_value_score: Minimum value score to include
            
        Returns:
            Enhanced and prioritized target list
        """
        if not self.enabled or not self.features or not self.features.intelligence:
            return target_user_ids
        
        try:
            logger.info(f"🤖 Auto-analyzing {len(target_user_ids)} campaign targets...")
            
            # Analyze all targets (batch process)
            intel_results = await self.features.intelligence.batch_analyze_users(
                client, 
                target_user_ids[:100],  # Limit to first 100 for speed
                deep_analysis=False,  # Quick analysis
                delay_range=(0.5, 1.0)  # Fast delays
            )
            
            # Filter by minimum value score
            qualified_users = [
                intel for intel in intel_results 
                if intel.value_score >= min_value_score
            ]
            
            if prioritize_by_value:
                # Sort by value score (highest first)
                qualified_users.sort(key=lambda x: x.value_score, reverse=True)
            
            # Get just the user IDs
            enhanced_ids = [intel.user_id for intel in qualified_users]
            
            # Add remaining unanalyzed targets
            analyzed_ids = {intel.user_id for intel in intel_results}
            remaining_ids = [uid for uid in target_user_ids if uid not in analyzed_ids]
            enhanced_ids.extend(remaining_ids)
            
            logger.info(f"✅ Campaign enhanced: {len(qualified_users)} high-value targets prioritized")
            
            return enhanced_ids
            
        except Exception as e:
            logger.warning(f"Auto-enhancement failed: {e}, using original targets")
            return target_user_ids
    
    async def auto_track_message_sent(self, user_id: int, message_text: str):
        """Automatically track message being sent.
        
        Args:
            user_id: Target user ID
            message_text: Message text
        """
        if not self.enabled or not self.features:
            return
        
        try:
            # Track with status intelligence
            if self.features.status_tracker:
                self.features.status_tracker.track_message_sent(
                    message_id=0,  # Will be set by actual send
                    chat_id=user_id,
                    user_id=user_id
                )
            
            # Log interaction
            if self.features.intelligence:
                self.features.intelligence.log_interaction(
                    user_id=user_id,
                    interaction_type="campaign_message",
                    metadata={'message_preview': message_text[:50]}
                )
        except Exception as e:
            logger.debug(f"Auto-tracking failed: {e}")
    
    async def auto_process_group_message(self, client, message):
        """Automatically process group messages for engagement.
        
        Args:
            client: Pyrogram client
            message: Message object
        """
        if not self.enabled or not self.features:
            return
        
        try:
            # Auto-engage if applicable
            if self.features.engagement:
                engaged = await self.features.engagement.process_message(client, message)
                if engaged:
                    logger.info(f"🎯 Auto-engaged with message in {message.chat.title}")
            
            # Track competitor if they're being monitored
            if self.features.competitor and message.from_user:
                await self.features.competitor.track_competitor_message(message)
            
            # Build relationship graph
            if self.features.relationships and message.from_user:
                self.features.relationships.analyze_message_for_relationships(message)
        
        except Exception as e:
            logger.debug(f"Auto-processing failed: {e}")
    
    def get_status(self) -> Dict:
        """Get auto-integrator status.
        
        Returns:
            Status dictionary
        """
        return {
            'enabled': self.enabled,
            'features_available': self.features is not None,
            'intelligence_active': bool(self.features and self.features.intelligence),
            'engagement_active': bool(self.features and self.features.engagement),
            'tracking_active': bool(self.features and self.features.status_tracker)
        }


# Singleton instance
_auto_integrator = None

def get_auto_integrator(features_manager=None):
    """Get or create auto-integrator instance.
    
    Args:
        features_manager: AdvancedFeaturesManager (required on first call)
        
    Returns:
        AutoIntegrator instance
    """
    global _auto_integrator
    
    if _auto_integrator is None and features_manager:
        _auto_integrator = AutoIntegrator(features_manager)
    
    return _auto_integrator

