"""
Advanced Features Manager - Unified interface for all advanced features.

This module provides a single point of integration for all advanced features,
making it easy to add them to your existing bot.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ai.competitor_intelligence import CompetitorIntelligence
from ai.conversation_analyzer import ConversationAnalyzer

# Import all advanced features
from ai.intelligence_engine import IntelligenceEngine, UserIntelligence
from ai.media_intelligence import MediaIntelligence
from ai.network_analytics import NetworkAnalytics
from ai.status_intelligence import StatusIntelligence
from anti_detection.shadowban_detector import ShadowBanDetector
from campaigns.engagement_automation import EngagementAutomation, EngagementRule, EngagementStrategy
from campaigns.intelligent_scheduler import IntelligentScheduler
from recovery.recovery_protocol import RecoveryProtocol
from scraping.group_discovery_engine import GroupDiscoveryEngine
from scraping.relationship_mapper import RelationshipMapper

logger = logging.getLogger(__name__)


class AdvancedFeaturesManager:
    """Unified manager for all advanced features."""

    def __init__(self, enabled_features: Optional[List[str]] = None):
        """Initialize advanced features manager.

        Args:
            enabled_features: List of features to enable. None = enable all.
                Options: 'intelligence', 'engagement', 'discovery', 'status',
                        'shadowban', 'recovery', 'network', 'competitor', 'media',
                        'scheduler'
        """
        self.state_file = Path("advanced_features_state.json")
        state = self._load_state()

        self.enabled_features = (
            enabled_features
            or state.get("enabled_features")
            or [
                "intelligence",
                "engagement",
                "discovery",
                "status",
                "shadowban",
                "recovery",
                "network",
                "competitor",
                "media",
                "scheduler",
            ]
        )

        self.timezone_detection_error: Optional[str] = None
        self.timezone_preference = state.get("timezone") or self._load_timezone_preference()
        if not self.timezone_preference:
            try:
                timezone = datetime.now().astimezone().tzinfo
                self.timezone_preference = (
                    getattr(timezone, "key", None) or getattr(timezone, "zone", None) or "UTC"
                )
            except Exception as exc:
                self.timezone_preference = "UTC"
                self.timezone_detection_error = f"Failed to detect timezone automatically: {exc}"
                logger.warning(self.timezone_detection_error)
        if not self.timezone_detection_error and self.timezone_preference == "UTC":
            self.timezone_detection_error = "Timezone detection unavailable; defaulted to UTC"

        logger.info(f"Initializing Advanced Features Manager with: {self.enabled_features}")

        # Initialize systems with error handling
        try:
            self.intelligence = (
                IntelligenceEngine() if "intelligence" in self.enabled_features else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize IntelligenceEngine: {e}")
            self.intelligence = None

        try:
            self.engagement = (
                EngagementAutomation() if "engagement" in self.enabled_features else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize EngagementAutomation: {e}")
            self.engagement = None

        try:
            self.group_discovery = (
                GroupDiscoveryEngine() if "discovery" in self.enabled_features else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize GroupDiscoveryEngine: {e}")
            self.group_discovery = None

        try:
            self.status_tracker = (
                StatusIntelligence() if "status" in self.enabled_features else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize StatusIntelligence: {e}")
            self.status_tracker = None

        try:
            self.shadowban = ShadowBanDetector() if "shadowban" in self.enabled_features else None
        except Exception as e:
            logger.warning(f"Failed to initialize ShadowBanDetector: {e}")
            self.shadowban = None

        try:
            self.recovery = (
                RecoveryProtocol()
                if "recovery" in self.enabled_features or "shadowban" in self.enabled_features
                else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize RecoveryProtocol: {e}")
            self.recovery = None

        try:
            self.network = NetworkAnalytics() if "network" in self.enabled_features else None
        except Exception as e:
            logger.warning(f"Failed to initialize NetworkAnalytics: {e}")
            self.network = None

        try:
            self.competitor = (
                CompetitorIntelligence() if "competitor" in self.enabled_features else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize CompetitorIntelligence: {e}")
            self.competitor = None

        try:
            self.media = MediaIntelligence() if "media" in self.enabled_features else None
        except Exception as e:
            logger.warning(f"Failed to initialize MediaIntelligence: {e}")
            self.media = None

        try:
            self.scheduler = (
                IntelligentScheduler() if "scheduler" in self.enabled_features else None
            )
        except Exception as e:
            logger.warning(f"Failed to initialize IntelligentScheduler: {e}")
            self.scheduler = None

        try:
            self.conversation = ConversationAnalyzer()
        except Exception as e:
            logger.warning(f"Failed to initialize ConversationAnalyzer: {e}")
            self.conversation = None

        try:
            self.relationships = RelationshipMapper()
        except Exception as e:
            logger.warning(f"Failed to initialize RelationshipMapper: {e}")
            self.relationships = None

        logger.info("Advanced Features Manager initialized successfully")

    # === Intelligence Features ===

    async def analyze_user(
        self, client, user_id: int, deep: bool = False
    ) -> Optional[UserIntelligence]:
        """Analyze a user with intelligence engine.

        Args:
            client: Pyrogram client
            user_id: User ID to analyze
            deep: Perform deep analysis (includes common groups)

        Returns:
            UserIntelligence object or None
        """
        if not self.intelligence:
            return None

        return await self.intelligence.gather_user_intelligence(client, user_id, deep_analysis=deep)

    async def analyze_campaign_targets(self, client, user_ids: List[int]) -> List[UserIntelligence]:
        """Analyze campaign targets and return prioritized list.

        Args:
            client: Pyrogram client
            user_ids: List of user IDs

        Returns:
            List of UserIntelligence sorted by value score
        """
        if not self.intelligence:
            return []

        results = await self.intelligence.batch_analyze_users(client, user_ids, deep_analysis=True)
        return sorted(results, key=lambda x: x.value_score, reverse=True)

    def get_high_value_targets(
        self, min_score: float = 60.0, limit: int = 100
    ) -> List[UserIntelligence]:
        """Get high-value targets from intelligence database.

        Args:
            min_score: Minimum value score
            limit: Maximum number to return

        Returns:
            List of high-value users
        """
        if not self.intelligence:
            return []

        return self.intelligence.get_top_value_users(limit=limit, min_score=min_score)

    # === Engagement Features ===

    async def auto_engage_message(self, client, message) -> bool:
        """Automatically engage with a group message if appropriate.

        Args:
            client: Pyrogram client
            message: Message to process

        Returns:
            True if engaged
        """
        if not self.engagement:
            return False

        return await self.engagement.process_message(client, message)

    def setup_engagement_rule(
        self, name: str, strategy: str, target_groups: List[int] = None, keywords: List[str] = None
    ) -> Optional[EngagementRule]:
        """Setup an engagement automation rule.

        Args:
            name: Rule name
            strategy: 'conservative', 'moderate', 'aggressive', or 'targeted'
            target_groups: List of group IDs to target
            keywords: Keywords to match

        Returns:
            Created EngagementRule
        """
        if not self.engagement:
            return None

        strategy_map = {
            "conservative": EngagementStrategy.CONSERVATIVE,
            "moderate": EngagementStrategy.MODERATE,
            "aggressive": EngagementStrategy.AGGRESSIVE,
            "targeted": EngagementStrategy.TARGETED,
        }

        return self.engagement.create_smart_rule(
            name,
            strategy_map.get(strategy, EngagementStrategy.MODERATE),
            target_groups=target_groups or [],
            keywords=keywords or [],
        )

    def _load_state(self) -> Dict[str, Any]:
        try:
            if self.state_file.exists():
                data = self.state_file.read_text(encoding="utf-8")
                if data:
                    return json.loads(data)
        except Exception as exc:
            logger.debug(f"Failed to load advanced feature state: {exc}")
        return {}

    def _persist_state(self, payload: Dict[str, Any]):
        try:
            self.state_file.write_text(json.dumps(payload), encoding="utf-8")
        except Exception as exc:
            logger.debug(f"Failed to persist advanced feature state: {exc}")

    def persist_enabled_features(self, features: List[str]):
        """Persist enabled features selection for future launches."""
        self.enabled_features = features
        next_state = self._load_state()
        next_state["enabled_features"] = features
        if self.timezone_preference:
            next_state.setdefault("timezone", self.timezone_preference)
        self._persist_state(next_state)

    def _load_timezone_preference(self) -> Optional[str]:
        try:
            if self.state_file.exists():
                data = self.state_file.read_text(encoding="utf-8")
                if data:
                    payload = json.loads(data)
                    return payload.get("timezone")
        except Exception as exc:
            logger.debug(f"Failed to load timezone preference: {exc}")
        return None

    def _persist_timezone_preference(self, timezone_name: str):
        try:
            current_state = self._load_state()
            current_state["timezone"] = timezone_name
            if self.enabled_features:
                current_state.setdefault("enabled_features", self.enabled_features)
            self._persist_state(current_state)
            self.timezone_preference = timezone_name
        except Exception as exc:
            self.timezone_detection_error = f"Failed to persist timezone preference: {exc}"
            logger.warning(self.timezone_detection_error)

    def get_timezone_status(self) -> Dict[str, Any]:
        """Expose timezone preference and any detection errors for the UI layer."""
        return {
            "timezone": self.timezone_preference,
            "error": self.timezone_detection_error,
        }

    # === Status & Timing Features ===

    async def track_user_status(self, client, user_id: int):
        """Track user's online status.

        Args:
            client: Pyrogram client
            user_id: User ID to track
        """
        if not self.status_tracker:
            return

        await self.status_tracker.track_user_status(client, user_id)

    def get_best_send_time(self, user_id: int) -> Optional[datetime]:
        """Get optimal time to message a user.

        Args:
            user_id: User ID

        Returns:
            Optimal datetime or None
        """
        if not self.scheduler:
            return None

        tz_name = self.timezone_preference or "UTC"
        return_time = self.scheduler.schedule_optimal(user_id, "placeholder", tz_name)
        self._persist_timezone_preference(tz_name)
        return return_time

    def predict_online(self, user_id: int, hour: int, day: int) -> float:
        """Predict probability user is online at given time.

        Args:
            user_id: User ID
            hour: Hour of day (0-23)
            day: Day of week (0-6)

        Returns:
            Probability (0-1)
        """
        if not self.status_tracker:
            return 0.5

        return self.status_tracker.get_online_probability(user_id, hour, day)

    # === Shadow Ban & Recovery ===

    async def check_shadowban(self, client, account_id: str, canary_user_id: int) -> Dict:
        """Check if account is shadow banned.

        Args:
            client: Pyrogram client
            account_id: Account ID to check
            canary_user_id: Canary account user ID

        Returns:
            Status dictionary
        """
        if not self.shadowban:
            return {"status": "unknown"}

        await self.shadowban.test_delivery(client, account_id, canary_user_id)
        status = self.shadowban.get_account_status(account_id)

        return {
            "delivery_rate": status.get("delivery_rate", 1.0),
            "status": status.get("status", "clear"),
            "needs_recovery": status.get("status") in ["suspected", "likely", "confirmed"],
        }

    def initiate_recovery(self, account_id: str, severity: str = "moderate"):
        """Initiate recovery protocol for an account.

        Args:
            account_id: Account ID
            severity: 'mild', 'moderate', or 'severe'
        """
        if not self.recovery:
            return

        self.recovery.initiate_recovery(account_id, severity)

    def can_account_send(self, account_id: str) -> tuple:
        """Check if account can send messages.

        Returns:
            (can_send, reason) tuple
        """
        if not self.recovery:
            return (True, "No recovery system")

        return self.recovery.can_send_message(account_id)

    # === Group Discovery ===

    async def discover_groups(self, client, method: str, **kwargs) -> List:
        """Discover groups using various methods.

        Args:
            client: Pyrogram client
            method: 'nearby', 'common', 'invite'
            **kwargs: Method-specific parameters

        Returns:
            List of discovered groups
        """
        if not self.group_discovery:
            return []

        if method == "nearby":
            location = kwargs.get("location")
            return await self.group_discovery.discover_nearby_groups(client, location)
        elif method == "common":
            user_ids = kwargs.get("user_ids", [])
            return await self.group_discovery.discover_from_common_groups(client, user_ids)

        return []

    def get_best_groups(self, limit: int = 20, min_score: float = 60.0) -> List:
        """Get best quality discovered groups.

        Args:
            limit: Number to return
            min_score: Minimum quality score

        Returns:
            List of groups
        """
        if not self.group_discovery:
            return []

        return self.group_discovery.get_top_quality_groups(limit, min_score)

    # === Network Analytics ===

    def add_interaction(self, user_id_1: int, user_id_2: int, strength: float = 1.0):
        """Record an interaction between two users.

        Args:
            user_id_1: First user
            user_id_2: Second user
            strength: Interaction strength
        """
        if self.network:
            self.network.add_connection(user_id_1, user_id_2, strength)

        if self.relationships:
            self.relationships.add_relationship(user_id_1, user_id_2, "message", strength)

    def get_influencers(self, limit: int = 20) -> List:
        """Get most influential users in network.

        Args:
            limit: Number to return

        Returns:
            List of influential users
        """
        if not self.network:
            return []

        return self.network.get_top_influencers(limit)

    # === Competitor Intelligence ===

    def add_competitor(self, user_id: int, username: str = None) -> str:
        """Add a competitor to track.

        Args:
            user_id: Competitor user ID
            username: Competitor username

        Returns:
            Competitor ID
        """
        if not self.competitor:
            return ""

        return self.competitor.add_competitor(user_id, username)

    async def track_competitor(self, message):
        """Track competitor message.

        Args:
            message: Message object
        """
        if not self.competitor:
            return

        await self.competitor.track_competitor_message(message)

    # === Unified Analytics ===

    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall statistics from all systems.

        Returns:
            Dictionary with all stats
        """
        stats = {"timestamp": datetime.now().isoformat(), "enabled_features": self.enabled_features}

        if self.intelligence:
            stats["intelligence"] = self.intelligence.get_user_statistics()

        if self.engagement:
            stats["engagement"] = self.engagement.get_engagement_stats(24)

        if self.group_discovery:
            stats["discovery"] = self.group_discovery.get_discovery_stats()

        if self.status_tracker:
            stats["status"] = self.status_tracker.get_statistics()

        if self.network:
            stats["network"] = self.network.get_network_stats()

        return stats

    def log_status(self):
        """Log current status of all systems."""
        logger.info("=== Advanced Features Status ===")

        if self.intelligence:
            stats = self.intelligence.get_user_statistics()
            logger.info(f"Intelligence: {stats.get('total_users', 0)} users tracked")

        if self.engagement:
            stats = self.engagement.get_engagement_stats(24)
            logger.info(f"Engagement: {stats.get('total_reactions', 0)} reactions (24h)")

        if self.network:
            stats = self.network.get_network_stats()
            logger.info(
                f"Network: {stats.get('total_nodes', 0)} nodes, "
                f"{stats.get('total_connections', 0)} connections"
            )

        logger.info("================================")


# Singleton instance for easy access
_manager_instance = None


def get_features_manager(enabled_features: Optional[List[str]] = None) -> AdvancedFeaturesManager:
    """Get or create the features manager singleton.

    Args:
        enabled_features: List of features to enable (only on first call)

    Returns:
        AdvancedFeaturesManager instance
    """
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = AdvancedFeaturesManager(enabled_features)

    return _manager_instance
