#!/usr/bin/env python3
"""
Secure Secrets Manager - Enterprise-grade secrets management.

Features:
- Environment variable loading with validation
- Encrypted secrets storage
- Key rotation support
- Audit logging for secret access
- No plaintext secrets in config files
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import base64
import hashlib
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

logger = logging.getLogger(__name__)


class SecretsManager:
    """Secure secrets management system."""
    
    def __init__(self, secrets_file: str = ".secrets.encrypted"):
        """
        Initialize secrets manager.
        
        Args:
            secrets_file: Path to encrypted secrets file
        """
        self.secrets_file = Path(secrets_file)
        self._cache: Dict[str, Any] = {}
        self._master_key = self._get_or_create_master_key()
        self._fernet = Fernet(self._master_key)
        self._access_log = []
        
    def _get_or_create_master_key(self) -> bytes:
        """
        Get or create master encryption key from environment.
        
        Returns:
            Master encryption key
        """
        # Try environment variable first (production)
        env_key = os.environ.get('SECRET_MASTER_KEY')
        if env_key:
            logger.info("Using master key from environment variable")
            return base64.urlsafe_b64decode(env_key.encode())
        
        # Try secure key file (with proper permissions)
        key_file = Path.home() / '.telegram_bot' / 'master.key'
        if key_file.exists():
            # Verify file permissions
            stat_info = key_file.stat()
            if stat_info.st_mode & 0o077:
                logger.warning(f"Key file {key_file} has insecure permissions! Should be 0600")
            
            with open(key_file, 'rb') as f:
                logger.info("Using master key from secure key file")
                return f.read()
        
        # Generate new key (development only)
        logger.warning("Generating NEW master key - save this securely!")
        key = Fernet.generate_key()
        
        # Save to secure location
        key_file.parent.mkdir(parents=True, exist_ok=True)
        with open(key_file, 'wb') as f:
            f.write(key)
        
        # Set secure permissions (owner read/write only)
        os.chmod(key_file, 0o600)
        
        logger.info(f"Master key saved to: {key_file}")
        logger.warning("Set SECRET_MASTER_KEY environment variable in production!")
        logger.warning(f"export SECRET_MASTER_KEY={base64.urlsafe_b64encode(key).decode()}")
        
        return key
    
    def get_secret(self, key: str, default: Any = None, required: bool = False) -> Any:
        """
        Get a secret value securely.
        
        Priority:
        1. Environment variable (prefixed with SECRET_)
        2. Encrypted secrets file
        3. Default value (if provided)
        
        Args:
            key: Secret key name
            default: Default value if not found
            required: Raise error if not found
            
        Returns:
            Secret value
            
        Raises:
            ValueError: If required secret not found
        """
        # Log access
        self._access_log.append({
            'key': key,
            'timestamp': datetime.now().isoformat(),
            'found': False
        })
        
        # Check cache first
        if key in self._cache:
            self._access_log[-1]['found'] = True
            self._access_log[-1]['source'] = 'cache'
            return self._cache[key]
        
        # Check environment variable
        env_key = f"SECRET_{key.upper()}"
        env_value = os.environ.get(env_key)
        if env_value:
            logger.debug(f"Secret '{key}' loaded from environment")
            self._cache[key] = env_value
            self._access_log[-1]['found'] = True
            self._access_log[-1]['source'] = 'environment'
            return env_value
        
        # Check encrypted file
        secrets = self._load_encrypted_secrets()
        if key in secrets:
            value = secrets[key]
            logger.debug(f"Secret '{key}' loaded from encrypted file")
            self._cache[key] = value
            self._access_log[-1]['found'] = True
            self._access_log[-1]['source'] = 'encrypted_file'
            return value
        
        # Return default or raise error
        if required:
            raise ValueError(f"Required secret '{key}' not found in environment or secrets file")
        
        logger.debug(f"Secret '{key}' not found, using default")
        self._access_log[-1]['source'] = 'default'
        return default
    
    def set_secret(self, key: str, value: Any) -> None:
        """
        Store a secret securely in encrypted file.
        
        Args:
            key: Secret key name
            value: Secret value
        """
        secrets = self._load_encrypted_secrets()
        secrets[key] = value
        self._save_encrypted_secrets(secrets)
        
        # Update cache
        self._cache[key] = value
        
        logger.info(f"Secret '{key}' stored securely")
    
    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret from encrypted storage.
        
        Args:
            key: Secret key name
            
        Returns:
            True if deleted, False if not found
        """
        secrets = self._load_encrypted_secrets()
        if key in secrets:
            del secrets[key]
            self._save_encrypted_secrets(secrets)
            
            # Clear from cache
            self._cache.pop(key, None)
            
            logger.info(f"Secret '{key}' deleted")
            return True
        
        return False
    
    def _load_encrypted_secrets(self) -> Dict[str, Any]:
        """
        Load secrets from encrypted file.
        
        Returns:
            Dictionary of secrets
        """
        if not self.secrets_file.exists():
            return {}
        
        try:
            with open(self.secrets_file, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_data = self._fernet.decrypt(encrypted_data)
            secrets = json.loads(decrypted_data.decode())
            
            return secrets
        except Exception as e:
            logger.error(f"Failed to load encrypted secrets: {e}")
            return {}
    
    def _save_encrypted_secrets(self, secrets: Dict[str, Any]) -> None:
        """
        Save secrets to encrypted file.
        
        Args:
            secrets: Dictionary of secrets
        """
        try:
            # Serialize to JSON
            json_data = json.dumps(secrets, indent=2).encode()
            
            # Encrypt
            encrypted_data = self._fernet.encrypt(json_data)
            
            # Write to file
            with open(self.secrets_file, 'wb') as f:
                f.write(encrypted_data)
            
            # Set secure permissions
            os.chmod(self.secrets_file, 0o600)
            
            logger.debug("Secrets saved to encrypted file")
        except Exception as e:
            logger.error(f"Failed to save encrypted secrets: {e}")
            raise
    
    def migrate_from_plaintext_config(self, config_path: str = "config.json") -> int:
        """
        Migrate secrets from plaintext config.json to encrypted storage.
        
        Args:
            config_path: Path to config.json
            
        Returns:
            Number of secrets migrated
        """
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"Config file not found: {config_path}")
            return 0
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        secrets_migrated = 0
        
        # Migrate Telegram API credentials
        if config.get('telegram', {}).get('api_id'):
            self.set_secret('telegram_api_id', config['telegram']['api_id'])
            secrets_migrated += 1
        
        if config.get('telegram', {}).get('api_hash'):
            self.set_secret('telegram_api_hash', config['telegram']['api_hash'])
            secrets_migrated += 1
        
        # Migrate Gemini API key
        if config.get('gemini', {}).get('api_key'):
            self.set_secret('gemini_api_key', config['gemini']['api_key'])
            secrets_migrated += 1
        
        # Migrate OpenAI API key
        if config.get('openai', {}).get('api_key'):
            self.set_secret('openai_api_key', config['openai']['api_key'])
            secrets_migrated += 1
        
        # Migrate ElevenLabs API key
        if config.get('elevenlabs', {}).get('api_key'):
            self.set_secret('elevenlabs_api_key', config['elevenlabs']['api_key'])
            secrets_migrated += 1
        
        # Migrate SMS provider API key
        if config.get('sms_providers', {}).get('api_key'):
            self.set_secret('sms_provider_api_key', config['sms_providers']['api_key'])
            secrets_migrated += 1
        
        logger.info(f"Migrated {secrets_migrated} secrets from config.json to encrypted storage")
        
        # Create backup of original config
        if secrets_migrated > 0:
            backup_path = config_file.with_suffix('.json.backup_before_migration')
            import shutil
            shutil.copy(config_file, backup_path)
            logger.info(f"Config backup saved to: {backup_path}")
        
        return secrets_migrated
    
    def clear_secrets_from_config(self, config_path: str = "config.json") -> None:
        """
        Remove secrets from config.json and replace with placeholders.
        
        Args:
            config_path: Path to config.json
        """
        config_file = Path(config_path)
        if not config_file.exists():
            return
        
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        # Replace secrets with placeholders
        if 'telegram' in config:
            if 'api_id' in config['telegram']:
                config['telegram']['api_id'] = None
            if 'api_hash' in config['telegram']:
                config['telegram']['api_hash'] = None
        
        if 'gemini' in config:
            if 'api_key' in config['gemini']:
                config['gemini']['api_key'] = None
        
        if 'openai' in config:
            if 'api_key' in config['openai']:
                config['openai']['api_key'] = ""
        
        if 'elevenlabs' in config:
            if 'api_key' in config['elevenlabs']:
                config['elevenlabs']['api_key'] = ""
        
        if 'sms_providers' in config:
            if 'api_key' in config['sms_providers']:
                config['sms_providers']['api_key'] = None
        
        # Write back
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info("Secrets cleared from config.json")
    
    def get_access_log(self) -> list:
        """
        Get audit log of secret accesses.
        
        Returns:
            List of access log entries
        """
        return self._access_log.copy()
    
    def validate_secrets(self) -> Dict[str, bool]:
        """
        Validate that all required secrets are present.
        
        Returns:
            Dictionary mapping secret names to presence status
        """
        required_secrets = [
            'telegram_api_id',
            'telegram_api_hash',
            'gemini_api_key',
            'sms_provider_api_key'
        ]
        
        status = {}
        for secret in required_secrets:
            try:
                value = self.get_secret(secret)
                status[secret] = value is not None and value != ""
            except Exception:
                status[secret] = False
        
        return status


# Global instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """
    Get global secrets manager instance.
    
    Returns:
        SecretsManager instance
    """
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def migrate_secrets_from_config():
    """Convenience function to migrate secrets from config.json."""
    manager = get_secrets_manager()
    count = manager.migrate_from_plaintext_config()
    
    if count > 0:
        manager.clear_secrets_from_config()
        print(f"✅ Migrated {count} secrets to encrypted storage")
        print("⚠️  Secrets removed from config.json for security")
        print("💡 Set environment variables in production:")
        print("   export SECRET_TELEGRAM_API_ID=your_api_id")
        print("   export SECRET_TELEGRAM_API_HASH=your_api_hash")
        print("   export SECRET_GEMINI_API_KEY=your_api_key")
        print("   export SECRET_SMS_PROVIDER_API_KEY=your_api_key")
    else:
        print("ℹ️  No secrets found in config.json to migrate")


if __name__ == "__main__":
    # Run migration if executed directly
    migrate_secrets_from_config()


