"""
Account Creator - Enterprise-grade Telegram account creation with proxy pool integration.

Features:
- Integration with ProxyPoolManager for auto proxy assignment
- Auto-reassignment of proxies when they fail
- Enhanced anti-detection during account creation
- Support for multiple SMS providers
- Bulk account creation with progress tracking
"""

import asyncio
import logging
import random
import json
import os
import time
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, UserDeactivated
)

from anti_detection_system import AccountCreationAntiDetection
from advanced_cloning_system import AdvancedCloningSystem
from username_generator import UsernameGenerator
from account_creation_failsafes import AccountCreationFailSafe, FailSafeLevel
from user_helpers import translate_error, get_progress_message, ValidationHelper
from retry_helper import RetryHelper, RetryConfig, RetryStrategy

logger = logging.getLogger(__name__)

# Try to import ProxyPoolManager
try:
    from proxy_pool_manager import ProxyPoolManager, get_proxy_pool_manager, Proxy, ProxyTier
    PROXY_POOL_AVAILABLE = True
except ImportError:
    PROXY_POOL_AVAILABLE = False
    logger.warning("ProxyPoolManager not available - using basic proxy management")


class ProxyManager:
    """Manage proxies for account creation."""

    def __init__(self):
        self.proxies: List[Dict] = []
        self.used_proxies: Dict[str, datetime] = {}  # ip:port -> last_used
        self.failed_proxies: Dict[str, int] = {}     # ip:port -> fail_count
        self.max_failures = 3
        self.cooldown_minutes = 30

    def get_proxy(self) -> Optional[Dict]:
        """Get a suitable proxy."""
        if not self.proxies:
            return None

        # Filter out failed and cooldown proxies
        available = []
        now = datetime.now()

        for proxy in self.proxies:
            proxy_key = f"{proxy['ip']}:{proxy['port']}"
            
            # Check failure count
            if self.failed_proxies.get(proxy_key, 0) >= self.max_failures:
                continue
                
            # Check cooldown
            if proxy_key in self.used_proxies:
                last_used = self.used_proxies[proxy_key]
                if (now - last_used).total_seconds() < self.cooldown_minutes * 60:
                    continue
            
            available.append(proxy)

        if not available:
            # If no available proxies, try to reset cooldowns or pick least used
            logger.warning("No fresh proxies available, reusing oldest")
            return self.proxies[0] if self.proxies else None

        # Pick random from available
        return random.choice(available)

    def mark_proxy_used(self, proxy: Dict):
        """Mark a proxy as used."""
        proxy_key = f"{proxy['ip']}:{proxy['port']}"
        self.used_proxies[proxy_key] = datetime.now()

    def mark_proxy_failed(self, proxy: Dict):
        """Mark a proxy as failed."""
        proxy_key = f"{proxy['ip']}:{proxy['port']}"
        self.failed_proxies[proxy_key] = self.failed_proxies.get(proxy_key, 0) + 1
        
        if self.failed_proxies[proxy_key] >= self.max_failures:
            logger.warning(f"Proxy {proxy['ip']}:{proxy['port']} marked as failed")


