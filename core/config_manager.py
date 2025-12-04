"""
Configuration Manager - Centralized configuration handling.
"""
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from copy import deepcopy

logger = logging.getLogger(__name__)

# Import secrets manager for secure credential handling
try:
    from core.secrets_manager import get_secrets_manager
    SECRETS_AVAILABLE = True
except ImportError:
    SECRETS_AVAILABLE = False
    logger.warning("Secrets manager not available")


class ConfigurationManager:
    """Load and persist application configuration."""

    DEFAULT_CONFIG = {
        "telegram": {
            "api_id": "",
            "api_hash": "",
            "phone_number": ""
        },
        "gemini": {
            "api_key": ""
        },
        "brain": {
            "prompt": "",
            "auto_reply_enabled": True,
            "typing_delay": 2,
            "max_history": 50
        },
        "advanced": {
            "max_reply_length": 1024,
            "enable_logging": True,
            "realistic_typing": True,
            "random_delays": True
        },
        "anti_detection": {
            "min_delay": 2,
            "max_delay": 30,
            "messages_per_hour": 50,
            "burst_limit": 3,
            "online_simulation": True,
            "random_skip": True,
            "time_based_delays": True,
            "error_backoff": True,
            "session_recovery": True
        }
    }

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self._config: Dict[str, Any] = deepcopy(self.DEFAULT_CONFIG)
        self._load()

    def _load(self) -> None:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                    self._deep_merge(self._config, data)
            except Exception as exc:
                logger.error(f"Failed to load configuration: {exc}")

    def save(self) -> None:
        try:
            # Ensure config_path is valid
            if not self.config_path or str(self.config_path).strip() in ("", "."):
                logger.warning("Invalid config path, using default 'config.json'")
                self.config_path = Path("config.json")

            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Save configuration
            with open(self.config_path, "w", encoding="utf-8") as handle:
                json.dump(self._config, handle, indent=2)
            logger.debug(f"Configuration saved to {self.config_path}")
        except Exception as exc:
            logger.error(f"Failed to save configuration: {exc}", exc_info=True)

    def get(self, section: str, default: Optional[Any] = None) -> Any:
        return deepcopy(self._config.get(section, default))

    def set(self, section: str, values: Dict[str, Any]) -> None:
        if section not in self._config:
            self._config[section] = {}
        self._deep_merge(self._config[section], values)
        self.save()

    def reload_config(self) -> None:
        """Reload configuration from file."""
        self._load()

    @staticmethod
    def _deep_merge(base: Dict[str, Any], updates: Dict[str, Any]) -> None:
        for key, value in updates.items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                ConfigurationManager._deep_merge(base[key], value)
            else:
                base[key] = value
    
    def get_secret(self, secret_name: str, required: bool = False) -> Optional[str]:
        """Get a secret value from secrets manager.
        
        Args:
            secret_name: Name of the secret (e.g., 'telegram_api_id', 'gemini_api_key')
            required: If True, raises ValueError if secret not found
            
        Returns:
            Secret value or None if not found (and not required)
            
        Raises:
            ValueError: If secret is required but not found
        """
        if not SECRETS_AVAILABLE:
            logger.warning(f"Secrets manager not available, secret '{secret_name}' not retrieved")
            if required:
                raise ValueError(f"Secret '{secret_name}' is required but secrets manager not available")
            return None
            
        try:
            secrets_manager = get_secrets_manager()
            return secrets_manager.get_secret(secret_name, required=required)
        except Exception as exc:
            logger.error(f"Failed to retrieve secret '{secret_name}': {exc}")
            if required:
                raise
            return None
    
    def get_telegram_api_id(self) -> Optional[str]:
        """Get Telegram API ID from secrets manager."""
        return self.get_secret('telegram_api_id', required=True)
    
    def get_telegram_api_hash(self) -> Optional[str]:
        """Get Telegram API hash from secrets manager."""
        return self.get_secret('telegram_api_hash', required=True)
    
    def get_gemini_api_key(self) -> Optional[str]:
        """Get Gemini API key from secrets manager."""
        return self.get_secret('gemini_api_key', required=True)
    
    def get_sms_provider_api_key(self) -> Optional[str]:
        """Get SMS provider API key from secrets manager."""
        return self.get_secret('sms_provider_api_key', required=False)









