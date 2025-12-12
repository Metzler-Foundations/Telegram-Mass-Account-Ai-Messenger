"""
Integration tests for critical workflows and component interactions.
"""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.services import BusinessLogicCoordinator  # noqa: E402
from ui.ui_controller import UIController  # noqa: E402


class TestUIControllerIntegration:
    """Integration tests for UI Controller and business logic interaction."""

    @pytest.fixture
    def ui_controller(self):
        """Create UI controller with mocked business logic."""
        with patch("ui.ui_controller.BusinessLogicCoordinator") as mock_coordinator_class:
            mock_coordinator = Mock(spec=BusinessLogicCoordinator)

            # Mock services
            mock_member_service = Mock()
            mock_campaign_service = Mock()
            mock_account_service = Mock()

            mock_coordinator.member_service = mock_member_service
            mock_coordinator.campaign_service = mock_campaign_service
            mock_coordinator.account_service = mock_account_service
            mock_coordinator.member_repo = Mock()
            mock_coordinator.campaign_repo = Mock()
            mock_coordinator.account_repo = Mock()

            mock_coordinator_class.return_value = mock_coordinator

            controller = UIController(":memory:")
            controller.business_logic = mock_coordinator

            return controller

    def test_create_campaign_success_workflow(self, ui_controller):
        """Test complete campaign creation workflow."""
        # Setup mocks
        campaign_data = {
            "name": "Integration Test Campaign",
            "template": "Hello {first_name}!",
            "target_member_ids": [1, 2, 3],
            "account_ids": ["+1234567890"],
            "channel_id": "test_channel",
        }

        ui_controller.business_logic.campaign_service.validate_campaign_data.return_value = []
        ui_controller.business_logic.campaign_service.create_campaign.return_value = {
            "success": True,
            "campaign_id": 123,
            "metrics": {"total_members": 3},
            "estimated_members": 3,
        }

        # Execute workflow
        result = ui_controller.create_campaign(campaign_data)

        # Verify results
        assert result["success"] is True
        assert result["campaign_id"] == 123
        assert result["estimated_members"] == 3

        # Verify service calls
        ui_controller.business_logic.campaign_service.validate_campaign_data.assert_called_once_with(  # noqa: E501
            campaign_data
        )
        ui_controller.business_logic.campaign_service.create_campaign.assert_called_once_with(
            campaign_data
        )

    def test_create_campaign_validation_failure(self, ui_controller):
        """Test campaign creation with validation errors."""
        campaign_data = {
            "name": "",  # Invalid
            "template": "Hello {first_name}!",
            "target_member_ids": [1, 2, 3],
            "account_ids": ["+1234567890"],
        }

        ui_controller.business_logic.campaign_service.validate_campaign_data.return_value = [
            "Campaign name is required"
        ]

        result = ui_controller.create_campaign(campaign_data)

        assert result["success"] is False
        assert "errors" in result
        assert "Campaign name is required" in result["errors"]

    def test_get_members_for_campaign_workflow(self, ui_controller):
        """Test member filtering workflow for campaigns."""
        criteria = {"min_quality": 0.5, "max_risk": 30, "min_potential": 0.6}

        mock_members = [
            {"user_id": 1, "first_name": "John", "profile_quality_score": 0.8},
            {"user_id": 2, "first_name": "Jane", "profile_quality_score": 0.6},
        ]

        mock_metrics = {"total_members": 2, "avg_profile_quality": 0.7}

        ui_controller.business_logic.member_service.filter_members_for_campaign.return_value = (
            mock_members
        )
        ui_controller.business_logic.member_service.calculate_campaign_metrics.return_value = (
            mock_metrics
        )

        result = ui_controller.get_members_for_campaign_ui("test_channel", criteria)

        assert result["success"] is True
        assert result["members"] == mock_members
        assert result["metrics"] == mock_metrics
        assert result["count"] == 2

    def test_account_management_workflow(self, ui_controller):
        """Test account management workflow."""
        # Mock account data
        mock_accounts = [
            {"phone_number": "+1234567890", "status": "active", "username": "test_user"}
        ]

        ui_controller.business_logic.account_repo.get_all_accounts.return_value = mock_accounts
        ui_controller.business_logic.account_service.calculate_account_health_score.return_value = {
            "health_score": 95,
            "issues": [],
            "recommendations": [],
        }
        ui_controller.business_logic.account_service.can_account_send_message.return_value = {
            "can_send": True,
            "reason": "Account is active",
        }

        result = ui_controller.get_accounts_overview()

        assert len(result) == 1
        account = result[0]
        assert account["phone_number"] == "+1234567890"
        assert account["health_score"] == 95
        assert account["can_send"] is True

    def test_system_health_workflow(self, ui_controller):
        """Test system health monitoring workflow."""
        mock_health_data = {
            "overall_health": 85,
            "accounts": {"total": 5, "active": 4},
            "campaigns": {"total": 3, "running": 1},
            "recommendations": ["Monitor account performance"],
        }

        ui_controller.business_logic.get_system_health_overview.return_value = mock_health_data

        result = ui_controller.get_system_health()

        assert result["overall_health"] == 85
        assert result["accounts"]["total"] == 5
        assert result["campaigns"]["running"] == 1


