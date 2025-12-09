#!/usr/bin/env python3
"""Environment-specific configuration management."""

import os
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class EnvironmentManager:
    """Manages environment-specific settings."""
    
    ENVIRONMENTS = ['development', 'staging', 'production']
    
    def __init__(self):
        self.env = self._detect_environment()
        logger.info(f"Running in {self.env} environment")
    
    def _detect_environment(self) -> str:
        """Detect current environment."""
        env = os.getenv('APP_ENV', 'development').lower()
        
        if env not in self.ENVIRONMENTS:
            logger.warning(f"Unknown environment '{env}', defaulting to development")
            return 'development'
        
        return env
    
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == 'production'
    
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.env == 'development'
    
    def get_config_value(self, key: str, default: Any = None) -> Any:
        """Get environment-specific config value."""
        env_key = f"{self.env.upper()}_{key}"
        return os.getenv(env_key, os.getenv(key, default))
    
    def get_db_path(self) -> str:
        """Get environment-specific database path."""
        if self.is_production():
            return '/var/lib/telegram-bot/database.db'
        elif self.env == 'staging':
            return './data/staging/database.db'
        else:
            return './database.db'


_env_manager = None

def get_env_manager():
    global _env_manager
    if _env_manager is None:
        _env_manager = EnvironmentManager()
    return _env_manager





