"""
Test data factories and sample data for testing.
"""
from datetime import datetime
from typing import Dict, List, Any
import random


def create_test_account(
    phone_number: str = "+1234567890",
    status: str = "active",
    **kwargs
) -> Dict[str, Any]:
    """Create a test account dictionary."""
    account = {
        'phone_number': phone_number,
        'username': kwargs.get('username', f'user_{phone_number[-4:]}'),
        'status': status,
        'api_id': kwargs.get('api_id', '12345678'),
        'api_hash': kwargs.get('api_hash', 'a' * 32),
        'created_at': kwargs.get('created_at', datetime.now()),
        'last_active': kwargs.get('last_active', datetime.now()),
        'risk_score': kwargs.get('risk_score', 0),
        'warmup_stage': kwargs.get('warmup_stage', 0),
        'messages_sent': kwargs.get('messages_sent', 0),
        'messages_received': kwargs.get('messages_received', 0),
    }
    account.update(kwargs)
    return account


def create_test_member(
    user_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a test member dictionary."""
    if user_id is None:
        user_id = random.randint(100000, 999999)
    
    member = {
        'user_id': user_id,
        'first_name': kwargs.get('first_name', f'User{user_id}'),
        'last_name': kwargs.get('last_name', 'Test'),
        'username': kwargs.get('username', f'user{user_id}'),
        'phone': kwargs.get('phone', None),
        'bio': kwargs.get('bio', 'Test bio'),
        'profile_quality_score': kwargs.get('profile_quality_score', 0.7),
        'messaging_potential_score': kwargs.get('messaging_potential_score', 0.6),
        'risk_score': kwargs.get('risk_score', 10),
        'is_bot': kwargs.get('is_bot', False),
        'is_verified': kwargs.get('is_verified', False),
        'last_seen': kwargs.get('last_seen', datetime.now()),
        'scraped_from': kwargs.get('scraped_from', 'test_channel'),
        'scraped_at': kwargs.get('scraped_at', datetime.now()),
    }
    member.update(kwargs)
    return member


def create_test_campaign(
    campaign_id: int = None,
    **kwargs
) -> Dict[str, Any]:
    """Create a test campaign dictionary."""
    if campaign_id is None:
        campaign_id = random.randint(1, 9999)
    
    campaign = {
        'id': campaign_id,
        'name': kwargs.get('name', f'Test Campaign {campaign_id}'),
        'template': kwargs.get('template', 'Hello {first_name}!'),
        'status': kwargs.get('status', 'draft'),
        'target_channel_id': kwargs.get('target_channel_id', '@testchannel'),
        'target_member_ids': kwargs.get('target_member_ids', [1, 2, 3]),
        'account_ids': kwargs.get('account_ids', ['+1234567890']),
        'created_at': kwargs.get('created_at', datetime.now()),
        'started_at': kwargs.get('started_at', None),
        'completed_at': kwargs.get('completed_at', None),
        'total_targets': kwargs.get('total_targets', 3),
        'sent_count': kwargs.get('sent_count', 0),
        'failed_count': kwargs.get('failed_count', 0),
        'blocked_count': kwargs.get('blocked_count', 0),
        'rate_limit_delay': kwargs.get('rate_limit_delay', 5),
        'max_messages_per_hour': kwargs.get('max_messages_per_hour', 20),
        'max_messages_per_account': kwargs.get('max_messages_per_account', 100),
        'config': kwargs.get('config', {}),
    }
    campaign.update(kwargs)
    return campaign


# Sample data sets
sample_accounts: List[Dict[str, Any]] = [
    create_test_account('+1234567890', 'active', username='test_user1'),
    create_test_account('+1234567891', 'active', username='test_user2'),
    create_test_account('+1234567892', 'warmup', username='test_user3'),
    create_test_account('+1234567893', 'banned', username='test_user4'),
    create_test_account('+1234567894', 'suspended', username='test_user5'),
]

sample_members: List[Dict[str, Any]] = [
    create_test_member(100001, first_name='Alice', profile_quality_score=0.9),
    create_test_member(100002, first_name='Bob', profile_quality_score=0.7),
    create_test_member(100003, first_name='Charlie', profile_quality_score=0.5),
    create_test_member(100004, first_name='David', is_bot=True),
    create_test_member(100005, first_name='Eve', risk_score=50),
]

sample_campaigns: List[Dict[str, Any]] = [
    create_test_campaign(1, name='Test Campaign 1', status='draft'),
    create_test_campaign(2, name='Test Campaign 2', status='running'),
    create_test_campaign(3, name='Test Campaign 3', status='completed'),
]

sample_proxies: List[Dict[str, Any]] = [
    {
        'id': 1,
        'ip': '1.2.3.4',
        'port': 8080,
        'protocol': 'http',
        'username': None,
        'password': None,
        'country': 'US',
        'status': 'active',
        'health': 100,
        'last_checked': datetime.now(),
    },
    {
        'id': 2,
        'ip': '5.6.7.8',
        'port': 1080,
        'protocol': 'socks5',
        'username': 'user',
        'password': 'pass',
        'country': 'UK',
        'status': 'active',
        'health': 90,
        'last_checked': datetime.now(),
    },
]


def create_large_member_dataset(count: int = 1000) -> List[Dict[str, Any]]:
    """Create a large dataset of test members for performance testing."""
    return [
        create_test_member(
            user_id=100000 + i,
            first_name=f'User{i}',
            profile_quality_score=0.5 + (i % 50) / 100,
            messaging_potential_score=0.4 + (i % 60) / 100,
        )
        for i in range(count)
    ]

