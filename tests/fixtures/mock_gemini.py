"""
Mock Google Gemini AI service for testing.
"""
from typing import Optional, List, Dict, Any
import asyncio


class MockGenerativeModel:
    """Mock Gemini generative model."""
    
    def __init__(
        self,
        model_name: str = "gemini-1.5-flash-latest",
        generation_config: Optional[Dict] = None,
        **kwargs
    ):
        self.model_name = model_name
        self.generation_config = generation_config or {}
        self.call_count = 0
    
    async def generate_content_async(self, prompt: str) -> 'MockGenerateContentResponse':
        """Mock async content generation."""
        self.call_count += 1
        await asyncio.sleep(0.01)  # Simulate API delay
        
        # Generate simple mock response
        response_text = f"Mock response to: {prompt[:50]}..."
        
        return MockGenerateContentResponse(text=response_text)
    
    def generate_content(self, prompt: str) -> 'MockGenerateContentResponse':
        """Mock sync content generation."""
        self.call_count += 1
        response_text = f"Mock response to: {prompt[:50]}..."
        return MockGenerateContentResponse(text=response_text)


class MockGenerateContentResponse:
    """Mock Gemini API response."""
    
    def __init__(self, text: str):
        self._text = text
    
    @property
    def text(self) -> str:
        """Get response text."""
        return self._text


class MockGeminiService:
    """Mock Gemini service for testing."""
    
    def __init__(
        self,
        api_key: str,
        brain_config: Optional[Dict[str, Any]] = None
    ):
        self.api_key = api_key
        self.brain_config = brain_config or {}
        self.model = MockGenerativeModel()
        self.conversation_history: Dict[int, List[Dict[str, str]]] = {}
        self.brain_prompt = brain_config.get('custom_prompt', '') if brain_config else ''
    
    async def generate_response(
        self,
        message: str,
        chat_id: int,
        context: Optional[str] = None,
        **kwargs
    ) -> str:
        """Mock generate response."""
        await asyncio.sleep(0.01)  # Simulate API delay
        
        # Store in history
        if chat_id not in self.conversation_history:
            self.conversation_history[chat_id] = []
        
        self.conversation_history[chat_id].append({
            'role': 'user',
            'content': message,
        })
        
        # Generate mock response
        response = f"AI response to: {message[:30]}..."
        
        self.conversation_history[chat_id].append({
            'role': 'assistant',
            'content': response,
        })
        
        return response
    
    def update_brain_prompt(self, prompt: str):
        """Mock update brain prompt."""
        self.brain_prompt = prompt
    
    def get_conversation_history(self, chat_id: int) -> List[Dict[str, str]]:
        """Get conversation history for chat."""
        return self.conversation_history.get(chat_id, [])
    
    def clear_conversation_history(self, chat_id: Optional[int] = None):
        """Clear conversation history."""
        if chat_id is None:
            self.conversation_history.clear()
        else:
            self.conversation_history.pop(chat_id, None)

