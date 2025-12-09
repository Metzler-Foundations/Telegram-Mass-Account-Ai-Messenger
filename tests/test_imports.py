#!/usr/bin/env python3
"""
Test all module imports to ensure no import path issues.
"""
import os
import sys

import pytest

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestModuleImports:
    """Test that all modules can be imported successfully."""

    def test_core_modules(self):
        """Test core infrastructure imports."""
        modules = [
            "core.config_manager",
            "core.service_container",
            "core.services",
            "core.repositories",
            "core.error_handler",
            "core.setup_logging",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_telegram_modules(self):
        """Test Telegram-related imports."""
        modules = [
            "telegram.telegram_client",
            "telegram.telegram_worker",
            "telegram.persistent_connection_manager",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_ai_modules(self):
        """Test AI-related imports."""
        modules = [
            "ai.gemini_service",
            "ai.intelligence_engine",
            "ai.conversation_analyzer",
            "ai.response_optimizer",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_account_modules(self):
        """Test account management imports."""
        modules = [
            "accounts.account_manager",
            "accounts.account_creator",
            "accounts.account_warmup_service",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_scraping_modules(self):
        """Test member scraping imports."""
        modules = [
            "scraping.member_scraper",
            "scraping.member_filter",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_campaign_modules(self):
        """Test campaign management imports."""
        modules = [
            "campaigns.dm_campaign_manager",
            "campaigns.campaign_tracker",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_ui_modules(self):
        """Test UI component imports."""
        modules = [
            "ui.settings_window",
            "ui.welcome_wizard",
            "ui.ui_components",
            "ui.analytics_dashboard",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_anti_detection_modules(self):
        """Test anti-detection imports."""
        modules = [
            "anti_detection.anti_detection_system",
            "anti_detection.shadowban_detector",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_integration_modules(self):
        """Test integration imports."""
        modules = [
            "integrations.api_key_manager",
            "integrations.auto_integrator",
        ]

        for module in modules:
            try:
                __import__(module)
            except ImportError as e:
                pytest.fail(f"Failed to import {module}: {e}")

    def test_main_app_import(self):
        """Test main application import."""
        try:
            from main import MainWindow

            assert MainWindow is not None
        except ImportError as e:
            pytest.fail(f"Failed to import MainWindow: {e}")

    def test_app_launcher_import(self):
        """Test app launcher import."""
        try:
            from app_launcher import launch_application

            assert launch_application is not None
        except ImportError as e:
            pytest.fail(f"Failed to import launch_application: {e}")


class TestClassInstantiations:
    """Test that key classes can be instantiated."""

    def test_config_manager(self):
        """Test ConfigurationManager instantiation."""
        try:
            from core.config_manager import ConfigurationManager

            config = ConfigurationManager()
            assert config is not None
        except Exception as e:
            pytest.fail(f"Failed to create ConfigurationManager: {e}")

    def test_service_container(self):
        """Test ServiceContainer instantiation."""
        try:
            from core.service_container import ServiceContainer

            container = ServiceContainer()
            assert container is not None
        except Exception as e:
            pytest.fail(f"Failed to create ServiceContainer: {e}")

    def test_error_handler(self):
        """Test ErrorHandler functionality."""
        try:
            from core.error_handler import ErrorHandler

            # Just test import, don't instantiate as it might need GUI
            assert ErrorHandler is not None
        except Exception as e:
            pytest.fail(f"Failed to import ErrorHandler: {e}")
