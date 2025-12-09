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
            "phone_number": "",
            "profile": {
                "username": "",
                "first_name": "",
                "last_name": "",
                "phone_number": "",
                "photo_path": "",
                "validated": False,
                "validated_at": ""
            },
            "validated": False,
            "validated_at": ""
        },
        "gemini": {
            "api_key": "",
            "validated": False,
            "validated_at": ""
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
        },
        "performance": {
            "low_power": False,
            "enable_sampling": False,
            "sampling_interval_seconds": 30,
            "stats_interval_ms": 30000,
            "dashboard_interval_ms": 5000,
            "background_services_enabled": True,
            "warmup_autostart": True,
            "campaign_autostart": True,
            "resource_limits": {
                "max_concurrent_operations": 10,
                "memory_limit_mb": 512,
                "cpu_limit_percent": 80,
                "resource_check_interval": 30
            },
            "accounts": {
                "max_concurrent_connections": 50,
                "max_per_shard": 10,
                "health_check_interval": 30,
                "batch_update_interval": 5.0
            },
            "scraping": {
                "max_workers": 5,
                "queue_poll_interval": 0.1
            },
            "ai": {
                "max_tokens": 1024,
                "max_history": 50
            }
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

                # SECURITY: Migrate any credentials found in config to secrets manager
                self._migrate_credentials_to_secrets(data)

                self._deep_merge(self._config, data)
            except Exception as exc:
                logger.error(f"Failed to load configuration: {exc}")

    def _migrate_credentials_to_secrets(self, data: Dict[str, Any]) -> None:
        """Migrate any credentials found in config to secrets manager and remove them."""
        if not SECRETS_AVAILABLE:
            logger.warning("Secrets manager not available, credentials remain in config (INSECURE)")
            return

        try:
            secrets_manager = get_secrets_manager()
            migrated = False

            # Migrate Telegram credentials
            if "telegram" in data:
                telegram_cfg = data["telegram"]
                if telegram_cfg.get("api_id"):
                    secrets_manager.set_secret('telegram_api_id', telegram_cfg["api_id"])
                    del telegram_cfg["api_id"]
                    migrated = True
                if telegram_cfg.get("api_hash"):
                    secrets_manager.set_secret('telegram_api_hash', telegram_cfg["api_hash"])
                    del telegram_cfg["api_hash"]
                    migrated = True

            # Migrate Gemini API key
            if "gemini" in data and data["gemini"].get("api_key"):
                secrets_manager.set_secret('gemini_api_key', data["gemini"]["api_key"])
                del data["gemini"]["api_key"]
                migrated = True

            # Migrate SMS provider API key
            if "sms_providers" in data and data["sms_providers"].get("api_key"):
                secrets_manager.set_secret('sms_provider_api_key', data["sms_providers"]["api_key"])
                del data["sms_providers"]["api_key"]
                migrated = True

            if migrated:
                logger.info("Migrated credentials from config.json to secure secrets manager")
                # Save the cleaned config back to disk
                try:
                    with open(self.config_path, "w", encoding="utf-8") as handle:
                        json.dump(data, handle, indent=2)
                    logger.info("Cleaned config.json saved (credentials removed)")
                except Exception as save_exc:
                    logger.error(f"Failed to save cleaned config: {save_exc}")

        except Exception as exc:
            logger.error(f"Failed to migrate credentials to secrets manager: {exc}")
            logger.warning("Credentials may remain in config.json (INSECURE)")

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
        return self.get_secret('gemini_api_key', required=False)
    
    def get_sms_provider_api_key(self) -> Optional[str]:
        """Get SMS provider API key from secrets manager."""
        return self.get_secret('sms_provider_api_key', required=False)









