import asyncio
import logging
import json
import os
import base64
import hashlib
import secrets
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import aiohttp
import google.generativeai as genai
from monitoring.performance_monitor import get_resilience_manager

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Comprehensive API key management system for all services."""

    def __init__(self):
        self.api_keys: Dict[str, Dict[str, Any]] = {}
        self.key_validation_cache: Dict[str, Dict[str, Any]] = {}
        self.keys_file = Path("api_keys.json")

        # Migrate encryption key from insecure location if needed
        self._migrate_encryption_key()

        self.encryption_key = self._get_or_create_encryption_key()

        # Resilience management
        self.resilience_manager = get_resilience_manager()
        self._setup_resilience_strategies()

        # Load existing keys
        self.load_api_keys()

        # Service configurations
        self.service_configs = {
            'gemini': {
                'validation_url': 'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent',
                'test_prompt': 'Say "Hello" in exactly 5 words.',
                'headers': {'Content-Type': 'application/json'},
                'rate_limit': 60,  # requests per minute
            },
            'openai': {
                'validation_url': 'https://api.openai.com/v1/chat/completions',
                'test_prompt': 'Say "Hello" in exactly 5 words.',
                'headers': {'Content-Type': 'application/json'},
                'rate_limit': 60,
            },
            'anthropic': {
                'validation_url': 'https://api.anthropic.com/v1/messages',
                'test_prompt': 'Say "Hello" in exactly 5 words.',
                'headers': {'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
                'rate_limit': 50,
            },
            'sms_pool': {
                'validation_url': 'https://api.smspool.net/purchase/sms',
                'test_endpoint': True,
                'rate_limit': 30,
            },
            'textverified': {
                'validation_url': 'https://www.textverified.com/api/requests',
                'test_endpoint': True,
                'rate_limit': 30,
            },
            'sms_activate': {
                'validation_url': 'https://api.sms-activate.org/stubs/handler_api.php',
                'test_endpoint': True,
                'rate_limit': 30,
            },
            'sms_hub': {
                'validation_url': 'https://smshub.org/api.php',
                'test_endpoint': True,
                'rate_limit': 30,
            },
            'five_sim': {
                'validation_url': 'https://5sim.net/v1/user/profile',
                'test_endpoint': True,
                'rate_limit': 30,
            },
            'daisysms': {
                'validation_url': 'https://api.daisysms.com/v1/balance',
                'test_endpoint': True,
                'rate_limit': 30,
            }
        }

    def _migrate_encryption_key(self):
        """Migrate encryption key from insecure location to secure storage."""
        old_key_file = Path("encryption_key.bin")

        if not old_key_file.exists():
            return  # No old key to migrate

        try:
            # Read old key
            with open(old_key_file, 'rb') as f:
                old_key = f.read()

            if len(old_key) != 32:
                logger.warning("Old encryption key has invalid length, skipping migration")
                return

            # Try to store in secure location
            try:
                import keyring
                keyring_service_name = "telegram_bot_api_keys"
                keyring.set_password(keyring_service_name, "encryption_key", base64.urlsafe_b64encode(old_key).decode())
                logger.info("Successfully migrated encryption key to OS keyring")

                # Remove old insecure file
                old_key_file.unlink()
                logger.info("Removed old insecure encryption key file")

            except (ImportError, Exception) as e:
                logger.warning(f"Failed to migrate to keyring: {e}, trying secure directory")

                # Try secure directory migration
                try:
                    import platformdirs
                    config_dir = Path(platformdirs.user_config_dir("telegram_bot", "telegram_bot"))
                    config_dir.mkdir(parents=True, exist_ok=True)

                    new_key_file = config_dir / "encryption_key.bin"
                    with open(new_key_file, 'wb') as f:
                        f.write(old_key)

                    # Set restrictive permissions
                    try:
                        import stat
                        new_key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
                    except Exception:
                        pass  # Ignore permission setting failures on some systems

                    logger.info(f"Successfully migrated encryption key to secure directory: {config_dir}")

                    # Remove old insecure file
                    old_key_file.unlink()
                    logger.info("Removed old insecure encryption key file")

                except Exception as e2:
                    logger.error(f"Failed to migrate encryption key to secure storage: {e2}")
                    logger.warning("Encryption key remains in insecure location - manual migration recommended")

        except Exception as e:
            logger.error(f"Error during encryption key migration: {e}")

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for API keys using secure storage."""
        # Try to use OS keyring first (most secure)
        try:
            import keyring
            keyring_service_name = "telegram_bot_api_keys"

            # Try to get existing key from keyring
            stored_key = keyring.get_password(keyring_service_name, "encryption_key")
            if stored_key:
                return base64.urlsafe_b64decode(stored_key)

            # Generate new key and store in keyring
            key = secrets.token_bytes(32)
            keyring.set_password(keyring_service_name, "encryption_key", base64.urlsafe_b64encode(key).decode())
            logger.info("Generated new encryption key and stored in OS keyring")
            return key

        except ImportError:
            logger.warning("keyring library not available, falling back to secure directory storage")
        except Exception as e:
            logger.warning(f"Failed to use OS keyring: {e}, falling back to secure directory storage")

        # Fallback: Use secure directory with restricted permissions
        try:
            # Use user home directory with .config or similar
            import platformdirs
            config_dir = Path(platformdirs.user_config_dir("telegram_bot", "telegram_bot"))
            config_dir.mkdir(parents=True, exist_ok=True)

            # Try to set restrictive permissions on the directory
            try:
                import os
                import stat
                config_dir.chmod(stat.S_IRWXU)  # Owner read/write/execute only
            except Exception:
                pass  # Ignore permission setting failures on some systems

            key_file = config_dir / "encryption_key.bin"

            if key_file.exists():
                with open(key_file, 'rb') as f:
                    key_data = f.read()
                    # Validate key length
                    if len(key_data) == 32:
                        return key_data
                    else:
                        logger.warning("Invalid encryption key length, regenerating")

            # Generate new key
            key = secrets.token_bytes(32)
            with open(key_file, 'wb') as f:
                f.write(key)

            # Try to set restrictive permissions on the key file
            try:
                key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # Owner read/write only
            except Exception:
                pass  # Ignore permission setting failures on some systems

            logger.info(f"Generated new encryption key and stored in secure config directory: {config_dir}")
            return key

        except Exception as e:
            logger.error(f"Failed to create secure key storage: {e}")
            # Last resort fallback (less secure but functional)
            logger.warning("Using application directory for key storage - NOT RECOMMENDED for production")
            key_file = Path("encryption_key.bin.secure")

            if key_file.exists():
                with open(key_file, 'rb') as f:
                    return f.read()
            else:
                key = secrets.token_bytes(32)
                with open(key_file, 'wb') as f:
                    f.write(key)
                logger.warning(f"Stored encryption key in application directory: {key_file}")
                return key

    def _setup_resilience_strategies(self):
        """Set up circuit breakers and fallback strategies for API key operations."""
        # Circuit breaker for API key operations
        self.api_key_circuit_breaker = self.resilience_manager.get_circuit_breaker(
            "api_key_operations",
            failure_threshold=3,
            recovery_timeout=30,
            success_threshold=1
        )

        # Fallback strategies for encryption/decryption
        encrypt_fallback = self.resilience_manager.get_fallback_strategy("api_key_encryption")

        # Primary: Standard encryption
        def primary_encrypt(key):
            return self._encrypt_key(key)

        # Fallback 1: Simple base64 encoding (less secure but functional)
        def fallback_base64_encrypt(key):
            return base64.b64encode(key.encode()).decode()

        encrypt_fallback.add_fallback(primary_encrypt, "Fernet encryption")
        encrypt_fallback.add_fallback(fallback_base64_encrypt, "Base64 encoding fallback")

        # Fallback strategies for decryption
        decrypt_fallback = self.resilience_manager.get_fallback_strategy("api_key_decryption")

        def primary_decrypt(encrypted_key):
            return self._decrypt_key(encrypted_key)

        def fallback_base64_decrypt(encrypted_key):
            try:
                return base64.b64decode(encrypted_key).decode()
            except Exception:
                # If it's not base64, try standard decryption
                return self._decrypt_key(encrypted_key)

        decrypt_fallback.add_fallback(primary_decrypt, "Fernet decryption")
        decrypt_fallback.add_fallback(fallback_base64_decrypt, "Base64 decoding fallback")

    def _encrypt_key(self, key: str) -> str:
        """Encrypt an API key."""
        from cryptography.fernet import Fernet
        fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key))
        return fernet.encrypt(key.encode()).decode()

    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt an API key."""
        from cryptography.fernet import Fernet
        fernet = Fernet(base64.urlsafe_b64encode(self.encryption_key))
        return fernet.decrypt(encrypted_key.encode()).decode()

    def _normalize_service_name(self, service: str) -> str:
        """Normalize service name to internal key format."""
        service = service.lower().replace('-', '_').replace(' ', '_')
        if service == '5sim':
            return 'five_sim'
        return service

    def _validate_api_key(self, service: str, key: str) -> bool:
        """Validate API key format for specific service."""
        try:
            from user_helpers import ValidationHelper

            service = self._normalize_service_name(service)

            if service in ['gemini', 'google_ai', 'palm']:
                return ValidationHelper.validate_gemini_api_key(key)[0]
            elif service in ['elevenlabs', 'voice']:
                # ElevenLabs API keys are typically 32-character strings
                return len(key.strip()) >= 20 and key.strip().replace('-', '').replace('_', '').isalnum()
            elif service in ['openai', 'gpt']:
                # OpenAI API keys start with 'sk-'
                return key.strip().startswith('sk-') and len(key.strip()) > 20
            elif service in ['sms_activate', '5sim', 'five_sim', 'sms_hub']:
                # SMS service API keys are usually alphanumeric
                return len(key.strip()) >= 10 and key.strip().replace('-', '').replace('_', '').isalnum()
            else:
                # Generic validation for unknown services
                return len(key.strip()) >= 8

        except ImportError:
            # Fallback validation if ValidationHelper not available
            logger.warning("ValidationHelper not available, using basic validation")
            return len(key.strip()) >= 8
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return False

    def add_api_key(self, service: str, key: str, metadata: Dict[str, Any] = None) -> bool:
        """Add a new API key with resilience features."""
        try:
            # Check circuit breaker
            if not self.api_key_circuit_breaker.can_execute():
                logger.warning(f"API key operations circuit breaker is OPEN, rejecting request")
                return False

            # Validate inputs
            if not service or not isinstance(service, str):
                logger.error("Service name is required and must be a string")
                self.api_key_circuit_breaker.record_failure(ValueError("Invalid service name"))
                return False

            if not key or not isinstance(key, str):
                logger.error("API key is required and must be a string")
                self.api_key_circuit_breaker.record_failure(ValueError("Invalid API key"))
                return False

            # Validate API key format based on service
            if not self._validate_api_key(service, key):
                logger.error(f"Invalid API key format for service: {service}")
                self.api_key_circuit_breaker.record_failure(ValueError("Invalid API key format"))
                return False

            service = self._normalize_service_name(service)

            if metadata is None:
                metadata = {}

            # Use fallback strategy for encryption
            encrypt_fallback = self.resilience_manager.get_fallback_strategy("api_key_encryption")

            try:
                encrypted_key = encrypt_fallback.fallbacks[0]['func'](key)  # Try primary first
            except Exception as e:
                logger.warning(f"Primary encryption failed, trying fallback: {e}")
                try:
                    encrypted_key = encrypt_fallback.fallbacks[1]['func'](key)  # Try fallback
                except Exception as e2:
                    logger.error(f"All encryption strategies failed: {e2}")
                    self.api_key_circuit_breaker.record_failure(e2)
                    return False

            self.api_keys[service] = {
                'key': encrypted_key,
                'added_at': datetime.now().isoformat(),
                'last_validated': None,
                'is_valid': False,
                'validation_attempts': 0,
                'last_used': None,
                'usage_count': 0,
                'metadata': metadata
            }

            self.save_api_keys()
            logger.info(f"✅ Added API key for service: {service}")

            # Record success
            self.api_key_circuit_breaker.record_success()

            # Validate the key immediately (schedule for async execution)
            # Note: This is called from sync context, so we need to handle it properly
            try:
                loop = asyncio.get_running_loop()
                asyncio.create_task(self.validate_api_key(service))
            except RuntimeError:
                # No running loop, validation will happen on next access
                logger.debug(f"Scheduled validation for {service} (no running event loop)")

            return True

        except Exception as e:
            logger.error(f"Failed to add API key for {service}: {e}")
            self.api_key_circuit_breaker.record_failure(e)
            return False

    def get_api_key(self, service: str) -> Optional[str]:
        """Get a decrypted API key with resilience features."""
        service = self._normalize_service_name(service)
        if service not in self.api_keys:
            return None

        # Check circuit breaker
        if not self.api_key_circuit_breaker.can_execute():
            logger.warning(f"API key operations circuit breaker is OPEN, rejecting get request for {service}")
            return None

        try:
            encrypted_key = self.api_keys[service]['key']

            # Use fallback strategy for decryption
            decrypt_fallback = self.resilience_manager.get_fallback_strategy("api_key_decryption")

            try:
                decrypted_key = decrypt_fallback.fallbacks[0]['func'](encrypted_key)  # Try primary first
            except Exception as e:
                logger.warning(f"Primary decryption failed for {service}, trying fallback: {e}")
                try:
                    decrypted_key = decrypt_fallback.fallbacks[1]['func'](encrypted_key)  # Try fallback
                except Exception as e2:
                    logger.error(f"All decryption strategies failed for {service}: {e2}")
                    self.api_key_circuit_breaker.record_failure(e2)
                    return None

            # Update usage statistics
            self.api_keys[service]['last_used'] = datetime.now().isoformat()
            self.api_keys[service]['usage_count'] += 1
            self.save_api_keys()

            # Record success
            self.api_key_circuit_breaker.record_success()

            return decrypted_key

        except Exception as e:
            logger.error(f"Failed to get API key for {service}: {e}")
            self.api_key_circuit_breaker.record_failure(e)
            return None

    def remove_api_key(self, service: str) -> bool:
        """Remove an API key."""
        service = self._normalize_service_name(service)
        if service in self.api_keys:
            del self.api_keys[service]
            self.save_api_keys()
            logger.info(f"🗑️ Removed API key for service: {service}")
            return True
        return False

    async def validate_api_key(self, service: str, force: bool = False) -> Tuple[bool, str]:
        """Validate an API key by testing it against the service."""
        service = self._normalize_service_name(service)
        if service not in self.api_keys:
            return False, "API key not found"

        key_data = self.api_keys[service]

        # Check cache unless force validation
        if not force and service in self.key_validation_cache:
            cache_data = self.key_validation_cache[service]
            cache_age = datetime.now() - datetime.fromisoformat(cache_data['validated_at'])

            # Use cache if less than 1 hour old
            if cache_age < timedelta(hours=1):
                return cache_data['is_valid'], cache_data.get('error', '')

        # Perform validation
        key_data['validation_attempts'] += 1
        decrypted_key = self.get_api_key(service)

        if not decrypted_key:
            error_msg = "Failed to decrypt API key"
            self._update_validation_result(service, False, error_msg)
            return False, error_msg

        try:
            is_valid, error_msg = await self._test_api_key(service, decrypted_key)

            self._update_validation_result(service, is_valid, error_msg)
            return is_valid, error_msg

        except Exception as e:
            error_msg = f"Validation error: {str(e)}"
            self._update_validation_result(service, False, error_msg)
            return False, error_msg

    def _update_validation_result(self, service: str, is_valid: bool, error_msg: str = ""):
        """Update validation result in storage and cache."""
        self.api_keys[service]['last_validated'] = datetime.now().isoformat()
        self.api_keys[service]['is_valid'] = is_valid

        if not is_valid:
            self.api_keys[service]['last_error'] = error_msg

        # Update cache
        self.key_validation_cache[service] = {
            'is_valid': is_valid,
            'error': error_msg,
            'validated_at': datetime.now().isoformat()
        }

        self.save_api_keys()

    async def _test_api_key(self, service: str, api_key: str) -> Tuple[bool, str]:
        """Test an API key against its service."""
        if service not in self.service_configs:
            return False, f"Unknown service: {service}"

        config = self.service_configs[service]

        try:
            if service == 'gemini':
                return await self._test_gemini_key(api_key, config)
            elif service == 'openai':
                return await self._test_openai_key(api_key, config)
            elif service == 'anthropic':
                return await self._test_anthropic_key(api_key, config)
            elif service in ['sms_pool', 'textverified', 'sms_activate', 'sms_hub', 'five_sim', 'daisysms']:
                return await self._test_sms_provider_key(service, api_key, config)
            else:
                return False, f"No validation method for service: {service}"

        except Exception as e:
            return False, f"Test failed: {str(e)}"

    async def _test_gemini_key(self, api_key: str, config: Dict) -> Tuple[bool, str]:
        """Test Gemini API key."""
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')

            response = await model.generate_content_async(config['test_prompt'])
            if response and response.text:
                return True, ""
            else:
                return False, "No response from Gemini API"

        except Exception as e:
            return False, f"Gemini API error: {str(e)}"

    async def _test_openai_key(self, api_key: str, config: Dict) -> Tuple[bool, str]:
        """Test OpenAI API key."""
        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {**config['headers'], 'Authorization': f'Bearer {api_key}'}
                data = {
                    'model': 'gpt-3.5-turbo',
                    'messages': [{'role': 'user', 'content': config['test_prompt']}],
                    'max_tokens': 10
                }

                async with session.post(config['validation_url'], headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if 'choices' in result and len(result['choices']) > 0:
                            return True, ""
                        else:
                            return False, "Invalid response format"
                    else:
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status}')
                        except Exception:
                            error_msg = f'HTTP {response.status}'
                        return False, error_msg

        except asyncio.TimeoutError:
            return False, "Request timed out after 30 seconds"
        except aiohttp.ClientError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"OpenAI API test failed: {str(e)}"

    async def _test_anthropic_key(self, api_key: str, config: Dict) -> Tuple[bool, str]:
        """Test Anthropic API key."""
        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    **config['headers'],
                    'x-api-key': api_key
                }
                data = {
                    'model': 'claude-3-haiku-20240307',
                    'max_tokens': 10,
                    'messages': [{'role': 'user', 'content': config['test_prompt']}]
                }

                async with session.post(config['validation_url'], headers=headers, json=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if 'content' in result and len(result['content']) > 0:
                            return True, ""
                        else:
                            return False, "Invalid response format"
                    else:
                        try:
                            error_data = await response.json()
                            error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status}')
                        except Exception:
                            error_msg = f'HTTP {response.status}'
                        return False, error_msg

        except asyncio.TimeoutError:
            return False, "Request timed out after 30 seconds"
        except aiohttp.ClientError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"Anthropic API test failed: {str(e)}"

    async def _test_sms_provider_key(self, service: str, api_key: str, config: Dict) -> Tuple[bool, str]:
        """Test SMS provider API key."""
        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            
            # For SMS providers, we do a basic balance/credit check
            if service == 'sms_pool':
                headers = {'Authorization': f'Bearer {api_key}'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://api.smspool.net/me', headers=headers) as response:
                        if response.status == 200:
                            return True, ""
                        else:
                            return False, f"Balance check failed (HTTP {response.status})"

            elif service == 'textverified':
                headers = {'Authorization': f'Bearer {api_key}'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://www.textverified.com/api/me', headers=headers) as response:
                        if response.status == 200:
                            return True, ""
                        else:
                            return False, f"Account check failed (HTTP {response.status})"

            elif service == 'sms_activate':
                params = {'api_key': api_key, 'action': 'getBalance'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://api.sms-activate.org/stubs/handler_api.php', params=params) as response:
                        response_text = await response.text()
                        if response_text.startswith('ACCESS_BALANCE'):
                            return True, ""
                        else:
                            return False, f"Balance check failed: {response_text[:100]}"
            
            elif service == 'sms_hub':
                params = {'api_key': api_key, 'action': 'getBalance'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://smshub.org/api.php', params=params) as response:
                        response_text = await response.text()
                        if response_text.startswith('ACCESS_BALANCE'):
                            return True, ""
                        else:
                            return False, f"Balance check failed: {response_text[:100]}"

            elif service == 'five_sim':
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Accept': 'application/json'
                }
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://5sim.net/v1/user/profile', headers=headers) as response:
                        if response.status == 200:
                            return True, ""
                        else:
                            return False, f"Profile check failed (HTTP {response.status})"

            elif service == 'daisysms':
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Accept': 'application/json'
                }
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://api.daisysms.com/v1/balance', headers=headers) as response:
                        if response.status == 200:
                            return True, ""
                        else:
                            return False, f"Balance check failed (HTTP {response.status})"

            return False, "Unknown SMS provider"

        except asyncio.TimeoutError:
            return False, "Request timed out after 30 seconds"
        except aiohttp.ClientError as e:
            return False, f"Connection error: {str(e)}"
        except Exception as e:
            return False, f"SMS provider test failed: {str(e)}"

    def get_api_key_status(self, service: str) -> Optional[Dict[str, Any]]:
        """Get status information for an API key."""
        service = self._normalize_service_name(service)
        if service not in self.api_keys:
            return None

        key_data = self.api_keys[service].copy()
        # Remove the encrypted key from the response
        key_data.pop('key', None)

        # Add validation cache info
        if service in self.key_validation_cache:
            key_data['cached_validation'] = self.key_validation_cache[service]

        return key_data

    def get_all_api_keys_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all API keys."""
        return {service: self.get_api_key_status(service) for service in self.api_keys.keys()}

    async def validate_all_keys(self) -> Dict[str, Tuple[bool, str]]:
        """Validate all stored API keys."""
        results = {}
        for service in self.api_keys.keys():
            results[service] = await self.validate_api_key(service, force=True)
        return results

    def save_api_keys(self):
        """Save API keys to encrypted file."""
        try:
            # Ensure parent directory exists
            self.keys_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first, then rename (atomic write)
            temp_file = self.keys_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.api_keys, f, indent=2, default=str)
            
            # Atomic rename
            temp_file.replace(self.keys_file)
            logger.debug(f"API keys saved to {self.keys_file}")
        except PermissionError as e:
            logger.error(f"Permission denied saving API keys: {e}")
        except OSError as e:
            logger.error(f"OS error saving API keys: {e}")
        except Exception as e:
            logger.error(f"Failed to save API keys: {e}", exc_info=True)

    def load_api_keys(self):
        """Load API keys from file."""
        if not self.keys_file.exists():
            logger.debug("API keys file does not exist, starting with empty keys")
            return

        try:
            with open(self.keys_file, 'r', encoding='utf-8') as f:
                loaded_keys = json.load(f)
                
            # Validate loaded data is a dictionary
            if not isinstance(loaded_keys, dict):
                logger.error(f"Invalid API keys file format: expected dict, got {type(loaded_keys)}")
                return
                
            self.api_keys = loaded_keys
            logger.info(f"Loaded {len(self.api_keys)} API keys from {self.keys_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse API keys file (invalid JSON): {e}")
            # Try to backup corrupted file
            try:
                backup_file = self.keys_file.with_suffix('.corrupted')
                self.keys_file.rename(backup_file)
                logger.warning(f"Corrupted API keys file backed up to {backup_file}")
            except Exception:
                pass
        except PermissionError as e:
            logger.error(f"Permission denied loading API keys: {e}")
        except Exception as e:
            logger.error(f"Failed to load API keys: {e}", exc_info=True)

    def get_service_rate_limit(self, service: str) -> int:
        """Get rate limit for a service."""
        return self.service_configs.get(self._normalize_service_name(service), {}).get('rate_limit', 60)

    def is_service_supported(self, service: str) -> bool:
        """Check if a service is supported."""
        return self._normalize_service_name(service) in self.service_configs

    def get_supported_services(self) -> List[str]:
        """Get list of supported services."""
        return list(self.service_configs.keys())

    async def get_service_balance(self, service: str) -> Optional[float]:
        """Get balance/credits for a service if available."""
        service = self._normalize_service_name(service)
        if service not in self.api_keys:
            return None

        api_key = self.get_api_key(service)
        if not api_key:
            return None

        try:
            timeout = aiohttp.ClientTimeout(total=30)  # 30 second timeout
            
            if service == 'sms_pool':
                headers = {'Authorization': f'Bearer {api_key}'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://api.smspool.net/me', headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            return float(data.get('balance', 0))
                        else:
                            logger.warning(f"Failed to get balance for {service}: HTTP {response.status}")

            elif service == 'textverified':
                headers = {'Authorization': f'Bearer {api_key}'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://www.textverified.com/api/me', headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            return float(data.get('balance', 0))
                        else:
                            logger.warning(f"Failed to get balance for {service}: HTTP {response.status}")

            elif service == 'sms_activate':
                params = {'api_key': api_key, 'action': 'getBalance'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://api.sms-activate.org/stubs/handler_api.php', params=params) as response:
                        response_text = await response.text()
                        if response_text.startswith('ACCESS_BALANCE:'):
                            balance_str = response_text.split(':')[1]
                            return float(balance_str)
                        else:
                            logger.warning(f"Failed to get balance for {service}: {response_text[:100]}")
            
            elif service == 'sms_hub':
                params = {'api_key': api_key, 'action': 'getBalance'}
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://smshub.org/api.php', params=params) as response:
                        response_text = await response.text()
                        if response_text.startswith('ACCESS_BALANCE:'):
                            balance_str = response_text.split(':')[1]
                            return float(balance_str)
                        else:
                            logger.warning(f"Failed to get balance for {service}: {response_text[:100]}")

            elif service == 'five_sim':
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Accept': 'application/json'
                }
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://5sim.net/v1/user/profile', headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            return float(data.get('balance', 0))
                        else:
                            logger.warning(f"Failed to get balance for {service}: HTTP {response.status}")

            elif service == 'daisysms':
                headers = {
                    'Authorization': f'Bearer {api_key}',
                    'Accept': 'application/json'
                }
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get('https://api.daisysms.com/v1/balance', headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            return float(data.get('balance', 0))
                        else:
                            logger.warning(f"Failed to get balance for {service}: HTTP {response.status}")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout getting balance for {service}")
        except aiohttp.ClientError as e:
            logger.warning(f"Connection error getting balance for {service}: {e}")
        except (ValueError, KeyError) as e:
            logger.warning(f"Failed to parse balance for {service}: {e}")
        except Exception as e:
            logger.warning(f"Failed to get balance for {service}: {e}", exc_info=True)

        return None
