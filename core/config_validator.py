"""
Configuration validation helpers for critical credentials.
"""

import os
from typing import Any, Dict, List

from core.config_manager import ConfigurationManager


def _is_blank(value: Any) -> bool:
    """Check if a value is empty/whitespace."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def validate_core_credentials(config: ConfigurationManager) -> Dict[str, Any]:
    """
    Validate that the minimal required credentials exist.

    Returns:
        dict: {
            "ok": bool,
            "issues": List[str],
            "warnings": List[str],
            "effective": { "telegram_api_id": str, ... }
        }
    """
    issues: List[str] = []
    warnings: List[str] = []

    telegram_cfg = config.get("telegram", {}) or {}
    api_id = telegram_cfg.get("api_id") or os.getenv("TELEGRAM_API_ID", "")
    api_hash = telegram_cfg.get("api_hash") or os.getenv("TELEGRAM_API_HASH", "")
    phone_number = telegram_cfg.get("phone_number") or os.getenv("TELEGRAM_PHONE_NUMBER", "")

    if _is_blank(api_id):
        issues.append("Telegram API ID is missing (set TELEGRAM_API_ID or in Settings).")
    if _is_blank(api_hash):
        issues.append("Telegram API hash is missing (set TELEGRAM_API_HASH or in Settings).")
    if _is_blank(phone_number):
        warnings.append("Telegram phone number is missing; interactive login will be required.")

    # Check Gemini API key from secrets manager
    try:
        from core.secrets_manager import get_secrets_manager

        secrets_manager = get_secrets_manager()
        gemini_key = secrets_manager.get_secret("gemini_api_key", required=False)
    except Exception:
        # Fallback to config/env if secrets manager fails
        gemini_cfg = config.get("gemini", {}) or {}
        gemini_key = gemini_cfg.get("api_key") or os.getenv("GEMINI_API_KEY", "")

    if _is_blank(gemini_key):
        warnings.append("Gemini API key not configured; AI will run in offline/template fallback.")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "effective": {
            "telegram_api_id": api_id,
            "telegram_api_hash": api_hash,
            "telegram_phone_number": phone_number,
            "gemini_api_key_present": not _is_blank(gemini_key),
        },
    }
