"""
Unit tests for business logic services.
"""

import pytest
import sqlite3
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services import MemberService, CampaignService, AccountService, BusinessLogicCoordinator
from core.repositories import MemberRepository, CampaignRepository, AccountRepository


class TestMemberService:
    """Test cases for MemberService business logic."""

    @pytest.fixture
    def member_repo_mock(self):
        """Mock member repository."""
        mock_repo = Mock(spec=MemberRepository)
        return mock_repo

    @pytest.fixture
    def member_service(self, member_repo_mock):
        """Create MemberService with mocked repository."""
        return MemberService(member_repo_mock)

    def test_validate_member_for_campaign_success(self, member_service):
        """Test successful member validation for campaign."""
        member = {
            "profile_quality_score": 0.8,
            "messaging_potential_score": 0.7,
            "threat_score": 20,
        }
        criteria = {"max_risk": 50, "min_quality": 0.3, "min_potential": 0.5}

        result = member_service.validate_member_for_campaign(member, criteria)
        assert result is True

    def test_validate_member_for_campaign_too_risky(self, member_service):
        """Test member validation failure due to high risk."""
        member = {
            "profile_quality_score": 0.8,
            "messaging_potential_score": 0.7,
            "threat_score": 60,  # Above max_risk of 50
        }
        criteria = {"max_risk": 50, "min_quality": 0.3, "min_potential": 0.5}

        result = member_service.validate_member_for_campaign(member, criteria)
        assert result is False

    def test_validate_member_for_campaign_low_quality(self, member_service):
        """Test member validation failure due to low profile quality."""
        member = {
            "profile_quality_score": 0.2,  # Below min_quality of 0.3
            "messaging_potential_score": 0.7,
            "threat_score": 20,
        }
        criteria = {"max_risk": 50, "min_quality": 0.3, "min_potential": 0.5}

        result = member_service.validate_member_for_campaign(member, criteria)
        assert result is False

    def test_calculate_campaign_metrics(self, member_service):
        """Test campaign metrics calculation."""
        members = [
            {"profile_quality_score": 0.8, "messaging_potential_score": 0.7},
            {"profile_quality_score": 0.6, "messaging_potential_score": 0.8},
            {"profile_quality_score": 0.9, "messaging_potential_score": 0.6},
        ]

        metrics = member_service.calculate_campaign_metrics(members)

        assert metrics["total_members"] == 3
        assert (
            metrics["avg_profile_quality"] == 0.77
        )  # (0.8 + 0.6 + 0.9) / 3 = 0.7666... rounded to 0.77
        assert metrics["avg_messaging_potential"] == 0.7  # (0.7 + 0.8 + 0.6) / 3 = 0.7
        assert metrics["high_potential_count"] == 1  # 1 member with score >= 0.8 (member 2 has 0.8)
        assert (
            metrics["high_potential_percentage"] == 33.33
        )  # 1/3 * 100 = 33.333... rounded to 33.33


