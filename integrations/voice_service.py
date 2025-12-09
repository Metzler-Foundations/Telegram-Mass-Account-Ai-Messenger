"""
Voice Service - ElevenLabs TTS integration for realistic voice messages.

Features:
- Generate realistic female voice messages using ElevenLabs API
- Cache audio files to reduce API costs
- Support multiple voice options
- Generate OGG files compatible with Telegram voice messages
- Smart triggering based on conversation context
- Analytics and usage tracking
- Rate limiting and error recovery
"""

import asyncio
import hashlib
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class VoiceGender(Enum):
    """Voice gender options."""

    FEMALE = "female"
    MALE = "male"


@dataclass
class VoiceProfile:
    """Voice profile information."""

    voice_id: str
    name: str
    gender: VoiceGender
    age_range: str  # e.g., "18-25", "25-35"
    description: str
    accent: str
    personality: str = ""  # e.g., "flirty", "professional", "playful"
    best_for: List[str] = field(default_factory=list)  # e.g., ["sales", "casual"]


# Pre-configured young female voices from ElevenLabs
# These are real ElevenLabs voice IDs for young-sounding female voices
AVAILABLE_VOICES: Dict[str, VoiceProfile] = {
    "rachel": VoiceProfile(
        voice_id="21m00Tcm4TlvDq8ikWAM",
        name="Rachel",
        gender=VoiceGender.FEMALE,
        age_range="18-25",
        description="Young, friendly American female voice - warm and conversational",
        accent="American",
        personality="warm",
        best_for=["sales", "casual", "friendly"],
    ),
    "elli": VoiceProfile(
        voice_id="MF3mGyEYCl7XYWbV9V6O",
        name="Elli",
        gender=VoiceGender.FEMALE,
        age_range="18-22",
        description="Young, energetic female voice - playful and engaging",
        accent="American",
        personality="playful",
        best_for=["flirty", "energetic", "outreach"],
    ),
    "bella": VoiceProfile(
        voice_id="EXAVITQu4vr4xnSDxMaL",
        name="Bella",
        gender=VoiceGender.FEMALE,
        age_range="20-28",
        description="Soft, gentle female voice - intimate and warm",
        accent="American",
        personality="intimate",
        best_for=["intimate", "sales", "personal"],
    ),
    "charlotte": VoiceProfile(
        voice_id="XB0fDUnXU5powFXDhCwa",
        name="Charlotte",
        gender=VoiceGender.FEMALE,
        age_range="18-25",
        description="Sweet, youthful female voice - natural and relatable",
        accent="American/Neutral",
        personality="sweet",
        best_for=["casual", "friendly", "relatable"],
    ),
    "sarah": VoiceProfile(
        voice_id="EXAVITQu4vr4xnSDxMaL",
        name="Sarah",
        gender=VoiceGender.FEMALE,
        age_range="20-25",
        description="Confident young female voice - clear and expressive",
        accent="American",
        personality="confident",
        best_for=["professional", "confident", "sales"],
    ),
}

# Default voice for the system
DEFAULT_VOICE = "rachel"

# Fallback voice order (if primary fails)
FALLBACK_VOICE_ORDER = ["rachel", "bella", "charlotte", "elli", "sarah"]

# Character limits for voice messages
MAX_VOICE_CHARS = 2500  # ElevenLabs limit per request
OPTIMAL_VOICE_CHARS = 500  # Ideal length for natural voice messages

# Rate limiting
MAX_VOICE_MESSAGES_PER_HOUR = 30
MAX_VOICE_MESSAGES_PER_CHAT_PER_HOUR = 5

# Test phrases for voice preview
TEST_PHRASES = {
    "greeting": "Hey! How's it going? I was just thinking about you.",
    "flirty": "Mmm, I like the way you think... Tell me more about yourself.",
    "sales": "I've got something special I think you'd really enjoy. Want me to tell you about it?",
    "casual": "Haha that's so funny! You always know how to make me smile.",
    "interested": "Oh really? That sounds super interesting... I'd love to hear more about that.",
}


class VoiceTriggerMode(Enum):
    """Voice message trigger modes."""

    RANDOM = "random"  # Random chance per message
    EVERY_NTH = "every_nth"  # Every Nth message in conversation
    KEYWORD = "keyword"  # When specific keywords detected
    SMART = "smart"  # AI-determined based on context
    ALWAYS = "always"  # Always send voice message
    NEVER = "never"  # Never send voice (disabled)


