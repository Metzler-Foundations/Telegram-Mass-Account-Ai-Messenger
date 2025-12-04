import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import psutil

logger = logging.getLogger(__name__)

# Import randomization utilities and app context
from utils.utils import RandomizationUtils, app_context
from monitoring.performance_monitor import get_resilience_manager


class GeminiService:
    """Service for interacting with Google Gemini AI.
    
    Supports both shared brain configuration and per-account custom prompts.
    """

    def __init__(self, api_key: str, brain_config: Dict[str, Any] = None):
        """Initialize the Gemini service.

        Args:
            api_key: Google Gemini API key
            brain_config: Optional per-account brain configuration dict with:
                - use_shared_brain: bool
                - custom_prompt: str
                - gemini_temperature: float
                - gemini_top_p: float
                - gemini_top_k: int
                - gemini_max_tokens: int
        """
        self.api_key = api_key
        self.model = None
        self.conversation_history: Dict[int, List[Dict[str, str]]] = {}
        self.brain_prompt = ""
        self.max_history_length = 50  # Maximum messages to keep in history per chat
        
        # Per-account brain configuration
        self.brain_config = brain_config or {}
        self.custom_generation_config = None
        
        # Apply brain config if provided
        if brain_config and not brain_config.get('use_shared_brain', True):
            self._apply_brain_config(brain_config)

        self._initialize_model()

        # Resilience management
        self.resilience_manager = get_resilience_manager()
        self._setup_resilience_strategies()

    def _setup_resilience_strategies(self):
        """Set up circuit breakers and fallback strategies for Gemini AI operations."""
        # Circuit breaker for Gemini API calls
        self.gemini_circuit_breaker = self.resilience_manager.get_circuit_breaker(
            "gemini_api_calls",
            failure_threshold=5,
            recovery_timeout=60,
            success_threshold=2
        )

        # Fallback strategies for text generation
        generation_fallback = self.resilience_manager.get_fallback_strategy("gemini_text_generation")

        # Primary: Full Gemini generation with history
        async def primary_generation(prompt, chat_id, **kwargs):
            return await self._generate_with_gemini(prompt, chat_id, **kwargs)

        # Fallback 1: Gemini generation without history
        async def fallback_no_history(prompt, chat_id, **kwargs):
            # Temporarily disable history
            original_history = self.conversation_history.get(chat_id, [])
            self.conversation_history[chat_id] = []
            try:
                result = await self._generate_with_gemini(prompt, chat_id, **kwargs)
                return result
            finally:
                self.conversation_history[chat_id] = original_history

        # Fallback 2: Simple template-based response
        async def fallback_template(prompt, chat_id, **kwargs):
            # Generate a simple response based on keywords
            if "hello" in prompt.lower() or "hi" in prompt.lower():
                return "Hello! How can I help you today?"
            elif "bye" in prompt.lower() or "goodbye" in prompt.lower():
                return "Goodbye! Have a great day!"
            else:
                return "I understand you're reaching out. How can I assist you?"

        generation_fallback.add_fallback(primary_generation, "Full Gemini generation")
        generation_fallback.add_fallback(fallback_no_history, "Gemini without history")
        generation_fallback.add_fallback(fallback_template, "Template-based fallback")

    def _initialize_model(self) -> None:
        """Initialize the Gemini model."""
        try:
            genai.configure(api_key=self.api_key)
            
            # Use custom generation config if set, otherwise use defaults
            default_config = {
                'temperature': 0.7,
                'top_p': 0.8,
                'top_k': 40,
                'max_output_tokens': 1024,
            }
            
            gen_config = self.custom_generation_config or default_config
            
            # Use BLOCK_NONE for content generation (required for adult content scenarios)
            self.model = genai.GenerativeModel(
                model_name='gemini-1.5-flash',
                generation_config=gen_config,
                safety_settings={
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                }
            )
            logger.info("Gemini model initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            self.model = None
    
    def _apply_brain_config(self, brain_config: Dict[str, Any]) -> None:
        """Apply per-account brain configuration.
        
        Args:
            brain_config: Brain configuration dictionary
        """
        # Set custom prompt if provided
        custom_prompt = brain_config.get('custom_prompt', '')
        if custom_prompt:
            self.brain_prompt = custom_prompt
            logger.info("Applied custom brain prompt from brain_config")
        
        # Build custom generation config
        self.custom_generation_config = {
            'temperature': brain_config.get('gemini_temperature', 0.8),
            'top_p': brain_config.get('gemini_top_p', 0.9),
            'top_k': brain_config.get('gemini_top_k', 40),
            'max_output_tokens': brain_config.get('gemini_max_tokens', 1000),
        }
        
        logger.info(f"Applied custom brain config: temp={self.custom_generation_config['temperature']}, "
                   f"top_p={self.custom_generation_config['top_p']}")
    
    def update_brain_config(self, brain_config: Dict[str, Any]) -> None:
        """Update the brain configuration and reinitialize the model.
        
        Args:
            brain_config: New brain configuration
        """
        self.brain_config = brain_config
        
        if brain_config and not brain_config.get('use_shared_brain', True):
            self._apply_brain_config(brain_config)
        else:
            # Reset to defaults
            self.custom_generation_config = None
        
        # Reinitialize model with new config
        self._initialize_model()
        logger.info("Brain configuration updated")

    def set_brain_prompt(self, prompt: str) -> None:
        """Set the brain/system prompt for the AI.

        Args:
            prompt: The system prompt that defines the AI's personality and behavior
        """
        self.brain_prompt = prompt
        logger.info("Brain prompt updated")

    def set_max_history_length(self, length: int) -> None:
        """Set the maximum conversation history length.

        Args:
            length: Maximum number of messages to keep in history (5-200)
        """
        self.max_history_length = max(5, min(length, 200))  # Clamp between 5 and 200
        logger.info(f"Max history length updated to {self.max_history_length}")

    def clear_conversation_history(self, chat_id: int) -> None:
        """Clear conversation history for a specific chat.

        Args:
            chat_id: Chat ID to clear history for
        """
        if chat_id in self.conversation_history:
            self.conversation_history[chat_id] = []
            logger.info(f"Cleared conversation history for chat {chat_id}")

    def _get_conversation_context(self, chat_id: int, new_message: str) -> str:
        """Build conversation context for the AI.

        Args:
            chat_id: Chat ID
            new_message: New incoming message

        Returns:
            str: Formatted conversation context
        """
        context_parts = []

        # Add brain prompt if set
        if self.brain_prompt:
            context_parts.append(f"System: {self.brain_prompt}")

        # Add recent conversation history
        if chat_id in self.conversation_history:
            history = self.conversation_history[chat_id][-10:]  # Last 10 messages
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                context_parts.append(f"{role}: {msg['content']}")

        # Add current message
        context_parts.append(f"User: {new_message}")

        # Add instruction for response
        context_parts.append("\nAssistant: Please respond naturally and helpfully based on the system instructions above.")

        return "\n\n".join(context_parts)

    def _add_to_history(self, chat_id: int, role: str, content: str) -> None:
        """Add a message to conversation history.

        Args:
            chat_id: Chat ID
            role: Role of the message sender ('user' or 'assistant')
            content: Message content
        """
        if chat_id not in self.conversation_history:
            self.conversation_history[chat_id] = []

        self.conversation_history[chat_id].append({
            "role": role,
            "content": content
        })

        # Trim history if it gets too long
        if len(self.conversation_history[chat_id]) > self.max_history_length:
            # Keep only the most recent messages
            self.conversation_history[chat_id] = self.conversation_history[chat_id][-self.max_history_length:]

        # Periodic cleanup of old conversation histories (keep only active chats)
        self._cleanup_old_histories()

    async def generate_reply(self, message: str, chat_id: int, max_retries: int = 3) -> Optional[str]:
        """Generate a reply using Gemini AI with resilience features and anti-detection measures.

        Args:
            message: Incoming message text
            chat_id: Chat ID for conversation context
            max_retries: Maximum number of retry attempts (deprecated - resilience manager handles this)

        Returns:
            Optional[str]: Generated reply text, or None if generation failed
        """
        if not self.model:
            logger.error("Gemini model not initialized")
            return None  # Don't send error messages to avoid detection

        if not message.strip():
            return None

        # Use resilience manager for fault-tolerant generation
        try:
            result, fallback_used = await self.resilience_manager.execute_with_resilience(
                f"gemini_generation_{chat_id}",
                self._generate_reply_operation,
                message, chat_id,
                circuit_breaker=True,
                fallback=True
            )

            if fallback_used:
                logger.info(f"Used fallback strategy for Gemini generation: {fallback_used}")

            return result

        except Exception as e:
            logger.error(f"All Gemini generation strategies failed for chat {chat_id}: {e}")
            # Record error metrics
            app_context.record_api_call(0, error=True)
            return None

    async def _generate_reply_operation(self, message: str, chat_id: int) -> Optional[str]:
        """Core reply generation operation with anti-detection measures."""
        start_time = time.time()

        # Anti-detection: Advanced rate limiting with randomization
        current_time = time.time()
        if hasattr(self, '_last_request_time'):
            time_since_last = current_time - self._last_request_time
            min_interval = RandomizationUtils.get_interval_range()
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)

        self._last_request_time = current_time

        # Anti-detection: Randomize request timing
        if random.random() < 0.1:  # 10% chance
            await asyncio.sleep(RandomizationUtils.get_typing_delay())

        # Add user message to history
        self._add_to_history(chat_id, "user", message)

        # Build conversation context with anti-detection measures
        context = self._get_conversation_context(chat_id, message)

        # Use custom generation config or randomized defaults
        if self.custom_generation_config:
            # Use custom config with slight randomization
            generation_config = {
                'temperature': self.custom_generation_config['temperature'] * random.uniform(0.95, 1.05),
                'top_p': self.custom_generation_config['top_p'],
                'top_k': self.custom_generation_config['top_k'],
                'max_output_tokens': self.custom_generation_config['max_output_tokens'],
            }
        else:
            # Anti-detection: Vary model parameters slightly
            generation_config = {
                'temperature': RandomizationUtils.get_gemini_temperature(),
                'top_p': RandomizationUtils.get_gemini_top_p(),
                'top_k': RandomizationUtils.get_gemini_top_k(),
                'max_output_tokens': RandomizationUtils.get_gemini_max_tokens(),
            }

        # Generate response with anti-detection timeout
        response = await asyncio.wait_for(
            self.model.generate_content_async(context, generation_config=generation_config),
            timeout=RandomizationUtils.get_api_timeout()
        )

        # Record performance metrics
        response_time = time.time() - start_time
        # Record API call performance
        app_context.record_api_call(response_time)

        if response and response.text:
            reply_text = response.text.strip()

            # Anti-detection: Vary response length and formatting
            reply_text = self._apply_anti_detection_formatting(reply_text, message)

            # Validate response length
            if len(reply_text) > 4000:  # Telegram message limit is 4096
                reply_text = reply_text[:3997] + "..."

            # Anti-detection: Sometimes don't save to history to avoid patterns
            if random.random() > 0.1:  # 90% chance to save
                self._add_to_history(chat_id, "assistant", reply_text)

            logger.info(f"Generated anti-detection reply for chat {chat_id}: {len(reply_text)} chars")
            return reply_text
        else:
            raise Exception("Empty response from Gemini API")

        return None

    def _apply_anti_detection_formatting(self, reply_text: str, original_message: str) -> str:
        """Apply subtle formatting variations to avoid detection."""
        # Occasionally vary punctuation
        if random.random() < 0.2:  # 20% chance
            if reply_text.endswith('.'):
                reply_text = reply_text[:-1] + '!' if random.random() < 0.5 else reply_text[:-1] + '...'

        # Vary capitalization patterns occasionally
        if random.random() < 0.1:  # 10% chance
            words = reply_text.split()
            if len(words) > 2:
                # Randomly capitalize a word
                idx = random.randint(0, len(words)-1)
                words[idx] = words[idx].capitalize()
                reply_text = ' '.join(words)

        # Occasionally add filler words
        filler_words = ["well", "you know", "like", "actually", "hmm"]
        if random.random() < 0.05 and len(reply_text.split()) > 3:  # 5% chance
            words = reply_text.split()
            insert_pos = random.randint(1, len(words)-1)
            filler = random.choice(filler_words)
            words.insert(insert_pos, filler)
            reply_text = ' '.join(words)

        return reply_text

    def is_initialized(self) -> bool:
        """Check if the Gemini service is properly initialized.

        Returns:
            bool: True if initialized, False otherwise
        """
        return self.model is not None

    def get_conversation_stats(self, chat_id: int) -> Dict[str, Any]:
        """Get statistics about a conversation.

        Args:
            chat_id: Chat ID to get stats for

        Returns:
            Dict with conversation statistics
        """
        history = self.conversation_history.get(chat_id, [])
        return {
            "message_count": len(history),
            "chat_id": chat_id,
            "has_brain_prompt": bool(self.brain_prompt)
        }

    def update_api_key(self, new_api_key: str) -> bool:
        """Update the Gemini API key.

        Args:
            new_api_key: New API key

        Returns:
            bool: True if update successful, False otherwise
        """
        try:
            self.api_key = new_api_key
            self._initialize_model()
            return self.is_initialized()
        except Exception as e:
            logger.error(f"Failed to update API key: {e}")
            return False

    def _cleanup_old_histories(self, max_chats: int = 100, max_age_hours: int = 24, max_memory_mb: float = 50.0):
        """Clean up old conversation histories to prevent memory leaks."""
        import time
        import sys

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        # Check memory usage first
        process = psutil.Process()
        memory_mb = process.memory_info().rss / 1024 / 1024

        if memory_mb > max_memory_mb:
            logger.warning(f"High memory usage detected: {memory_mb:.1f}MB, cleaning up conversation histories")

        # Remove chats that haven't been active recently or if memory is high
        chats_to_remove = []
        for chat_id, history in self.conversation_history.items():
            if not history:
                chats_to_remove.append(chat_id)
                continue

            # Check if the last message is too old
            last_message_time = history[-1].get('timestamp', 0)
            if isinstance(last_message_time, str):
                # Convert ISO string to timestamp if needed
                try:
                    from datetime import datetime
                    last_message_time = datetime.fromisoformat(last_message_time.replace('Z', '+00:00')).timestamp()
                except (ValueError, AttributeError, TypeError) as e:
                    logger.debug(f"Could not parse last message time: {e}")
                    last_message_time = 0

            # Remove if too old or if memory pressure is high
            age_seconds = current_time - last_message_time
            if age_seconds > max_age_seconds or (memory_mb > max_memory_mb and age_seconds > 3600):  # 1 hour if memory high
                chats_to_remove.append(chat_id)

        # Remove old chats
        for chat_id in chats_to_remove:
            del self.conversation_history[chat_id]

        # If still too many chats or high memory, remove oldest ones
        if len(self.conversation_history) > max_chats or memory_mb > max_memory_mb:
            # Sort by last activity and keep only the most recent
            sorted_chats = sorted(
                self.conversation_history.items(),
                key=lambda x: x[1][-1].get('timestamp', 0) if x[1] else 0,
                reverse=True
            )

            # Keep fewer chats if memory is high
            keep_count = max_chats // 2 if memory_mb > max_memory_mb else max_chats
            self.conversation_history = dict(sorted_chats[:keep_count])

            if chats_to_remove or len(sorted_chats) > keep_count:
                logger.info(f"Cleaned up conversation histories: removed {len(chats_to_remove)} old chats, "
                          f"kept {len(self.conversation_history)} active chats, "
                          f"memory usage: {memory_mb:.1f}MB")


