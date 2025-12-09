"""
Timezone Detector - Infer user timezone from activity patterns.

Features:
- Activity-based timezone inference
- Confidence scoring
- Multiple timezone candidates
"""

import logging
from typing import List, Tuple, Optional
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


class TimezoneDetector:
    """Detect user timezone from activity patterns."""

    @staticmethod
    def infer_timezone(
        activity_hours: List[int], confidence_threshold: float = 0.6
    ) -> Tuple[Optional[int], float]:
        """Infer timezone offset from activity hours.

        Args:
            activity_hours: List of hours when user was active (0-23)
            confidence_threshold: Minimum confidence to return result

        Returns:
            (timezone_offset, confidence) tuple
        """
        if not activity_hours:
            return None, 0.0

        # Typical active hours are 9-23 (9 AM to 11 PM)
        typical_waking_hours = list(range(9, 24))

        # Calculate average activity hour
        avg_hour = statistics.mean(activity_hours)

        # Assume average activity should be around 3 PM (15:00)
        target_hour = 15
        offset = int(target_hour - avg_hour)

        # Clamp offset to valid range
        offset = max(-12, min(14, offset))

        # Calculate confidence based on how well activities cluster
        hour_variance = statistics.variance(activity_hours) if len(activity_hours) > 1 else 0
        confidence = 1.0 / (1.0 + (hour_variance / 10.0))

        if confidence >= confidence_threshold:
            return offset, confidence

        return None, confidence
