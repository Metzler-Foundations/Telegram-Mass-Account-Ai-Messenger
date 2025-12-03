"""
Shared utilities and constants to avoid circular imports.
"""
import re
import random
import string
from typing import Dict, Any, Tuple

# Event types for decoupled communication
EVENT_MESSAGE_RECEIVED = "message.received"
EVENT_MESSAGE_SENT = "message.sent"
EVENT_VOICE_MESSAGE_SENT = "voice.message.sent"
EVENT_VOICE_MESSAGE_FAILED = "voice.message.failed"
EVENT_AI_RESPONSE_GENERATED = "ai.response.generated"
EVENT_SERVICE_STARTED = "service.started"
EVENT_SERVICE_STOPPED = "service.stopped"
EVENT_STATUS_CHANGED = "status.changed"
EVENT_CONFIG_CHANGED = "config.changed"
EVENT_ACCOUNT_TYPE_CHANGED = "account.type.changed"
EVENT_VOICE_CONFIG_CHANGED = "voice.config.changed"
EVENT_ERROR_OCCURRED = "error.occurred"
EVENT_BACKUP_COMPLETED = "backup.completed"
EVENT_ANTI_DETECTION_TRIGGERED = "anti_detection.triggered"

# Global application context to avoid circular imports
class ApplicationContext:
    """Global application context for accessing shared services without circular imports."""

    _instance = None
    _main_window = None
    _performance_monitor = None
    _event_system = None

    def __init__(self):
        self._main_window = None
        self._performance_monitor = None
        self._event_system = None

    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_main_window(self, main_window):
        """Set reference to main window."""
        self._main_window = main_window

    def set_performance_monitor(self, monitor):
        """Set reference to performance monitor."""
        self._performance_monitor = monitor

    def set_event_system(self, event_system):
        """Set reference to event system."""
        self._event_system = event_system

    def get_main_window(self):
        """Get main window reference."""
        return self._main_window

    def get_performance_monitor(self):
        """Get performance monitor reference."""
        return self._performance_monitor

    def get_event_system(self):
        """Get event system reference."""
        return self._event_system

    def publish_event(self, event_type: str, data=None):
        """Publish event if event system is available."""
        if self._event_system:
            try:
                self._event_system.publish(event_type, data)
            except Exception as e:
                # Don't let event publishing break the main flow
                pass

    def record_api_call(self, response_time: float = None, error: bool = False):
        """Record API call in performance monitor."""
        if self._performance_monitor:
            try:
                self._performance_monitor.record_api_call(response_time, error)
            except Exception:
                pass

    def record_db_query(self, error: bool = False):
        """Record database query in performance monitor."""
        if self._performance_monitor:
            try:
                self._performance_monitor.record_db_query(error)
            except Exception:
                pass

# Global instance
app_context = ApplicationContext.get_instance()

# Anti-detection randomization ranges
MIN_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 30
MIN_INTERVAL_SECONDS = 1.5
MAX_INTERVAL_SECONDS = 3.0
MIN_GEMINI_TEMPERATURE = 0.6
MAX_GEMINI_TEMPERATURE = 0.9
MIN_GEMINI_TOP_P = 0.7
MAX_GEMINI_TOP_P = 0.9
MIN_GEMINI_TOP_K = 30
MAX_GEMINI_TOP_K = 50
MIN_GEMINI_MAX_TOKENS = 800
MAX_GEMINI_MAX_TOKENS = 1200
MIN_API_TIMEOUT = 12
MAX_API_TIMEOUT = 18

# Retry backoff settings
MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY = 2
MIN_RETRY_MULTIPLIER = 1
MAX_RETRY_MULTIPLIER = 3


