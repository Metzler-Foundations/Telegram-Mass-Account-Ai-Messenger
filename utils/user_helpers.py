#!/usr/bin/env python3
"""
User-Friendly Helpers - Validation, Error Messages, and Guidance
Translates technical errors into actionable user guidance
"""

import logging
import re
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class ValidationHelper:
    """Validates user input and provides helpful feedback."""

    @staticmethod
    def validate_phone_number(phone: str) -> Tuple[bool, str]:
        """
        Validate phone number format.

        Returns:
            (is_valid, error_message)
        """
        if not phone:
            return False, "Phone number is required. Example: +1234567890"

        # Remove spaces and dashes
        cleaned = phone.replace(" ", "").replace("-", "")

        if not cleaned.startswith("+"):
            return (
                False,
                "Phone number must start with '+' followed by country code. Example: +1234567890",
            )

        # Check if rest is digits
        if not cleaned[1:].isdigit():
            return (
                False,
                "Phone number should only contain digits after the '+'. Example: +1234567890",
            )

        if len(cleaned) < 10:
            return False, "Phone number seems too short. Include country code. Example: +1234567890"

        if len(cleaned) > 16:
            return False, "Phone number seems too long. Example: +1234567890"

        return True, ""

    @staticmethod
    def validate_api_id(api_id: str) -> Tuple[bool, str]:
        """Validate Telegram API ID."""
        if not api_id:
            return False, "API ID is required. Get it from https://my.telegram.org/apps"

        if not api_id.isdigit():
            return (
                False,
                "API ID should be a number (e.g., 12345678). "
                "Get it from https://my.telegram.org/apps",
            )

        if len(api_id) < 6:
            return (
                False,
                "API ID seems too short. It should be 7-8 digits. "
                "Check https://my.telegram.org/apps",
            )

        return True, ""

    @staticmethod
    def validate_api_hash(api_hash: str) -> Tuple[bool, str]:
        """Validate Telegram API Hash."""
        if not api_hash:
            return False, "API Hash is required. Get it from https://my.telegram.org/apps"

        if len(api_hash) != 32:
            return (
                False,
                "API Hash should be exactly 32 characters. Check https://my.telegram.org/apps",
            )

        if not re.match(r"^[a-f0-9]{32}$", api_hash.lower()):
            return (
                False,
                "API Hash should contain only letters (a-f) and numbers (0-9). "
                "Check https://my.telegram.org/apps",
            )

        return True, ""

    @staticmethod
    def validate_gemini_api_key(api_key: str) -> Tuple[bool, str]:
        """Validate Gemini API key format."""
        if not api_key:
            return (
                False,
                "Gemini API key is required for AI features. "
                "Get it from https://makersuite.google.com/app/apikey",
            )

        # Gemini keys typically start with "AI" and are ~39 characters
        if not api_key.startswith("AI"):
            return (
                False,
                "Gemini API key should start with 'AIza'. "
                "Get it from https://makersuite.google.com/app/apikey",
            )

        if len(api_key) < 30:
            return (
                False,
                "Gemini API key seems too short. Check https://makersuite.google.com/app/apikey",
            )

        return True, ""

    @staticmethod
    def validate_proxy(proxy: str) -> Tuple[bool, str]:
        """Validate proxy format."""
        if not proxy:
            return True, ""  # Proxy is optional

        # Expected format: ip:port or ip:port:username:password
        parts = proxy.split(":")

        if len(parts) < 2:
            return False, "Proxy format should be: ip:port or ip:port:username:password"

        ip, port = parts[0], parts[1]

        # Validate IP
        ip_parts = ip.split(".")
        if len(ip_parts) != 4:
            return False, f"Invalid IP address: {ip}. Should be like 192.168.1.1"

        try:
            for part in ip_parts:
                num = int(part)
                if not 0 <= num <= 255:
                    return False, f"Invalid IP address: {ip}. Each part should be 0-255"
        except ValueError:
            return False, f"Invalid IP address: {ip}. Should contain only numbers and dots"

        # Validate port
        try:
            port_num = int(port)
            if not 1 <= port_num <= 65535:
                return False, f"Invalid port: {port}. Should be between 1 and 65535"
        except ValueError:
            return False, f"Invalid port: {port}. Should be a number"

        return True, ""

    @staticmethod
    def validate_config(config: Dict[str, Any]) -> List[str]:
        """
        Validate complete configuration and return list of errors.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Check Telegram config
        if "telegram" in config:
            tg = config["telegram"]

            valid, msg = ValidationHelper.validate_api_id(tg.get("api_id", ""))
            if not valid:
                errors.append(f"Telegram API ID: {msg}")

            valid, msg = ValidationHelper.validate_api_hash(tg.get("api_hash", ""))
            if not valid:
                errors.append(f"Telegram API Hash: {msg}")

            valid, msg = ValidationHelper.validate_phone_number(tg.get("phone_number", ""))
            if not valid:
                errors.append(f"Phone Number: {msg}")
        else:
            errors.append("Telegram configuration is missing. Please configure it in Settings.")

        # Check Gemini config (optional for some features)
        if "gemini" in config:
            gem = config["gemini"]
            api_key = gem.get("api_key", "")
            if api_key:  # Only validate if provided
                valid, msg = ValidationHelper.validate_gemini_api_key(api_key)
                if not valid:
                    errors.append(f"Gemini API Key: {msg}")

        return errors


class ErrorTranslator:
    """Translates technical errors into user-friendly messages."""

    ERROR_TRANSLATIONS = {
        # Pyrogram/Telegram errors
        "PhoneNumberInvalid": {
            "title": "Invalid Phone Number",
            "message": "The phone number format is incorrect.",
            "solution": "Make sure to include the country code with '+'. Example: +1234567890",
        },
        "PhoneCodeInvalid": {
            "title": "Invalid Verification Code",
            "message": "The verification code you entered is incorrect.",
            "solution": "Check the code Telegram sent you and try again. The code usually has 5 digits.",
        },
        "PhoneCodeExpired": {
            "title": "Verification Code Expired",
            "message": "The verification code has expired.",
            "solution": "Request a new code and enter it within 5 minutes.",
        },
        "SessionPasswordNeeded": {
            "title": "Two-Factor Authentication Required",
            "message": "This account has 2FA (two-factor authentication) enabled.",
            "solution": (
                "You'll need to enter your 2FA password. "
                "For new account creation, use a number without 2FA."
            ),
        },
        "FloodWait": {
            "title": "Rate Limit Reached",
            "message": "Telegram has temporarily rate-limited this action.",
            "solution": (
                "Please wait {wait_time} seconds before trying again. "
                "This is Telegram's anti-spam protection."
            ),
        },
        "UserDeactivated": {
            "title": "Account Deactivated",
            "message": "This Telegram account has been deactivated or banned.",
            "solution": "You cannot use this account. Create a new one or contact Telegram support.",
        },
        "ApiIdInvalid": {
            "title": "Invalid API Credentials",
            "message": "Your Telegram API ID or Hash is incorrect.",
            "solution": "Double-check your credentials at https://my.telegram.org/apps",
        },
        "ApiIdPublishedFlood": {
            "title": "API Credentials Compromised",
            "message": "These API credentials have been flagged by Telegram.",
            "solution": "Create new API credentials at https://my.telegram.org/apps",
        },
        # Phone provider errors
        "Failed to get phone number": {
            "title": "Phone Number Service Issue",
            "message": "Could not get a phone number from the provider.",
            "solution": (
                "Check: 1) Your API key is valid 2) You have credit in your account "
                "3) The country you selected is available"
            ),
        },
        "Failed to get SMS code": {
            "title": "SMS Code Not Received",
            "message": "The SMS verification code was not received within the timeout period.",
            "solution": (
                "This could mean: 1) The number is blacklisted by Telegram "
                "2) SMS delivery is delayed 3) The provider has issues. "
                "Try with a different country or provider."
            ),
        },
        # Network errors
        "Connection": {
            "title": "Connection Error",
            "message": "Could not connect to Telegram servers.",
            "solution": "Check your internet connection. If using a proxy, verify it's working.",
        },
        "Timeout": {
            "title": "Connection Timeout",
            "message": "The connection timed out.",
            "solution": (
                "Your internet might be slow or Telegram servers might be busy. "
                "Try again in a moment."
            ),
        },
        # Gemini errors
        "API_KEY_INVALID": {
            "title": "Invalid Gemini API Key",
            "message": "Your Gemini API key is not valid.",
            "solution": "Check your API key at https://makersuite.google.com/app/apikey",
        },
        "RESOURCE_EXHAUSTED": {
            "title": "Gemini API Quota Exceeded",
            "message": "You've exceeded your Gemini API quota.",
            "solution": (
                "Wait for quota to reset or upgrade your plan at "
                "https://makersuite.google.com/"
            ),
        },
        # Database errors
        "database is locked": {
            "title": "Database Locked",
            "message": "The database is locked by another process.",
            "solution": "Close any other instances of this application. If problem persists, restart the app.",
        },
        # Proxy errors
        "Proxy": {
            "title": "Proxy Connection Failed",
            "message": "Could not connect through the proxy.",
            "solution": "Check: 1) Proxy IP and port are correct 2) Proxy is online 3) Username/password if required",
        },
    }

    @staticmethod
    def translate_error(error: Exception, context: str = "") -> Dict[str, str]:
        """
        Translate a technical error into user-friendly message.

        Args:
            error: The exception/error
            context: Additional context (e.g., "account creation", "sending message")

        Returns:
            Dict with title, message, solution
        """
        error_str = str(error)
        error_type = type(error).__name__

        # Check if we have a direct translation
        if error_type in ErrorTranslator.ERROR_TRANSLATIONS:
            translation = ErrorTranslator.ERROR_TRANSLATIONS[error_type].copy()
            # Handle FloodWait special case
            if error_type == "FloodWait" and hasattr(error, "value"):
                translation["solution"] = translation["solution"].format(wait_time=error.value)
            return translation

        # Check if error string contains known patterns
        for pattern, translation in ErrorTranslator.ERROR_TRANSLATIONS.items():
            if pattern.lower() in error_str.lower():
                return translation.copy()

        # Fallback: generic error message
        return {
            "title": f"Error{' during ' + context if context else ''}",
            "message": error_str if len(error_str) < 200 else error_str[:200] + "...",
            "solution": "If this error persists, please check the logs or contact support.",
        }

    @staticmethod
    def format_error_for_user(error: Exception, context: str = "") -> str:
        """
        Format error as a user-friendly string.

        Returns:
            Formatted error message
        """
        translated = ErrorTranslator.translate_error(error, context)

        return (
            f"❌ {translated['title']}\n\n{translated['message']}\n\n"
            f"💡 Solution:\n{translated['solution']}"
        )


class ProgressHelper:
    """Provides user-friendly progress messages."""

    STAGE_MESSAGES = {
        # Account creation stages
        "getting_proxy": "🌐 Finding a proxy server...",
        "getting_phone": "📱 Getting a phone number...",
        "initializing_client": "🔧 Initializing Telegram client...",
        "sending_code": "📤 Requesting verification code...",
        "waiting_sms": "⏳ Waiting for SMS code (this may take 1-2 minutes)...",
        "signing_in": "🔐 Signing in...",
        "setting_up_profile": "👤 Setting up profile...",
        "generating_username": "✏️ Creating username...",
        "setting_photo": "📸 Uploading profile photo...",
        "warmup_queued": "♨️ Account queued for warmup...",
        "complete": "✅ Account created successfully!",
        # Campaign stages
        "loading_accounts": "📋 Loading accounts...",
        "loading_members": "👥 Loading target members...",
        "preparing_messages": "📝 Preparing messages...",
        "sending": "📤 Sending messages...",
        "campaign_complete": "✅ Campaign completed!",
        # Scraping stages
        "connecting": "🔌 Connecting to Telegram...",
        "fetching_members": "👥 Fetching members (this may take a while)...",
        "saving": "💾 Saving to database...",
        "scrape_complete": "✅ Scraping completed!",
        # Warmup stages
        "warmup_waiting": "⏸️ Waiting for warmup schedule...",
        "warmup_profile": "👤 Completing profile setup...",
        "warmup_groups": "👥 Joining groups...",
        "warmup_activity": "💬 Simulating activity...",
        "warmup_complete": "✅ Warmup completed!",
    }

    @staticmethod
    def get_message(stage: str, progress: int = 0) -> str:
        """
        Get user-friendly progress message.

        Args:
            stage: Stage identifier
            progress: Progress percentage (0-100)

        Returns:
            Formatted progress message
        """
        base_message = ProgressHelper.STAGE_MESSAGES.get(
            stage, f"⚙️ {stage.replace('_', ' ').title()}..."
        )

        if progress > 0:
            return f"{base_message} ({progress}%)"

        return base_message


class TooltipHelper:
    """Provides helpful tooltips for UI elements."""

    TOOLTIPS = {
        # API Settings
        "telegram_api_id": "Your Telegram API ID from https://my.telegram.org/apps\nExample: 12345678",
        "telegram_api_hash": (
            "Your Telegram API Hash from https://my.telegram.org/apps\n"
            "Example: 0123456789abcdef0123456789abcdef"
        ),
        "telegram_phone": "Your phone number with country code\nExample: +1234567890",
        "gemini_api_key": (
            "Your Gemini AI API key from https://makersuite.google.com/app/apikey\n"
            "Required for AI responses and profile cloning"
        ),
        # Anti-Detection
        "min_delay": "Minimum seconds to wait between actions\nLower = faster but riskier\nRecommended: 2-5 seconds",
        "max_delay": "Maximum seconds to wait between actions\nHigher = safer but slower\nRecommended: 20-60 seconds",
        "messages_per_hour": (
            "How many messages to send per hour\nTelegram limit: ~200/hour\n"
            "Safe rate: 30-50/hour\nAggressive: 80-100/hour"
        ),
        "burst_limit": "Max messages to send in quick succession\nRecommended: 2-3 messages\nLower is safer",
        "online_simulation": "Simulate realistic online/offline patterns\nMakes your bot appear more human",
        # Phone Provider
        "phone_provider": (
            "Service to get phone numbers for verification\n"
            "Popular: SMS-Activate, SMSPool\nCost: $0.08-0.15 per number"
        ),
        "provider_api_key": "API key from your phone number provider\nGet it from your provider's dashboard",
        "country": "Country for phone numbers\nUS numbers are most stable\nOther countries may be cheaper",
        # Proxy
        "proxy_format": "Format: ip:port or ip:port:username:password\nExample: 192.168.1.1:8080",
        "use_proxy": "Use proxy for account creation\nRecommended: Yes, especially for bulk creation\nHelps avoid IP bans",
        # Warmup
        "warmup_enabled": "Automatically warm up new accounts\nMakes accounts look legitimate to Telegram\nHighly recommended for new accounts",
        "warmup_duration": "How many days to warm up account\nRecommended: 3-7 days\nLonger = safer",
        # Campaign
        "campaign_schedule": "When to send messages\nNow: Start immediately\nScheduled: Set a specific time",
        "campaign_delay": "Delay between messages to same user\nRecommended: 24-48 hours\nAvoid seeming spammy",
        # Advanced
        "realistic_typing": "Simulate human typing speed\nAdds delays proportional to message length",
        "random_skip": "Randomly skip some messages\nMakes pattern less predictable",
        "session_recovery": "Automatically reconnect on network errors\nKeeps your bots running reliably",
    }

    @staticmethod
    def get(key: str) -> str:
        """Get tooltip for a UI element."""
        return TooltipHelper.TOOLTIPS.get(key, "")


# Convenience functions
def validate_config(config: Dict[str, Any]) -> List[str]:
    """Validate configuration and return errors."""
    return ValidationHelper.validate_config(config)


def translate_error(error: Exception, context: str = "") -> str:
    """Translate error to user-friendly message."""
    return ErrorTranslator.format_error_for_user(error, context)


def get_progress_message(stage: str, progress: int = 0) -> str:
    """Get progress message."""
    return ProgressHelper.get_message(stage, progress)


def get_tooltip(key: str) -> str:
    """Get tooltip for UI element."""
    return TooltipHelper.get(key)
