"""
UI Controller Layer - Mediates between UI and business logic.
"""
import logging
from typing import Dict, Any, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal

from core.services import BusinessLogicCoordinator
from core.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class UIController(QObject):
    """Controller that mediates between UI and business logic."""

    # Signals for UI updates
    campaign_created = pyqtSignal(dict)  # campaign_data
    campaign_updated = pyqtSignal(int, dict)  # campaign_id, stats
    account_status_changed = pyqtSignal(str, str)  # phone_number, status
    system_health_updated = pyqtSignal(dict)  # health_data
    error_occurred = pyqtSignal(str, str)  # error_type, details

    def __init__(self, db_path: str = "members.db"):
        super().__init__()
        self.business_logic = BusinessLogicCoordinator(db_path)

    # Campaign Operations
    def create_campaign(self, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new campaign through business logic."""
        try:
            result = self.business_logic.campaign_service.create_campaign(campaign_data)

            if result['success']:
                self.campaign_created.emit(result)
                logger.info(f"Campaign created successfully: {result['campaign_id']}")
            else:
                self.error_occurred.emit('campaign_validation', '; '.join(result['errors']))

            return result

        except Exception as e:
            logger.error(f"Error creating campaign: {e}")
            self.error_occurred.emit('campaign_creation', str(e))
            return {'success': False, 'errors': [str(e)]}

    def get_campaigns_overview(self) -> List[Dict[str, Any]]:
        """Get campaigns overview for UI display."""
        try:
            campaigns = self.business_logic.campaign_repo.get_all_campaigns()

            # Enrich with business logic insights
            for campaign in campaigns:
                optimization = self.business_logic.campaign_service.optimize_campaign_targeting(campaign['id'])
                campaign['optimization_score'] = optimization.get('optimization_score', 0)
                campaign['recommendations'] = optimization.get('recommendations', [])

            return campaigns

        except Exception as e:
            logger.error(f"Error getting campaigns overview: {e}")
            self.error_occurred.emit('data_access', str(e))
            return []

    def optimize_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """Optimize campaign targeting."""
        try:
            result = self.business_logic.campaign_service.optimize_campaign_targeting(campaign_id)

            if result['success']:
                # Emit optimization results
                self.campaign_updated.emit(campaign_id, {
                    'optimization_score': result['optimization_score'],
                    'recommendations': result['recommendations']
                })

            return result

        except Exception as e:
            logger.error(f"Error optimizing campaign {campaign_id}: {e}")
            return {'success': False, 'error': str(e)}

    # Account Operations
    def get_accounts_overview(self) -> List[Dict[str, Any]]:
        """Get accounts overview with health scores."""
        try:
            accounts = self.business_logic.account_repo.get_all_accounts()

            # Enrich with business logic health scores
            for account in accounts:
                health = self.business_logic.account_service.calculate_account_health_score(
                    account['phone_number']
                )
                account['health_score'] = health['health_score']
                account['health_issues'] = health['issues']
                account['can_send'] = self.business_logic.account_service.can_account_send_message(
                    account['phone_number']
                )['can_send']

            return accounts

        except Exception as e:
            logger.error(f"Error getting accounts overview: {e}")
            self.error_occurred.emit('data_access', str(e))
            return []

    def update_account_status(self, phone_number: str, status: str) -> bool:
        """Update account status through business logic."""
        try:
            success = self.business_logic.account_repo.update_account_status(phone_number, status)

            if success:
                self.account_status_changed.emit(phone_number, status)
                logger.info(f"Account {phone_number} status updated to {status}")
            else:
                self.error_occurred.emit('account_update', f"Failed to update account {phone_number}")

            return success

        except Exception as e:
            logger.error(f"Error updating account {phone_number}: {e}")
            self.error_occurred.emit('account_update', str(e))
            return False

    # Member Operations
    def get_members_for_campaign_ui(self, channel_id: str, criteria: Dict[str, Any]) -> Dict[str, Any]:
        """Get members for campaign with business logic filtering."""
        try:
            members = self.business_logic.member_service.filter_members_for_campaign(channel_id, criteria)
            metrics = self.business_logic.member_service.calculate_campaign_metrics(members)

            return {
                'success': True,
                'members': members,
                'metrics': metrics,
                'count': len(members)
            }

        except Exception as e:
            logger.error(f"Error getting members for campaign: {e}")
            return {
                'success': False,
                'error': str(e),
                'members': [],
                'metrics': {},
                'count': 0
            }

    # System Health Operations
    def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health overview."""
        try:
            health_data = self.business_logic.get_system_health_overview()
            self.system_health_updated.emit(health_data)
            return health_data

        except Exception as e:
            logger.error(f"Error getting system health: {e}")
            self.error_occurred.emit('system_health', str(e))
            return {'overall_health': 0, 'error': str(e)}

    # Validation Operations
    def validate_campaign_data(self, campaign_data: Dict[str, Any]) -> List[str]:
        """Validate campaign data using business rules."""
        return self.business_logic.campaign_service.validate_campaign_data(campaign_data)

    def validate_account_data(self, account_data: Dict[str, Any]) -> List[str]:
        """Validate account data using business rules."""
        return self.business_logic.account_service.validate_account_data(account_data)

    # Error Handling Integration
    def handle_error(self, error_type: str, details: str):
        """Handle errors with user-friendly messages."""
        self.error_occurred.emit(error_type, details)

    def show_error_dialog(self, error_type: str, details: str):
        """Show user-friendly error dialog."""
        ErrorHandler.show_error(None, error_type, details)