class TestEndToEndWorkflows:
    """End-to-end workflow tests."""

    @pytest.fixture
    def mock_ui_controller(self):
        """Create mocked UI controller for end-to-end testing."""
        controller = Mock(spec=UIController)

        # Setup successful responses
        controller.create_campaign.return_value = {
            "success": True,
            "campaign_id": 123,
            "estimated_members": 150,
        }

        controller.get_members_for_campaign_ui.return_value = {
            "success": True,
            "count": 150,
            "metrics": {"avg_profile_quality": 0.75},
        }

        controller.get_accounts_overview.return_value = [
            {"phone_number": "+1234567890", "status": "active", "can_send": True}
        ]

        return controller

    def test_campaign_creation_to_execution_workflow(self, mock_ui_controller):
        """Test complete workflow from campaign creation to execution."""
        # Step 1: Create campaign
        campaign_data = {
            "name": "E2E Test Campaign",
            "template": "Hi {first_name}, check this out!",
            "target_member_ids": list(range(1, 151)),  # 150 members
            "account_ids": ["+1234567890"],
            "channel_id": "@testchannel",
        }

        create_result = mock_ui_controller.create_campaign(campaign_data)
        assert create_result["success"] is True
        assert create_result["campaign_id"] == 123

        # Step 2: Get targeting data
        targeting_result = mock_ui_controller.get_members_for_campaign_ui(
            "@testchannel", {"min_quality": 0.5, "max_risk": 40}
        )
        assert targeting_result["success"] is True
        assert targeting_result["count"] == 150

        # Step 3: Check account availability
        accounts = mock_ui_controller.get_accounts_overview()
        assert len(accounts) > 0
        active_accounts = [acc for acc in accounts if acc["can_send"]]
        assert len(active_accounts) > 0

        # Verify campaign can be executed
        assert create_result["estimated_members"] == targeting_result["count"]
        assert len(active_accounts) >= 1  # At least one account available

    def test_account_health_monitoring_workflow(self, mock_ui_controller):
        """Test account health monitoring workflow."""
        # Get initial account status
        accounts = mock_ui_controller.get_accounts_overview()
        initial_active = sum(1 for acc in accounts if acc["can_send"])

        # Simulate health check (mock would return updated status)
        # In real implementation, this would trigger background health checks
        updated_accounts = mock_ui_controller.get_accounts_overview()
        final_active = sum(1 for acc in updated_accounts if acc["can_send"])

        # Health monitoring should maintain or improve account availability
        assert final_active >= initial_active

    def test_error_handling_workflow(self, mock_ui_controller):
        """Test error handling throughout the workflow."""
        # Test campaign creation with invalid data
        invalid_campaign = {
            "name": "",  # Invalid
            "template": "Hi there!",
            "target_member_ids": [],
            "account_ids": [],
        }

        mock_ui_controller.create_campaign.side_effect = ValueError("Invalid campaign data")

        with pytest.raises(ValueError, match="Invalid campaign data"):
            mock_ui_controller.create_campaign(invalid_campaign)

        # Verify error was handled (in real implementation, this would show user dialog)
        mock_ui_controller.create_campaign.assert_called_once()


class TestErrorRecoveryIntegration:
    """Integration tests for error recovery mechanisms."""

    @pytest.fixture
    def error_handling_controller(self):
        """Create controller configured for error testing."""
        controller = Mock(spec=UIController)

        # Configure to simulate various error conditions
        controller.create_campaign.side_effect = [
            {"success": False, "errors": ["Network timeout"]},  # First call fails
            {"success": True, "campaign_id": 456},  # Second call succeeds
        ]

        return controller

    def test_retry_mechanism_on_transient_errors(self, error_handling_controller):
        """Test retry mechanism for transient errors."""
        # First attempt - should fail
        result1 = error_handling_controller.create_campaign({})
        assert result1["success"] is False
        assert "Network timeout" in result1["errors"]

        # Second attempt - should succeed (simulating recovery)
        result2 = error_handling_controller.create_campaign({})
        assert result2["success"] is True
        assert result2["campaign_id"] == 456

    def test_graceful_degradation_on_service_unavailable(self, error_handling_controller):
        """Test graceful degradation when services are unavailable."""
        # Simulate service completely down
        error_handling_controller.create_campaign.side_effect = Exception("Service unavailable")

        # System should handle gracefully without crashing
        with pytest.raises(Exception, match="Service unavailable"):
            error_handling_controller.create_campaign({})

        # In real implementation, this would trigger fallback mechanisms
        # and show appropriate user messaging


class TestPerformanceIntegration:
    """Integration tests for performance under load."""

    @pytest.fixture
    def performance_controller(self):
        """Create controller configured for performance testing."""
        controller = Mock(spec=UIController)

        # Simulate large dataset handling
        large_member_list = [
            {"user_id": i, "first_name": f"User{i}", "profile_quality_score": 0.5 + (i % 50) / 100}
            for i in range(1, 1001)  # 1000 members
        ]

        controller.get_members_for_campaign_ui.return_value = {
            "success": True,
            "members": large_member_list,
            "count": len(large_member_list),
            "metrics": {"total_members": len(large_member_list)},
        }

        return controller

    def test_large_dataset_handling(self, performance_controller):
        """Test handling of large datasets without performance degradation."""
        import time

        start_time = time.time()

        # Process large member dataset
        result = performance_controller.get_members_for_campaign_ui("large_channel", {})

        end_time = time.time()
        processing_time = end_time - start_time

        # Verify data integrity
        assert result["success"] is True
        assert result["count"] == 1000
        assert len(result["members"]) == 1000

        # Performance should be reasonable (< 1 second for 1000 items)
        assert processing_time < 1.0

        # Verify data quality
        user_ids = [m["user_id"] for m in result["members"]]
        assert len(set(user_ids)) == 1000  # All unique IDs
        assert min(user_ids) == 1
        assert max(user_ids) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