class TestCampaignService:
    """Test cases for CampaignService business logic."""

    @pytest.fixture
    def campaign_repo_mock(self):
        """Mock campaign repository."""
        mock_repo = Mock(spec=CampaignRepository)
        return mock_repo

    @pytest.fixture
    def member_service_mock(self):
        """Mock member service."""
        mock_service = Mock(spec=MemberService)
        return mock_service

    @pytest.fixture
    def campaign_service(self, campaign_repo_mock, member_service_mock):
        """Create CampaignService with mocked dependencies."""
        return CampaignService(campaign_repo_mock, member_service_mock)

    def test_validate_campaign_data_success(self, campaign_service):
        """Test successful campaign data validation."""
        campaign_data = {
            "name": "Test Campaign",
            "template": "Hello {first_name}!",
            "target_member_ids": [1, 2, 3],
            "account_ids": ["+1234567890"],
        }

        errors = campaign_service.validate_campaign_data(campaign_data)
        assert len(errors) == 0

    def test_validate_campaign_data_missing_name(self, campaign_service):
        """Test campaign validation failure due to missing name."""
        campaign_data = {
            "name": "",
            "template": "Hello {first_name}!",
            "target_member_ids": [1, 2, 3],
            "account_ids": ["+1234567890"],
        }

        errors = campaign_service.validate_campaign_data(campaign_data)
        assert "Campaign name is required" in errors

    def test_validate_campaign_data_name_too_long(self, campaign_service):
        """Test campaign validation failure due to name being too long."""
        campaign_data = {
            "name": "A" * 101,  # 101 characters, over limit
            "template": "Hello {first_name}!",
            "target_member_ids": [1, 2, 3],
            "account_ids": ["+1234567890"],
        }

        errors = campaign_service.validate_campaign_data(campaign_data)
        assert "Campaign name must be less than 100 characters" in errors

    def test_validate_campaign_data_no_template(self, campaign_service):
        """Test campaign validation failure due to missing template."""
        campaign_data = {
            "name": "Test Campaign",
            "template": "",
            "target_member_ids": [1, 2, 3],
            "account_ids": ["+1234567890"],
        }

        errors = campaign_service.validate_campaign_data(campaign_data)
        assert "Message template is required" in errors

    def test_validate_campaign_data_too_many_members(self, campaign_service):
        """Test campaign validation failure due to too many target members."""
        campaign_data = {
            "name": "Test Campaign",
            "template": "Hello {first_name}!",
            "target_member_ids": list(range(10001)),  # 10,001 members, over limit
            "account_ids": ["+1234567890"],
        }

        errors = campaign_service.validate_campaign_data(campaign_data)
        assert "Campaign cannot target more than 10,000 members" in errors

    @patch("campaigns.dm_campaign_manager.MessageTemplateEngine.validate_template")
    def test_create_campaign_success(
        self, mock_validate, campaign_service, campaign_repo_mock, member_service_mock
    ):
        """Test successful campaign creation."""
        # Mock template validation
        mock_validate.return_value = (True, "")

        # Mock repository
        campaign_repo_mock.create_campaign.return_value = 123

        # Mock member service
        member_service_mock.filter_members_for_campaign.return_value = [
            {"user_id": 1, "profile_quality_score": 0.8}
        ]
        member_service_mock.calculate_campaign_metrics.return_value = {
            "total_members": 1,
            "avg_profile_quality": 0.8,
        }

        campaign_data = {
            "name": "Test Campaign",
            "template": "Hello {first_name}!",
            "target_member_ids": [1],
            "account_ids": ["+1234567890"],
            "channel_id": "test_channel",
        }

        result = campaign_service.create_campaign(campaign_data)

        assert result["success"] is True
        assert result["campaign_id"] == 123
        assert "metrics" in result
        campaign_repo_mock.create_campaign.assert_called_once()

    @patch("campaigns.dm_campaign_manager.MessageTemplateEngine.validate_template")
    def test_create_campaign_validation_failure(self, mock_validate, campaign_service):
        """Test campaign creation failure due to validation errors."""
        # Mock template validation
        mock_validate.return_value = (True, "")

        campaign_data = {
            "name": "",  # Invalid: empty name
            "template": "Hello {first_name}!",
            "target_member_ids": [1],
            "account_ids": ["+1234567890"],
        }

        result = campaign_service.create_campaign(campaign_data)

        assert result["success"] is False
        assert "errors" in result
        assert len(result["errors"]) > 0


