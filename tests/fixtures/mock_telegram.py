"""
Mock Telegram client for testing.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio


class MockUser:
    """Mock Telegram user."""
    
    def __init__(
        self,
        id: int,
        first_name: str = "Test",
        last_name: Optional[str] = None,
        username: Optional[str] = None,
        is_bot: bool = False,
    ):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.username = username
        self.is_bot = is_bot
        self.is_verified = False
        self.is_premium = False


class MockChat:
    """Mock Telegram chat."""
    
    def __init__(
        self,
        id: int,
        type: str = "private",
        title: Optional[str] = None,
        username: Optional[str] = None,
    ):
        self.id = id
        self.type = type
        self.title = title
        self.username = username


class MockMessage:
    """Mock Telegram message."""
    
    def __init__(
        self,
        message_id: int,
        from_user: MockUser,
        chat: MockChat,
        text: str = "",
        date: Optional[datetime] = None,
    ):
        self.message_id = message_id
        self.from_user = from_user
        self.chat = chat
        self.text = text
        self.date = date or datetime.now()
        self.reply_to_message = None


class MockTelegramClient:
    """Mock Telegram client for testing."""
    
    def __init__(
        self,
        api_id: str,
        api_hash: str,
        phone_number: str,
        **kwargs
    ):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.is_connected = False
        self.is_authorized = False
        self.sent_messages: List[Dict[str, Any]] = []
        self.received_messages: List[MockMessage] = []
        self._message_handlers = []
    
    async def initialize(self) -> bool:
        """Mock initialization."""
        await asyncio.sleep(0.01)  # Simulate async operation
        self.is_connected = True
        self.is_authorized = True
        return True
    
    async def start(self):
        """Mock start."""
        await self.initialize()
    
    async def stop(self):
        """Mock stop."""
        self.is_connected = False
    
    async def send_message(
        self,
        chat_id: int,
        text: str,
        **kwargs
    ) -> MockMessage:
        """Mock send message."""
        if not self.is_authorized:
            raise Exception("Not authorized")
        
        message = MockMessage(
            message_id=len(self.sent_messages) + 1,
            from_user=MockUser(id=12345, username="self"),
            chat=MockChat(id=chat_id),
            text=text,
        )
        
        self.sent_messages.append({
            'chat_id': chat_id,
            'text': text,
            'timestamp': datetime.now(),
            **kwargs
        })
        
        await asyncio.sleep(0.01)  # Simulate network delay
        return message
    
    async def get_chat_members(self, chat_id: int, limit: int = 100):
        """Mock get chat members."""
        for i in range(min(limit, 10)):
            yield MockUser(
                id=1000 + i,
                first_name=f"User{i}",
                username=f"user{i}",
            )
            await asyncio.sleep(0.001)  # Simulate API delay
    
    async def get_me(self) -> MockUser:
        """Mock get current user."""
        return MockUser(
            id=12345,
            first_name="Test",
            username="test_bot",
        )
    
    def add_handler(self, handler, group: int = 0):
        """Mock add handler."""
        self._message_handlers.append((handler, group))
    
    async def run_forever(self):
        """Mock run forever."""
        while self.is_connected:
            await asyncio.sleep(0.1)

