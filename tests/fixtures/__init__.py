"""
Test fixtures for comprehensive testing.

This module provides reusable test data and mock objects.
"""

from .mock_telegram import MockTelegramClient, MockMessage, MockUser, MockChat
from .mock_gemini import MockGeminiService, MockGenerativeModel
from .test_data import (
    sample_accounts,
    sample_members,
    sample_campaigns,
    sample_proxies,
    create_test_account,
    create_test_member,
    create_test_campaign,
)

__all__ = [
    'MockTelegramClient',
    'MockMessage',
    'MockUser',
    'MockChat',
    'MockGeminiService',
    'MockGenerativeModel',
    'sample_accounts',
    'sample_members',
    'sample_campaigns',
    'sample_proxies',
    'create_test_account',
    'create_test_member',
    'create_test_campaign',
]

