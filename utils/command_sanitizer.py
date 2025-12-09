#!/usr/bin/env python3
"""Command sanitization - Prevent command injection."""

import logging
import shlex
from typing import List

logger = logging.getLogger(__name__)


class CommandSanitizer:
    """Sanitizes external command execution."""

    # Dangerous characters in shell commands
    DANGEROUS_CHARS = set(";&|`$<>(){}[]!*?")

    @staticmethod
    def sanitize_command_arg(arg: str) -> str:
        """Sanitize single command argument."""
        if any(c in arg for c in CommandSanitizer.DANGEROUS_CHARS):
            logger.warning(f"Dangerous characters in command arg: {arg}")
            raise ValueError("Command argument contains dangerous characters")

        return shlex.quote(arg)

    @staticmethod
    def build_safe_command(command: str, args: List[str]) -> List[str]:
        """Build safe command with sanitized args."""
        safe_args = [CommandSanitizer.sanitize_command_arg(arg) for arg in args]
        return [command] + safe_args

    @staticmethod
    def validate_command_whitelist(command: str, whitelist: List[str]) -> bool:
        """Validate command is in whitelist."""
        return command in whitelist
