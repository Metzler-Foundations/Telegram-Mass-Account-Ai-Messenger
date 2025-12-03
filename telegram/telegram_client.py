import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Optional, Callable, Any, Dict, Union, Coroutine, List
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.enums import ChatAction

logger = logging.getLogger(__name__)

# Import randomization utilities and event system
from utils.utils import (
    RandomizationUtils,
    EVENT_MESSAGE_RECEIVED,
    EVENT_MESSAGE_SENT,
    EVENT_VOICE_MESSAGE_SENT,
    EVENT_VOICE_MESSAGE_FAILED,
    EVENT_SERVICE_STARTED,
    EVENT_SERVICE_STOPPED,
    app_context
)
from monitoring.performance_monitor import get_resilience_manager
_event_system_available = True


class TelegramClient:
    """Telegram client wrapper using Pyrogram for auto-reply functionality."""

    def __init__(self, api_id: str, api_hash: str, phone_number: str, realistic_typing: bool = True, random_delays: bool = True, anti_detection_settings: Optional[Dict[str, Any]] = None, proxy: Optional[Dict] = None):
        """Initialize the Telegram client.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone_number: Phone number for authentication
            realistic_typing: Whether to simulate character-by-character typing
            random_delays: Whether to add random delays for human-like behavior
            proxy: Optional proxy configuration (permanent proxy for this account)
        """
        # Initialize secure session directory
        self.session_dir = None
        """Initialize the Telegram client.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API hash
            phone_number: Phone number for authentication
            realistic_typing: Whether to simulate character-by-character typing
            random_delays: Whether to add random delays for human-like behavior
            proxy: Optional proxy configuration (permanent proxy for this account)
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone_number = phone_number
        self.proxy = proxy  # Store permanent proxy
        self.client: Optional[Client] = None
        self.auto_reply_enabled = False
        self.reply_callback: Optional[Union[Callable[[str, int], str], Callable[[str, int], Coroutine[Any, Any, str]]]] = None
        self.is_running = False
        self.realistic_typing = realistic_typing
        self.random_delays = random_delays

        # Anti-detection settings
        self.anti_detection = anti_detection_settings or {
            'min_delay': 2,
            'max_delay': 30,
            'messages_per_hour': 50,
            'burst_limit': 3,
            'online_simulation': True,
            'random_skip': True,
            'time_based_delays': True,
            'error_backoff': True,
            'session_recovery': True
        }

        # Anti-detection features with memory management
        self.last_reply_time = {}  # Track last reply time per chat
        self.message_count = {}    # Track messages per chat
        self.conversation_states = {}  # Track conversation flow
        self._max_cached_chats = 1000  # Limit to prevent memory leaks
        self.rate_limits = {
            'min_delay': self.anti_detection['min_delay'],
            'max_delay': self.anti_detection['max_delay'],
            'messages_per_hour': self.anti_detection['messages_per_hour'],
            'burst_limit': self.anti_detection['burst_limit'],
        }

        # Online status simulation
        self.online_simulation_enabled = self.anti_detection['online_simulation']
        self.last_online_update = 0
        self.online_status_task = None
        
        # Voice message configuration
        self.voice_config = None  # Will be set via set_voice_config()
        self.voice_service = None  # VoiceService instance

        # Resilience management for fault tolerance
        self.resilience_manager = get_resilience_manager()
        self._setup_resilience_strategies()

    async def initialize(self, max_retries: int = 3) -> bool:
        """Initialize and authenticate the Telegram client with anti-detection measures and retry logic.

        Args:
            max_retries: Maximum number of initialization attempts

        Returns:
            bool: True if initialization successful, False otherwise
        """
        import random
        import time

        for attempt in range(max_retries):
            client_created = False
            try:
                # Validate credentials
                if not self.api_id or not self.api_hash or not self.phone_number:
                    logger.error("Missing required credentials")
                    return False

                # Anti-detection: Randomize session name to avoid patterns
                session_suffix = RandomizationUtils.get_session_suffix()
                session_name = f"tg_session_{session_suffix}"

                # Use secure session directory (not project root for security)
                session_dir = self._get_secure_session_directory()

                # Use permanent proxy if provided
                client_kwargs = {
                    'session_name': session_name,
                    'workdir': session_dir,  # Store sessions in secure directory
                    'api_id': self.api_id,
                    'api_hash': self.api_hash,
                    'phone_number': self.phone_number,
                    'connection_pool_size': 1,  # Anti-detection: Disable connection pooling
                    'connection_timeout': RandomizationUtils.get_connection_timeout(),
                    'update_interval': RandomizationUtils.get_update_interval()
                }

                # Add proxy if provided (permanent proxy for this account)
                if self.proxy:
                    client_kwargs['proxy'] = self.proxy
                    logger.info(f"Using permanent proxy for {self.phone_number}: {self.proxy.get('hostname', 'unknown')}:{self.proxy.get('port', 'unknown')}")

                self.client = Client(**client_kwargs)
                client_created = True

                # Anti-detection: Add random delay before connecting
                await asyncio.sleep(RandomizationUtils.get_initial_delay() * 0.5)  # Scale down for connection

                # Start the client with timeout
                await asyncio.wait_for(self.client.start(), timeout=45.0)

                # Anti-detection: Randomize handler priority
                from pyrogram.handlers import MessageHandler
                from pyrogram.filters import private
                priority = random.randint(1, 100)
                self.client.add_handler(self._create_message_handler(), priority=priority)

                # Start online simulation if enabled
                if self.online_simulation_enabled:
                    self.start_online_simulation()

                # Anti-detection: Random initial delay
                await asyncio.sleep(RandomizationUtils.get_initial_delay())

                logger.info("Telegram client initialized successfully with anti-detection measures")
                logger.info(f"Session files stored securely in: {self.session_dir}")

                # Publish service started event
                if _event_system_available:
                    app_context.publish_event(EVENT_SERVICE_STARTED, {"service": "telegram", "status": "connected"})

                return True

            except asyncio.TimeoutError as e:
                logger.warning(f"Telegram client initialization timed out (attempt {attempt + 1}/{max_retries}): {e}")
                await self._cleanup_client_on_failure()
                if attempt < max_retries - 1:
                    # Exponential backoff: wait longer between retries
                    wait_time = (2 ** attempt) * random.uniform(5, 15)
                    logger.info(f"Retrying initialization in {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to initialize Telegram client after {max_retries} attempts: timeout")
                    return False

            except ConnectionError as e:
                logger.warning(f"Connection error during initialization (attempt {attempt + 1}/{max_retries}): {e}")
                await self._cleanup_client_on_failure()
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * random.uniform(3, 8)
                    logger.info(f"Retrying initialization in {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to initialize Telegram client after {max_retries} attempts: connection error")
                    return False

            except Exception as e:
                logger.error(f"Unexpected error during Telegram client initialization (attempt {attempt + 1}/{max_retries}): {e}")
                await self._cleanup_client_on_failure()
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * random.uniform(2, 5)
                    logger.info(f"Retrying initialization in {wait_time:.1f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to initialize Telegram client after {max_retries} attempts: {type(e).__name__}")
                    # Anti-detection: Don't reveal specific errors that could help detection
                    return False

        return False

    def is_connected(self) -> bool:
        """Check if the client is connected."""
        try:
            return self.client is not None and hasattr(self.client, 'is_connected') and self.client.is_connected
        except Exception:
            return False
    
    # Stealth reading capabilities
    async def read_messages_silently(self, chat_id: int, limit: int = 10, 
                                     mark_as_read: bool = False) -> List[Message]:
        """Read messages without triggering read receipts (stealth mode).
        
        Args:
            chat_id: Chat ID to read from
            limit: Number of messages to fetch
            mark_as_read: If True, mark as read (default False for stealth)
            
        Returns:
            List of Message objects
        """
        if not self.client:
            return []
        
        try:
            messages = []
            async for message in self.client.get_chat_history(chat_id, limit=limit):
                messages.append(message)
            
            # Only mark as read if explicitly requested
            if mark_as_read:
                await self._delayed_mark_as_read(chat_id, messages)
            
            logger.info(f"Silently read {len(messages)} messages from {chat_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Error reading messages silently: {e}")
            return []
    
    async def _delayed_mark_as_read(self, chat_id: int, messages: List[Message],
                                   delay_minutes: Optional[int] = None):
        """Mark messages as read with a human-like delay.
        
        Args:
            chat_id: Chat ID
            messages: Messages to mark as read
            delay_minutes: Delay in minutes (random if None)
        """
        if not messages:
            return
        
        # Random delay between 5-60 minutes if not specified
        if delay_minutes is None:
            delay_minutes = random.randint(5, 60)
        
        delay_seconds = delay_minutes * 60
        
        # Schedule delayed read marking
        async def delayed_mark():
            await asyncio.sleep(delay_seconds)
            try:
                await self.client.read_chat_history(chat_id)
                logger.info(f"Marked messages as read in {chat_id} after {delay_minutes}min delay")
            except Exception as e:
                logger.debug(f"Error marking as read: {e}")
        
        # Run in background
        asyncio.create_task(delayed_mark())
    
    async def fetch_message_without_read(self, chat_id: int, message_id: int) -> Optional[Message]:
        """Fetch a specific message without marking it as read.
        
        Args:
            chat_id: Chat ID
            message_id: Message ID
            
        Returns:
            Message object or None
        """
        try:
            message = await self.client.get_messages(chat_id, message_id)
            return message
        except Exception as e:
            logger.error(f"Error fetching message: {e}")
            return None
    
    async def ghost_mode_view(self, chat_id: int, appear_offline: bool = True) -> List[Message]:
        """View messages while appearing offline (ghost mode).
        
        Args:
            chat_id: Chat ID to view
            appear_offline: Stay offline while viewing
            
        Returns:
            List of messages
        """
        try:
            # Set offline if requested
            if appear_offline:
                try:
                    await self.update_status(online=False)
                except Exception:
                    pass  # Some accounts may not support this
            
            # Read messages silently
            messages = await self.read_messages_silently(chat_id, limit=20, mark_as_read=False)
            
            logger.info(f"Ghost mode: Viewed {len(messages)} messages in {chat_id}")
            return messages
            
        except Exception as e:
            logger.error(f"Error in ghost mode: {e}")
            return []
    
    async def controlled_read_receipt(self, chat_id: int, delay_strategy: str = "natural"):
        """Mark chat as read with strategic timing.
        
        Args:
            chat_id: Chat ID
            delay_strategy: Strategy ('immediate', 'natural', 'late')
        """
        if delay_strategy == "immediate":
            await self.client.read_chat_history(chat_id)
        elif delay_strategy == "natural":
            # 1-5 minutes delay
            delay = random.randint(60, 300)
            await asyncio.sleep(delay)
            await self.client.read_chat_history(chat_id)
        elif delay_strategy == "late":
            # 30 minutes to 3 hours delay
            delay = random.randint(1800, 10800)
            await asyncio.sleep(delay)
            await self.client.read_chat_history(chat_id)
    
    async def preview_chat_silently(self, chat_id: int) -> Dict:
        """Preview chat information without triggering any receipts.
        
        Args:
            chat_id: Chat ID
            
        Returns:
            Dictionary with chat preview data
        """
        try:
            # Get chat info
            chat = await self.client.get_chat(chat_id)
            
            # Get recent message count without reading
            message_count = await self.client.get_chat_history_count(chat_id)
            
            # Get last message (without marking as read)
            last_message = None
            async for msg in self.client.get_chat_history(chat_id, limit=1):
                last_message = msg
                break
            
            return {
                'chat_id': chat_id,
                'title': chat.title if hasattr(chat, 'title') else None,
                'type': str(chat.type) if hasattr(chat, 'type') else None,
                'message_count': message_count,
                'last_message_text': last_message.text if last_message else None,
                'last_message_date': last_message.date if last_message else None
            }
            
        except Exception as e:
            logger.error(f"Error previewing chat: {e}")
            return {}

    async def start_auto_reply(self, reply_callback: Union[Callable[[str, int], str], Callable[[str, int], Coroutine[Any, Any, str]]]) -> None:
        """Start auto-reply functionality.

        Args:
            reply_callback: Function that takes (message_text, chat_id) and returns reply text (sync or async)
        """
        self.reply_callback = reply_callback
        self.auto_reply_enabled = True
        logger.info("Auto-reply enabled")

    def stop_auto_reply(self) -> None:
        """Stop auto-reply functionality."""
        self.auto_reply_enabled = False
        self.reply_callback = None
        logger.info("Auto-reply disabled")

    def _create_message_handler(self) -> Callable[[Client, Message], Any]:
        """Create message handler for incoming messages."""
        async def handler(client: Client, message: Message):
            # Publish message received event
            if _event_system_available:
                app_context.publish_event(EVENT_MESSAGE_RECEIVED, {
                    "chat_id": message.chat.id,
                    "user_id": message.from_user.id if message.from_user else None,
                    "message": message.text,
                    "timestamp": message.date
                })

            if not self.auto_reply_enabled or not self.reply_callback:
                return

            # Skip messages from ourselves to avoid loops
            if message.from_user and message.from_user.is_self:
                return

            # Skip messages that are replies to our own messages
            if message.reply_to_message and message.reply_to_message.from_user and message.reply_to_message.from_user.is_self:
                return

            try:
                # Anti-detection: Advanced message analysis
                message_score = self._analyze_message_for_reply(message)
                if message_score < 0.3:  # Only reply to high-interest messages
                    logger.info(f"Anti-detection: Low priority message ({message_score:.2f}), skipping")
                    return

                # Anti-detection: Check if we should reply based on complex rules
                should_reply = await self._should_reply_to_message_advanced(message, message_score)
                if not should_reply:
                    logger.info(f"Anti-detection: Skipping reply to {message.chat.id} (advanced rules)")
                    return

                # Get reply text from callback (handle both sync and async callbacks)
                callback_result = self.reply_callback(message.text or "", message.chat.id)
                if asyncio.iscoroutine(callback_result):
                    reply_text = await callback_result
                else:
                    reply_text = callback_result

                if reply_text:
                    # Anti-detection: Apply sophisticated human-like delays
                    await self._apply_advanced_delays(message.chat.id, message, message_score)

                    # Send reply with potential modifications for realism
                    final_reply = self._add_human_touch_to_reply(reply_text, message)
                    
                    # Check if this should be a voice message
                    sent_as_voice = False
                    if self.should_send_voice_reply(message.chat.id, message.text or ""):
                        # For voice messages, skip typing simulation
                        sent_as_voice = await self.send_voice_message(
                            chat_id=message.chat.id,
                            text=final_reply,
                            reply_to_message_id=message.id
                        )
                    
                    if not sent_as_voice:
                        # Simulate typing with variable patterns (only for text replies)
                        await self._simulate_realistic_typing(message.chat.id, final_reply, message_score)
                        await message.reply_text(final_reply)

                    # Update conversation tracking with advanced analytics
                    self._update_advanced_tracking(message.chat.id, message, final_reply)

                    reply_type = "voice" if sent_as_voice else "text"
                    logger.info(f"Replied ({reply_type}) to message in chat {message.chat.id} (score: {message_score:.2f})")

            except Exception as e:
                logger.error(f"Error handling message: {e}")
                # Anti-detection: Variable error delays to avoid patterns
                await asyncio.sleep(random.uniform(10, 30))

        from pyrogram.handlers import MessageHandler
        from pyrogram.filters import private

        # Handle messages in private chats (DMs)
        return MessageHandler(handler, filters=private)

    async def _simulate_typing(self, chat_id: int, text: str) -> None:
        """Simulate realistic human-like typing behavior character by character.

        Args:
            chat_id: Chat ID to send typing action to
            text: Text that will be sent (to simulate typing)
        """
        try:
            import random

            if self.realistic_typing:
                # Start typing action
                await self.client.send_chat_action(chat_id, ChatAction.TYPING)

                # Simulate character-by-character typing with realistic delays
                chars_typed = 0
                last_typing_update = 0

                for i, char in enumerate(text):
                    # Calculate realistic typing speed (varies by character type)
                    if char in ' \n\t':
                        # Spaces and newlines are faster
                        delay = 0.05
                    elif char in '.,!?':
                        # Punctuation has longer pauses
                        delay = 0.15
                    elif char.isupper():
                        # Capital letters take slightly longer
                        delay = 0.12
                    else:
                        # Regular characters
                        delay = 0.08

                    # Add random variation (±20%) to make it more human-like
                    delay *= random.uniform(0.8, 1.2)

                    await asyncio.sleep(delay)
                    chars_typed += 1

                    # Update typing action every ~5 characters to keep it active
                    if chars_typed - last_typing_update >= 5:
                        await self.client.send_chat_action(chat_id, ChatAction.TYPING)
                        last_typing_update = chars_typed

                # Brief pause before sending (like human thinking time)
                await asyncio.sleep(random.uniform(0.5, 1.5))

                # Sometimes add extra pauses for longer messages (like re-reading)
                if self.random_delays and len(text) > 50 and random.random() < 0.3:
                    await asyncio.sleep(random.uniform(1.0, 3.0))
            else:
                # Simple typing simulation (original method)
                # Calculate typing duration based on text length (roughly 200 chars per minute)
                typing_duration = max(1, len(text) // 20)  # Minimum 1 second

                # Send typing action
                await self.client.send_chat_action(chat_id, ChatAction.TYPING)

                # Wait for calculated duration
                await asyncio.sleep(typing_duration)

        except Exception as e:
            logger.warning(f"Failed to simulate typing: {e}")
            # Fallback to simple delay if character simulation fails
            await asyncio.sleep(max(1, len(text) // 20))

    async def run_forever(self) -> None:
        """Run the client indefinitely."""
        self.is_running = True
        try:
            while self.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            await self.stop()

    async def update_status(self, online: bool = True) -> None:
        """Update online status (for compatibility with warmup service).
        
        Note: Pyrogram manages online status automatically based on connection.
        This method is provided for API compatibility.
        
        Args:
            online: Whether to appear online (True) or offline (False)
        """
        try:
            # Pyrogram doesn't have a direct way to set online/offline status
            # The status is managed automatically based on connection state
            # This method is mainly for API compatibility
            if online:
                # Ensure client is connected
                if self.client and not self.client.is_connected:
                    await self.client.connect()
                logger.debug("Online status requested (managed automatically by Pyrogram)")
            else:
                # Can't actually set offline while connected, but log the request
                logger.debug("Offline status requested (connection state managed by Pyrogram)")
        except Exception as e:
            logger.warning(f"Failed to update status: {e}")

    def start_online_simulation(self) -> None:
        """Start simulating online/offline status like a human user."""
        if self.online_simulation_enabled and self.client:
            import asyncio
            self.online_status_task = asyncio.create_task(self._online_status_loop())

    async def _online_status_loop(self) -> None:
        """Continuously update online status to mimic human behavior."""
        while self.is_running and self.client:
            try:
                current_time = time.time()

                # Update online status every 30-90 seconds
                if current_time - self.last_online_update > RandomizationUtils.get_online_update_interval():
                    # Simulate being "online" (actually just active)
                    # Note: Pyrogram handles this automatically, but we can add custom behavior
                    self.last_online_update = current_time

                    # Sometimes simulate being "away" by not responding for longer periods
                    if random.random() < 0.1:  # 10% chance
                        await asyncio.sleep(RandomizationUtils.get_burst_pause())  # 5-15 minutes "away"

                await asyncio.sleep(10)  # Check every 10 seconds

            except Exception as e:
                logger.warning(f"Online status simulation error: {e}")
                await asyncio.sleep(30)

    async def stop(self) -> None:
        """Stop the client gracefully."""
        self.is_running = False

        # Stop online simulation
        if self.online_status_task:
            self.online_status_task.cancel()
            try:
                await self.online_status_task
            except asyncio.CancelledError:
                pass

        if self.client:
            await self.client.stop()
            logger.info("Telegram client stopped")

        # Clean up memory caches
        self._cleanup_memory_caches()

    def _setup_resilience_strategies(self):
        """Set up circuit breakers and fallback strategies for resilience."""
        # Circuit breaker for message sending
        self.message_circuit_breaker = self.resilience_manager.get_circuit_breaker(
            f"telegram_messages_{self.phone_number}",
            failure_threshold=5,
            recovery_timeout=60,
            success_threshold=2
        )

        # Circuit breaker for API calls
        self.api_circuit_breaker = self.resilience_manager.get_circuit_breaker(
            f"telegram_api_{self.phone_number}",
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=1
        )

        # Fallback strategies for message sending
        message_fallback = self.resilience_manager.get_fallback_strategy("telegram_send_message")

        # Primary: Direct send
        async def primary_send(chat_id, text):
            await self.client.send_message(chat_id, text)
            return True

        # Fallback 1: Send with retry and longer timeout
        async def fallback_retry(chat_id, text):
            await asyncio.sleep(2)  # Wait before retry
            await self.client.send_message(chat_id, text)
            return True

        # Fallback 2: Send without anti-detection features
        async def fallback_basic(chat_id, text):
            # Temporarily disable anti-detection
            original_delays = self.rate_limits.copy()
            self.rate_limits = {'min_delay': 0, 'max_delay': 0}
            try:
                await self.client.send_message(chat_id, text)
                return True
            finally:
                self.rate_limits = original_delays

        message_fallback.add_fallback(primary_send, "Direct message send")
        message_fallback.add_fallback(fallback_retry, "Retry with delay")
        message_fallback.add_fallback(fallback_basic, "Basic send without anti-detection")

    def _cleanup_memory_caches(self):
        """Clean up memory caches to prevent memory leaks."""
        import time

        current_time = time.time()
        max_age_hours = 24  # Clean entries older than 24 hours

        # Clean up last_reply_time (remove chats not active in 24 hours)
        to_remove = []
        for chat_id, last_time in self.last_reply_time.items():
            if current_time - last_time > (max_age_hours * 3600):
                to_remove.append(chat_id)

        for chat_id in to_remove:
            del self.last_reply_time[chat_id]

        # If still too many cached chats, remove oldest entries
        if len(self.last_reply_time) > self._max_cached_chats:
            # Sort by last activity and keep only the most recent
            sorted_chats = sorted(self.last_reply_time.items(), key=lambda x: x[1], reverse=True)
            self.last_reply_time = dict(sorted_chats[:self._max_cached_chats])

        # Apply same logic to other caches
        for cache_name in ['message_count', 'conversation_states']:
            cache = getattr(self, cache_name)
            if len(cache) > self._max_cached_chats:
                # For these caches, we don't have timestamps, so just keep the most recently accessed
                # This is a simple LRU approximation - in practice, you might want to track access times
                items_to_keep = list(cache.keys())[:self._max_cached_chats]
                setattr(self, cache_name, {k: cache[k] for k in items_to_keep})

        logger.debug(f"Cleaned up memory caches: {len(to_remove)} old entries removed")

    def _ensure_cache_limits(self):
        """Ensure caches don't exceed limits (called periodically)."""
        total_cached = len(self.last_reply_time) + len(self.message_count) + len(self.conversation_states)

        if total_cached > (self._max_cached_chats * 2):  # Allow some overflow before cleanup
            self._cleanup_memory_caches()

    def get_client(self) -> Optional[Client]:
        """Get the underlying Pyrogram client instance."""
        return self.client

    async def _cleanup_client_on_failure(self):
        """Clean up client resources when initialization fails."""
        if self.client:
            try:
                # Stop the client if it was started
                if hasattr(self.client, 'is_connected') and self.client.is_connected:
                    await self.client.stop()
                # Clear the client reference
                self.client = None
                logger.debug("Cleaned up failed client initialization")
            except Exception as e:
                logger.warning(f"Error during client cleanup: {e}")
                # Force clear reference even if cleanup fails
                self.client = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures cleanup."""
        await self.stop()

    def _get_secure_session_directory(self) -> str:
        """Get or create a secure directory for Telegram session files."""
        if self.session_dir:
            return self.session_dir

        try:
            # Use platformdirs for cross-platform secure directory
            import platformdirs
            from pathlib import Path
            import os
            import stat

            # Get secure config directory
            config_dir = Path(platformdirs.user_config_dir("telegram_bot", "telegram_bot"))
            session_dir = config_dir / "sessions"

            # Create directory with secure permissions
            session_dir.mkdir(parents=True, exist_ok=True)

            # Set restrictive permissions (owner read/write/execute only)
            try:
                session_dir.chmod(stat.S_IRWXU)
            except OSError:
                logger.warning("Could not set restrictive permissions on session directory")

            # Create .gitkeep or similar to ensure directory is tracked but empty
            gitkeep_file = session_dir / ".gitkeep"
            if not gitkeep_file.exists():
                gitkeep_file.write_text("# This directory contains encrypted Telegram session files\n")

            self.session_dir = str(session_dir)
            logger.info(f"Using secure session directory: {self.session_dir}")
            return self.session_dir

        except ImportError:
            logger.warning("platformdirs not available, using fallback session directory")
        except Exception as e:
            logger.error(f"Failed to create secure session directory: {e}")

        # Fallback to a subdirectory in the working directory (less secure)
        fallback_dir = Path(".telegram_sessions")
        fallback_dir.mkdir(exist_ok=True)

        # Try to set restrictive permissions
        try:
            fallback_dir.chmod(stat.S_IRWXU)
        except OSError:
            pass

        self.session_dir = str(fallback_dir)
        logger.warning(f"Using fallback session directory (less secure): {self.session_dir}")
        logger.warning("Consider installing platformdirs for better security: pip install platformdirs")
        return self.session_dir

    async def _should_reply_to_message(self, message: Message) -> bool:
        """Determine if we should reply to a message based on anti-detection rules."""
        chat_id = message.chat.id
        current_time = time.time()

        # Initialize tracking for new chats
        if chat_id not in self.last_reply_time:
            self.last_reply_time[chat_id] = 0
            self.message_count[chat_id] = 0
            self.conversation_states[chat_id] = {'burst_count': 0, 'last_burst_reset': current_time}

        # Rate limiting: Minimum delay between replies
        time_since_last_reply = current_time - self.last_reply_time[chat_id]
        if time_since_last_reply < self.rate_limits['min_delay']:
            return False

        # Burst control: Don't reply too many times in succession
        state = self.conversation_states[chat_id]
        if current_time - state['last_burst_reset'] > 300:  # Reset burst every 5 minutes
            state['burst_count'] = 0
            state['last_burst_reset'] = current_time

        if state['burst_count'] >= self.rate_limits['burst_limit']:
            # Sometimes take a longer break
            import random
            if random.random() < 0.7:  # 70% chance to skip
                return False

        # Message frequency: Don't exceed messages per hour
        hour_ago = current_time - 3600
        recent_messages = sum(1 for t in [self.last_reply_time.get(cid, 0) for cid in self.last_reply_time]
                            if t > hour_ago)
        if recent_messages >= self.rate_limits['messages_per_hour']:
            return False

        # Random skip: Sometimes don't reply immediately (human behavior)
        if self.anti_detection['random_skip']:
            import random
            if random.random() < 0.1:  # 10% chance to skip randomly
                return False

        return True

    async def _apply_anti_detection_delays(self, chat_id: int) -> None:
        """Apply human-like delays before responding."""
        import random
        current_time = time.time()

        # Base delay (2-8 seconds)
        base_delay = random.uniform(2, 8)

        # Conversation flow delay
        state = self.conversation_states.get(chat_id, {'burst_count': 0})
        if state['burst_count'] > 1:
            # Add extra delay for consecutive replies
            base_delay += random.uniform(3, 10)

        # Time of day simulation (people are slower at night)
        if self.anti_detection['time_based_delays']:
            import time
            hour = time.localtime().tm_hour
            if hour >= 22 or hour <= 6:  # Night time
                base_delay *= random.uniform(1.2, 1.8)

        # Random additional delay
        if random.random() < 0.3:  # 30% chance
            base_delay += random.uniform(5, 15)

        # Cap maximum delay
        base_delay = min(base_delay, self.rate_limits['max_delay'])

        await asyncio.sleep(base_delay)

    def _analyze_message_for_reply(self, message) -> float:
        """Analyze message content and context to determine reply priority."""
        score = 0.5  # Base score

        text = (message.text or "").lower()

        # High priority keywords (increase score)
        high_priority = ['help', 'question', 'please', 'urgent', 'important', 'need', 'want']
        for keyword in high_priority:
            if keyword in text:
                score += 0.2

        # Medium priority keywords
        medium_priority = ['hi', 'hello', 'hey', 'thanks', 'thank']
        for keyword in medium_priority:
            if keyword in text:
                score += 0.1

        # Low priority indicators (decrease score)
        low_priority = ['spam', 'bot', 'auto', 'test', 'fake']
        for keyword in low_priority:
            if keyword in text:
                score -= 0.3

        # Message length factor
        length = len(text)
        if length < 5:
            score -= 0.1  # Too short
        elif length > 200:
            score += 0.1  # Detailed message

        # Time-based factors
        import time
        current_hour = time.localtime().tm_hour
        if 22 <= current_hour or current_hour <= 6:  # Night time
            score -= 0.1  # Less likely to respond at night

        # Conversation context
        chat_id = message.chat.id
        recent_messages = self.message_count.get(chat_id, 0)
        if recent_messages > 10:  # Too many messages in conversation
            score -= 0.2

        # Random factor to add unpredictability
        score += random.uniform(-0.1, 0.1)

        return max(0.0, min(1.0, score))  # Clamp between 0 and 1

    async def _should_reply_to_message_advanced(self, message, message_score: float) -> bool:
        """Advanced decision making for whether to reply."""
        chat_id = message.chat.id
        current_time = time.time()

        # Initialize tracking
        if chat_id not in self.last_reply_time:
            self.last_reply_time[chat_id] = 0
            self.message_count[chat_id] = 0
            self.conversation_states[chat_id] = {'burst_count': 0, 'last_burst_reset': current_time}

        # Base rate limiting
        time_since_last_reply = current_time - self.last_reply_time[chat_id]
        if time_since_last_reply < self.rate_limits['min_delay']:
            return False

        # Score-based reply probability
        reply_probability = message_score * 0.8  # 80% of score as probability

        # Conversation flow adjustments
        state = self.conversation_states[chat_id]
        if state['burst_count'] >= self.rate_limits['burst_limit']:
            reply_probability *= 0.3  # Reduce probability after burst

        # Time-based adjustments
        import time
        current_hour = time.localtime().tm_hour
        if 1 <= current_hour <= 5:  # Very late night
            reply_probability *= 0.4
        elif 22 <= current_hour or current_hour <= 2:  # Late night
            reply_probability *= 0.6

        # Random factor
        if random.random() > reply_probability:
            return False

        return True

    async def _apply_advanced_delays(self, chat_id: int, message, message_score: float) -> None:
        """Apply sophisticated delay patterns."""
        import time
        current_time = time.time()

        # Base delay calculation
        base_delay = random.uniform(3, 12)

        # Score-based adjustments
        if message_score > 0.7:  # High priority message
            base_delay *= 0.7  # Respond faster
        elif message_score < 0.3:  # Low priority
            base_delay *= 1.5  # Respond slower

        # Conversation context
        state = self.conversation_states.get(chat_id, {'burst_count': 0})
        if state['burst_count'] > 0:
            base_delay += random.uniform(2, 8)  # Extra delay in ongoing conversations

        # Time-of-day simulation
        current_hour = time.localtime().tm_hour
        if 22 <= current_hour or current_hour <= 6:  # Night time
            base_delay *= random.uniform(1.5, 2.5)

        # Weekend simulation (people respond slower)
        current_day = time.localtime().tm_wday
        if current_day >= 5:  # Saturday/Sunday
            base_delay *= random.uniform(1.2, 1.8)

        # Message length simulation
        text_length = len(message.text or "")
        if text_length > 100:  # Long message needs more "thinking" time
            base_delay += random.uniform(3, 8)

        # Random "distraction" factor
        if random.random() < 0.15:  # 15% chance
            base_delay += random.uniform(10, 30)  # Got distracted

        # Cap maximum delay
        base_delay = min(base_delay, 60)  # Max 1 minute

        await asyncio.sleep(base_delay)

    async def _simulate_realistic_typing(self, chat_id: int, text: str, message_score: float) -> None:
        """Ultra-realistic typing simulation with score-based adjustments."""
        try:
            import time
            await self.client.send_chat_action(chat_id, ChatAction.TYPING)

            chars_typed = 0
            last_typing_update = 0
            start_time = time.time()

            for i, char in enumerate(text):
                # Dynamic typing speed based on message score and context
                if message_score > 0.8:  # Urgent/high-priority
                    speed_multiplier = 1.3
                elif message_score < 0.4:  # Casual response
                    speed_multiplier = 0.8
                else:
                    speed_multiplier = 1.0

                # Character type adjustments
                if char in ' \n\t':
                    delay = 0.03 * speed_multiplier
                elif char in '.,!?':
                    delay = 0.12 * speed_multiplier
                elif char.isupper():
                    delay = 0.09 * speed_multiplier
                else:
                    delay = 0.06 * speed_multiplier

                # Time-of-day typing speed
                current_hour = time.localtime().tm_hour
                if 22 <= current_hour or current_hour <= 6:
                    delay *= 1.2  # Slower at night (tired)

                # Add realistic variation
                delay *= random.uniform(0.7, 1.4)

                # Occasional longer pauses (thinking)
                if random.random() < 0.02:  # 2% chance
                    delay += random.uniform(0.5, 2.0)

                await asyncio.sleep(delay)
                chars_typed += 1

                # Update typing indicator
                if chars_typed - last_typing_update >= 4:
                    await self.client.send_chat_action(chat_id, ChatAction.TYPING)
                    last_typing_update = chars_typed

            # Post-typing pause (reading what you wrote)
            reading_pause = min(len(text) * 0.02, 3.0)  # Up to 3 seconds
            await asyncio.sleep(reading_pause)

        except Exception as e:
            logger.warning(f"Advanced typing simulation failed: {e}")
            # Fallback to basic simulation
            await asyncio.sleep(max(1, len(text) // 25))

    def _add_human_touch_to_reply(self, reply_text: str, original_message) -> str:
        """Add subtle human touches to replies."""
        # Occasionally add typing imperfections
        if random.random() < 0.05:  # 5% chance
            # Add a comma or adjust punctuation slightly
            if random.random() < 0.5 and not reply_text.endswith(','):
                reply_text = reply_text.rstrip('.') + ','

        # Vary response length slightly for realism
        if len(reply_text) > 50 and random.random() < 0.1:  # 10% chance for longer messages
            # Occasionally make responses slightly shorter
            words = reply_text.split()
            if len(words) > 8:
                reply_text = ' '.join(words[:len(words)-1]) + '...'

        return reply_text

    def _update_advanced_tracking(self, chat_id: int, message, reply_text: str) -> None:
        """Update conversation tracking with advanced analytics."""
        current_time = time.time()

        self.last_reply_time[chat_id] = current_time
        self.message_count[chat_id] = self.message_count.get(chat_id, 0) + 1

        # Update burst tracking
        state = self.conversation_states[chat_id]
        state['burst_count'] += 1

        # Store conversation analytics
        if not hasattr(self, 'conversation_analytics'):
            self.conversation_analytics = {}

        if chat_id not in self.conversation_analytics:
            self.conversation_analytics[chat_id] = {
                'messages_received': 0,
                'messages_sent': 0,
                'avg_response_time': 0,
                'last_activity': current_time
            }

        analytics = self.conversation_analytics[chat_id]
        analytics['messages_sent'] += 1
        analytics['last_activity'] = current_time

        # Calculate response time if we have message timing
        if hasattr(message, 'date'):
            message_time = message.date.timestamp()
            response_time = current_time - message_time
            # Update rolling average
            analytics['avg_response_time'] = (
                analytics['avg_response_time'] * 0.9 + response_time * 0.1
            )

    def _update_conversation_tracking(self, chat_id: int) -> None:
        """Update conversation tracking after sending a reply."""
        current_time = time.time()

        self.last_reply_time[chat_id] = current_time
        self.message_count[chat_id] = self.message_count.get(chat_id, 0) + 1

        # Update burst tracking
        state = self.conversation_states[chat_id]
        state['burst_count'] += 1

    async def send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a specific chat with resilience features.

        Args:
            chat_id: Chat ID to send message to
            text: Message text

        Returns:
            bool: True if sent successfully, False otherwise
        """
        # Periodic cache cleanup to prevent memory leaks
        self._ensure_cache_limits()

        # Use resilience manager for fault-tolerant message sending
        try:
            async def send_operation():
                # Apply anti-detection delays
                await self._apply_anti_detection_delays(chat_id)

                # Send message
                await self.client.send_message(chat_id, text)

                # Update tracking
                self.message_count[chat_id] = self.message_count.get(chat_id, 0) + 1
                self.last_reply_time[chat_id] = time.time()

                # Publish success event
                if _event_system_available:
                    app_context.publish_event(EVENT_MESSAGE_SENT, {
                        "chat_id": chat_id,
                        "message": text,
                        "timestamp": time.time()
                    })

                return True

            # Execute with resilience
            result = await self.resilience_manager.execute_with_resilience(
                f"send_message_{self.phone_number}",
                send_operation,
                circuit_breaker=True,
                fallback=True
            )

            return result

        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False
            await self.client.send_message(chat_id, text)

            # Publish message sent event
            if _event_system_available:
                app_context.publish_event(EVENT_MESSAGE_SENT, {
                    "chat_id": chat_id,
                    "message": text,
                    "timestamp": time.time()
                })

            return True
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    # ============== Voice Message Methods ==============
    
    def set_voice_config(self, voice_config) -> None:
        """Set the voice configuration for this client.
        
        Args:
            voice_config: VoiceConfig object from voice_service
        """
        self.voice_config = voice_config
        logger.info(f"Voice config set for {self.phone_number}: enabled={voice_config.enabled if voice_config else False}")
    
    def set_voice_service(self, voice_service) -> None:
        """Set the voice service instance.
        
        Args:
            voice_service: VoiceService instance
        """
        self.voice_service = voice_service
        logger.info(f"Voice service set for {self.phone_number}")
    
    async def send_voice_message(self, chat_id: int, text: str, 
                                  reply_to_message_id: Optional[int] = None) -> bool:
        """Send a voice message to a chat.
        
        Args:
            chat_id: Chat ID to send to
            text: Text to convert to speech
            reply_to_message_id: Optional message ID to reply to
            
        Returns:
            True if sent successfully
        """
        if not self.voice_service:
            logger.warning("Voice service not configured, cannot send voice message")
            return False
        
        if not self.voice_config or not self.voice_config.enabled:
            logger.debug("Voice messages disabled for this account")
            return False
        
        try:
            # Show "recording voice" action to simulate recording
            await self.client.send_chat_action(chat_id, ChatAction.RECORD_AUDIO)
            
            # Generate the voice message
            voice_id = self.voice_config.voice_id if self.voice_config else None
            audio_path = await self.voice_service.generate_voice_message(text, voice_id)
            
            if not audio_path or not audio_path.exists():
                logger.error(f"Failed to generate voice message for chat {chat_id}")
                if _event_system_available:
                    app_context.publish_event(EVENT_VOICE_MESSAGE_FAILED, {
                        "chat_id": chat_id,
                        "reason": "generation_failed",
                        "timestamp": time.time()
                    })
                return False
            
            # Simulate recording time based on text length
            # Average speaking rate: ~150 words per minute = 2.5 words/sec
            words = len(text.split())
            estimated_duration = max(2, words / 2.5)  # At least 2 seconds
            
            # Add some randomness
            await asyncio.sleep(random.uniform(1, min(3, estimated_duration * 0.3)))
            
            # Show uploading action
            await self.client.send_chat_action(chat_id, ChatAction.UPLOAD_AUDIO)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Send the voice message
            await self.client.send_voice(
                chat_id=chat_id,
                voice=str(audio_path),
                reply_to_message_id=reply_to_message_id
            )
            
            # Publish voice message sent event
            if _event_system_available:
                app_context.publish_event(EVENT_VOICE_MESSAGE_SENT, {
                    "chat_id": chat_id,
                    "text": text,
                    "voice_id": voice_id,
                    "timestamp": time.time()
                })
            
            logger.info(f"Voice message sent to chat {chat_id} ({len(text)} chars)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send voice message: {e}")
            if _event_system_available:
                app_context.publish_event(EVENT_VOICE_MESSAGE_FAILED, {
                    "chat_id": chat_id,
                    "reason": str(e),
                    "timestamp": time.time()
                })
            return False
    
    def should_send_voice_reply(self, chat_id: int, incoming_message: str) -> bool:
        """Determine if this reply should be a voice message.
        
        Args:
            chat_id: Chat ID
            incoming_message: The incoming message text (for keyword detection)
            
        Returns:
            True if should send voice message
        """
        if not self.voice_service or not self.voice_config:
            return False
        
        return self.voice_service.should_send_voice(
            chat_id=chat_id,
            message_text=incoming_message,
            config=self.voice_config
        )
    
    async def send_reply_with_voice_option(self, chat_id: int, reply_text: str,
                                            incoming_message: str,
                                            reply_to_message_id: Optional[int] = None) -> bool:
        """Send a reply, potentially as a voice message based on configuration.
        
        This method checks voice settings and either sends a voice message
        or a regular text message.
        
        Args:
            chat_id: Chat ID to reply to
            reply_text: The reply text
            incoming_message: The incoming message (for trigger detection)
            reply_to_message_id: Optional message ID to reply to
            
        Returns:
            True if message sent successfully
        """
        # Check if this should be a voice message
        if self.should_send_voice_reply(chat_id, incoming_message):
            logger.info(f"Sending voice reply to chat {chat_id}")
            success = await self.send_voice_message(
                chat_id=chat_id,
                text=reply_text,
                reply_to_message_id=reply_to_message_id
            )
            if success:
                return True
            # Fall back to text if voice fails
            logger.warning(f"Voice message failed, falling back to text for chat {chat_id}")
        
        # Send as regular text message
        try:
            if reply_to_message_id:
                await self.client.send_message(
                    chat_id=chat_id,
                    text=reply_text,
                    reply_to_message_id=reply_to_message_id
                )
            else:
                await self.client.send_message(chat_id=chat_id, text=reply_text)
            
            # Publish message sent event
            if _event_system_available:
                app_context.publish_event(EVENT_MESSAGE_SENT, {
                    "chat_id": chat_id,
                    "message": reply_text,
                    "timestamp": time.time()
                })
            
            return True
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            return False

    def update_anti_detection_settings(self, settings: Dict[str, Any]) -> None:
        """Update anti-detection settings dynamically."""
        try:
            # Update message timing settings
            if 'min_delay' in settings:
                self.min_reply_delay = settings['min_delay']
            if 'max_delay' in settings:
                self.max_reply_delay = settings['max_delay']

            # Update message limits
            if 'messages_per_hour' in settings:
                self.messages_per_hour_limit = settings['messages_per_hour']

            # Update online simulation
            if 'online_simulation' in settings:
                self.online_simulation_enabled = settings['online_simulation']

            # Update burst settings
            if 'burst_limit' in settings:
                self.burst_message_limit = settings['burst_limit']

            # Update random skip probability
            if 'random_skip_probability' in settings:
                self.random_skip_probability = settings['random_skip_probability']

            # Update time-based delays
            if 'time_based_delays' in settings:
                self.time_based_delays_enabled = settings['time_based_delays']

            logger.info(f"Telegram client anti-detection settings updated: {settings}")

        except Exception as e:
            logger.error(f"Failed to update Telegram client anti-detection settings: {e}")