class TestAccountService:
    """Test cases for AccountService business logic."""

    @pytest.fixture
    def account_repo_mock(self):
        """Mock account repository."""
        mock_repo = Mock(spec=AccountRepository)
        return mock_repo

    @pytest.fixture
    def account_service(self, account_repo_mock):
        """Create AccountService with mocked repository."""
        return AccountService(account_repo_mock)

    def test_validate_account_data_success(self, account_service):
        """Test successful account data validation."""
        account_data = {"phone_number": "+1234567890", "api_id": "12345678", "api_hash": "a" * 32}

        errors = account_service.validate_account_data(account_data)
        assert len(errors) == 0

    def test_validate_account_data_missing_phone(self, account_service):
        """Test account validation failure due to missing phone."""
        account_data = {"phone_number": "", "api_id": "12345678", "api_hash": "a" * 32}

        errors = account_service.validate_account_data(account_data)
        assert "Phone number is required" in errors

    def test_validate_account_data_invalid_phone_format(self, account_service):
        """Test account validation failure due to invalid phone format."""
        account_data = {
            "phone_number": "1234567890",  # Missing + prefix
            "api_id": "12345678",
            "api_hash": "a" * 32,
        }

        errors = account_service.validate_account_data(account_data)
        assert any("Phone number must start with country code" in error for error in errors)

    def test_validate_account_data_invalid_api_id(self, account_service):
        """Test account validation failure due to non-numeric API ID."""
        account_data = {"phone_number": "+1234567890", "api_id": "invalid_id", "api_hash": "a" * 32}

        errors = account_service.validate_account_data(account_data)
        assert "API ID must be numeric" in errors

    def test_validate_account_data_short_api_hash(self, account_service):
        """Test account validation failure due to short API hash."""
        account_data = {"phone_number": "+1234567890", "api_id": "12345678", "api_hash": "short"}

        errors = account_service.validate_account_data(account_data)
        assert "API Hash must be 32 characters" in errors

    def test_can_account_send_message_active(self, account_service, account_repo_mock):
        """Test account can send when status is active."""
        account_repo_mock.get_account_by_phone.return_value = {"status": "active"}

        result = account_service.can_account_send_message("+1234567890")

        assert result["can_send"] is True
        assert result["reason"] == "Account is active"

    def test_can_account_send_message_banned(self, account_service, account_repo_mock):
        """Test account cannot send when banned."""
        account_repo_mock.get_account_by_phone.return_value = {"status": "banned"}

        result = account_service.can_account_send_message("+1234567890")

        assert result["can_send"] is False
        assert result["reason"] == "Account is banned"

    def test_can_account_send_message_not_found(self, account_service, account_repo_mock):
        """Test account cannot send when not found."""
        account_repo_mock.get_account_by_phone.return_value = None

        result = account_service.can_account_send_message("+1234567890")

        assert result["can_send"] is False
        assert result["reason"] == "Account not found"

    def test_calculate_account_health_score_healthy(self, account_service, account_repo_mock):
        """Test health score calculation for healthy account."""
        account_repo_mock.get_account_by_phone.return_value = {
            "status": "active",
            "error_count": 2,
            "last_success": datetime.now().isoformat(),
        }

        result = account_service.calculate_account_health_score("+1234567890")

        assert result["health_score"] == 100
        assert len(result["issues"]) == 0

    def test_calculate_account_health_score_problematic(self, account_service, account_repo_mock):
        """Test health score calculation for problematic account."""
        account_repo_mock.get_account_by_phone.return_value = {
            "status": "limited",
            "error_count": 15,
            "last_success": (datetime.now() - timedelta(days=10)).isoformat(),  # 10 days ago
        }

        result = account_service.calculate_account_health_score("+1234567890")

        assert result["health_score"] < 50  # Should be reduced
        assert len(result["issues"]) > 0
        assert len(result["recommendations"]) > 0


class TestBusinessLogicCoordinator:
    """Test cases for BusinessLogicCoordinator integration."""

    @pytest.fixture
    def coordinator(self):
        """Create coordinator with in-memory database for testing."""
        # Create in-memory database for testing
        with patch("core.repositories.MemberRepository.__init__", lambda self, db_path: None):
            with patch("core.repositories.CampaignRepository.__init__", lambda self, db_path: None):
                with patch(
                    "core.repositories.AccountRepository.__init__", lambda self, db_path: None
                ):
                    # Mock the database connections
                    coordinator = BusinessLogicCoordinator(":memory:")

                    # Mock the repositories to use in-memory operations
                    coordinator.member_repo = Mock(spec=MemberRepository)
                    coordinator.campaign_repo = Mock(spec=CampaignRepository)
                    coordinator.account_repo = Mock(spec=AccountRepository)

                    return coordinator

    def test_get_system_health_overview(self, coordinator):
        """Test system health overview calculation."""
        # Mock repository responses
        coordinator.account_repo.get_all_accounts.return_value = [
            {"phone_number": "+1234567890", "status": "active"},
            {"phone_number": "+0987654321", "status": "banned"},
        ]

        coordinator.campaign_repo.get_all_campaigns.return_value = [
            {"id": 1, "status": "running"},
            {"id": 2, "status": "completed"},
            {"id": 3, "status": "running"},
        ]

        result = coordinator.get_system_health_overview()

        assert "overall_health" in result
        assert "accounts" in result
        assert "campaigns" in result
        assert "recommendations" in result

        assert result["accounts"]["total"] == 2
        assert result["accounts"]["active"] == 1
        assert result["campaigns"]["running"] == 2


if __name__ == "__main__":
    pytest.main([__file__])
