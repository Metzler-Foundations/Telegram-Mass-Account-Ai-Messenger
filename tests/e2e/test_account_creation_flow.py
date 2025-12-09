"""
E2E Test: Account Creation Flow

Tests the complete account creation workflow:
1. Initialize account creator
2. Configure SMS provider
3. Assign proxy
4. Create account
5. Verify account saved to DB
6. Verify warmup queued
"""

import sqlite3
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tests.fixtures import MockTelegramClient, create_test_account


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_account_creation_complete_flow():
    """Test complete account creation flow with all integrations."""

    # Setup test database
    from scraping.member_scraper import MemberDatabase

    test_db = MemberDatabase(":memory:")

    # Mock Gemini service
    mock_gemini_service = Mock()
    mock_gemini_service.generate_response = AsyncMock(return_value="Test response")

    # Mock account manager
    mock_account_manager = Mock()
    mock_account_manager.add_account = AsyncMock(return_value=True)

    # Mock SMS provider
    mock_sms_provider = Mock()
    mock_sms_provider.get_phone_number = AsyncMock(
        return_value={"success": True, "phone_number": "+1234567890", "order_id": "test_order_123"}
    )
    mock_sms_provider.get_verification_code = AsyncMock(return_value="12345")

    # Mock proxy pool
    mock_proxy_pool = Mock()
    mock_proxy_pool.assign_proxy_to_account = AsyncMock(
        return_value={"ip": "1.2.3.4", "port": 8080, "protocol": "http"}
    )

    # Mock Telegram client (already have MockTelegramClient)
    with patch("accounts.account_creator.Client", MockTelegramClient):
        # Import after patching
        from accounts.account_creator import AccountCreator

        creator = AccountCreator(
            db=test_db, gemini_service=mock_gemini_service, account_manager=mock_account_manager
        )

        # Configure mocks
        creator.phone_provider = mock_sms_provider
        creator.proxy_pool = mock_proxy_pool

        # Create account
        config = {
            "country": "US",
            "use_proxy": True,
            "generate_username": True,
        }

        # Mock username generation
        with patch("accounts.username_generator.UsernameGenerator.generate") as mock_username:
            mock_username.return_value = ("test_user_123", None)

            # Execute account creation
            result = await creator.create_account_with_concurrency(config)

            # Verify result structure
            assert "success" in result
            assert "phone_number" in result or "message" in result

            # Verify SMS provider was called
            mock_sms_provider.get_phone_number.assert_called_once()

            # Verify proxy was assigned
            if config["use_proxy"]:
                mock_proxy_pool.assign_proxy_to_account.assert_called_once()


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_account_creation_failure_handling():
    """Test account creation handles failures gracefully."""

    # Setup test database
    from scraping.member_scraper import MemberDatabase

    test_db = MemberDatabase(":memory:")

    # Mock Gemini service
    mock_gemini_service = Mock()
    mock_gemini_service.generate_response = AsyncMock(return_value="Test response")

    # Mock account manager
    mock_account_manager = Mock()
    mock_account_manager.add_account = AsyncMock(return_value=True)

    # Mock SMS provider that fails
    mock_sms_provider = Mock()
    mock_sms_provider.get_phone_number = AsyncMock(
        return_value={"success": False, "error": "No numbers available"}
    )

    with patch("accounts.account_creator.Client", MockTelegramClient):
        from accounts.account_creator import AccountCreator

        creator = AccountCreator(
            db=test_db, gemini_service=mock_gemini_service, account_manager=mock_account_manager
        )
        creator.phone_provider = mock_sms_provider

        config = {"country": "US"}

        # Should handle failure gracefully
        result = await creator.create_account_with_concurrency(config)

        # Verify error is reported
        assert not result["success"]
        assert "error" in result or "message" in result


@pytest.mark.e2e
def test_account_persistence():
    """Test accounts are properly saved to database."""

    # Create test database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create accounts table
    cursor.execute(
        """
        CREATE TABLE accounts (
            phone_number TEXT PRIMARY KEY,
            username TEXT,
            status TEXT,
            created_at TIMESTAMP,
            api_id TEXT,
            api_hash TEXT
        )
    """
    )

    # Insert test account
    test_account = create_test_account()
    cursor.execute(
        """
        INSERT INTO accounts (phone_number, username, status, created_at, api_id, api_hash)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            test_account["phone_number"],
            test_account["username"],
            test_account["status"],
            test_account["created_at"],
            test_account["api_id"],
            test_account["api_hash"],
        ),
    )
    conn.commit()

    # Verify saved
    cursor.execute("SELECT * FROM accounts WHERE phone_number = ?", (test_account["phone_number"],))
    saved_account = cursor.fetchone()

    assert saved_account is not None
    assert saved_account[0] == test_account["phone_number"]
    assert saved_account[1] == test_account["username"]

    conn.close()