@dataclass
class VoiceConfig:
    """Voice configuration for an account."""

    enabled: bool = False
    voice_id: str = DEFAULT_VOICE
    trigger_mode: VoiceTriggerMode = VoiceTriggerMode.RANDOM
    random_chance: int = 30  # percentage (0-100)
    nth_message: int = 3  # for EVERY_NTH mode
    keywords: List[str] = None  # for KEYWORD mode
    # Advanced settings
    time_boost_enabled: bool = True  # Increase voice chance during prime hours
    prime_hours: Tuple[int, int] = (18, 23)  # 6 PM to 11 PM
    prime_hour_boost: int = 20  # Extra % chance during prime hours
    rapport_boost_enabled: bool = True  # More voice as conversation progresses
    min_messages_before_voice: int = 2  # Don't send voice in first N messages

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = [
                "hey",
                "hi",
                "hello",
                "interested",
                "price",
                "how much",
                "tell me more",
                "😊",
                "❤️",
            ]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "enabled": self.enabled,
            "voice_id": self.voice_id,
            "trigger_mode": (
                self.trigger_mode.value
                if isinstance(self.trigger_mode, VoiceTriggerMode)
                else self.trigger_mode
            ),
            "random_chance": self.random_chance,
            "nth_message": self.nth_message,
            "keywords": self.keywords,
            "time_boost_enabled": self.time_boost_enabled,
            "prime_hours": list(self.prime_hours),
            "prime_hour_boost": self.prime_hour_boost,
            "rapport_boost_enabled": self.rapport_boost_enabled,
            "min_messages_before_voice": self.min_messages_before_voice,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceConfig":
        """Create from dictionary."""
        if not data:
            return cls()

        trigger_mode = data.get("trigger_mode", "random")
        if isinstance(trigger_mode, str):
            try:
                trigger_mode = VoiceTriggerMode(trigger_mode)
            except ValueError:
                trigger_mode = VoiceTriggerMode.RANDOM

        prime_hours = data.get("prime_hours", [18, 23])
        if isinstance(prime_hours, list) and len(prime_hours) == 2:
            prime_hours = tuple(prime_hours)
        else:
            prime_hours = (18, 23)

        return cls(
            enabled=data.get("enabled", False),
            voice_id=data.get("voice_id", DEFAULT_VOICE),
            trigger_mode=trigger_mode,
            random_chance=data.get("random_chance", 30),
            nth_message=data.get("nth_message", 3),
            keywords=data.get(
                "keywords", ["hey", "hi", "hello", "interested", "price", "how much"]
            ),
            time_boost_enabled=data.get("time_boost_enabled", True),
            prime_hours=prime_hours,
            prime_hour_boost=data.get("prime_hour_boost", 20),
            rapport_boost_enabled=data.get("rapport_boost_enabled", True),
            min_messages_before_voice=data.get("min_messages_before_voice", 2),
        )


@dataclass
class VoiceAnalytics:
    """Analytics for voice message usage."""

    total_generated: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_cached_hits: int = 0
    characters_used: int = 0
    last_generated: Optional[datetime] = None
    by_voice: Dict[str, int] = field(default_factory=dict)
    by_hour: Dict[int, int] = field(default_factory=lambda: defaultdict(int))

    def record_generation(self, voice_id: str, char_count: int, from_cache: bool = False):
        """Record a voice message generation."""
        self.total_generated += 1
        self.characters_used += char_count
        self.last_generated = datetime.now()

        if voice_id not in self.by_voice:
            self.by_voice[voice_id] = 0
        self.by_voice[voice_id] += 1

        hour = datetime.now().hour
        self.by_hour[hour] += 1

        if from_cache:
            self.total_cached_hits += 1

    def record_sent(self):
        """Record a successful send."""
        self.total_sent += 1

    def record_failed(self):
        """Record a failed generation/send."""
        self.total_failed += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_generated": self.total_generated,
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "total_cached_hits": self.total_cached_hits,
            "characters_used": self.characters_used,
            "cache_hit_rate": round(self.total_cached_hits / max(1, self.total_generated) * 100, 1),
            "success_rate": round(self.total_sent / max(1, self.total_generated) * 100, 1),
            "last_generated": self.last_generated.isoformat() if self.last_generated else None,
            "by_voice": dict(self.by_voice),
            "peak_hour": max(self.by_hour.items(), key=lambda x: x[1])[0] if self.by_hour else None,
        }


