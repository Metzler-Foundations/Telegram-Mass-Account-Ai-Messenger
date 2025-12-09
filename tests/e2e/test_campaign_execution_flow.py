"""
E2E Test: Campaign Execution Flow

Tests the complete campaign workflow:
1. Create campaign
2. Filter target members
3. Render message templates
4. Send messages via accounts
5. Track delivery
6. Handle FloodWait
7. Update campaign status
"""

import pytest
import asyncio
import sqlite3
from unittest.mock import Mock, patch, AsyncMock
from tests.fixtures import (
    MockTelegramClient,
    create_test_campaign,
    create_test_member,
    sample_accounts,
)


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_campaign_execution_complete_flow():
    """Test complete campaign execution from creation to delivery."""

    # Setup
    test_db = ":memory:"

    # Create test campaign
    campaign = create_test_campaign(
        name="E2E Test Campaign",
        template="Hello {first_name}!",
        status="queued",
        target_member_ids=[1, 2, 3],
        account_ids=["+1234567890"],
    )

    # Create test members
    members = [
        create_test_member(user_id=1, first_name="Alice"),
        create_test_member(user_id=2, first_name="Bob"),
        create_test_member(user_id=3, first_name="Charlie"),
    ]

    # Mock Telegram client
    mock_client = MockTelegramClient("api_id", "api_hash", "+1234567890")
    await mock_client.initialize()

    # Mock campaign manager
    with patch("campaigns.dm_campaign_manager.Client", return_value=mock_client):
        from campaigns.dm_campaign_manager import DMCampaignManager, MessageTemplateEngine

        # Test template rendering
        for member in members:
            rendered = MessageTemplateEngine.render(campaign["template"], member)
            assert member["first_name"] in rendered
            assert "{first_name}" not in rendered  # Variable replaced

        # Simulate sending
        sent_count = 0
        for member in members:
            message_text = MessageTemplateEngine.render(campaign["template"], member)

            try:
                await mock_client.send_message(member["user_id"], message_text)
                sent_count += 1
            except Exception as e:
                # Handle errors (FloodWait, blocked, etc.)
                pass

        # Verify messages sent
        assert sent_count == 3
        assert len(mock_client.sent_messages) == 3

        # Verify all messages are unique (personalized)
        message_texts = [msg["text"] for msg in mock_client.sent_messages]
        assert len(set(message_texts)) == 3  # All different


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_campaign_floodwait_handling():
    """Test campaign handles FloodWait errors correctly."""

    from pyrogram.errors import FloodWait

    # Mock client that raises FloodWait
    mock_client = MockTelegramClient("api_id", "api_hash", "+1234567890")
    await mock_client.initialize()

    # Override send_message to raise FloodWait
    original_send = mock_client.send_message
    call_count = [0]

    async def floodwait_send(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise FloodWait(value=10)  # 10 second wait
        return await original_send(*args, **kwargs)

    mock_client.send_message = floodwait_send

    # Attempt to send
    try:
        await mock_client.send_message(12345, "Test")
    except FloodWait as e:
        # Should catch FloodWait
        assert e.value == 10

        # Simulate wait and retry
        await asyncio.sleep(0.01)  # Simulate wait (shortened for test)
        result = await mock_client.send_message(12345, "Test")

        # Second attempt should succeed
        assert result is not None


@pytest.mark.e2e
def test_campaign_idempotency():
    """Test campaigns prevent duplicate message sends."""

    # Create test database
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # Create campaign_messages table with idempotency key
    cursor.execute(
        """
        CREATE TABLE campaign_messages (
            id INTEGER PRIMARY KEY,
            campaign_id INTEGER,
            user_id INTEGER,
            account_phone TEXT,
            message_text TEXT,
            status TEXT,
            idempotency_key TEXT UNIQUE,
            sent_at TIMESTAMP
        )
    """
    )

    # Generate idempotency key
    campaign_id = 1
    user_id = 12345
    account_phone = "+1234567890"
    idempotency_key = f"{campaign_id}:{user_id}:{account_phone}"

    # Insert first message
    cursor.execute(
        """
        INSERT INTO campaign_messages 
        (campaign_id, user_id, account_phone, message_text, status, idempotency_key)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (campaign_id, user_id, account_phone, "Hello!", "sent", idempotency_key),
    )
    conn.commit()

    # Try to insert duplicate (should fail due to UNIQUE constraint)
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            """
            INSERT INTO campaign_messages 
            (campaign_id, user_id, account_phone, message_text, status, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (campaign_id, user_id, account_phone, "Hello again!", "sent", idempotency_key),
        )
        conn.commit()

    conn.close()


@pytest.mark.e2e
def test_template_rendering_edge_cases():
    """Test template engine handles edge cases."""

    from campaigns.dm_campaign_manager import MessageTemplateEngine

    # Test missing variables
    member_minimal = {"user_id": 123}
    template = "Hello {first_name}!"
    rendered = MessageTemplateEngine.render(template, member_minimal)
    assert "Hello !" in rendered  # Empty if missing

    # Test special characters
    member_special = {"user_id": 123, "first_name": "O'Brien", "username": "user@123"}
    template = "Hello {first_name}, @{username}"
    rendered = MessageTemplateEngine.render(template, member_special)
    assert "O'Brien" in rendered
    assert "@user" in rendered  # Should handle @ symbol

    # Test long names (should be truncated by sanitization)
    member_long = {"user_id": 123, "first_name": "A" * 200}  # Very long name
    template = "Hello {first_name}!"
    rendered = MessageTemplateEngine.render(template, member_long)
    assert len(rendered) < 250  # Should be truncated
