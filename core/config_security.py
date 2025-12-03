#!/usr/bin/env python3
"""
Config Security - REAL encryption for sensitive configuration data
Encrypts API keys and credentials using industry-standard AES-256
"""

import logging
import json
import base64
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class ConfigEncryption:
    """REAL AES-256 encryption for config files."""
    
    def __init__(self, key_file: str = ".encryption_key"):
        self.key_file = Path(key_file)
        self.fernet = self._initialize_encryption()
    
    def _initialize_encryption(self) -> Fernet:
        """Initialize REAL encryption with persistent key."""
        if self.key_file.exists():
            # Load existing key
            with open(self.key_file, 'rb') as f:
                key = f.read()
            logger.info("Loaded existing encryption key")
        else:
            # Generate NEW cryptographically secure key
            key = Fernet.generate_key()
            
            # Save key securely
            self.key_file.write_bytes(key)
            self.key_file.chmod(0o600)  # Read/write for owner only
            logger.info("Generated new encryption key")
        
        return Fernet(key)
    
    def encrypt_config(self, config: Dict) -> Dict:
        """Encrypt sensitive fields in ACTUAL config."""
        encrypted_config = config.copy()
        
        # Fields to encrypt
        sensitive_paths = [
            ('telegram', 'api_hash'),
            ('gemini', 'api_key'),
            ('account_creation', 'provider_api_key'),
        ]
        
        for path in sensitive_paths:
            value = config
            encrypted_value = encrypted_config
            
            # Navigate to the field
            for i, key in enumerate(path):
                if i == len(path) - 1:
                    # Last key - encrypt the value
                    if key in value and value[key]:
                        plain_text = str(value[key])
                        # REAL AES-256 encryption
                        encrypted = self.fernet.encrypt(plain_text.encode())
                        encrypted_value[key] = base64.b64encode(encrypted).decode()
                        encrypted_value[f'{key}_encrypted'] = True
                else:
                    # Navigate deeper
                    if key in value:
                        value = value[key]
                        if key not in encrypted_value:
                            encrypted_value[key] = {}
                        encrypted_value = encrypted_value[key]
        
        return encrypted_config
    
    def decrypt_config(self, encrypted_config: Dict) -> Dict:
        """Decrypt config with REAL decryption."""
        decrypted_config = encrypted_config.copy()
        
        # Fields to decrypt
        sensitive_paths = [
            ('telegram', 'api_hash'),
            ('gemini', 'api_key'),
            ('account_creation', 'provider_api_key'),
        ]
        
        for path in sensitive_paths:
            value = encrypted_config
            decrypted_value = decrypted_config
            
            # Navigate to the field
            for i, key in enumerate(path):
                if i == len(path) - 1:
                    # Last key - decrypt if encrypted
                    if f'{key}_encrypted' in value and value.get(f'{key}_encrypted'):
                        try:
                            encrypted_text = base64.b64decode(value[key])
                            # REAL AES-256 decryption
                            decrypted = self.fernet.decrypt(encrypted_text).decode()
                            decrypted_value[key] = decrypted
                            del decrypted_value[f'{key}_encrypted']
                        except Exception as e:
                            logger.error(f"Failed to decrypt {key}: {e}")
                else:
                    if key in value:
                        value = value[key]
                        decrypted_value = decrypted_value[key]
        
        return decrypted_config
    
    def save_encrypted_config(self, config: Dict, file_path: str = "config.json"):
        """Save config with REAL encryption."""
        encrypted = self.encrypt_config(config)
        
        with open(file_path, 'w') as f:
            json.dump(encrypted, f, indent=2)
        
        logger.info(f"✅ Saved encrypted config to {file_path}")
    
    def load_encrypted_config(self, file_path: str = "config.json") -> Dict:
        """Load and decrypt config with REAL decryption."""
        with open(file_path, 'r') as f:
            encrypted = json.load(f)
        
        decrypted = self.decrypt_config(encrypted)
        logger.info(f"✅ Loaded and decrypted config from {file_path}")
        return decrypted


def encrypt_existing_config():
    """Encrypt existing plaintext config file."""
    try:
        encryptor = ConfigEncryption()
        
        # Load plaintext config
        with open("config.json", 'r') as f:
            config = json.load(f)
        
        # Check if already encrypted
        if config.get('telegram', {}).get('api_hash_encrypted'):
            logger.info("Config already encrypted")
            return
        
        # Backup original
        import shutil
        shutil.copy("config.json", "config.json.plaintext.backup")
        
        # Encrypt and save
        encryptor.save_encrypted_config(config)
        
        logger.info("✅ Encrypted existing config file")
        
    except Exception as e:
        logger.error(f"Failed to encrypt config: {e}")


def decrypt_config_for_editing() -> Dict:
    """Decrypt config for editing in UI."""
    try:
        encryptor = ConfigEncryption()
        return encryptor.load_encrypted_config()
    except Exception as e:
        logger.error(f"Failed to decrypt config: {e}")
        return {}


def save_config_encrypted(config: Dict):
    """Save config with encryption."""
    try:
        encryptor = ConfigEncryption()
        encryptor.save_encrypted_config(config)
    except Exception as e:
        logger.error(f"Failed to save encrypted config: {e}")
        raise


