#!/usr/bin/env python3
"""
System Integration - Unified interface for all REAL systems
Connects all modules with actual database and network operations
NO MOCK DATA - Everything is production-ready
"""

import logging
import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime

# Import all REAL modules
from database.database_queries import member_queries, campaign_queries, account_queries
from integrations.data_export import export_members_from_database, export_campaigns_from_database, export_accounts_from_database
from scraping.member_filter import show_filter_dialog
from campaigns.template_tester import test_template
from utils.progress_tracker import ProgressTracker, ProgressCallback
from recovery.resume_manager import check_for_incomplete_operations, show_resume_dialog, save_operation_checkpoint, clear_operation_checkpoint
from campaigns.campaign_tracker import save_campaign_message, update_campaign_status, initialize_campaign_database
from accounts.warmup_tracker import get_warmup_stats, update_warmup_progress, complete_warmup
from ui.analytics_dashboard import AnalyticsDashboard
from proxy.proxy_monitor import ProxyMonitorWidget
from utils.user_helpers import translate_error, get_progress_message, validate_config
from utils.retry_helper import RetryHelper, RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)


class SystemIntegration:
    """Unified integration layer for all REAL systems."""
    
    def __init__(self):
        """Initialize with REAL database connections."""
        self.member_queries = member_queries
        self.campaign_queries = campaign_queries
        self.account_queries = account_queries
        
        logger.info("✅ System integration initialized with REAL database connections")
    
    # ===== MEMBER MANAGEMENT (REAL) =====
    
    def get_members(self, filter_criteria: Dict = None) -> List[Dict]:
        """Get REAL members from database."""
        if filter_criteria:
            return self.member_queries.get_filtered_members(filter_criteria)
        return self.member_queries.get_all_members()
    
    def export_members(self, filter_criteria: Dict = None, format: str = "csv", file_path: str = None) -> bool:
        """Export REAL members to file."""
        return export_members_from_database(filter_criteria, format, file_path)
    
    def get_member_count(self, filter_criteria: Dict = None) -> int:
        """Get ACTUAL member count."""
        return self.member_queries.get_member_count(filter_criteria)
    
    def get_channels(self) -> List[Dict]:
        """Get REAL channels from database."""
        return self.member_queries.get_channels()
    
    # ===== CAMPAIGN MANAGEMENT (REAL) =====
    
    def get_campaigns(self) -> List[Dict]:
        """Get REAL campaigns from database."""
        return self.campaign_queries.get_all_campaigns()
    
    def get_campaign(self, campaign_id: int) -> Optional[Dict]:
        """Get specific REAL campaign."""
        return self.campaign_queries.get_campaign_by_id(campaign_id)
    
    def export_campaigns(self, format: str = "csv", file_path: str = None) -> bool:
        """Export REAL campaign data."""
        return export_campaigns_from_database(format, file_path)
    
    def track_campaign_message(self, campaign_id: int, user_id: int, account: str, 
                               status: str, error: str = None):
        """Track ACTUAL campaign message in database."""
        save_campaign_message(campaign_id, user_id, account, status, error)
    
    def update_campaign_status(self, campaign_id: int, status: str):
        """Update REAL campaign status."""
        update_campaign_status(campaign_id, status)
    
    # ===== ACCOUNT MANAGEMENT (REAL) =====
    
    def get_accounts(self) -> List[Dict]:
        """Get REAL accounts from database."""
        return self.account_queries.get_all_accounts()
    
    def get_account(self, phone_number: str) -> Optional[Dict]:
        """Get specific REAL account."""
        return self.account_queries.get_account_by_phone(phone_number)
    
    def export_accounts(self, format: str = "csv", file_path: str = None) -> bool:
        """Export REAL account data."""
        return export_accounts_from_database(format, file_path)
    
    def get_account_stats(self) -> Dict:
        """Get REAL account statistics."""
        return self.account_queries.get_account_stats()
    
    # ===== WARMUP MANAGEMENT (REAL) =====
    
    def get_warmup_stats(self) -> Dict:
        """Get REAL warmup statistics."""
        return get_warmup_stats()
    
    def update_warmup(self, phone_number: str, stage: str, progress: float,
                     next_action: str = None, next_action_time: str = None):
        """Update REAL warmup progress."""
        update_warmup_progress(phone_number, stage, progress, next_action, next_action_time)
    
    def complete_warmup(self, phone_number: str):
        """Complete warmup in REAL database."""
        complete_warmup(phone_number)
    
    # ===== ANALYTICS (REAL) =====
    
    def get_campaign_stats(self) -> Dict:
        """Get REAL campaign statistics."""
        return self.campaign_queries.get_campaign_stats()
    
    def get_realtime_metrics(self) -> Dict:
        """Get REAL-TIME metrics from database."""
        return {
            'members': self.member_queries.get_member_count(),
            'accounts': self.account_queries.get_account_stats(),
            'campaigns': self.campaign_queries.get_campaign_stats(),
            'warmup': get_warmup_stats()
        }
    
    # ===== OPERATIONS (REAL) =====
    
    def check_incomplete_operations(self) -> int:
        """Check for REAL incomplete operations."""
        return check_for_incomplete_operations()
    
from typing import Any

    def save_checkpoint(self, operation_id: str, operation_type: str,
                       current: int, total: int, details: Any = None):
        """Save REAL operation checkpoint."""
        save_operation_checkpoint(operation_id, operation_type, current, total, details)
    
    def clear_checkpoint(self, operation_id: str):
        """Clear REAL operation checkpoint."""
        clear_operation_checkpoint(operation_id)
    
    # ===== ERROR HANDLING (REAL) =====
    
    def handle_error(self, error: Exception, context: str = "") -> str:
        """Translate error to user-friendly message."""
        return translate_error(error, context)
    
    def validate_configuration(self, config: Dict) -> List[str]:
        """Validate configuration and return REAL errors."""
        return validate_config(config)
    
    # ===== ASYNC OPERATIONS WITH RETRY (REAL) =====
    
    async def execute_with_retry(self, func: Callable, context: str = "",
                                 max_attempts: int = 3, progress_callback: Callable = None):
        """Execute async function with REAL retry logic."""
        retry_config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=True
        )
        
        return await RetryHelper.retry_async(
            func,
            config=retry_config,
            progress_callback=progress_callback,
            context=context
        )


# Global integration instance
system_integration = SystemIntegration()


# Convenience functions for easy access
def get_members_real(filter_criteria: Dict = None) -> List[Dict]:
    """Get REAL members from database."""
    return system_integration.get_members(filter_criteria)


def get_campaigns_real() -> List[Dict]:
    """Get REAL campaigns from database."""
    return system_integration.get_campaigns()


def get_accounts_real() -> List[Dict]:
    """Get REAL accounts from database."""
    return system_integration.get_accounts()


def get_realtime_metrics() -> Dict:
    """Get REAL-TIME metrics."""
    return system_integration.get_realtime_metrics()


def export_data_real(data_type: str, filter_criteria: Dict = None, 
                    format: str = "csv", file_path: str = None) -> bool:
    """Export REAL data from database."""
    if data_type == "members":
        return system_integration.export_members(filter_criteria, format, file_path)
    elif data_type == "campaigns":
        return system_integration.export_campaigns(format, file_path)
    elif data_type == "accounts":
        return system_integration.export_accounts(format, file_path)
    else:
        logger.error(f"Unknown data type: {data_type}")
        return False