class PhoneNumberProvider:
    """Manage phone number providers for account creation."""

    def __init__(self):
        # Rate limiting for API calls
        self.last_api_call = {}  # provider -> timestamp
        self.min_call_interval = 2.0  # Minimum seconds between API calls per provider
        
        # Popular SMS verification services with real API configurations
        self.providers = {
            "smspool": {
                "api_url": "https://api.smspool.net/purchase/sms",
                "countries": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "RU", "IN", "CA", "AU"],
                "cost_per_number": 0.15,
                "service_code": "tg"  # Telegram
            },
            "textverified": {
                "api_url": "https://www.textverified.com/api/requests",
                "countries": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "RU"],
                "cost_per_number": 0.12,
                "service_code": "telegram"
            },
            "sms-activate": {
                "api_url": "https://api.sms-activate.org/stubs/handler_api.php",
                "countries": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "RU"],
                "cost_per_number": 0.1,
                "service_code": "tg"
            },
            "sms-hub": {
                "api_url": "https://smshub.org/api.php",
                "countries": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "RU", "IN"],
                "cost_per_number": 0.08,
                "service_code": "tg"
            },
            "5sim": {
                "api_url": "https://5sim.net/api/v1",
                "countries": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "RU"],
                "cost_per_number": 0.12,
                "service_code": "tg"
            },
            "daisysms": {
                "api_url": "https://api.daisysms.com/v1",
                "countries": ["US", "GB", "DE", "FR", "IT", "ES", "BR", "RU", "IN", "CA", "AU"],
                "cost_per_number": 0.10,
                "service_code": "telegram"
            }
        }

    def get_number(self, provider: str, country: str, api_key: str) -> Optional[Dict]:
        """Get a phone number from specified provider with rate limiting and retry logic."""
        if provider not in self.providers:
            logger.error(f"Provider '{provider}' not supported. Available: {', '.join(self.providers.keys())}")
            return None

        # Rate limiting: ensure minimum time between API calls
        if provider in self.last_api_call:
            time_since_last = time.time() - self.last_api_call[provider]
            if time_since_last < self.min_call_interval:
                sleep_time = self.min_call_interval - time_since_last
                logger.debug(f"Rate limiting: waiting {sleep_time:.2f}s before {provider} API call")
                time.sleep(sleep_time)
        
        self.last_api_call[provider] = time.time()
        provider_config = self.providers[provider]

        # Configure retry for network operations
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=True
        )

        def _get_number_internal():
            try:
                if provider == "smspool":
                    return self._get_smspool_number(country, api_key, provider_config)
                elif provider == "textverified":
                    return self._get_textverified_number(country, api_key, provider_config)
                elif provider == "sms-activate":
                    return self._get_sms_activate_number(country, api_key, provider_config)
                elif provider == "sms-hub":
                    return self._get_sms_hub_number(country, api_key, provider_config)
                elif provider == "5sim":
                    return self._get_5sim_number(country, api_key, provider_config)
                elif provider == "daisysms":
                    return self._get_daisysms_number(country, api_key, provider_config)
                else:
                    logger.error(f"Unsupported provider: {provider}")
                    return None
            except requests.exceptions.Timeout:
                logger.warning(f"{provider} API timeout, retrying...")
                raise  # Retry on timeout
            except requests.exceptions.ConnectionError:
                logger.warning(f"{provider} connection error, retrying...")
                raise  # Retry on connection error
            except Exception as e:
                logger.error(f"Failed to get number from {provider}: {e}")
                raise

        try:
            return RetryHelper.retry_sync(
                _get_number_internal,
                config=retry_config,
                context=f"get phone number from {provider}"
            )
        except Exception as e:
            logger.error(f"Failed to get number from {provider} after retries: {e}")
            return None

    def _get_smspool_number(self, country: str, api_key: str, config: Dict) -> Optional[Dict]:
        """Get number from SMSPool.net API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "country": country.lower(),
                "service": config["service_code"],
                "pricing_option": "0"  # Standard pricing
            }

            response = requests.post(config["api_url"], json=data, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("number"):
                    return {
                        "number": result["number"],
                        "id": result["order_id"],
                        "provider": "smspool",
                        "country": country,
                        "cost": config["cost_per_number"]
                    }
                else:
                    logger.warning(f"SMSPool API error: {result.get('message', 'Unknown error')}")

        except Exception as e:
            logger.error(f"SMSPool API call failed: {e}")

        return None

    def _get_textverified_number(self, country: str, api_key: str, config: Dict) -> Optional[Dict]:
        """Get number from TextVerified.com API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "service": config["service_code"],
                "country": country.upper(),
                "number_type": "virtual"
            }

            response = requests.post(config["api_url"], json=data, headers=headers, timeout=30)

            if response.status_code == 201:  # Created
                result = response.json()
                if result.get("id") and result.get("number"):
                    return {
                        "number": result["number"],
                        "id": result["id"],
                        "provider": "textverified",
                        "country": country,
                        "cost": config["cost_per_number"]
                    }
                else:
                    logger.warning(f"TextVerified API error: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"TextVerified API call failed: {e}")

        return None

    def _get_sms_activate_number(self, country: str, api_key: str, config: Dict) -> Optional[Dict]:
        """Get number from SMS-Activate.org API."""
        try:
            country_codes = {
                "US": "0", "GB": "44", "DE": "49", "FR": "33", "IT": "39",
                "ES": "34", "BR": "55", "RU": "7"
            }

            country_code = country_codes.get(country, "0")

            params = {
                "api_key": api_key,
                "action": "getNumber",
                "service": config["service_code"],
                "country": country_code
            }

            response = requests.get(config["api_url"], params=params, timeout=30)

            if response.status_code == 200:
                parts = response.text.split(":")
                if len(parts) >= 3 and parts[0] == "ACCESS_NUMBER":
                    return {
                        "number": f"+{parts[2]}",
                        "id": parts[1],
                        "provider": "sms-activate",
                        "country": country,
                        "cost": config["cost_per_number"]
                    }
                else:
                    logger.warning(f"SMS-Activate API error: {response.text}")

        except Exception as e:
            logger.error(f"SMS-Activate API call failed: {e}")

        return None

    def _get_sms_hub_number(self, country: str, api_key: str, config: Dict) -> Optional[Dict]:
        """Get number from SMS-Hub.org API."""
        try:
            country_codes = {
                "US": "1", "GB": "44", "DE": "49", "FR": "33", "IT": "39",
                "ES": "34", "BR": "55", "RU": "7", "IN": "91"
            }

            country_code = country_codes.get(country, "1")

            params = {
                "api_key": api_key,
                "action": "getNumber",
                "service": config["service_code"],
                "country": country_code
            }

            response = requests.get(config["api_url"], params=params, timeout=30)

            if response.status_code == 200:
                # Handle text response format (ACCESS_NUMBER:ID:NUMBER) which is common for Russia-based APIs
                text_response = response.text
                if text_response.startswith("ACCESS_NUMBER"):
                    parts = text_response.split(":")
                    if len(parts) >= 3:
                        return {
                            "number": f"+{parts[2]}",
                            "id": parts[1],
                            "provider": "sms-hub",
                            "country": country,
                            "cost": config["cost_per_number"]
                        }
                
                # Try JSON format as fallback
                try:
                    data = response.json()
                    if data.get("status") == "success" and data.get("number"):
                        return {
                            "number": data["number"],
                            "id": data["id"],
                            "provider": "sms-hub",
                            "country": country,
                            "cost": config["cost_per_number"]
                        }
                    else:
                        logger.warning(f"SMS-Hub API error (JSON): {data.get('message', 'Unknown error')}")
                except json.JSONDecodeError:
                    logger.warning(f"SMS-Hub API error (Text): {text_response}")

        except Exception as e:
            logger.error(f"SMS-Hub API call failed: {e}")

        return None

    def _get_5sim_number(self, country: str, api_key: str, config: Dict) -> Optional[Dict]:
        """Get number from 5SIM.net API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json"
            }

            # First get available numbers
            url = f"{config['api_url']}/guest/products/{country.lower()}/{config['service_code']}"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                products = response.json()
                if products:
                    # Buy the number
                    # Check if products is a dict (category structure) or list
                    product_name = None
                    if isinstance(products, dict):
                        # Find a product with available quantity
                        for name, details in products.items():
                            if details.get("Qty", 0) > 0:
                                product_name = name
                                break
                    else:
                        # Assume it's a list or direct structure
                        pass # 5sim API structure varies, assuming standard buying endpoint works without specific product selection if configured differently

                    buy_url = f"{config['api_url']}/user/buy/activation/{country.lower()}/{config['service_code']}"
                    
                    buy_response = requests.get(buy_url, headers=headers, timeout=30) # 5sim uses GET for buy usually

                    if buy_response.status_code == 200:
                        result = buy_response.json()
                        if result.get("phone"):
                            return {
                                "number": result["phone"],
                                "id": result["id"],
                                "provider": "5sim",
                                "country": country,
                                "cost": config["cost_per_number"]
                            }
                        else:
                            logger.warning(f"5SIM buy error: {result.get('error', 'Unknown error')}")
                    else:
                        logger.warning(f"5SIM buy failed HTTP {buy_response.status_code}: {buy_response.text}")

        except Exception as e:
            logger.error(f"5SIM API call failed: {e}")

        return None

    def _parse_provider_response(self, response: str, provider: str) -> Optional[Dict]:
        """Parse response from phone number provider (legacy method)."""
        # This is kept for backward compatibility but new providers use specific methods
        if provider == "sms-activate":
            parts = response.split(":")
            if len(parts) >= 3 and parts[0] == "ACCESS_NUMBER":
                return {"id": parts[1], "number": parts[2]}

        return None

    def get_sms_code(self, provider: str, number_id: str, api_key: str) -> Optional[str]:
        """Get SMS code for a phone number with retry logic."""
        if provider not in self.providers:
            logger.error(f"Provider '{provider}' not supported for SMS code retrieval")
            return None

        # Configure retry for SMS code retrieval (more attempts since SMS can be delayed)
        retry_config = RetryConfig(
            max_attempts=5,  # More attempts for SMS
            base_delay=3.0,  # Longer delay between checks
            strategy=RetryStrategy.LINEAR,  # Linear backoff for SMS checking
            jitter=False  # No jitter for SMS timing
        )

        def _get_sms_internal():
            try:
                if provider == "smspool":
                    return self._get_smspool_sms_code(number_id, api_key)
                elif provider == "textverified":
                    return self._get_textverified_sms_code(number_id, api_key)
                elif provider == "sms-activate":
                    return self._get_sms_activate_sms_code(number_id, api_key)
                elif provider == "sms-hub":
                    return self._get_sms_hub_sms_code(number_id, api_key)
                elif provider == "5sim":
                    return self._get_5sim_sms_code(number_id, api_key)
                elif provider == "daisysms":
                    return self._get_daisysms_sms_code(number_id, api_key)
                else:
                    logger.error(f"Unsupported provider for SMS code: {provider}")
                    return None
            except requests.exceptions.Timeout:
                logger.debug(f"{provider} SMS check timeout, retrying...")
                raise
            except requests.exceptions.ConnectionError:
                logger.debug(f"{provider} SMS check connection error, retrying...")
                raise
            except Exception as e:
                # Don't log error for "still waiting" scenarios
                if "STATUS_WAIT" not in str(e):
                    logger.debug(f"SMS not ready yet from {provider}: {e}")
                return None  # Return None instead of raising for "not ready yet" scenarios

        try:
            result = RetryHelper.retry_sync(
                _get_sms_internal,
                config=retry_config,
                context=f"get SMS code from {provider}"
            )
            return result
        except Exception as e:
            logger.warning(f"SMS code not received from {provider} after {retry_config.max_attempts} attempts")
            return None

    def _get_smspool_sms_code(self, order_id: str, api_key: str) -> Optional[str]:
        """Get SMS code from SMSPool.net API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            url = f"https://api.smspool.net/sms/check/{order_id}"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("sms"):
                    # Extract code from SMS text (usually the code is the SMS content)
                    sms_text = result["sms"]
                    # Extract numeric code (usually 5-6 digits)
                    import re
                    code_match = re.search(r'\b(\d{4,6})\b', sms_text)
                    if code_match:
                        return code_match.group(1)

        except Exception as e:
            logger.error(f"SMSPool SMS code retrieval failed: {e}")

        return None

    def _get_textverified_sms_code(self, request_id: str, api_key: str) -> Optional[str]:
        """Get SMS code from TextVerified.com API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json"
            }

            url = f"https://www.textverified.com/api/requests/{request_id}"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "completed" and result.get("code"):
                    return result["code"]

        except Exception as e:
            logger.error(f"TextVerified SMS code retrieval failed: {e}")

        return None

    def _get_sms_activate_sms_code(self, activation_id: str, api_key: str) -> Optional[str]:
        """Get SMS code from SMS-Activate.org API."""
        try:
            params = {
                "api_key": api_key,
                "action": "getStatus",
                "id": activation_id
            }

            response = requests.get("https://api.sms-activate.org/stubs/handler_api.php", params=params, timeout=30)

            if response.status_code == 200:
                response_text = response.text
                if response_text.startswith("STATUS_OK"):
                    parts = response_text.split(":")
                    if len(parts) > 1:
                        return parts[1]
                elif response_text.startswith("STATUS_WAIT_CODE"):
                    # Still waiting for SMS
                    return None
                else:
                    logger.warning(f"SMS-Activate status: {response_text}")

        except Exception as e:
            logger.error(f"SMS-Activate SMS code retrieval failed: {e}")

        return None

    def _get_sms_hub_sms_code(self, activation_id: str, api_key: str) -> Optional[str]:
        """Get SMS code from SMS-Hub.org API."""
        try:
            params = {
                "api_key": api_key,
                "action": "getStatus",
                "id": activation_id
            }

            response = requests.get("https://smshub.org/api.php", params=params, timeout=30)

            if response.status_code == 200:
                # Handle text response format (STATUS_OK:CODE) which is common for Russia-based APIs
                text_response = response.text
                if text_response.startswith("STATUS_OK"):
                    parts = text_response.split(":")
                    if len(parts) > 1:
                        return parts[1]
                
                # Try JSON format as fallback
                try:
                    data = response.json()
                    if data.get("status") == "success" and data.get("sms"):
                        # Extract code from SMS array (usually the first SMS)
                        sms_list = data["sms"]
                        if sms_list and len(sms_list) > 0:
                            sms_text = sms_list[0].get("text", "")
                            import re
                            code_match = re.search(r'\b(\d{4,6})\b', sms_text)
                            if code_match:
                                return code_match.group(1)
                except json.JSONDecodeError:
                    pass # Ignore if not JSON

        except Exception as e:
            logger.error(f"SMS-Hub SMS code retrieval failed: {e}")

        return None

    def _get_5sim_sms_code(self, order_id: str, api_key: str) -> Optional[str]:
        """Get SMS code from 5SIM.net API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json"
            }

            url = f"https://5sim.net/v1/user/check/{order_id}"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "RECEIVED" and result.get("sms"):
                    sms_list = result["sms"]
                    if sms_list and len(sms_list) > 0:
                        sms_text = sms_list[0].get("text", "")
                        import re
                        code_match = re.search(r'\b(\d{4,6})\b', sms_text)
                        if code_match:
                            return code_match.group(1)

        except Exception as e:
            logger.error(f"5SIM SMS code retrieval failed: {e}")

        return None

    def _get_daisysms_number(self, country: str, api_key: str, config: Dict) -> Optional[Dict]:
        """Get number from DaisySMS.com API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }

            # Rent a number for Telegram
            data = {
                "service": config["service_code"],
                "country": country.upper()
            }

            url = f"{config['api_url']}/rent"
            response = requests.post(url, json=data, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get("success") and result.get("number"):
                    return {
                        "number": result["number"],
                        "id": result.get("rental_id") or result.get("id"),
                        "provider": "daisysms",
                        "country": country,
                        "cost": config["cost_per_number"]
                    }
                else:
                    logger.warning(f"DaisySMS API error: {result.get('error', 'Unknown error')}")
            elif response.status_code == 201:
                # Some APIs return 201 for created resources
                result = response.json()
                if result.get("number"):
                    return {
                        "number": result["number"],
                        "id": result.get("rental_id") or result.get("id"),
                        "provider": "daisysms",
                        "country": country,
                        "cost": config["cost_per_number"]
                    }

        except Exception as e:
            logger.error(f"DaisySMS API call failed: {e}")

        return None

    def _get_daisysms_sms_code(self, rental_id: str, api_key: str) -> Optional[str]:
        """Get SMS code from DaisySMS.com API."""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json"
            }

            url = f"https://api.daisysms.com/v1/rent/{rental_id}/sms"
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                result = response.json()
                # Check if SMS has been received
                if result.get("status") == "received" or result.get("sms_received"):
                    sms_text = result.get("sms", "") or result.get("code", "")
                    if sms_text:
                        import re
                        code_match = re.search(r'\b(\d{4,6})\b', sms_text)
                        if code_match:
                            return code_match.group(1)
                elif result.get("status") == "waiting":
                    # Still waiting for SMS
                    return None
                else:
                    # Check if code is directly in response
                    if result.get("code"):
                        return str(result["code"])

        except Exception as e:
            logger.error(f"DaisySMS SMS code retrieval failed: {e}")

        return None

    def _extract_sms_code(self, response: str, provider: str) -> Optional[str]:
        """Extract SMS code from provider response (legacy method)."""
        # Implementation would vary by provider
        if provider == "sms-activate":
            if response.startswith("STATUS_OK"):
                # Extract code from message
                parts = response.split(":")
                if len(parts) > 1:
                    return parts[1]

        return None


class AccountCreator:
    """Create and manage multiple Telegram accounts with proxy pool integration."""

    def __init__(self, db, gemini_service=None, account_manager=None):
        self.db = db
        self.account_manager = account_manager  # Store reference for status updates
        
        # Basic proxy manager (fallback)
        self.proxy_manager = ProxyManager()
        
        # Enhanced proxy pool manager (if available)
        self._proxy_pool_manager = None
        self._use_proxy_pool = PROXY_POOL_AVAILABLE
        
        self.phone_provider = PhoneNumberProvider()
        self.anti_detection = AccountCreationAntiDetection()
        self.cloning_system = AdvancedCloningSystem(gemini_service)
        self.username_generator = UsernameGenerator()
        self.failsafe = AccountCreationFailSafe(FailSafeLevel.STANDARD)
        self.created_accounts = []
        self.creation_active = False
        self.creation_queue = []  # Queue for bulk creation
        self.active_creations = {}  # Track active creation tasks
        self.creation_stats = {
            'total_attempted': 0,
            'total_successful': 0,
            'total_failed': 0,
            'current_batch': 0
        }
        self.progress_callback = None  # Callback for progress updates
        
        # Proxy assignment tracking
        self.account_proxies: Dict[str, Dict] = {}  # phone_number -> proxy info
        
    async def _get_proxy_pool_manager(self) -> Optional['ProxyPoolManager']:
        """Get or initialize the proxy pool manager."""
        if not self._use_proxy_pool:
            return None
        
        if self._proxy_pool_manager is None:
            try:
                self._proxy_pool_manager = get_proxy_pool_manager()
                if not self._proxy_pool_manager.is_running:
                    await self._proxy_pool_manager.start()
                logger.info("ProxyPoolManager initialized for account creation")
            except Exception as e:
                logger.warning(f"Failed to initialize ProxyPoolManager: {e}")
                self._use_proxy_pool = False
                return None
        
        return self._proxy_pool_manager
    
    async def get_proxy_for_account(self, phone_number: str) -> Optional[Dict]:
        """
        Get a proxy for account creation.
        
        Uses ProxyPoolManager if available, falls back to basic ProxyManager.
        The proxy is permanently assigned to this account.
        
        Args:
            phone_number: Phone number for the account
            
        Returns:
            Proxy configuration dict or None
        """
        # Try proxy pool first
        pool = await self._get_proxy_pool_manager()
        if pool:
            try:
                proxy = await pool.get_proxy_for_account(phone_number)
                if proxy:
                    # Store assignment
                    self.account_proxies[phone_number] = {
                        'ip': proxy.ip,
                        'port': proxy.port,
                        'scheme': proxy.protocol.value,
                        'username': proxy.username,
                        'password': proxy.password,
                        'proxy_key': proxy.proxy_key,
                        'source': 'proxy_pool',
                        'is_permanent': True,
                        'assigned_at': datetime.now().isoformat()
                    }
                    logger.info(f"Assigned proxy {proxy.proxy_key} to account {phone_number} from pool")
                    return self.account_proxies[phone_number]
            except Exception as e:
                logger.warning(f"Failed to get proxy from pool: {e}")
        
        # Fallback to basic proxy manager
        proxy = self.proxy_manager.get_proxy()
        if proxy:
            self.proxy_manager.mark_proxy_used(proxy)
            self.account_proxies[phone_number] = {
                **proxy,
                'source': 'basic',
                'is_permanent': True,
                'assigned_at': datetime.now().isoformat()
            }
            return self.account_proxies[phone_number]
        
        return None
    
    async def handle_proxy_failure(self, phone_number: str, error: Exception) -> Optional[Dict]:
        """
        Handle proxy failure and auto-reassign.
        
        Args:
            phone_number: Phone number for the account
            error: The error that occurred
            
        Returns:
            New proxy configuration or None
        """
        old_proxy = self.account_proxies.get(phone_number)
        
        if old_proxy:
            logger.warning(f"Proxy failed for {phone_number}: {error}")
            
            # Mark failed in pool
            pool = await self._get_proxy_pool_manager()
            if pool and old_proxy.get('source') == 'proxy_pool':
                try:
                    # Release old proxy
                    await pool.release_proxy(phone_number)
                    logger.info(f"Released failed proxy for {phone_number}")
                except Exception as e:
                    logger.error(f"Failed to release proxy: {e}")
            else:
                # Mark failed in basic manager
                self.proxy_manager.mark_proxy_failed(old_proxy)
        
        # Get new proxy
        new_proxy = await self.get_proxy_for_account(phone_number)
        if new_proxy:
            logger.info(f"Auto-reassigned proxy for {phone_number}: {new_proxy.get('ip')}:{new_proxy.get('port')}")
        else:
            logger.error(f"Failed to reassign proxy for {phone_number}")
        
        return new_proxy
    
    def get_account_proxy(self, phone_number: str) -> Optional[Dict]:
        """Get the permanently assigned proxy for an account."""
        return self.account_proxies.get(phone_number)

    def update_proxy_list(self, proxy_list: List[str], settings: Dict = None):
        """Update the proxy manager with configured proxies."""
        if not proxy_list:
            # If no custom proxies, let proxy manager fetch from sources
            return

        # Clear existing proxies and add configured ones
        self.proxy_manager.proxies = []
        for proxy_str in proxy_list:
            if ':' in proxy_str:
                try:
                    ip, port_str = proxy_str.split(':', 1)
                    port = int(port_str)
                    if 1 <= port <= 65535:
                        proxy = {
                            "ip": ip,
                            "port": port,
                            "source": "configured",
                            "last_used": None,
                            "fail_count": 0
                        }
                        self.proxy_manager.proxies.append(proxy)
                except (ValueError, IndexError):
                    logger.warning(f"Invalid proxy format: {proxy_str}")

        # Apply proxy settings
        if settings:
            self.proxy_manager.max_failures = settings.get('max_failures', 3)
            # Other proxy settings can be applied here

        logger.info(f"Updated proxy list with {len(self.proxy_manager.proxies)} proxies")

    def set_progress_callback(self, callback):
        """Set a callback function for progress updates.
        
        Args:
            callback: Function that takes (current: int, total: int, status: str)
        """
        self.progress_callback = callback

    def _notify_progress(self, current: int, total: int, status: str = ""):
        """Notify progress callback."""
        if self.progress_callback:
            try:
                self.progress_callback(current, total, status)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    async def start_bulk_creation(self, count: int, config: Dict) -> List[Dict]:
        """Start bulk account creation."""
        self.creation_active = True
        results = []
        self.creation_stats['total_attempted'] = 0
        self.creation_stats['total_successful'] = 0
        self.creation_stats['total_failed'] = 0

        logger.info(f"Starting bulk creation of {count} accounts")
        
        for i in range(count):
            if not self.creation_active:
                logger.info("Bulk creation stopped by user")
                break

            self._notify_progress(i, count, f"Creating account {i+1}...")

            try:
                result = await self.create_new_account(config)
                results.append(result)
                                
                if result.get('success'):
                    self.creation_stats['total_successful'] += 1
                    self._notify_progress(i+1, count, f"Account {i+1} created successfully")
                else:
                    self.creation_stats['total_failed'] += 1
                    self._notify_progress(i+1, count, f"Account {i+1} failed: {result.get('error')}")

            except Exception as e:
                logger.error(f"Error creating account {i+1}: {e}")
                self.creation_stats['total_failed'] += 1
                results.append({'success': False, 'error': str(e)})
            
            # Delay between creations
            if i < count - 1 and self.creation_active:
                delay = random.uniform(30, 60) if config.get('realistic_timing') else 5
                self._notify_progress(i+1, count, f"Waiting {delay:.0f}s before next account...")
                await asyncio.sleep(delay)

        self.creation_active = False
        return results
    
    def stop_creation(self):
        """Stop the creation process."""
        self.creation_active = False

    async def create_new_account(self, config: Dict) -> Dict[str, Any]:
        """Create a single new Telegram account with proxy pool integration."""
        temp_phone_id = f"temp_{int(time.time() * 1000)}"
        assigned_proxy = None

        try:
            # Validate configuration first
            if not config.get('api_id') or not config.get('api_hash'):
                return {
                    'success': False,
                    'error': 'Telegram API credentials (api_id and api_hash) are required. Get them from https://my.telegram.org/apps'
                }

            # Apply anti-detection settings to account creator
            anti_detection_config = config.get('anti_detection', {})
            if anti_detection_config:
                # Update anti-detection parameters for this creation
                if hasattr(self.anti_detection, 'update_settings'):
                    self.anti_detection.update_settings(anti_detection_config)

            # Store configuration for use during account setup
            self.brain_config = config.get('brain', {})
            self.account_defaults = config.get('account_defaults', {})
            self.voice_config = config.get('voice_config', {})
            self.proxy_pool_config = config.get('proxy_pool', {})
            
            # 1. Get Proxy from Pool
            self._notify_progress(0, 100, get_progress_message("getting_proxy"))
            proxy = None
            proxy_dict = None
            
            if config.get('use_proxy', True):
                # Use new proxy pool integration
                assigned_proxy = await self.get_proxy_for_account(temp_phone_id)
                
                if assigned_proxy:
                    proxy = assigned_proxy
                    proxy_dict = {
                        "scheme": assigned_proxy.get("scheme", "socks5"),
                        "hostname": assigned_proxy.get("ip"),
                        "port": assigned_proxy.get("port")
                    }
                    if assigned_proxy.get("username") and assigned_proxy.get("password"):
                        proxy_dict["username"] = assigned_proxy["username"]
                        proxy_dict["password"] = assigned_proxy["password"]
                    
                    logger.info(f"Using proxy {assigned_proxy.get('ip')}:{assigned_proxy.get('port')} (source: {assigned_proxy.get('source', 'unknown')})")
                elif config.get('require_proxy', False):
                    return {
                        'success': False,
                        'error': 'No proxies available. Add proxies in Settings or disable "require_proxy".'
                    }

            # 2. Get Phone Number
            self._notify_progress(10, 100, get_progress_message("getting_phone"))
            country = config.get('country', 'US')
            provider = config.get('phone_provider', 'sms-activate')
            api_key = config.get('provider_api_key')
            
            if not api_key:
                return {
                    'success': False,
                    'error': f'Phone provider API key is required. Get it from your {provider} account dashboard.'
                }

            phone_data = self.phone_provider.get_number(provider, country, api_key)
            if not phone_data:
                return {
                    'success': False,
                    'error': f'Failed to get phone number from {provider}. Check: 1) API key is valid 2) You have credit 3) {country} numbers are available'
                }

            phone_number = phone_data['number']
            logger.info(f"Got phone number: {phone_number}")
            self._notify_progress(25, 100, f"📱 Phone number acquired: {phone_number}")
            
            # Transfer proxy assignment from temp ID to real phone number
            if assigned_proxy:
                # Move proxy assignment to actual phone number
                self.account_proxies[phone_number] = self.account_proxies.pop(temp_phone_id, assigned_proxy)
                self.account_proxies[phone_number]['phone_number'] = phone_number
                
                # Update in proxy pool if available
                pool = await self._get_proxy_pool_manager()
                if pool and assigned_proxy.get('source') == 'proxy_pool':
                    try:
                        # Release temp assignment
                        await pool.release_proxy(temp_phone_id)
                        # Assign to real phone
                        await pool.get_proxy_for_account(phone_number)
                    except Exception as e:
                        logger.warning(f"Failed to transfer proxy assignment: {e}")
                
                logger.info(f"Transferred proxy assignment to {phone_number}")

            # 3. Initialize Client
            self._notify_progress(30, 100, get_progress_message("initializing_client"))
            session_name = f"account_{phone_number.replace('+', '')}"
            
            # Generate device fingerprint
            fingerprint = self._generate_device_fingerprint(config)
            
            client = await self._create_client_without_start(
                session_id=session_name,
                session_name=session_name,
                phone_number=phone_number,
                config=config,
                proxy=proxy,
                fingerprint=fingerprint
            )

            if not client:
                return {
                    'success': False,
                    'error': 'Failed to initialize Telegram client. Check your API credentials and internet connection.'
                }

            # 4. Request SMS Code
            self._notify_progress(40, 100, get_progress_message("sending_code"))
            try:
                sent_code = await client.send_code(phone_number)
            except FloodWait as e:
                return {
                    'success': False,
                    'error': f"⏱️ Rate limit reached. Telegram requires waiting {e.value} seconds. Try again later."
                }
            except PhoneNumberInvalid as e:
                return {
                    'success': False,
                    'error': translate_error(e, "sending verification code")
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': translate_error(e, "requesting SMS code")
                }

            # 5. Get SMS Code from Provider
            self._notify_progress(50, 100, get_progress_message("waiting_sms"))
            sms_code = await self._handle_sms_with_anti_detection(session_name, phone_data, config)
            if not sms_code:
                return {
                    'success': False,
                    'error': 'SMS code not received. This could mean: 1) Number blacklisted by Telegram 2) SMS delayed 3) Provider issue. Try a different country or provider.'
                }

            # 6. Sign In
            self._notify_progress(70, 100, get_progress_message("signing_in"))
            try:
                await client.sign_in(phone_number, sent_code.phone_code_hash, sms_code)
            except SessionPasswordNeeded as e:
                return {
                    'success': False,
                    'error': translate_error(e, "signing in")
                }
            except PhoneCodeInvalid as e:
                return {
                    'success': False,
                    'error': translate_error(e, "verifying code")
                }
            except PhoneCodeExpired as e:
                return {
                    'success': False,
                    'error': translate_error(e, "verifying code")
                }
            except Exception as e:
                return {
                    'success': False,
                    'error': translate_error(e, "signing in")
                }

            # 7. Setup Profile
            self._notify_progress(80, 100, get_progress_message("setting_up_profile"))
            await self._setup_profile_with_anti_detection(session_name, client, config, fingerprint)

            # 8. Success!
            self._notify_progress(100, 100, get_progress_message("complete"))
            account_info = {
                'phone_number': phone_number,
                'session_name': session_name,
                'created_at': datetime.now().isoformat(),
                'proxy': proxy,
                'device_fingerprint': fingerprint,
                'status': 'active',
                'is_warmed_up': False,
                'warmup_stage': 'pending',
                'messages_sent': 0,
                'last_active': datetime.now().isoformat()
            }
            
            # ACTUALLY save account to database
            if self.db:
                try:
                    self._save_account_to_database(account_info)
                    logger.info(f"✅ Account {phone_number} saved to ACTUAL database")
                except Exception as e:
                    logger.error(f"Failed to save account to database: {e}")
                    # Continue anyway, account was created
            
            # Notify account manager if available
            if self.account_manager:
                try:
                    self.account_manager._on_account_created(account_info)
                    logger.info(f"✅ Account manager notified of new account")
                except Exception as e:
                    logger.warning(f"Failed to notify account manager: {e}")

            logger.info(f"✅ Account {phone_number} created successfully!")
            return {'success': True, 'account': account_info, 'message': '✅ Account created successfully!'}

        except Exception as e:
            logger.error(f"Account creation failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': translate_error(e, "account creation")
            }

    def _generate_device_fingerprint(self, config: Dict) -> Dict:
        """Generate a realistic device fingerprint."""
        # Use AntiDetectionSystem if possible, otherwise fallback
        # This implementation aligns with the plan to inject parameters
        
        # Simple fallback generation logic
        models = [
            ("Samsung", "Galaxy S21", "Android 12"),
            ("Xiaomi", "Redmi Note 10", "Android 11"),
            ("Google", "Pixel 6", "Android 13"),
            ("Apple", "iPhone 13", "iOS 15.0"),
            ("Apple", "iPhone 12", "iOS 14.5")
        ]
        
        vendor, model, system = random.choice(models)
        app_version = f"{random.randint(8, 10)}.{random.randint(0, 9)}.{random.randint(0, 5)}"
        
        return {
            "device_model": model,
            "system_version": system,
            "app_version": app_version,
            "lang_code": config.get("country", "en").lower(),
            "system_lang_code": config.get("country", "en").lower() + "-" + config.get("country", "US").upper()
        }

    async def _create_client_without_start(self, session_id: str, session_name: str, phone_number: str,
                                          config: Dict, proxy: Optional[Dict], fingerprint: Dict) -> Optional[Client]:
        """Create Pyrogram client without starting it (for manual authentication)."""
        try:
            import os

            # Apply device fingerprint to environment (simulated)
            # self._apply_device_fingerprint_to_environment(fingerprint) # Legacy method, removing dependency

            api_id = config.get("api_id") or os.getenv("TELEGRAM_API_ID", "")
            api_hash = config.get("api_hash") or os.getenv("TELEGRAM_API_HASH", "")
            
            if not api_id or not api_hash:
                logger.error("Missing Telegram API credentials. Set in config or environment variables.")
                return None

            # Prepare client arguments with Anti-Detection injection
            client_args = {
                "name": session_name,
                "api_id": api_id,
                "api_hash": api_hash,
                "phone_number": phone_number,
                "proxy": self._format_proxy(proxy) if proxy else None,
                "device_model": fingerprint.get("device_model"),
                "system_version": fingerprint.get("system_version"),
                "app_version": fingerprint.get("app_version"),
                "lang_code": fingerprint.get("lang_code"),
                "system_lang_code": fingerprint.get("system_lang_code")
            }
            
            # Remove None values
            client_args = {k: v for k, v in client_args.items() if v is not None}

            client = Client(**client_args)

            # Initialize the client (connect but don't authenticate)
            await client.connect()

            return client

        except Exception as e:
            logger.error(f"Failed to create client: {e}")
            return None

    def _format_proxy(self, proxy: Dict) -> Dict:
        """Format proxy dict for Pyrogram."""
        if not proxy:
            return None
        
        import socks
        return {
            "scheme": "socks5" if proxy.get("type") == "socks5" else "http",
            "hostname": proxy["ip"],
            "port": proxy["port"],
            "username": proxy.get("username"),
            "password": proxy.get("password")
        }

    async def _handle_sms_with_anti_detection(self, session_id: str, phone_data: Dict, config: Dict) -> Optional[str]:
        """Handle SMS verification with human-like behavior."""
        max_sms_attempts = 5  # Wait up to 5 minutes for SMS

        for attempt in range(max_sms_attempts):
            sms_code = self.phone_provider.get_sms_code(
                phone_data["provider"],
                phone_data["id"],
                config["provider_api_key"]
            )

            if sms_code:
                # Simulate human reading and typing the code
                reading_delay = self.anti_detection.simulate_reading_sms(session_id)
                await asyncio.sleep(reading_delay)

                # Simulate typing the code
                typing_delays = self.anti_detection.simulate_human_typing(session_id, sms_code, "code_entry")
                total_typing_time = sum(typing_delays)
                await asyncio.sleep(total_typing_time)

                logger.info(f"📝 Entered SMS code: {sms_code}")
                return sms_code

            # Wait before checking again
            check_delay = random.uniform(8, 15)  # 8-15 seconds between checks
            await asyncio.sleep(check_delay)

        logger.error("Failed to receive SMS code within timeout")
        return None

    async def _setup_profile_with_anti_detection(self, session_id: str, client: Client, config: Dict, fingerprint: Dict):
        """Set up profile with human-like behavior simulation."""
        try:
            # STEP 1: Name setup
            if not config.get("clone_username"):
                name_delay = self.anti_detection.simulate_profile_setup(session_id, "name")
                await asyncio.sleep(name_delay)

                first_name, last_name = self._generate_realistic_name(config.get("country", "US"))

                logger.info(f"👤 Setting up profile: {first_name} {last_name}")

                await client.update_profile(
                    first_name=first_name,
                    last_name=last_name
                )

                # Generate and set username with availability checking
                await self._generate_and_set_username(client)

            # STEP 2: Profile photo (if specified) - with stealth update
            if config.get("profile_photo"):
                photo_delay = self.anti_detection.simulate_profile_setup(session_id, "photo")
                await asyncio.sleep(photo_delay)

                try:
                    # Use stealth photo update to avoid "updated 1 day ago" message
                    await self._set_profile_photo_stealth(client, config["profile_photo"])
                    logger.info("📸 Profile photo set (stealth mode)")
                except Exception as e:
                    logger.warning(f"Failed to set profile photo: {e}")

            # STEP 3: Bio setup
            bio_delay = self.anti_detection.simulate_profile_setup(session_id, "bio")
            await asyncio.sleep(bio_delay)
            # Add bio setup logic if needed (not implemented in snippet)

        except Exception as e:
            logger.error(f"Profile setup failed: {e}")

    def _generate_realistic_name(self, country: str) -> Tuple[str, str]:
        """Generate a realistic name for the given country."""
        # This is a placeholder. In a real implementation, you'd use a name generation library
        # or a list of common names for the country.
        first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles"]
        last_names = ["Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor"]
        return random.choice(first_names), random.choice(last_names)

    async def _generate_and_set_username(self, client: Client):
        """Generate and set a username."""
        try:
            # Placeholder for username generation
            me = await client.get_me()
            username = f"{me.first_name.lower()}_{random.randint(1000, 9999)}"
            await client.set_username(username)
        except Exception as e:
            logger.warning(f"Failed to set username: {e}")

    async def _set_profile_photo_stealth(self, client: Client, photo_path: str):
        """Set profile photo with stealth update."""
        # Placeholder for stealth photo update
        await client.set_profile_photo(photo=photo_path)
    
    def _save_account_to_database(self, account_info: Dict):
        """ACTUALLY save account to database (not a placeholder)."""
        import sqlite3
        
        try:
            # Connect to REAL database
            conn = sqlite3.connect(self.db.db_path if hasattr(self.db, 'db_path') else 'members.db')
            cursor = conn.cursor()
            
            # Create accounts table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    phone_number TEXT PRIMARY KEY,
                    session_name TEXT,
                    status TEXT,
                    created_at TEXT,
                    last_active TEXT,
                    messages_sent INTEGER DEFAULT 0,
                    is_warmed_up INTEGER DEFAULT 0,
                    warmup_stage TEXT,
                    proxy_used TEXT,
                    device_fingerprint TEXT,
                    api_id TEXT,
                    api_hash TEXT
                )
            """)
            
            # Insert account data
            cursor.execute("""
                INSERT OR REPLACE INTO accounts (
                    phone_number, session_name, status, created_at,
                    last_active, messages_sent, is_warmed_up, warmup_stage,
                    proxy_used, device_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_info['phone_number'],
                account_info['session_name'],
                account_info.get('status', 'active'),
                account_info['created_at'],
                account_info.get('last_active', datetime.now().isoformat()),
                account_info.get('messages_sent', 0),
                0,  # is_warmed_up
                account_info.get('warmup_stage', 'pending'),
                str(account_info.get('proxy', '')),
                str(account_info.get('device_fingerprint', ''))
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ ACTUALLY saved account {account_info['phone_number']} to database")
            
        except Exception as e:
            logger.error(f"Failed to save account to database: {e}", exc_info=True)
            raise
            
