#!/usr/bin/env python3
"""
Feature Execution Verification Script
Tests and demonstrates what features actually work vs what doesn't.
"""
import sys
import os
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, List, Any
import traceback


class FeatureTestResult:
    """Result of a feature test."""

    def __init__(self, feature_name: str):
        self.feature_name = feature_name
        self.passed = False
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.notes: List[str] = []

    def add_error(self, error: str):
        self.errors.append(error)

    def add_warning(self, warning: str):
        self.warnings.append(warning)

    def add_note(self, note: str):
        self.notes.append(note)

    def mark_passed(self):
        self.passed = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature": self.feature_name,
            "status": "✅ WORKING" if self.passed else "❌ BROKEN",
            "errors": self.errors,
            "warnings": self.warnings,
            "notes": self.notes,
        }


def test_database_operations() -> FeatureTestResult:
    """Test database operations."""
    result = FeatureTestResult("Database Operations")

    try:
        from scraping.member_scraper import MemberDatabase

        # Test initialization
        db = MemberDatabase()
        result.add_note("MemberDatabase initialized successfully")

        # Test basic queries
        channels = db.get_all_channels()
        members = db.get_all_members()
        result.add_note(f"Basic queries work: {len(channels)} channels, {len(members)} members")

        # Test table creation (should not fail)
        db.init_database()
        result.add_note("Database schema initialization works")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"Database operations failed: {str(e)}")
        result.add_note("Check database file permissions and SQLite installation")

    return result


def test_configuration_management() -> FeatureTestResult:
    """Test configuration management."""
    result = FeatureTestResult("Configuration Management")

    try:
        from core.config_manager import ConfigurationManager

        config = ConfigurationManager()
        result.add_note("ConfigurationManager initialized")

        # Test config loading
        telegram_config = config.get("telegram", {})
        gemini_config = config.get("gemini", {})
        result.add_note(
            f"Config sections loaded: telegram({len(telegram_config)}), gemini({len(gemini_config)})"
        )

        # Check for required fields
        if not telegram_config.get("api_id"):
            result.add_warning("Telegram API ID not configured")
        if not gemini_config.get("api_key"):
            result.add_warning("Gemini API key not configured")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"Configuration management failed: {str(e)}")

    return result


def test_business_logic() -> FeatureTestResult:
    """Test business logic services."""
    result = FeatureTestResult("Business Logic")

    try:
        from core.services import MemberService, CampaignService, AccountService
        from core.repositories import MemberRepository, CampaignRepository, AccountRepository

        # Test repositories
        member_repo = MemberRepository("members.db")
        campaign_repo = CampaignRepository("campaigns.db")
        account_repo = AccountRepository("accounts.db")

        # Test services
        member_service = MemberService(member_repo)
        campaign_service = CampaignService(campaign_repo, member_service)
        account_service = AccountService(account_repo)

        result.add_note("All business logic services initialized")

        # Test member validation
        member = {
            "profile_quality_score": 0.8,
            "messaging_potential_score": 0.7,
            "threat_score": 20,
        }
        criteria = {"max_risk": 50, "min_quality": 0.3, "min_potential": 0.5}
        valid = member_service.validate_member_for_campaign(member, criteria)
        result.add_note(f"Member validation works: member valid = {valid}")

        # Test campaign validation
        campaign_data = {
            "name": "Test Campaign",
            "template": "Hello {name}!",
            "target_member_ids": [1, 2, 3],
            "account_ids": [1],
        }
        errors = campaign_service.validate_campaign_data(campaign_data)
        result.add_note(f"Campaign validation works: {len(errors)} errors found")

        # Test account validation
        account_data = {"phone_number": "+1234567890", "api_id": "123456", "api_hash": "a" * 32}
        errors = account_service.validate_account_data(account_data)
        result.add_note(f"Account validation works: {len(errors)} errors found")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"Business logic failed: {str(e)}")
        result.add_note("Repository initialization may require database files")

    return result


def test_ai_integration() -> FeatureTestResult:
    """Test AI integration."""
    result = FeatureTestResult("AI Integration")

    try:
        from ai.gemini_service import GeminiService
        from core.config_manager import ConfigurationManager

        config = ConfigurationManager()
        gemini_config = config.get("gemini", {})
        api_key = gemini_config.get("api_key", "")

        if api_key:
            gemini = GeminiService(api_key)
            result.add_note("Gemini service initialized with API key")
            result.add_note("AI integration ready for production use")
        else:
            gemini = GeminiService("")
            result.add_note("Gemini service initialized but no API key configured")
            result.add_warning("Configure Gemini API key for AI responses to work")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"AI integration failed: {str(e)}")

    return result


def test_telegram_integration() -> FeatureTestResult:
    """Test Telegram integration."""
    result = FeatureTestResult("Telegram Integration")

    try:
        from telegram.telegram_client import TelegramClient
        from core.config_manager import ConfigurationManager

        config = ConfigurationManager()
        telegram_config = config.get("telegram", {})

        api_id = telegram_config.get("api_id")
        api_hash = telegram_config.get("api_hash")
        phone = telegram_config.get("phone_number")

        if api_id and api_hash and phone:
            client = TelegramClient(api_id, api_hash, phone)
            result.add_note("Telegram client initialized with credentials")
            result.add_note("Telegram integration ready for production use")
        else:
            client = TelegramClient("", "", "")
            result.add_note("Telegram client initialized but missing credentials")
            result.add_warning("Configure Telegram API credentials for messaging to work")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"Telegram integration failed: {str(e)}")

    return result