class RandomizationUtils:
    """Centralized randomization utilities to reduce code duplication."""

    @staticmethod
    def get_delay_range() -> float:
        """Get a randomized delay for anti-detection."""
        return random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS)

    @staticmethod
    def get_interval_range() -> float:
        """Get a randomized interval for rate limiting."""
        return random.uniform(MIN_INTERVAL_SECONDS, MAX_INTERVAL_SECONDS)

    @staticmethod
    def get_gemini_temperature() -> float:
        """Get randomized temperature for Gemini API."""
        return random.uniform(MIN_GEMINI_TEMPERATURE, MAX_GEMINI_TEMPERATURE)

    @staticmethod
    def get_gemini_top_p() -> float:
        """Get randomized top_p for Gemini API."""
        return random.uniform(MIN_GEMINI_TOP_P, MAX_GEMINI_TOP_P)

    @staticmethod
    def get_gemini_top_k() -> int:
        """Get randomized top_k for Gemini API."""
        return random.randint(MIN_GEMINI_TOP_K, MAX_GEMINI_TOP_K)

    @staticmethod
    def get_gemini_max_tokens() -> int:
        """Get randomized max tokens for Gemini API."""
        return random.randint(MIN_GEMINI_MAX_TOKENS, MAX_GEMINI_MAX_TOKENS)

    @staticmethod
    def get_api_timeout() -> float:
        """Get randomized API timeout."""
        return random.uniform(MIN_API_TIMEOUT, MAX_API_TIMEOUT)

    @staticmethod
    def get_retry_delay(attempt: int, base_multiplier: float = BASE_RETRY_DELAY) -> float:
        """Get exponential backoff delay for retries."""
        multiplier = random.uniform(MIN_RETRY_MULTIPLIER, MAX_RETRY_MULTIPLIER)
        return (base_multiplier ** attempt) * multiplier

    @staticmethod
    def get_session_suffix() -> str:
        """Generate a random session suffix."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

    @staticmethod
    def get_connection_timeout() -> float:
        """Get randomized connection timeout."""
        return random.uniform(5, 15)

    @staticmethod
    def get_update_interval() -> float:
        """Get randomized update interval."""
        return random.uniform(30, 90)

    @staticmethod
    def get_typing_delay() -> float:
        """Get randomized typing delay."""
        return random.uniform(0.5, 2.0)

    @staticmethod
    def get_initial_delay() -> float:
        """Get randomized initial delay."""
        return random.uniform(2, 8)

    @staticmethod
    def get_online_update_interval() -> float:
        """Get randomized online status update interval."""
        return random.uniform(30, 90)

    @staticmethod
    def get_burst_pause() -> float:
        """Get randomized burst pause."""
        return random.uniform(300, 900)  # 5-15 minutes


class InputValidator:
    """Enhanced input validation and sanitization."""

    # Phone number patterns for different countries
    PHONE_PATTERNS = {
        'international': re.compile(r'^\+[1-9]\d{1,14}$'),
        'us': re.compile(r'^\+1\d{10}$'),
        'russia': re.compile(r'^\+7\d{10}$'),
        'ukraine': re.compile(r'^\+380\d{9}$'),
        'general': re.compile(r'^\+?\d{7,15}$')
    }

    # Channel/username patterns
    CHANNEL_PATTERNS = {
        'telegram_url': re.compile(r'^(?:https?://)?(?:www\.)?t\.me/([a-zA-Z0-9_]{5,32})(?:/\w+)?/?$'),
        'username': re.compile(r'^@[a-zA-Z0-9_]{5,32}$'),
        'channel_id': re.compile(r'^-?\d+$')
    }

    # Email pattern
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    # API key pattern (basic validation)
    API_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{20,}$')

    @staticmethod
    def sanitize_text(text: str, max_length: int = 1000, allow_html: bool = False) -> str:
        """Sanitize text input."""
        if not isinstance(text, str):
            return ""

        # Remove null bytes and control characters
        text = text.replace('\0', '').replace('\r', '').replace('\n', ' ')

        # Remove dangerous control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n')

        if not allow_html:
            # Remove HTML tags
            text = re.sub(r'<[^>]+>', '', text)

        # Limit length
        if len(text) > max_length:
            text = text[:max_length]

        return text.strip()

    @staticmethod
    def validate_phone_number(phone: str) -> Tuple[bool, str]:
        """Validate phone number format."""
        if not phone or not isinstance(phone, str):
            return False, "Phone number is required"

        phone = phone.strip()

        # Check against common patterns
        for pattern_name, pattern in InputValidator.PHONE_PATTERNS.items():
            if pattern.match(phone):
                return True, "Valid phone number"

        return False, "Invalid phone number format. Use international format: +1234567890"

    @staticmethod
    def validate_channel_url(url: str) -> Tuple[bool, str]:
        """Validate Telegram channel URL or username."""
        if not url or not isinstance(url, str):
            return False, "Channel URL/username is required"

        url = url.strip()

        # Check different formats
        for pattern_name, pattern in InputValidator.CHANNEL_PATTERNS.items():
            if pattern.match(url):
                return True, "Valid channel identifier"

        return False, "Invalid channel format. Use @username, https://t.me/channel, or channel ID"

    @staticmethod
    def validate_api_key(key: str) -> Tuple[bool, str]:
        """Validate API key format."""
        if not key or not isinstance(key, str):
            return False, "API key is required"

        key = key.strip()

        if len(key) < 20:
            return False, "API key too short"

        if not InputValidator.API_KEY_PATTERN.match(key):
            return False, "Invalid API key format"

        return True, "Valid API key format"

    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """Validate email address."""
        if not email or not isinstance(email, str):
            return False, "Email is required"

        email = email.strip()

        if not InputValidator.EMAIL_PATTERN.match(email):
            return False, "Invalid email format"

        return True, "Valid email address"

    @staticmethod
    def validate_integer(value: str, min_val: int = None, max_val: int = None) -> Tuple[bool, str]:
        """Validate integer input."""
        try:
            int_val = int(value)
            if min_val is not None and int_val < min_val:
                return False, f"Value must be at least {min_val}"
            if max_val is not None and int_val > max_val:
                return False, f"Value must be at most {max_val}"
            return True, f"Valid integer: {int_val}"
        except ValueError:
            return False, "Must be a valid integer"

    @staticmethod
    def validate_url(url: str) -> Tuple[bool, str]:
        """Validate URL format."""
        if not url or not isinstance(url, str):
            return False, "URL is required"

        url = url.strip()

        # Basic URL validation
        if not url.startswith(('http://', 'https://')):
            return False, "URL must start with http:// or https://"

        # Check for basic URL structure
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if not url_pattern.match(url):
            return False, "Invalid URL format"

        return True, "Valid URL"

