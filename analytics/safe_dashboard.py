#!/usr/bin/env python3
"""Analytics dashboard with safe missing data handling."""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class SafeDashboard:
    """Analytics dashboard with graceful error handling."""
    
    @staticmethod
    def get_metric(data: Dict, key: str, default: Any = 0) -> Any:
        """Safely get metric with default."""
        try:
            keys = key.split('.')
            value = data
            for k in keys:
                value = value.get(k, default) if isinstance(value, dict) else default
            return value if value is not None else default
        except Exception as e:
            logger.warning(f"Failed to get metric {key}: {e}")
            return default
    
    @staticmethod
    def calculate_rate(numerator: int, denominator: int, default: float = 0.0) -> float:
        """Safely calculate rate."""
        try:
            if denominator == 0:
                return default
            return round((numerator / denominator) * 100, 2)
        except Exception as e:
            logger.error(f"Rate calculation failed: {e}")
            return default
    
    @staticmethod
    def aggregate_metrics(metrics_list: List[Dict]) -> Dict:
        """Aggregate metrics with error handling."""
        if not metrics_list:
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'rate': 0.0
            }
        
        try:
            total = sum(m.get('count', 0) for m in metrics_list)
            success = sum(m.get('success', 0) for m in metrics_list)
            failed = sum(m.get('failed', 0) for m in metrics_list)
            
            return {
                'total': total,
                'success': success,
                'failed': failed,
                'success_rate': SafeDashboard.calculate_rate(success, total)
            }
        except Exception as e:
            logger.error(f"Metric aggregation failed: {e}")
            return {'error': str(e)}


def safe_get_metric(data: Dict, key: str, default=0):
    """Get metric safely."""
    return SafeDashboard.get_metric(data, key, default)


