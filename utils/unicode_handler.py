#!/usr/bin/env python3
"""
Unicode Handler - Safe Unicode operations.

Features:
- Unicode normalization
- Emoji handling
- Encoding safety
- Invalid character filtering
"""

import logging
import unicodedata

logger = logging.getLogger(__name__)


class UnicodeHandler:
    """Safe Unicode text handling with comprehensive error handling."""

    @staticmethod
    def normalize(text: str, form: str = "NFC") -> str:
        """
        Normalize Unicode text with error handling.

        Args:
            text: Text to normalize
            form: Normalization form (NFC, NFD, NFKC, NFKD)

        Returns:
            Normalized text
        """
        if not isinstance(text, str):
            try:
                text = str(text)
            except Exception as e:
                logger.error(f"Failed to convert to string: {e}")
                return ""

        try:
            # Validate form
            if form not in ("NFC", "NFD", "NFKC", "NFKD"):
                logger.warning(f"Invalid normalization form: {form}, using NFC")
                form = "NFC"

            return unicodedata.normalize(form, text)
        except Exception as e:
            logger.error(f"Unicode normalization failed: {e}")
            return text

    @staticmethod
    def safe_encode(text: str, encoding: str = "utf-8", errors: str = "replace") -> bytes:
        """Safely encode text."""
        try:
            return text.encode(encoding, errors=errors)
        except Exception as e:
            logger.error(f"Encoding failed: {e}")
            return text.encode("utf-8", errors="replace")

    @staticmethod
    def safe_decode(data: bytes, encoding: str = "utf-8", errors: str = "replace") -> str:
        """Safely decode bytes."""
        try:
            return data.decode(encoding, errors=errors)
        except Exception as e:
            logger.error(f"Decoding failed: {e}")
            return data.decode("utf-8", errors="replace")

    @staticmethod
    def filter_invalid_chars(text: str, allowed_chars: set = None) -> str:
        """
        Remove invalid characters with comprehensive filtering.

        Args:
            text: Text to filter
            allowed_chars: Set of explicitly allowed characters

        Returns:
            Filtered text
        """
        if not isinstance(text, str):
            text = str(text)

        if allowed_chars:
            return "".join(c for c in text if c in allowed_chars or c.isalnum() or c.isspace())

        # Remove control characters except common ones
        filtered = []
        for c in text:
            try:
                cat = unicodedata.category(c)
                # Allow printable chars and common whitespace
                if cat[0] != "C" or c in "\n\r\t":
                    filtered.append(c)
            except Exception:
                # Skip characters that cause errors
                continue

        return "".join(filtered)

    @staticmethod
    def truncate_safe(text: str, max_length: int, ellipsis: bool = False) -> str:
        """
        Truncate text without breaking multi-byte characters or emoji.

        Args:
            text: Text to truncate
            max_length: Maximum length
            ellipsis: Add ellipsis if truncated

        Returns:
            Safely truncated text
        """
        if not isinstance(text, str):
            text = str(text)

        if len(text) <= max_length:
            return text

        # Reserve space for ellipsis if needed
        target_len = max_length - 3 if ellipsis else max_length

        # Truncate and ensure valid UTF-8
        truncated = text[:target_len]
        try:
            truncated.encode("utf-8")
            return truncated + "..." if ellipsis else truncated
        except UnicodeEncodeError:
            # Back off until valid (handles emoji and multi-byte chars)
            for i in range(target_len - 1, max(0, target_len - 4), -1):
                try:
                    truncated = text[:i]
                    truncated.encode("utf-8")
                    return truncated + "..." if ellipsis else truncated
                except UnicodeEncodeError:
                    continue

        # Last resort: remove all non-ASCII
        safe_text = "".join(c for c in text if ord(c) < 128)[:target_len]
        return safe_text + "..." if ellipsis else safe_text

    @staticmethod
    def is_emoji(char: str) -> bool:
        """Check if character is an emoji."""
        try:
            return unicodedata.category(char) in ("So", "Sm", "Sk")
        except Exception:
            return False

    @staticmethod
    def count_emojis(text: str) -> int:
        """Count emojis in text."""
        return sum(1 for char in text if UnicodeHandler.is_emoji(char))

    @staticmethod
    def remove_emojis(text: str) -> str:
        """Remove all emojis from text."""
        return "".join(char for char in text if not UnicodeHandler.is_emoji(char))

    @staticmethod
    def validate_utf8(text: str) -> bool:
        """Validate that text is valid UTF-8."""
        try:
            text.encode("utf-8").decode("utf-8")
            return True
        except (UnicodeEncodeError, UnicodeDecodeError):
            return False