class VoiceService:
    """Service for generating realistic voice messages using ElevenLabs."""

    def __init__(self, api_key: str = None, cache_dir: str = None):
        """Initialize the voice service.

        Args:
            api_key: ElevenLabs API key
            cache_dir: Directory to cache generated audio files
        """
        self.api_key = api_key
        self.cache_dir = Path(cache_dir) if cache_dir else Path("voice_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # ElevenLabs client (lazy initialized)
        self._client = None

        # Track message counts per chat for EVERY_NTH mode
        self.message_counts: Dict[int, int] = {}

        # Track conversation depth per chat (for rapport boost)
        self.conversation_depth: Dict[int, int] = {}

        # Rate limiting tracking
        self.voice_timestamps: List[datetime] = []
        self.voice_timestamps_by_chat: Dict[int, List[datetime]] = defaultdict(list)

        # Analytics
        self.analytics = VoiceAnalytics()

        # API settings
        self.model_id = "eleven_monolingual_v1"  # Best for English
        self.stability = 0.5  # Voice stability (0.0-1.0)
        self.similarity_boost = 0.75  # Voice clarity (0.0-1.0)
        self.style = 0.0  # Style exaggeration
        self.use_speaker_boost = True  # Enhance speaker similarity

        # Retry settings
        self.max_retries = 3
        self.retry_delay = 1.0

        logger.info(f"VoiceService initialized with cache dir: {self.cache_dir}")

    def _get_client(self):
        """Get or create ElevenLabs client."""
        if self._client is None:
            if not self.api_key:
                raise ValueError("ElevenLabs API key not configured")

            try:
                from elevenlabs import ElevenLabs

                self._client = ElevenLabs(api_key=self.api_key)
                logger.info("ElevenLabs client initialized successfully")
            except ImportError:
                logger.error("elevenlabs package not installed. Run: pip install elevenlabs")
                raise
            except Exception as e:
                logger.error(f"Failed to initialize ElevenLabs client: {e}")
                raise

        return self._client

    def set_api_key(self, api_key: str) -> None:
        """Update the API key."""
        self.api_key = api_key
        self._client = None  # Reset client to use new key
        logger.info("ElevenLabs API key updated")

    def get_available_voices(self) -> List[VoiceProfile]:
        """Get list of available voice profiles."""
        return list(AVAILABLE_VOICES.values())

    def get_voice_profile(self, voice_id: str) -> Optional[VoiceProfile]:
        """Get a specific voice profile by ID."""
        return AVAILABLE_VOICES.get(voice_id)

    def get_recommended_voice(self, context: str = "sales") -> str:
        """Get recommended voice for a given context.

        Args:
            context: Use case context (sales, flirty, casual, professional)

        Returns:
            Recommended voice ID
        """
        for voice_id, profile in AVAILABLE_VOICES.items():
            if context.lower() in profile.best_for:
                return voice_id
        return DEFAULT_VOICE

    def _get_cache_path(self, text: str, voice_id: str) -> Path:
        """Generate cache file path for given text and voice."""
        # Create hash of text + voice_id for unique filename
        content_hash = hashlib.md5(
            f"{text}:{voice_id}".encode(), usedforsecurity=False
        ).hexdigest()  # Used for cache keys, not security
        return self.cache_dir / f"voice_{content_hash}.mp3"

    def _check_cache(self, text: str, voice_id: str) -> Optional[Path]:
        """Check if audio for this text/voice combo is cached."""
        cache_path = self._get_cache_path(text, voice_id)
        if cache_path.exists():
            logger.debug(f"Cache hit for voice message: {cache_path}")
            return cache_path
        return None

    def _check_rate_limit(self, chat_id: int = None) -> Tuple[bool, str]:
        """Check if we're within rate limits.

        Returns:
            (allowed, reason) tuple
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)

        # Clean old timestamps
        self.voice_timestamps = [t for t in self.voice_timestamps if t > hour_ago]

        # Check global limit
        if len(self.voice_timestamps) >= MAX_VOICE_MESSAGES_PER_HOUR:
            return False, f"Global rate limit reached ({MAX_VOICE_MESSAGES_PER_HOUR}/hour)"

        # Check per-chat limit if chat_id provided
        if chat_id is not None:
            self.voice_timestamps_by_chat[chat_id] = [
                t for t in self.voice_timestamps_by_chat[chat_id] if t > hour_ago
            ]
            if len(self.voice_timestamps_by_chat[chat_id]) >= MAX_VOICE_MESSAGES_PER_CHAT_PER_HOUR:
                return (
                    False,
                    f"Chat rate limit reached ({MAX_VOICE_MESSAGES_PER_CHAT_PER_HOUR}/hour per chat)",
                )

        return True, "OK"

    def _record_voice_sent(self, chat_id: int):
        """Record that a voice message was sent (for rate limiting)."""
        now = datetime.now()
        self.voice_timestamps.append(now)
        self.voice_timestamps_by_chat[chat_id].append(now)

    def _truncate_text(self, text: str) -> str:
        """Truncate text to fit within character limits.

        Args:
            text: Text to potentially truncate

        Returns:
            Truncated text with natural ending
        """
        if len(text) <= MAX_VOICE_CHARS:
            return text

        # Try to find a natural breaking point
        truncated = text[:MAX_VOICE_CHARS]

        # Look for sentence endings
        for end_char in [". ", "! ", "? ", "... "]:
            last_end = truncated.rfind(end_char)
            if last_end > MAX_VOICE_CHARS * 0.7:  # At least 70% of content
                return truncated[: last_end + 1].strip()

        # Fall back to word boundary
        last_space = truncated.rfind(" ")
        if last_space > MAX_VOICE_CHARS * 0.7:
            return truncated[:last_space].strip() + "..."

        return truncated.strip() + "..."

    async def generate_voice_message(
        self, text: str, voice_id: str = None, use_cache: bool = True, chat_id: int = None
    ) -> Optional[Path]:
        """Generate a voice message from text.

        Args:
            text: Text to convert to speech
            voice_id: Voice profile ID (from AVAILABLE_VOICES keys)
            use_cache: Whether to use cached audio if available
            chat_id: Optional chat ID for rate limiting

        Returns:
            Path to the generated audio file, or None if failed
        """
        if not text or not text.strip():
            logger.warning("Cannot generate voice message for empty text")
            return None

        # Check rate limits
        if chat_id is not None:
            allowed, reason = self._check_rate_limit(chat_id)
            if not allowed:
                logger.warning(f"Voice rate limited: {reason}")
                return None

        voice_id = voice_id or DEFAULT_VOICE

        # Truncate if necessary
        original_length = len(text)
        text = self._truncate_text(text)
        if len(text) < original_length:
            logger.info(f"Text truncated from {original_length} to {len(text)} chars")

        # Get the actual ElevenLabs voice ID
        voice_profile = AVAILABLE_VOICES.get(voice_id)
        if not voice_profile:
            logger.warning(f"Unknown voice ID '{voice_id}', using default")
            voice_profile = AVAILABLE_VOICES[DEFAULT_VOICE]
            voice_id = DEFAULT_VOICE

        # Check cache first
        if use_cache:
            cached = self._check_cache(text, voice_id)
            if cached:
                self.analytics.record_generation(voice_id, len(text), from_cache=True)
                return cached

        # Generate new audio with retry logic
        last_error = None
        voices_to_try = [voice_id] + [v for v in FALLBACK_VOICE_ORDER if v != voice_id]

        for attempt, try_voice_id in enumerate(voices_to_try[: self.max_retries]):
            try:
                client = self._get_client()

                try_profile = AVAILABLE_VOICES.get(try_voice_id, voice_profile)
                try_elevenlabs_id = try_profile.voice_id

                logger.info(
                    f"Generating voice message with voice '{try_profile.name}' "
                    f"({len(text)} chars, attempt {attempt + 1})"
                )

                # Generate audio using ElevenLabs API
                audio = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda client=client, try_elevenlabs_id=try_elevenlabs_id: client.generate(
                        text=text,
                        voice=try_elevenlabs_id,
                        model=self.model_id,
                        voice_settings={
                            "stability": self.stability,
                            "similarity_boost": self.similarity_boost,
                            "style": self.style,
                            "use_speaker_boost": self.use_speaker_boost,
                        },
                    ),
                )

                # Save to cache
                cache_path = self._get_cache_path(text, try_voice_id)

                with open(cache_path, "wb") as f:
                    for chunk in audio:
                        f.write(chunk)

                # Record analytics
                self.analytics.record_generation(try_voice_id, len(text))
                if chat_id is not None:
                    self._record_voice_sent(chat_id)

                logger.info(f"Voice message generated and cached: {cache_path}")
                return cache_path

            except ImportError:
                logger.error("elevenlabs package not installed")
                self.analytics.record_failed()
                return None
            except Exception as e:
                last_error = e
                logger.warning(f"Voice generation attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

        logger.error(
            f"Failed to generate voice message after {self.max_retries} attempts: {last_error}"
        )
        self.analytics.record_failed()
        return None

    def _is_prime_time(self, config: VoiceConfig) -> bool:
        """Check if current time is within prime hours."""
        if not config.time_boost_enabled:
            return False

        current_hour = datetime.now().hour
        start, end = config.prime_hours

        if start <= end:
            return start <= current_hour <= end
        else:  # Handles overnight ranges like (22, 2)
            return current_hour >= start or current_hour <= end

    def _get_rapport_boost(self, chat_id: int, config: VoiceConfig) -> int:
        """Get additional chance % based on conversation depth."""
        if not config.rapport_boost_enabled:
            return 0

        depth = self.conversation_depth.get(chat_id, 0)

        # Boost increases with conversation depth, max +25%
        if depth < 3:
            return 0
        elif depth < 6:
            return 10
        elif depth < 10:
            return 15
        elif depth < 20:
            return 20
        else:
            return 25

    def should_send_voice(self, chat_id: int, message_text: str, config: VoiceConfig) -> bool:
        """Determine if a voice message should be sent based on configuration.

        Args:
            chat_id: The chat ID
            message_text: The incoming message text (for keyword detection)
            config: Voice configuration for the account

        Returns:
            True if a voice message should be sent
        """
        if not config.enabled:
            return False

        # Update conversation depth
        self.conversation_depth[chat_id] = self.conversation_depth.get(chat_id, 0) + 1
        depth = self.conversation_depth[chat_id]

        # Check minimum messages requirement
        if depth < config.min_messages_before_voice:
            logger.debug(
                f"Skipping voice - conversation too new ({depth}/{config.min_messages_before_voice})"
            )
            return False

        # Check rate limits
        allowed, _ = self._check_rate_limit(chat_id)
        if not allowed:
            return False

        mode = config.trigger_mode

        if mode == VoiceTriggerMode.NEVER:
            return False

        if mode == VoiceTriggerMode.ALWAYS:
            return True

        if mode == VoiceTriggerMode.RANDOM:
            # Calculate effective chance with boosts
            chance = config.random_chance

            # Add prime time boost
            if self._is_prime_time(config):
                chance += config.prime_hour_boost
                logger.debug(f"Prime time boost: +{config.prime_hour_boost}%")

            # Add rapport boost
            rapport_boost = self._get_rapport_boost(chat_id, config)
            if rapport_boost > 0:
                chance += rapport_boost
                logger.debug(f"Rapport boost: +{rapport_boost}%")

            # Cap at 90%
            chance = min(90, chance)

            result = random.randint(1, 100) <= chance
            logger.debug(f"Voice random check: {chance}% -> {'send' if result else 'skip'}")
            return result

        if mode == VoiceTriggerMode.EVERY_NTH:
            # Increment message count for this chat
            self.message_counts[chat_id] = self.message_counts.get(chat_id, 0) + 1
            count = self.message_counts[chat_id]

            # Check if this is the Nth message
            if count >= config.nth_message:
                self.message_counts[chat_id] = 0  # Reset counter
                return True
            return False

        if mode == VoiceTriggerMode.KEYWORD:
            if not config.keywords:
                return False

            message_lower = message_text.lower()
            for keyword in config.keywords:
                if keyword.lower() in message_lower:
                    logger.debug(f"Keyword '{keyword}' detected, triggering voice message")
                    return True
            return False

        if mode == VoiceTriggerMode.SMART:
            # AI-like decision making
            # More likely to send voice when:
            # - User shows interest (keywords)
            # - Conversation is progressing well (depth)
            # - It's prime time
            # - Random factor

            score = 0

            # Keyword detection (up to +40)
            interest_keywords = [
                "interested",
                "tell me",
                "want",
                "like",
                "love",
                "price",
                "how much",
                "😊",
                "❤️",
                "🔥",
            ]
            for kw in interest_keywords:
                if kw.lower() in message_text.lower():
                    score += 15

            # Conversation depth (up to +25)
            score += min(25, depth * 3)

            # Prime time (+15)
            if self._is_prime_time(config):
                score += 15

            # Random factor (0-20)
            score += random.randint(0, 20)

            # Threshold is 50
            result = score >= 50
            logger.debug(f"Smart voice decision: score={score} -> {'send' if result else 'skip'}")
            return result

        return False

    def reset_conversation(self, chat_id: int) -> None:
        """Reset conversation tracking for a chat."""
        if chat_id in self.message_counts:
            self.message_counts[chat_id] = 0
        if chat_id in self.conversation_depth:
            self.conversation_depth[chat_id] = 0
        logger.debug(f"Reset conversation tracking for chat {chat_id}")

    def clear_cache(self, older_than_days: int = None) -> int:
        """Clear cached voice files.

        Args:
            older_than_days: Only clear files older than this many days.
                           If None, clear all cached files.

        Returns:
            Number of files deleted
        """
        deleted = 0
        current_time = time.time()
        max_age = older_than_days * 86400 if older_than_days else None

        for cache_file in self.cache_dir.glob("voice_*.mp3"):
            try:
                if max_age:
                    file_age = current_time - cache_file.stat().st_mtime
                    if file_age < max_age:
                        continue

                cache_file.unlink()
                deleted += 1
            except Exception as e:
                logger.warning(f"Failed to delete cache file {cache_file}: {e}")

        logger.info(f"Cleared {deleted} cached voice files")
        return deleted

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get statistics about the voice cache."""
        total_size = 0
        file_count = 0
        oldest_file = None
        newest_file = None

        for cache_file in self.cache_dir.glob("voice_*.mp3"):
            try:
                stat = cache_file.stat()
                total_size += stat.st_size
                file_count += 1

                mtime = datetime.fromtimestamp(stat.st_mtime)
                if oldest_file is None or mtime < oldest_file:
                    oldest_file = mtime
                if newest_file is None or mtime > newest_file:
                    newest_file = mtime
            except Exception:
                pass

        return {
            "file_count": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "cache_dir": str(self.cache_dir),
            "oldest_file": oldest_file.isoformat() if oldest_file else None,
            "newest_file": newest_file.isoformat() if newest_file else None,
        }

    def get_analytics(self) -> Dict[str, Any]:
        """Get voice message analytics."""
        return self.analytics.to_dict()

    async def test_voice_generation(
        self, voice_id: str = None, phrase_type: str = "greeting"
    ) -> Tuple[bool, Optional[Path]]:
        """Test voice generation with a sample phrase.

        Args:
            voice_id: Voice to test with
            phrase_type: Type of test phrase (greeting, flirty, sales, casual, interested)

        Returns:
            (success, audio_path) tuple
        """
        try:
            test_text = TEST_PHRASES.get(phrase_type, TEST_PHRASES["greeting"])
            voice_id = voice_id or DEFAULT_VOICE

            # Don't use cache for tests
            result = await self.generate_voice_message(test_text, voice_id, use_cache=False)

            if result and result.exists():
                logger.info(f"Voice generation test successful: {result}")
                return True, result

            return False, None
        except Exception as e:
            logger.error(f"Voice generation test failed: {e}")
            return False, None

    async def preview_voice(self, voice_id: str, text: str = None) -> Optional[Path]:
        """Generate a preview of a voice.

        Args:
            voice_id: Voice to preview
            text: Optional custom text (defaults to greeting)

        Returns:
            Path to preview audio or None
        """
        text = text or TEST_PHRASES["greeting"]
        return await self.generate_voice_message(text, voice_id, use_cache=True)

    def get_test_phrases(self) -> Dict[str, str]:
        """Get available test phrases."""
        return TEST_PHRASES.copy()


# Singleton instance for app-wide use
_voice_service_instance: Optional[VoiceService] = None


def get_voice_service() -> VoiceService:
    """Get the global voice service instance."""
    global _voice_service_instance
    if _voice_service_instance is None:
        _voice_service_instance = VoiceService()
    return _voice_service_instance


def init_voice_service(api_key: str, cache_dir: str = None) -> VoiceService:
    """Initialize the global voice service with API key."""
    global _voice_service_instance
    _voice_service_instance = VoiceService(api_key=api_key, cache_dir=cache_dir)
    return _voice_service_instance


async def cleanup_voice_cache(days_old: int = 7) -> int:
    """Utility function to clean up old voice cache files.

    Args:
        days_old: Delete files older than this many days

    Returns:
        Number of files deleted
    """
    service = get_voice_service()
    return service.clear_cache(older_than_days=days_old)