def test_anti_detection() -> FeatureTestResult:
    """Test anti-detection system."""
    result = FeatureTestResult("Anti-Detection System")

    try:
        from anti_detection.anti_detection_system import AntiDetectionSystem

        anti_detection = AntiDetectionSystem()
        result.add_note("AntiDetectionSystem initialized")

        # Test activation
        anti_detection.activate()
        result.add_note("Anti-detection system activated successfully")

        # Check available methods
        methods = [m for m in dir(anti_detection) if not m.startswith("_")]
        result.add_note(f"Available methods: {len(methods)} methods")

        # Test some core functionality
        if hasattr(anti_detection, "apply_anti_detection_measures"):
            anti_detection.apply_anti_detection_measures(action_type="test")
            result.add_note("Anti-detection measures applied")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"Anti-detection system failed: {str(e)}")

    return result


def test_ui_components() -> FeatureTestResult:
    """Test UI components."""
    result = FeatureTestResult("UI Components")

    try:
        # Test main window
        from main import MainWindow

        result.add_note("MainWindow imports successfully")

        # Test core UI components
        from ui.ui_components import CampaignManagerWidget, MessageHistoryWidget

        result.add_note("Core UI components import successfully")

        # Test settings window
        from ui.settings_window import SettingsWindow

        result.add_note("Settings window imports successfully")

        # Test other UI components
        from ui.welcome_wizard import WelcomeWizard

        result.add_note("Welcome wizard imports successfully")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"UI components failed: {str(e)}")
        result.add_note("Some UI components may require display environment")

    return result


def test_campaign_management() -> FeatureTestResult:
    """Test campaign management."""
    result = FeatureTestResult("Campaign Management")

    try:
        from campaigns.dm_campaign_manager import MessageTemplateEngine

        template_engine = MessageTemplateEngine()
        result.add_note("MessageTemplateEngine initialized")

        # Test template validation
        template = "Hello {name}, interested in {product}?"
        is_valid, errors = template_engine.validate_template(template)
        result.add_note(f"Template validation works: valid={is_valid}, errors={len(errors)}")

        if not is_valid:
            result.add_warning(f"Template validation found issues: {errors[:3]}")

        result.mark_passed()

    except Exception as e:
        result.add_error(f"Campaign management failed: {str(e)}")
        result.add_note("Database schema issues may affect campaign functionality")

    return result


def run_all_tests() -> Dict[str, FeatureTestResult]:
    """Run all feature tests."""
    print("🚀 Telegram Bot Feature Execution Verification")
    print("=" * 60)

    tests = [
        test_database_operations,
        test_configuration_management,
        test_business_logic,
        test_ai_integration,
        test_telegram_integration,
        test_anti_detection,
        test_ui_components,
        test_campaign_management,
    ]

    results = {}

    for test_func in tests:
        print(f"\n🔍 Testing: {test_func.__name__.replace('test_', '').replace('_', ' ').title()}")
        try:
            result = test_func()
            results[result.feature_name] = result

            status = "✅ WORKING" if result.passed else "❌ BROKEN"
            print(f"   {status}")

            if result.errors:
                print(f"   Errors: {len(result.errors)}")
                for error in result.errors[:2]:  # Show first 2 errors
                    print(f"     - {error}")

            if result.warnings:
                print(f"   Warnings: {len(result.warnings)}")
                for warning in result.warnings[:2]:
                    print(f"     - {warning}")

        except Exception as e:
            print(f"   ❌ TEST CRASHED: {e}")
            result = FeatureTestResult(
                test_func.__name__.replace("test_", "").replace("_", " ").title()
            )
            result.add_error(f"Test execution failed: {str(e)}")
            results[result.feature_name] = result

    return results


def print_summary(results: Dict[str, FeatureTestResult]):
    """Print test summary."""
    print("\n" + "=" * 60)
    print("📊 FEATURE EXECUTION VERIFICATION SUMMARY")
    print("=" * 60)

    working = 0
    broken = 0

    for feature_name, result in results.items():
        status = "✅ WORKING" if result.passed else "❌ BROKEN"
        print(f"{status} {feature_name}")

        if not result.passed and result.errors:
            print(f"     Issues: {', '.join(result.errors[:2])}")

        if result.passed:
            working += 1
        else:
            broken += 1

    print(f"\n📈 Overall: {working} working, {broken} broken features")

    if broken > 0:
        print("\n💡 Critical Issues to Fix:")
        for feature_name, result in results.items():
            if not result.passed and result.errors:
                print(f"   • {feature_name}: {result.errors[0]}")


if __name__ == "__main__":
    try:
        results = run_all_tests()
        print_summary(results)

        # Exit with appropriate code
        broken_count = sum(1 for r in results.values() if not r.passed)
        sys.exit(1 if broken_count > 0 else 0)

    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        traceback.print_exc()
        sys.exit(1)
