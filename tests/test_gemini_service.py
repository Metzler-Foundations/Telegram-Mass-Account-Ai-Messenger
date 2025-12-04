"""Tests for Gemini AI service."""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from tests.fixtures import MockGeminiService, MockGenerativeModel


class TestGeminiService:
    """Test Gemini service functionality."""
    
    @pytest.mark.asyncio
    async def test_generate_response(self):
        """Test AI response generation."""
        service = MockGeminiService('test_api_key')
        
        response = await service.generate_response("Hello", chat_id=123)
        
        assert "AI response" in response
        assert len(service.conversation_history[123]) == 2
    
    @pytest.mark.asyncio
    async def test_conversation_history(self):
        """Test conversation history tracking."""
        service = MockGeminiService('test_api_key')
        
        await service.generate_response("Message 1", chat_id=123)
        await service.generate_response("Message 2", chat_id=123)
        
        history = service.get_conversation_history(123)
        assert len(history) == 4  # 2 user + 2 assistant
    
    @pytest.mark.asyncio
    async def test_clear_history(self):
        """Test clearing conversation history."""
        service = MockGeminiService('test_api_key')
        
        await service.generate_response("Test", chat_id=123)
        assert len(service.get_conversation_history(123)) > 0
        
        service.clear_conversation_history(123)
        assert len(service.get_conversation_history(123)) == 0
    
    def test_brain_prompt_update(self):
        """Test updating brain prompt."""
        service = MockGeminiService('test_api_key')
        
        service.update_brain_prompt("New personality")
        assert service.brain_prompt == "New personality"

