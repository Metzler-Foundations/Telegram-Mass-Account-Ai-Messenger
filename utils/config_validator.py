#!/usr/bin/env python3
"""
Configuration Validator - Schema validation for config files.

Features:
- JSON schema validation
- Required field checking
- Type validation
- Range validation
- Custom validators
- Hot-reload support
"""

import json
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from datetime import datetime
import threading

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Configuration validation error."""
    pass


class ConfigValidator:
    """Validates configuration against schema."""
    
    # Configuration schema
    SCHEMA = {
        'telegram': {
            'required': True,
            'type': 'object',
            'properties': {
                'api_id': {'type': ['integer', 'null'], 'required': False},
                'api_hash': {'type': ['string', 'null'], 'required': False},
                'phone_number': {'type': ['string', 'null'], 'required': False}
            }
        },
        'gemini': {
            'required': True,
            'type': 'object',
            'properties': {
                'api_key': {'type': ['string', 'null'], 'required': False}
            }
        },
        'sms_providers': {
            'required': True,
            'type': 'object',
            'properties': {
                'provider': {'type': 'string', 'required': True, 'enum': [
                    'smspool', 'textverified', 'sms-activate', 'sms-hub', '5sim', 'daisysms'
                ]},
                'api_key': {'type': ['string', 'null'], 'required': False}
            }
        },
        'proxy_pool': {
            'required': False,
            'type': 'object',
            'properties': {
                'enabled': {'type': 'boolean', 'default': True},
                'min_score': {'type': 'integer', 'min': 0, 'max': 100, 'default': 30},
                'health_check_interval': {'type': 'integer', 'min': 10, 'max': 3600, 'default': 60}
            }
        },
        'anti_detection': {
            'required': False,
            'type': 'object',
            'properties': {
                'messages_per_hour': {'type': 'integer', 'min': 1, 'max': 200, 'default': 50},
                'burst_limit': {'type': 'integer', 'min': 1, 'max': 10, 'default': 3},
                'min_delay': {'type': 'number', 'min': 0.5, 'max': 10.0, 'default': 2.0},
                'max_delay': {'type': 'number', 'min': 5.0, 'max': 120.0, 'default': 30.0}
            }
        }
    }
    
    @staticmethod
    def validate(config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration against schema.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required sections
        for section, schema in ConfigValidator.SCHEMA.items():
            if schema.get('required', False) and section not in config:
                errors.append(f"Missing required section: {section}")
                continue
            
            if section in config:
                section_errors = ConfigValidator._validate_section(
                    config[section],
                    schema,
                    section
                )
                errors.extend(section_errors)
        
        return errors
    
    @staticmethod
    def _validate_section(
        value: Any,
        schema: Dict,
        path: str
    ) -> List[str]:
        """Validate a configuration section."""
        errors = []
        
        # Type validation
        expected_types = schema.get('type')
        if expected_types:
            if not isinstance(expected_types, list):
                expected_types = [expected_types]
            
            type_valid = False
            for expected_type in expected_types:
                if expected_type == 'object' and isinstance(value, dict):
                    type_valid = True
                elif expected_type == 'array' and isinstance(value, list):
                    type_valid = True
                elif expected_type == 'string' and isinstance(value, str):
                    type_valid = True
                elif expected_type == 'integer' and isinstance(value, int) and not isinstance(value, bool):
                    type_valid = True
                elif expected_type == 'number' and isinstance(value, (int, float)) and not isinstance(value, bool):
                    type_valid = True
                elif expected_type == 'boolean' and isinstance(value, bool):
                    type_valid = True
                elif expected_type == 'null' and value is None:
                    type_valid = True
            
            if not type_valid:
                errors.append(f"{path}: Invalid type (expected {expected_types}, got {type(value).__name__})")
                return errors
        
        # Object properties validation
        if isinstance(value, dict) and 'properties' in schema:
            for prop_name, prop_schema in schema['properties'].items():
                if prop_name in value:
                    prop_errors = ConfigValidator._validate_section(
                        value[prop_name],
                        prop_schema,
                        f"{path}.{prop_name}"
                    )
                    errors.extend(prop_errors)
                elif prop_schema.get('required', False):
                    errors.append(f"{path}.{prop_name}: Required field missing")
        
        # Range validation
        if isinstance(value, (int, float)):
            if 'min' in schema and value < schema['min']:
                errors.append(f"{path}: Value {value} below minimum {schema['min']}")
            if 'max' in schema and value > schema['max']:
                errors.append(f"{path}: Value {value} above maximum {schema['max']}")
        
        # Enum validation
        if 'enum' in schema and value not in schema['enum']:
            errors.append(f"{path}: Value '{value}' not in allowed values {schema['enum']}")
        
        return errors


class ConfigManager:
    """
    Manages configuration with validation and hot-reload support.
    
    Features:
    - Schema validation
    - Hot-reload capability
    - Change notifications
    - File watching
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize config manager.
        
        Args:
            config_path: Path to config file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.last_modified: Optional[datetime] = None
        self.change_callbacks: List[Callable] = []
        self.lock = threading.Lock()
        
        # Load initial config
        self.reload()
    
    def load(self) -> Dict[str, Any]:
        """
        Load and validate configuration.
        
        Returns:
            Configuration dictionary
            
        Raises:
            ValidationError: If validation fails
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            return {}
        
        try:
            # Load JSON safely
            from utils.json_safe import safe_json_load_file
            config = safe_json_load_file(
                str(self.config_path),
                default={},
                raise_on_error=True
            )
            
            # Validate schema
            errors = ConfigValidator.validate(config)
            
            if errors:
                error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
                logger.error(error_msg)
                raise ValidationError(error_msg)
            
            return config
            
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def reload(self) -> bool:
        """
        Reload configuration from file.
        
        Returns:
            True if config changed
        """
        try:
            # Check if file changed
            if self.config_path.exists():
                modified = datetime.fromtimestamp(self.config_path.stat().st_mtime)
                
                if self.last_modified and modified <= self.last_modified:
                    return False
                
                self.last_modified = modified
            
            # Load new config
            new_config = self.load()
            
            with self.lock:
                if new_config != self.config:
                    old_config = self.config
                    self.config = new_config
                    
                    logger.info("Configuration reloaded")
                    self._notify_changes(old_config, new_config)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Config reload failed: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value.
        
        Args:
            key: Dot-notation key (e.g., 'telegram.api_id')
            default: Default value if not found
            
        Returns:
            Configuration value
        """
        with self.lock:
            keys = key.split('.')
            value = self.config
            
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            
            return value
    
    def register_change_callback(self, callback: Callable):
        """
        Register callback for configuration changes.
        
        Args:
            callback: Function to call on config change
        """
        self.change_callbacks.append(callback)
        logger.debug(f"Registered config change callback: {callback.__name__}")
    
    def _notify_changes(self, old_config: Dict, new_config: Dict):
        """Notify callbacks of configuration changes."""
        for callback in self.change_callbacks:
            try:
                callback(old_config, new_config)
            except Exception as e:
                logger.error(f"Config change callback failed: {e}")
    
    def start_file_watcher(self, check_interval: float = 5.0):
        """
        Start watching config file for changes.
        
        Args:
            check_interval: Check interval in seconds
        """
        def watch_loop():
            import time
            while True:
                try:
                    self.reload()
                    time.sleep(check_interval)
                except Exception as e:
                    logger.error(f"File watcher error: {e}")
                    time.sleep(check_interval)
        
        watcher_thread = threading.Thread(target=watch_loop, daemon=True)
        watcher_thread.start()
        logger.info(f"Config file watcher started (interval: {check_interval}s)")


# Global instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """Get global config manager."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


