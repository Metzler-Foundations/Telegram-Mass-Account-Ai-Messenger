"""
Advanced Username Generator for creating visually similar usernames.
Uses Unicode lookalike characters, strategic replacements, and intelligent variations.
"""

import logging
import random
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class UsernameGenerator:
    """Generate visually similar usernames that are hard to detect as variations."""

    # Unicode lookalike character mappings (visually similar characters)
    LOOKALIKE_CHARS = {
        "a": ["а", "а", "a", "ɑ"],  # Cyrillic 'а', Latin 'a', etc.
        "e": ["е", "е", "e", "ё"],  # Cyrillic 'е'
        "o": ["о", "о", "o", "ο", "о"],  # Cyrillic 'о', Greek omicron
        "p": ["р", "р", "p"],  # Cyrillic 'р'
        "c": ["с", "с", "c", "ϲ"],  # Cyrillic 'с'
        "x": ["х", "х", "x", "х"],  # Cyrillic 'х'
        "y": ["у", "у", "y", "у"],  # Cyrillic 'у'
        "i": ["і", "і", "i", "і", "ı"],  # Cyrillic 'і'
        "m": ["м", "м", "m"],  # Cyrillic 'м'
        "n": ["п", "п", "n", "п"],  # Cyrillic 'п' (looks like n)
        "r": ["г", "г", "r"],  # Cyrillic 'г' (looks like r)
        "u": ["и", "и", "u"],  # Cyrillic 'и' (looks like u)
        "A": ["А", "А", "A"],  # Cyrillic 'А'
        "E": ["Е", "Е", "E"],  # Cyrillic 'Е'
        "O": ["О", "О", "O"],  # Cyrillic 'О'
        "C": ["С", "С", "C"],  # Cyrillic 'С'
        "P": ["Р", "Р", "P"],  # Cyrillic 'Р'
        "X": ["Х", "Х", "X"],  # Cyrillic 'Х'
        "B": ["В", "В", "B"],  # Cyrillic 'В'
        "H": ["Н", "Н", "H"],  # Cyrillic 'Н'
        "M": ["М", "М", "M"],  # Cyrillic 'М'
        "T": ["Т", "Т", "T"],  # Cyrillic 'Т'
    }

    # Similar-looking number replacements
    NUMBER_LOOKALIKES = {
        "0": ["0", "O", "о", "Ο"],  # Zero, O, Cyrillic о
        "1": ["1", "l", "I", "і", "І"],  # One, lowercase L, uppercase I
        "2": ["2", "Z", "z"],  # Two, Z
        "3": ["3", "Е", "е"],  # Three, Cyrillic Е
        "4": ["4", "ч"],  # Four, Cyrillic ч (looks similar)
        "5": ["5", "S", "s"],  # Five, S
        "6": ["6", "б"],  # Six, Cyrillic б
        "7": ["7", "Т", "т"],  # Seven, Cyrillic Т
        "8": ["8", "В", "в"],  # Eight, Cyrillic В
        "9": ["9", "g", "q"],  # Nine, g, q
    }

    # Strategic insertion points (common patterns)
    INSERTION_PATTERNS = [
        ("_", ""),  # Remove underscore
        ("", "_"),  # Add underscore
        ("", "."),  # Add dot (if allowed)
        ("", "-"),  # Add dash (if allowed)
    ]

    def __init__(self):
        self.generated_usernames = set()  # Track generated usernames to avoid duplicates

    def generate_visually_similar_username(
        self, source_username: str, max_attempts: int = 50
    ) -> Optional[str]:
        """
        Generate a visually similar username that looks almost identical.

        Strategies:
        1. Replace characters with Unicode lookalikes
        2. Strategic character swaps
        3. Minimal additions (dots, underscores) in natural positions
        4. Case variations
        5. Number replacements with lookalike characters

        Args:
            source_username: Original username to base variation on
            max_attempts: Maximum attempts to generate unique username

        Returns:
            Generated username or None if all attempts failed
        """
        if not source_username:
            return None

        # Clean source username
        source_username = source_username.strip().lstrip("@")

        for _attempt in range(max_attempts):
            # Strategy 1: Unicode lookalike replacement (most effective)
            username = self._apply_lookalike_replacements(source_username)

            # Strategy 2: Strategic character modifications
            if random.random() < 0.3:  # 30% chance
                username = self._apply_strategic_modifications(username)

            # Strategy 3: Minimal punctuation insertion
            if random.random() < 0.2:  # 20% chance
                username = self._insert_minimal_punctuation(username)

            # Strategy 4: Case variations (subtle)
            if random.random() < 0.15:  # 15% chance
                username = self._apply_case_variations(username)

            # Strategy 5: Number lookalike replacement
            if random.random() < 0.25:  # 25% chance
                username = self._apply_number_lookalikes(username)

            # Ensure it's different from source
            if username != source_username and username not in self.generated_usernames:
                # Validate Telegram username format
                if self._is_valid_telegram_username(username):
                    self.generated_usernames.add(username)
                    return username

        # Fallback: try simpler variations
        return self._generate_fallback_variation(source_username)

    def _apply_lookalike_replacements(self, username: str) -> str:
        """Replace characters with Unicode lookalikes."""
        result = []
        replaced_count = 0
        max_replacements = min(3, len(username) // 3)  # Replace up to 1/3 of chars, max 3

        for char in username:
            if replaced_count < max_replacements and char in self.LOOKALIKE_CHARS:
                if random.random() < 0.4:  # 40% chance to replace each eligible char
                    result.append(random.choice(self.LOOKALIKE_CHARS[char]))
                    replaced_count += 1
                else:
                    result.append(char)
            else:
                result.append(char)

        return "".join(result)

    def _apply_strategic_modifications(self, username: str) -> str:
        """Apply strategic character modifications."""
        if len(username) < 3:
            return username

        # Swap adjacent similar characters (subtle)
        if random.random() < 0.3 and len(username) >= 2:
            chars = list(username)
            # Find similar adjacent characters
            for i in range(len(chars) - 1):
                if chars[i].lower() == chars[i + 1].lower():
                    if random.random() < 0.5:
                        chars[i], chars[i + 1] = chars[i + 1], chars[i]
                        break
            return "".join(chars)

        # Remove or add a character in the middle (very subtle)
        if len(username) > 5 and random.random() < 0.2:
            if random.random() < 0.5:
                # Remove a character
                pos = random.randint(1, len(username) - 2)
                return username[:pos] + username[pos + 1 :]
            else:
                # Add a similar character
                pos = random.randint(1, len(username) - 1)
                char_to_add = username[pos - 1] if pos > 0 else username[pos]
                return username[:pos] + char_to_add + username[pos:]

        return username

    def _insert_minimal_punctuation(self, username: str) -> str:
        """Insert minimal punctuation in natural positions."""
        if len(username) < 4:
            return username

        # Only insert if there's no punctuation already
        if "_" in username or "." in username or "-" in username:
            return username

        # Insert in natural positions (not at start/end)
        pos = random.randint(1, len(username) - 2)
        punctuation = random.choice(["_", ".", "-"])

        return username[:pos] + punctuation + username[pos:]

    def _apply_case_variations(self, username: str) -> str:
        """Apply subtle case variations."""
        # Only change 1-2 characters to maintain visual similarity
        chars = list(username)
        changes = random.randint(1, min(2, len(chars)))

        for _ in range(changes):
            pos = random.randint(0, len(chars) - 1)
            if chars[pos].isalpha():
                chars[pos] = chars[pos].swapcase()

        return "".join(chars)

    def _apply_number_lookalikes(self, username: str) -> str:
        """Replace numbers with lookalike characters."""
        result = []
        for char in username:
            if char in self.NUMBER_LOOKALIKES:
                if random.random() < 0.5:  # 50% chance to replace
                    result.append(random.choice(self.NUMBER_LOOKALIKES[char]))
                else:
                    result.append(char)
            else:
                result.append(char)
        return "".join(result)

    def _generate_fallback_variation(self, source_username: str) -> Optional[str]:
        """Generate a fallback variation if main strategies fail."""
        # Try very minimal changes
        variations = [
            source_username + "_",  # Add underscore at end
            "_" + source_username,  # Add underscore at start
            source_username.replace("_", ""),  # Remove underscore
            source_username.replace("_", "."),  # Replace underscore with dot
        ]

        for var in variations:
            if var != source_username and self._is_valid_telegram_username(var):
                if var not in self.generated_usernames:
                    self.generated_usernames.add(var)
                    return var

        return None

    def _is_valid_telegram_username(self, username: str) -> bool:
        """Check if username is valid for Telegram with comprehensive validation."""
        if not username:
            logger.debug("Empty username")
            return False

        if not isinstance(username, str):
            logger.warning(f"Username must be string, got {type(username)}")
            return False

        # Telegram username rules:
        # - 5-32 characters
        # - Only letters, numbers, underscores
        # - Cannot start with number
        # - Cannot end with underscore
        # - No consecutive underscores
        # - Case insensitive (but we'll preserve case for visual similarity)

        if len(username) < 5:
            logger.debug(f"Username too short: {len(username)} < 5")
            return False

        if len(username) > 32:
            logger.debug(f"Username too long: {len(username)} > 32")
            return False

        # Check if starts with number (not allowed)
        if username[0].isdigit():
            logger.debug(f"Username starts with digit: {username[0]}")
            return False

        # Check if ends with underscore (not allowed)
        if username.endswith("_"):
            logger.debug("Username ends with underscore")
            return False

        # Check for consecutive underscores (not allowed)
        if "__" in username:
            logger.debug("Username contains consecutive underscores")
            return False

        # Validate characters
        from accounts.username_validator import UsernameValidator

        try:
            UsernameValidator.validate_username(username)
        except Exception as e:
            logger.debug(f"Username validation failed: {e}")
            return False

        # Check characters (allow Unicode for lookalikes but validate)
        try:
            # Ensure valid UTF-8
            username.encode("utf-8")

            # Allow Latin, Cyrillic, numbers, and underscores
            pattern = re.compile(r"^[a-zA-Z0-9_а-яА-ЯёЁіІєЄїЇґҐ]+$", re.UNICODE)
            if not pattern.match(username):
                logger.debug(f"Username contains invalid characters: {username}")
                return False
        except UnicodeEncodeError as e:
            logger.debug(f"Username encoding error: {e}")
            return False

        return True

    async def check_username_availability(
        self, client, username: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a username is available on Telegram with validation.

        Args:
            client: Pyrogram Client instance
            username: Username to check

        Returns:
            Tuple of (is_available, error_message)
        """
        # Validate format first
        if not self._is_valid_telegram_username(username):
            return False, "Invalid username format"

        try:
            # Normalize username (remove @, trim, lowercase for check)
            check_username = username.lstrip("@").strip()

            # Try to get user by username
            try:
                user = await client.get_users(check_username)
                # If we get here, username is taken
                logger.debug(
                    f"Username {check_username} is taken by user {user.id if user else 'unknown'}"
                )
                return False, "Username is already taken"
            except Exception as e:
                error_str = str(e).lower()
                if (
                    "username not occupied" in error_str
                    or "user not found" in error_str
                    or "not found" in error_str
                ):
                    logger.debug(f"Username {check_username} is available")
                    return True, None
                elif "username invalid" in error_str or "invalid" in error_str:
                    logger.debug(f"Username {check_username} has invalid format")
                    return False, "Invalid username format"
                elif "flood" in error_str:
                    logger.warning(f"Rate limited checking username: {e}")
                    return False, "Rate limited - try again later"
                else:
                    # Unknown error, log and treat as unavailable for safety
                    logger.warning(f"Unknown error checking username {check_username}: {e}")
                    return False, f"Error checking: {e}"
        except Exception as e:
            logger.error(f"Error checking username availability for {username}: {e}", exc_info=True)
            return False, str(e)

    async def find_available_similar_username(
        self, client, source_username: str, max_attempts: int = 100
    ) -> Optional[str]:
        """
        Find an available username that is visually similar to the source.

        Args:
            client: Pyrogram Client instance
            source_username: Original username to base variations on
            max_attempts: Maximum attempts to find available username

        Returns:
            Available username or None if all attempts failed
        """
        attempts = 0
        checked_usernames = set()

        while attempts < max_attempts:
            # Generate variation
            candidate = self.generate_visually_similar_username(source_username, max_attempts=10)

            if not candidate or candidate in checked_usernames:
                attempts += 1
                continue

            checked_usernames.add(candidate)

            # Check availability
            is_available, error = await self.check_username_availability(client, candidate)

            if is_available:
                logger.info(
                    f"✅ Found available similar username: {candidate} (from {source_username})"
                )
                return candidate
            else:
                logger.debug(f"Username {candidate} not available: {error}")

            attempts += 1

        logger.warning(
            f"Could not find available similar username for {source_username} "
            f"after {max_attempts} attempts"
        )
        return None

    def reset_generated_cache(self):
        """Reset the cache of generated usernames."""
        self.generated_usernames.clear()
