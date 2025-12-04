#!/usr/bin/env python3
"""Proxy configuration - timeouts and scoring."""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProxyConfig:
    """Configurable proxy settings."""
    
    DEFAULT_TIMEOUTS = {
        'connect_timeout': 10.0,
        'read_timeout': 30.0,
        'write_timeout': 30.0,
        'pool_timeout': 10.0
    }
    
    DEFAULT_SCORING = {
        'success_weight': 10,
        'failure_weight': -20,
        'timeout_weight': -15,
        'latency_threshold_ms': 1000,
        'min_score': -100,
        'max_score': 100
    }
    
    def __init__(self):
        self.timeouts = self.DEFAULT_TIMEOUTS.copy()
        self.scoring = self.DEFAULT_SCORING.copy()
    
    def set_timeout(self, timeout_type: str, value: float):
        """Set connection timeout."""
        if timeout_type in self.timeouts:
            self.timeouts[timeout_type] = value
            logger.info(f"Set {timeout_type} to {value}s")
        else:
            logger.warning(f"Unknown timeout type: {timeout_type}")
    
    def set_scoring_weight(self, weight_type: str, value: int):
        """Set scoring weight."""
        if weight_type in self.scoring:
            self.scoring[weight_type] = value
            logger.info(f"Set {weight_type} to {value}")
        else:
            logger.warning(f"Unknown weight type: {weight_type}")
    
    def calculate_proxy_score(self, proxy_stats: Dict) -> int:
        """Calculate proxy score based on statistics."""
        score = 0
        
        # Success rate
        successes = proxy_stats.get('successes', 0)
        failures = proxy_stats.get('failures', 0)
        timeouts = proxy_stats.get('timeouts', 0)
        
        score += successes * self.scoring['success_weight']
        score += failures * self.scoring['failure_weight']
        score += timeouts * self.scoring['timeout_weight']
        
        # Latency penalty
        avg_latency = proxy_stats.get('avg_latency_ms', 0)
        if avg_latency > self.scoring['latency_threshold_ms']:
            penalty = (avg_latency - self.scoring['latency_threshold_ms']) / 100
            score -= int(penalty)
        
        # Clamp score
        score = max(self.scoring['min_score'], min(score, self.scoring['max_score']))
        
        return score
    
    def get_timeout_config(self) -> Dict[str, float]:
        """Get timeout configuration."""
        return self.timeouts.copy()


_proxy_config = None

def get_proxy_config():
    global _proxy_config
    if _proxy_config is None:
        _proxy_config = ProxyConfig()
    return _proxy_config




