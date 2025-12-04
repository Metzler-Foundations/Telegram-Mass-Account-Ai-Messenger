#!/usr/bin/env python3
"""Gemini API error handler - Prevent crashes from AI errors."""

import logging
from typing import Optional
import asyncio

logger = logging.getLogger(__name__)


class GeminiErrorHandler:
    """Handles Gemini API errors gracefully."""
    
    @staticmethod
    async def safe_generate(client, prompt: str, max_retries: int = 3) -> Optional[str]:
        """Generate content with error handling."""
        for attempt in range(max_retries):
            try:
                response = await client.generate_content_async(prompt)
                if response and response.text:
                    return response.text
                
            except Exception as e:
                error_type = type(e).__name__
                logger.error(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {error_type} - {e}")
                
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    # Return fallback content
                    return "Hello! How can I help you today?"
        
        return None


async def generate_with_fallback(client, prompt: str, fallback: str = None) -> str:
    """Generate content with fallback."""
    result = await GeminiErrorHandler.safe_generate(client, prompt)
    return result or fallback or "Hi there!"



