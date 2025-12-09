"""
Timing Optimizer - ML-based send time optimization.

Features:
- Learn optimal send times from historical data
- Predict best messaging windows
- Adaptive learning from campaign results
- Timezone-aware scheduling
"""

import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TimingOptimizer:
    """ML-based timing optimization for messages."""

    def __init__(
        self, status_db: str = "status_intelligence.db", campaign_db: str = "campaigns.db"
    ):
        """Initialize timing optimizer.

        Args:
            status_db: Path to status intelligence database
            campaign_db: Path to campaigns database
        """
        self.status_db = status_db
        self.campaign_db = campaign_db

    def get_optimal_send_time(self, user_id: int) -> Optional[datetime]:
        """Get optimal send time for a user.

        Args:
            user_id: User ID

        Returns:
            Optimal datetime to send message
        """
        # Get user's typical online hours
        online_hours = self._get_typical_online_hours(user_id)
        if not online_hours:
            return None

        # Get user's best response hours from history
        best_response_hours = self._get_best_response_hours(user_id)

        # Combine signals
        if best_response_hours:
            # Weight response hours more heavily
            combined_scores = defaultdict(float)
            for hour in online_hours:
                combined_scores[hour] += 1.0
            for hour in best_response_hours:
                combined_scores[hour] += 2.0

            best_hour = max(combined_scores, key=combined_scores.get)
        else:
            best_hour = online_hours[0]

        # Calculate next occurrence of this hour
        now = datetime.now()
        target = now.replace(hour=best_hour, minute=random.randint(0, 59), second=0, microsecond=0)

        if target <= now:
            target += timedelta(days=1)

        return target

    def _get_typical_online_hours(self, user_id: int) -> List[int]:
        """Get user's typical online hours."""
        try:
            conn = sqlite3.connect(self.status_db)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT typical_online_hours FROM status_profiles WHERE user_id = ?
            """,
                (user_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                return json.loads(row[0])
            return []
        except Exception as e:
            logger.debug(f"Error getting online hours: {e}")
            return []

    def _get_best_response_hours(self, user_id: int) -> List[int]:
        """Get hours with best response rates."""
        try:
            conn = sqlite3.connect(self.status_db)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT hour_of_day, AVG(response_delay) as avg_delay, COUNT(*) as count
                FROM response_times
                WHERE user_id = ?
                GROUP BY hour_of_day
                HAVING count >= 3
                ORDER BY avg_delay ASC
                LIMIT 3
            """,
                (user_id,),
            )

            hours = [row[0] for row in cursor.fetchall()]
            conn.close()
            return hours
        except Exception as e:
            logger.debug(f"Error getting response hours: {e}")
            return []

    def batch_optimize_send_times(self, user_ids: List[int]) -> Dict[int, datetime]:
        """Optimize send times for multiple users.

        Args:
            user_ids: List of user IDs

        Returns:
            Dictionary mapping user_id to optimal send time
        """
        results = {}
        for user_id in user_ids:
            optimal_time = self.get_optimal_send_time(user_id)
            if optimal_time:
                results[user_id] = optimal_time
        return results


import random  # noqa: E402
