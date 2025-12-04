#!/usr/bin/env python3
"""Handle missing data gracefully in analytics dashboard."""

import logging
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MissingDataHandler:
    """Handles missing or incomplete data in analytics."""
    
    @staticmethod
    def fill_missing_dates(data: List[Dict], date_key: str = 'date', 
                          value_key: str = 'count', fill_value: Any = 0) -> List[Dict]:
        """Fill missing dates in time series data."""
        if not data:
            return []
        
        # Sort by date
        sorted_data = sorted(data, key=lambda x: x.get(date_key, ''))
        
        if len(sorted_data) < 2:
            return sorted_data
        
        # Fill gaps
        filled = []
        start = datetime.fromisoformat(sorted_data[0][date_key])
        end = datetime.fromisoformat(sorted_data[-1][date_key])
        
        current = start
        data_idx = 0
        
        while current <= end:
            date_str = current.isoformat()
            
            if data_idx < len(sorted_data) and sorted_data[data_idx][date_key] == date_str:
                filled.append(sorted_data[data_idx])
                data_idx += 1
            else:
                filled.append({date_key: date_str, value_key: fill_value})
            
            current += timedelta(days=1)
        
        return filled
    
    @staticmethod
    def get_with_default(data: Dict, key: str, default: Any = None) -> Any:
        """Get value with default fallback."""
        value = data.get(key, default)
        if value is None or value == '':
            return default
        return value
    
    @staticmethod
    def compute_missing_metrics(campaign_data: Dict) -> Dict:
        """Compute missing metrics from available data."""
        metrics = campaign_data.copy()
        
        # Compute delivery rate if missing
        if 'delivery_rate' not in metrics:
            sent = metrics.get('messages_sent', 0)
            delivered = metrics.get('messages_delivered', 0)
            if sent > 0:
                metrics['delivery_rate'] = (delivered / sent) * 100
            else:
                metrics['delivery_rate'] = 0.0
        
        # Compute response rate if missing
        if 'response_rate' not in metrics:
            delivered = metrics.get('messages_delivered', 0)
            responses = metrics.get('responses_received', 0)
            if delivered > 0:
                metrics['response_rate'] = (responses / delivered) * 100
            else:
                metrics['response_rate'] = 0.0
        
        # Add timestamps if missing
        if 'last_updated' not in metrics:
            metrics['last_updated'] = datetime.now().isoformat()
        
        return metrics


def handle_missing_data(data: Any, default: Any = None) -> Any:
    """General purpose missing data handler."""
    return data if data is not None else default

