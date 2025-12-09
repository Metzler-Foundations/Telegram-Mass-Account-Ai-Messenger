"""
Test fixtures for comprehensive testing.

This module provides reusable test data and mock objects.
"""

from .mock_gemini import MockGeminiService, MockGenerativeModel
from .mock_telegram import MockChat, MockMessage, MockTelegramClient, MockUser
from .test_data import (
    create_test_account,
    create_test_campaign,
    create_test_member,
    sample_accounts,
    sample_campaigns,
    sample_members,
    sample_proxies,
)

__all__ = [
    "MockTelegramClient",
    "MockMessage",
    "MockUser",
    "MockChat",
    "MockGeminiService",
    "MockGenerativeModel",
    "sample_accounts",
    "sample_members",
    "sample_campaigns",
    "sample_proxies",
    "create_test_account",
    "create_test_member",
    "create_test_campaign",
]
