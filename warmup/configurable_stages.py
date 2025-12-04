#!/usr/bin/env python3
"""Configurable warmup stages."""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class WarmupStageConfig:
    """Configuration for warmup stages."""
    
    DEFAULT_STAGES = [
        {
            'stage': 1,
            'name': 'Initial Activity',
            'duration_hours': 24,
            'actions_per_hour': 2,
            'action_types': ['view_profile', 'search']
        },
        {
            'stage': 2,
            'name': 'Light Engagement',
            'duration_hours': 48,
            'actions_per_hour': 5,
            'action_types': ['view_profile', 'search', 'join_channel']
        },
        {
            'stage': 3,
            'name': 'Group Participation',
            'duration_hours': 72,
            'actions_per_hour': 8,
            'action_types': ['view_profile', 'join_group', 'send_message']
        },
        {
            'stage': 4,
            'name': 'Active Messaging',
            'duration_hours': 96,
            'actions_per_hour': 12,
            'action_types': ['send_message', 'reply', 'forward']
        }
    ]
    
    def __init__(self, custom_stages: Optional[List[Dict]] = None):
        self.stages = custom_stages or self.DEFAULT_STAGES
    
    def get_stage(self, stage_number: int) -> Optional[Dict[str, Any]]:
        """Get configuration for specific stage."""
        for stage in self.stages:
            if stage['stage'] == stage_number:
                return stage
        return None
    
    def get_all_stages(self) -> List[Dict]:
        """Get all warmup stages."""
        return self.stages.copy()
    
    def update_stage(self, stage_number: int, updates: Dict):
        """Update stage configuration."""
        for stage in self.stages:
            if stage['stage'] == stage_number:
                stage.update(updates)
                logger.info(f"Updated warmup stage {stage_number}")
                return True
        return False


_warmup_config = None

def get_warmup_config():
    global _warmup_config
    if _warmup_config is None:
        _warmup_config = WarmupStageConfig()
    return _warmup_config