def create_gemini_service_for_account(api_key: str, account_data: Dict[str, Any], 
                                       shared_prompt: str = "") -> GeminiService:
    """Factory function to create a GeminiService configured for a specific account.
    
    Args:
        api_key: Gemini API key
        account_data: Account data dictionary containing brain_config
        shared_prompt: The shared/global brain prompt
        
    Returns:
        Configured GeminiService instance
    """
    brain_config = account_data.get('brain_config', {})
    
    # Create service with brain config
    service = GeminiService(api_key=api_key, brain_config=brain_config)
    
    # Set the appropriate prompt
    if brain_config.get('use_shared_brain', True):
        # Use shared prompt
        if shared_prompt:
            service.set_brain_prompt(shared_prompt)
    else:
        # Custom prompt should already be set from brain_config
        # But if not, try to get default based on account type
        if not service.brain_prompt:
            account_type = account_data.get('account_type', 'reactive')
            from account_manager import DEFAULT_BRAIN_PROMPTS, AccountType
            try:
                default_prompt = DEFAULT_BRAIN_PROMPTS.get(AccountType(account_type), "")
                if default_prompt:
                    service.set_brain_prompt(default_prompt)
            except Exception as exc:
                logger.warning(
                    "Failed to resolve default Gemini prompt for account type %s: %s",
                    account_type,
                    exc,
                )
    
    return service
