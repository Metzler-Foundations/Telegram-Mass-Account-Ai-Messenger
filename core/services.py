"""
Business Logic Layer - Service classes containing business rules and workflows.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from core.repositories import AccountRepository, CampaignRepository, MemberRepository

logger = logging.getLogger(__name__)


class BaseService:
    """Base service class with common functionality."""

    def __init__(self, repository):
        self.repository = repository


class MemberService(BaseService):
    """Business logic for member operations."""

    def __init__(self, member_repo: MemberRepository):
        super().__init__(member_repo)

    def validate_member_for_campaign(self, member: Dict, criteria: Dict) -> bool:
        """Validate if member meets campaign criteria."""
        # Business rules for member validation
        if member.get("threat_score", 0) > criteria.get("max_risk", 50):
            return False

        if member.get("profile_quality_score", 0) < criteria.get("min_quality", 0.3):
            return False

        if member.get("messaging_potential_score", 0) < criteria.get("min_potential", 0.5):
            return False

        return True

    def filter_members_for_campaign(self, channel_id: str, criteria: Dict) -> List[Dict]:
        """Get and filter members for a campaign."""
        members = self.repository.get_members_for_campaign(channel_id, criteria)

        # Apply business logic filtering
        filtered_members = []
        for member in members:
            if self.validate_member_for_campaign(member, criteria):
                filtered_members.append(member)

        return filtered_members

    def calculate_campaign_metrics(self, members: List[Dict]) -> Dict[str, Any]:
        """Calculate metrics for a set of members."""
        if not members:
            return {}

        total_members = len(members)
        avg_quality = sum(m.get("profile_quality_score", 0) for m in members) / total_members
        avg_potential = sum(m.get("messaging_potential_score", 0) for m in members) / total_members
        high_potential = sum(1 for m in members if m.get("messaging_potential_score", 0) >= 0.8)

        return {
            "total_members": total_members,
            "avg_profile_quality": round(
                avg_quality, 2
            ),  # Round to 2 decimals to avoid floating point issues
            "avg_messaging_potential": round(avg_potential, 2),
            "high_potential_count": high_potential,
            "high_potential_percentage": (
                round((high_potential / total_members) * 100, 2) if total_members > 0 else 0
            ),
        }


class CampaignService(BaseService):
    """Business logic for campaign operations."""

    def __init__(self, campaign_repo: CampaignRepository, member_service: MemberService):
        self.campaign_repo = campaign_repo
        self.member_service = member_service

    def validate_campaign_data(self, campaign_data: Dict) -> List[str]:
        """Validate campaign data according to business rules."""
        errors = []

        # Business rule validations
        if not campaign_data.get("name", "").strip():
            errors.append("Campaign name is required")

        if len(campaign_data.get("name", "")) > 100:
            errors.append("Campaign name must be less than 100 characters")

        if not campaign_data.get("template", "").strip():
            errors.append("Message template is required")

        if len(campaign_data.get("target_member_ids", [])) == 0:
            errors.append("At least one target member is required")

        if len(campaign_data.get("target_member_ids", [])) > 10000:
            errors.append("Campaign cannot target more than 10,000 members")

        if len(campaign_data.get("account_ids", [])) == 0:
            errors.append("At least one account is required")

        if len(campaign_data.get("account_ids", [])) > 50:
            errors.append("Campaign cannot use more than 50 accounts")

        return errors

    def create_campaign(self, campaign_data: Dict) -> Dict[str, Any]:
        """Create a new campaign with business logic validation."""
        # Validate business rules
        errors = self.validate_campaign_data(campaign_data)
        if errors:
            return {"success": False, "errors": errors}

        # Create campaign
        campaign_id = self.campaign_repo.create_campaign(campaign_data)
        if not campaign_id:
            return {"success": False, "errors": ["Failed to create campaign"]}

        # Calculate initial metrics
        criteria = campaign_data.get("criteria", {})
        members = self.member_service.filter_members_for_campaign(
            campaign_data.get("channel_id", ""), criteria
        )
        metrics = self.member_service.calculate_campaign_metrics(members)

        return {
            "success": True,
            "campaign_id": campaign_id,
            "metrics": metrics,
            "estimated_members": len(members),
        }

    def optimize_campaign_targeting(self, campaign_id: int) -> Dict[str, Any]:
        """Optimize campaign targeting based on performance data."""
        campaign = self.campaign_repo.get_campaign_by_id(campaign_id)
        if not campaign:
            return {"success": False, "error": "Campaign not found"}

        # Business logic for optimization
        current_stats = {
            "sent_count": campaign.get("sent_count", 0),
            "failed_count": campaign.get("failed_count", 0),
            "blocked_count": campaign.get("blocked_count", 0),
        }

        success_rate = current_stats["sent_count"] / max(
            current_stats["sent_count"] + current_stats["failed_count"], 1
        )

        # Optimization recommendations
        recommendations = []
        if success_rate < 0.5:
            recommendations.append("Consider improving member targeting criteria")
        if current_stats["blocked_count"] > current_stats["sent_count"] * 0.1:
            recommendations.append("High block rate detected - reduce message frequency")
        if success_rate > 0.9:
            recommendations.append("Excellent performance - consider scaling up")

        return {
            "success": True,
            "success_rate": success_rate,
            "recommendations": recommendations,
            "optimization_score": success_rate * 100,
        }


class AccountService(BaseService):
    """Business logic for account operations."""

    def __init__(self, account_repo: AccountRepository):
        super().__init__(account_repo)

    def validate_account_data(self, account_data: Dict) -> List[str]:
        """Validate account data according to business rules."""
        errors = []

        if not account_data.get("phone_number", "").strip():
            errors.append("Phone number is required")

        # Phone number format validation
        phone = account_data.get("phone_number", "")
        if phone and not phone.startswith("+"):
            errors.append("Phone number must start with country code (e.g., +1234567890)")

        if account_data.get("api_id") and not str(account_data["api_id"]).isdigit():
            errors.append("API ID must be numeric")

        if account_data.get("api_hash") and len(account_data["api_hash"]) != 32:
            errors.append("API Hash must be 32 characters")

        return errors

    def can_account_send_message(self, phone_number: str) -> Dict[str, Any]:
        """Determine if account can send messages based on business rules."""
        account = self.repository.get_account_by_phone(phone_number)
        if not account:
            return {"can_send": False, "reason": "Account not found"}

        status = account.get("status", "unknown")

        # Business rules for sending capability
        if status == "banned":
            return {"can_send": False, "reason": "Account is banned"}
        elif status == "limited":
            return {"can_send": False, "reason": "Account is rate limited"}
        elif status == "suspended":
            return {"can_send": False, "reason": "Account is temporarily suspended"}
        elif status in ["active", "online"]:
            return {"can_send": True, "reason": "Account is active"}

        return {"can_send": False, "reason": f"Unknown account status: {status}"}

    def calculate_account_health_score(self, phone_number: str) -> Dict[str, Any]:
        """Calculate overall health score for an account."""
        account = self.repository.get_account_by_phone(phone_number)
        if not account:
            return {"health_score": 0, "issues": ["Account not found"]}

        score = 100
        issues = []

        # Business logic for health scoring
        if account.get("status") != "active":
            score -= 50
            issues.append(f"Account status: {account.get('status')}")

        if account.get("error_count", 0) > 10:
            score -= 20
            issues.append("High error count")

        if (
            account.get("last_success")
            and (datetime.now() - datetime.fromisoformat(account["last_success"])).days > 7
        ):
            score -= 15
            issues.append("No successful operations recently")

        return {
            "health_score": max(0, score),
            "issues": issues,
            "recommendations": self._get_health_recommendations(score, issues),
        }

    def _get_health_recommendations(self, score: int, issues: List[str]) -> List[str]:
        """Get recommendations based on health score and issues."""
        recommendations = []

        if score < 30:
            recommendations.append(
                "Account requires immediate attention - consider creating a new account"
            )
        elif score < 50:
            recommendations.append("Account has significant issues - review error logs")
        elif score < 70:
            recommendations.append("Account performance is degraded - monitor closely")

        for issue in issues:
            if "banned" in issue.lower():
                recommendations.append("Account appears banned - avoid using this account")
            elif "error" in issue.lower():
                recommendations.append("Review recent errors and adjust usage patterns")
            elif "recent" in issue.lower():
                recommendations.append("Account needs activity - send some test messages")

        return recommendations


class BusinessLogicCoordinator:
    """Coordinates business logic across all services."""

    def __init__(self, db_path: str = "members.db"):
        # Initialize repositories
        self.member_repo = MemberRepository(db_path)
        self.campaign_repo = CampaignRepository(db_path)
        self.account_repo = AccountRepository(db_path)

        # Initialize services
        self.member_service = MemberService(self.member_repo)
        self.account_service = AccountService(self.account_repo)
        self.campaign_service = CampaignService(self.campaign_repo, self.member_service)

    def get_system_health_overview(self) -> Dict[str, Any]:
        """Get overall system health across all business domains."""
        # Aggregate health from all services
        accounts = self.account_repo.get_all_accounts()
        campaigns = self.campaign_repo.get_all_campaigns()

        # Calculate system metrics
        total_accounts = len(accounts)
        active_accounts = sum(1 for acc in accounts if acc.get("status") == "active")
        total_campaigns = len(campaigns)
        running_campaigns = sum(1 for camp in campaigns if camp.get("status") == "running")

        # Overall health score (simplified)
        health_score = 100
        if active_accounts < total_accounts * 0.5:
            health_score -= 30
        if running_campaigns > 5:  # Too many concurrent campaigns
            health_score -= 20

        return {
            "overall_health": health_score,
            "accounts": {
                "total": total_accounts,
                "active": active_accounts,
                "health_percentage": (active_accounts / max(total_accounts, 1)) * 100,
            },
            "campaigns": {"total": total_campaigns, "running": running_campaigns},
            "recommendations": self._get_system_recommendations(health_score),
        }

    def _get_system_recommendations(self, health_score: int) -> List[str]:
        """Get system-wide recommendations."""
        recommendations = []

        if health_score < 50:
            recommendations.append(
                "System health is poor - review account statuses and campaign configurations"
            )
        elif health_score < 80:
            recommendations.append(
                "System performance could be improved - consider optimizing campaign targeting"
            )

        return recommendations
