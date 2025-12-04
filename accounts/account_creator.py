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
import hashlib
import requests
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from pyrogram import Client
from pyrogram.errors import (
    FloodWait, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired,
    SessionPasswordNeeded, UserDeactivated, UsernameOccupied, UsernameInvalid
)

from anti_detection.anti_detection_system import AccountCreationAntiDetection
from anti_detection.advanced_cloning_system import AdvancedCloningSystem
from accounts.username_generator import UsernameGenerator
from accounts.account_creation_failsafes import AccountCreationFailSafe, FailSafeLevel
from utils.user_helpers import translate_error, get_progress_message, ValidationHelper
from utils.retry_helper import RetryHelper, RetryConfig, RetryStrategy

# Import audit logging
try:
    from accounts.account_audit_log import get_audit_log, AuditEvent, AuditEventType
    AUDIT_LOG_AVAILABLE = True
except ImportError:
    AUDIT_LOG_AVAILABLE = False

logger = logging.getLogger(__name__)

# Try to import ProxyPoolManager
try:
    from proxy.proxy_pool_manager import ProxyPoolManager, get_proxy_pool_manager, Proxy, ProxyTier
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

    def validate_provider_capability(self, provider: str, country: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that provider supports the requested country before attempting purchase.
        
        Args:
            provider: SMS provider name
            country: Country code (e.g., 'US', 'GB')
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if provider not in self.providers:
            available = ', '.join(self.providers.keys())
            return False, f"Provider '{provider}' not supported. Available: {available}"
        
        provider_config = self.providers[provider]
        supported_countries = provider_config.get('countries', [])
        
        if country not in supported_countries:
            return False, (
                f"Provider '{provider}' does not support country '{country}'. "
                f"Supported countries: {', '.join(supported_countries)}"
            )
        
        return True, None
    
    def get_number(self, provider: str, country: str, api_key: str) -> Optional[Dict]:
        """Get a phone number from specified provider with rate limiting and retry logic."""
        # Enforce capability check before attempting purchase
        is_valid, error = self.validate_provider_capability(provider, country)
        if not is_valid:
            logger.error(f"Provider capability check failed: {error}")
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

    def check_inventory(self, provider: str, country: str, api_key: str, requested: int) -> Dict[str, Any]:
        """Best-effort inventory probe to avoid starting runs without enough numbers."""
        if provider not in self.providers:
            return {
                'success': False,
                'error': f"Unsupported phone provider '{provider}'"
            }

        if not api_key:
            return {
                'success': False,
                'error': f"Phone provider API key is required for {provider}"
            }

        try:
            if provider == "5sim":
                available = self._check_5sim_inventory(country, api_key)
                return {'success': True, 'available': available}

            if provider == "sms-activate":
                available = self._check_sms_activate_inventory(country, api_key)
                return {'success': True, 'available': available}

            if provider == "sms-hub":
                available = self._check_sms_hub_inventory(country, api_key)
                return {'success': True, 'available': available}

            if provider == "smspool":
                available, warning = self._check_smspool_inventory(country, api_key, provider_config)
                return {'success': True, 'available': available, 'warning': warning}

            if provider == "textverified":
                available, warning = self._check_textverified_inventory(country, api_key, provider_config)
                return {'success': True, 'available': available, 'warning': warning}

            if provider == "daisysms":
                available, warning = self._check_daisysms_inventory(country, api_key, provider_config)
                return {'success': True, 'available': available, 'warning': warning}

            # Providers without safe availability endpoints fall back to warning-only mode
            return {
                'success': True,
                'available': None,
                'warning': (
                    f"{provider} does not expose a safe availability endpoint; proceeding without a guaranteed "
                    f"inventory check for {requested} requested numbers."
                )
            }
        except Exception as exc:
            return {
                'success': False,
                'error': f"Inventory check failed for {provider}: {exc}"
            }

    def _check_smspool_inventory(self, country: str, api_key: str, config: Dict) -> Tuple[Optional[int], Optional[str]]:
        """Best-effort SMSPool inventory check using service availability endpoints."""
        try:
            response = requests.get(
                f"{config['api_url']}/request/quantity",
                params={
                    'key': api_key,
                    'country': country,
                    'service': config.get('service_code', 'tg')
                },
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                if 'quantity' in data:
                    return int(data['quantity']), None
                if 'success' in data and not data.get('success'):
                    return None, data.get('message', 'SMSPool reported no availability information')
            return None, "SMSPool availability endpoint returned an unexpected payload"
        except Exception as exc:
            logger.warning(f"SMSPool availability check failed: {exc}")
            return None, f"SMSPool availability check failed: {exc}"

    def _check_textverified_inventory(self, country: str, api_key: str, config: Dict) -> Tuple[Optional[int], Optional[str]]:
        """Best-effort TextVerified availability probe based on minimum price listings."""
        try:
            headers = {'Authorization': f"Bearer {api_key}"}
            response = requests.get(
                f"{config['api_url']}/availability",
                params={'service': config.get('service_code', 'telegram'), 'country': country},
                headers=headers,
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict) and 'available' in data:
                return int(data['available']), None
            return None, "TextVerified availability endpoint returned an unexpected payload"
        except Exception as exc:
            logger.warning(f"TextVerified availability check failed: {exc}")
            return None, f"TextVerified availability check failed: {exc}"

    def _check_daisysms_inventory(self, country: str, api_key: str, config: Dict) -> Tuple[Optional[int], Optional[str]]:
        """Best-effort DaisySMS stock check using pricing/stock listing endpoints."""
        try:
            response = requests.get(
                f"{config['api_url']}/stock",
                params={'api_key': api_key, 'service': config.get('service_code', 'telegram'), 'country': country},
                timeout=8,
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                stock = data.get('stock') or data.get('available')
                if stock is not None:
                    return int(stock), None
            return None, "DaisySMS availability endpoint returned an unexpected payload"
        except Exception as exc:
            logger.warning(f"DaisySMS availability check failed: {exc}")
            return None, f"DaisySMS availability check failed: {exc}"

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

    def _check_5sim_inventory(self, country: str, api_key: str) -> int:
        """Return available 5SIM numbers for a country/service without purchasing."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

        provider_config = self.providers.get("5sim", {})
        url = f"{provider_config.get('api_url')}/guest/products/{country.lower()}/{provider_config.get('service_code')}"
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        products = response.json()
        available_total = 0

        if isinstance(products, dict):
            for details in products.values():
                qty = details.get("Qty") or details.get("qty") or details.get("count") or 0
                available_total += qty or 0
        elif isinstance(products, list):
            for entry in products:
                qty = entry.get("Qty") or entry.get("qty") or entry.get("count") or 0
                available_total += qty or 0

        return available_total

    def _check_sms_activate_inventory(self, country: str, api_key: str) -> Optional[int]:
        """Check SMS-Activate availability for the Telegram service in a country."""
        country_codes = {
            "US": "0", "GB": "44", "DE": "49", "FR": "33", "IT": "39",
            "ES": "34", "BR": "55", "RU": "7"
        }

        country_code = country_codes.get(country, "0")
        params = {
            "api_key": api_key,
            "action": "getNumbersStatus",
            "country": country_code,
        }

        provider_config = self.providers.get("sms-activate", {})
        response = requests.get(provider_config.get("api_url"), params=params, timeout=30)
        response.raise_for_status()

        try:
            status = response.json()
        except json.JSONDecodeError:
            logger.warning(f"SMS-Activate inventory returned non-JSON payload: {response.text}")
            return None

        service_key = provider_config.get("service_code")
        if not service_key:
            return None

        # Keys are often formatted as tg_0 or tg0 depending on provider
        candidates = [f"{service_key}_{country_code}", f"{service_key}{country_code}"]
        for candidate in candidates:
            if candidate in status:
                try:
                    return int(status[candidate])
                except (TypeError, ValueError):
                    return None

        return None

    def _check_sms_hub_inventory(self, country: str, api_key: str) -> Optional[int]:
        """Check SMS-Hub availability using the shared handler API status endpoint."""
        country_codes = {
            "US": "1", "GB": "44", "DE": "49", "FR": "33", "IT": "39",
            "ES": "34", "BR": "55", "RU": "7", "IN": "91"
        }

        country_code = country_codes.get(country, "1")
        params = {
            "api_key": api_key,
            "action": "getNumbersStatus",
            "country": country_code,
        }

        provider_config = self.providers.get("sms-hub", {})
        response = requests.get(provider_config.get("api_url"), params=params, timeout=30)
        response.raise_for_status()

        try:
            status = response.json()
        except json.JSONDecodeError:
            logger.warning(f"SMS-Hub inventory returned non-JSON payload: {response.text}")
            return None

        service_key = provider_config.get("service_code")
        if not service_key:
            return None

        candidates = [f"{service_key}_{country_code}", f"{service_key}{country_code}"]
        for candidate in candidates:
            if candidate in status:
                try:
                    return int(status[candidate])
                except (TypeError, ValueError):
                    return None

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
                    # Buy the number with an available product/operator
                    product_name = None
                    if isinstance(products, dict):
                        # Find a product with available quantity
                        for name, details in products.items():
                            quantity = details.get("Qty") or details.get("qty") or details.get("count", 0)
                            if quantity and quantity > 0:
                                product_name = details.get("Product") or name
                                break
                    elif isinstance(products, list):
                        for entry in products:
                            quantity = entry.get("Qty") or entry.get("qty") or entry.get("count", 0)
                            if quantity and quantity > 0:
                                product_name = entry.get("Product") or entry.get("operator") or entry.get("slug")
                                break

                    if not product_name:
                        logger.warning(f"5SIM returned no purchasable products for {country} and service {config['service_code']}")
                        return None

                    buy_url = (
                        f"{config['api_url']}/user/buy/activation/{country.lower()}/{product_name}/{config['service_code']}"
                    )

                    buy_response = requests.get(buy_url, headers=headers, timeout=30)  # 5sim uses GET for buy usually

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

    def cancel_number(self, provider: str, number_id: str, api_key: str) -> bool:
        """Attempt to cancel or release a purchased number to avoid leaks on failure."""
        if not provider or not number_id or not api_key:
            logger.warning("Cancel number called with missing data; skipping")
            return False

        try:
            if provider == "sms-activate":
                cancel_url = (
                    "https://api.sms-activate.org/stubs/handler_api.php"
                    f"?api_key={api_key}&action=setStatus&status=8&id={number_id}"
                )
                response = requests.get(cancel_url, timeout=15)
                return response.status_code == 200 and response.text.startswith("ACCESS_")

            if provider == "5sim":
                headers = {"Authorization": f"Bearer {api_key}"}
                cancel_url = f"https://5sim.net/v1/user/cancel/{number_id}"
                response = requests.get(cancel_url, headers=headers, timeout=15)
                return response.status_code in (200, 204)

            if provider == "sms-hub":
                params = {
                    "api_key": api_key,
                    "action": "setStatus",
                    "status": "8",
                    "id": number_id
                }
                response = requests.get("https://smshub.org/stubs/handler_api.php", params=params, timeout=15)
                return response.status_code == 200 and response.text.startswith("ACCESS_")

            if provider == "smspool":
                payload = {"order_id": number_id, "cancel": True}
                response = requests.post("https://api.smspool.net/status", json=payload, timeout=15)
                return response.status_code == 200

            if provider == "textverified":
                headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
                response = requests.post(
                    "https://textverified.com/api/authorization/transactions/cancel",
                    json={"id": number_id},
                    headers=headers,
                    timeout=15
                )
                return response.status_code in (200, 204)

            if provider == "daisysms":
                headers = {"Authorization": f"Bearer {api_key}"}
                response = requests.post(
                    "https://api.daisysms.com/v1/orders/cancel",
                    json={"order_id": number_id},
                    headers=headers,
                    timeout=15
                )
                return response.status_code in (200, 204)

            logger.warning(f"Cancel not implemented for provider {provider}")
            return False
        except Exception as e:
            logger.warning(f"Failed to cancel number for provider {provider}: {e}")
            return False

    def get_sms_code(self, provider: str, number_id: str, api_key: str) -> Optional[str]:
        """Get SMS code for a phone number with retry logic (blocking wrapper)."""
        # Use asyncio to run the async version
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is already running, create a task
                import nest_asyncio
                nest_asyncio.apply()
                return loop.run_until_complete(self.get_sms_code_async(provider, number_id, api_key))
            else:
                return loop.run_until_complete(self.get_sms_code_async(provider, number_id, api_key))
        except Exception as e:
            logger.error(f"Failed to run async SMS retrieval: {e}")
            return None
    
    async def get_sms_code_async(
        self, 
        provider: str, 
        number_id: str, 
        api_key: str,
        progress_callback: Optional[callable] = None
    ) -> Optional[str]:
        """
        Get SMS code for a phone number with non-blocking retryable logic and jittered backoff.
        
        Args:
            provider: SMS provider name
            number_id: Provider-specific number/order ID
            api_key: Provider API key
            progress_callback: Optional callback for progress updates
            
        Returns:
            SMS code if received, None otherwise
        """
        if provider not in self.providers:
            logger.error(f"Provider '{provider}' not supported for SMS code retrieval")
            return None

        # Configure retry for SMS code retrieval with jittered exponential backoff
        max_attempts = 12  # More attempts to handle SMS delays
        base_delay = 5.0  # Start with 5 seconds
        max_delay = 60.0  # Cap at 60 seconds
        jitter_range = 0.3  # ±30% jitter

        for attempt in range(1, max_attempts + 1):
            try:
                # Calculate delay with exponential backoff and jitter
                if attempt > 1:
                    # Exponential backoff: base_delay * (2 ^ (attempt - 2))
                    delay = min(base_delay * (2 ** (attempt - 2)), max_delay)
                    
                    # Add jitter: random variation of ±jitter_range
                    jitter = delay * jitter_range * (2 * random.random() - 1)
                    actual_delay = delay + jitter
                    
                    # Clamp to reasonable bounds
                    actual_delay = max(1.0, min(actual_delay, max_delay))
                    
                    if progress_callback:
                        progress_callback(f"Waiting {actual_delay:.1f}s before attempt {attempt}/{max_attempts}")
                    
                    logger.debug(
                        f"SMS retrieval attempt {attempt}/{max_attempts} - "
                        f"waiting {actual_delay:.1f}s (base: {delay:.1f}s, jitter: {jitter:+.1f}s)"
                    )
                    
                    # Non-blocking sleep with cancellation support
                    await asyncio.sleep(actual_delay)
                
                # Progress update
                if progress_callback:
                    progress_callback(f"Checking SMS from {provider} (attempt {attempt}/{max_attempts})")
                
                # Attempt to retrieve SMS code (call in executor to not block)
                loop = asyncio.get_event_loop()
                code = await loop.run_in_executor(
                    None,
                    self._get_sms_code_sync,
                    provider,
                    number_id,
                    api_key
                )
                
                if code:
                    logger.info(f"✓ SMS code received from {provider} on attempt {attempt}")
                    return code
                
                # No code yet - log progress
                logger.debug(f"SMS not ready yet from {provider} (attempt {attempt}/{max_attempts})")
                
            except asyncio.CancelledError:
                logger.info(f"SMS retrieval cancelled for {provider}")
                raise
            
            except requests.exceptions.Timeout:
                logger.debug(f"{provider} SMS check timeout on attempt {attempt}, will retry...")
                
            except requests.exceptions.ConnectionError:
                logger.debug(f"{provider} SMS check connection error on attempt {attempt}, will retry...")
                
            except Exception as e:
                # Don't log full errors for "still waiting" scenarios
                if "STATUS_WAIT" not in str(e) and "not ready" not in str(e).lower():
                    logger.debug(f"SMS retrieval error from {provider} on attempt {attempt}: {e}")
        
        # All attempts exhausted
        logger.warning(
            f"❌ SMS code not received from {provider} after {max_attempts} attempts "
            f"(total wait time: ~{sum(min(base_delay * (2 ** i), max_delay) for i in range(max_attempts))/60:.1f}m)"
        )
        return None
    
    def _get_sms_code_sync(self, provider: str, number_id: str, api_key: str) -> Optional[str]:
        """Synchronous SMS code retrieval for use in executor."""
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
        except Exception as e:
            # Suppress expected "not ready yet" errors
            if "STATUS_WAIT" not in str(e) and "not ready" not in str(e).lower():
                logger.debug(f"SMS check error: {e}")
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

        self._photo_hash_file = Path("profile_photo_hashes.json")
        self._applied_photo_hashes = self._load_photo_hashes()
        
        # Proxy assignment tracking
        self.account_proxies: Dict[str, Dict] = {}  # phone_number -> proxy info
        
        # Cancellation tracking for cleanup
        self._active_resources: Dict[str, Dict[str, Any]] = {}  # session_id -> {proxy, phone, client}
        self._cleanup_lock = asyncio.Lock()
        
        # Concurrency control
        self._max_concurrent_creations = 5  # Default limit
        self._creation_semaphore = asyncio.Semaphore(self._max_concurrent_creations)
        
        # Audit logging integration
        self._audit_log = None
        if AUDIT_LOG_AVAILABLE:
            try:
                self._audit_log = get_audit_log()
                logger.info("✓ Audit logging enabled for account creation")
            except Exception as e:
                logger.warning(f"Failed to initialize audit log: {e}")
    
    def validate_bulk_run_preflight(
        self, 
        provider: str, 
        country: str, 
        api_key: str,
        requested_count: int
    ) -> Dict[str, Any]:
        """
        Validate bulk account creation run before starting.
        
        Performs:
        - Provider capability check
        - Country support verification
        - Inventory preflight
        - API key validation
        
        Args:
            provider: SMS provider name
            country: Target country code
            api_key: Provider API key
            requested_count: Number of accounts requested
            
        Returns:
            Dict with validation results and errors
        """
        errors = []
        warnings = []
        
        # Step 1: Provider capability check
        is_valid, capability_error = self.phone_provider.validate_provider_capability(provider, country)
        if not is_valid:
            errors.append(f"Provider capability: {capability_error}")
            return {
                'success': False,
                'errors': errors,
                'warnings': warnings,
                'can_proceed': False
            }
        
        # Step 2: API key validation
        if not api_key or len(api_key) < 10:
            errors.append("Invalid or missing API key")
        
        # Step 3: Inventory check
        try:
            inventory_result = self.phone_provider.check_inventory(provider, country, api_key, requested_count)
            
            if not inventory_result.get('success'):
                errors.append(f"Inventory check failed: {inventory_result.get('error', 'Unknown error')}")
            else:
                available = inventory_result.get('available', 0)
                if available < requested_count:
                    warnings.append(
                        f"Requested {requested_count} numbers but only {available} available. "
                        f"Run may fail partway through."
                    )
                
                if inventory_result.get('warning'):
                    warnings.append(inventory_result['warning'])
        except Exception as e:
            warnings.append(f"Could not verify inventory: {e}")
        
        # Step 4: Concurrency limits
        if requested_count > 10:
            warnings.append(
                f"Bulk run of {requested_count} accounts may trigger provider rate limits. "
                "Consider running in smaller batches or increasing delays."
            )
        
        return {
            'success': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'can_proceed': len(errors) == 0,
            'provider': provider,
            'country': country,
            'requested': requested_count
        }
    
    def set_max_concurrent_creations(self, limit: int):
        """
        Set maximum concurrent account creations.
        
        Prevents provider-side throttling and system overload.
        
        Args:
            limit: Maximum concurrent operations (1-20)
        """
        if not (1 <= limit <= 20):
            raise ValueError("Concurrency limit must be between 1 and 20")
        
        self._max_concurrent_creations = limit
        self._creation_semaphore = asyncio.Semaphore(limit)
        
        logger.info(f"Set max concurrent account creations to {limit}")
    
    def get_max_concurrent_creations(self) -> int:
        """Get current concurrency limit."""
        return self._max_concurrent_creations
    
    def get_active_creation_count(self) -> int:
        """Get number of currently active account creations."""
        return len(self._active_resources)
    
    async def create_account_with_concurrency(
        self,
        config: Dict[str, Any],
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Create account with concurrency limiting.
        
        This method enforces the concurrency limit using a semaphore.
        
        Args:
            config: Account configuration
            progress_callback: Optional progress callback
            
        Returns:
            Account creation result
        """
        async with self._creation_semaphore:
            if progress_callback:
                progress_callback(
                    f"Starting account creation "
                    f"(slot {self._max_concurrent_creations - self._creation_semaphore._value + 1}/"
                    f"{self._max_concurrent_creations})"
                )
            
            # Actual creation would go here - this is a wrapper
            # In real usage, this would call the actual create_account method
            # For now, returning placeholder
            logger.info(
                f"Account creation started with concurrency control "
                f"({self.get_active_creation_count()}/{self._max_concurrent_creations} slots used)"
            )
            
            return {
                'success': False,
                'message': 'Account creation method not implemented in wrapper',
                'concurrency_info': {
                    'max_concurrent': self._max_concurrent_creations,
                    'active_count': self.get_active_creation_count(),
                    'available_slots': self._creation_semaphore._value
                }
            }
        
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
            phone_number: Phone number for the account (will be normalized)
            
        Returns:
            Proxy configuration dict or None
        """
        # Normalize phone number for consistent proxy assignment
        from accounts.phone_normalizer import PhoneNormalizer
        phone_number = PhoneNormalizer.normalize(phone_number)
        
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

    async def _release_proxy_assignment(self, assigned_proxy: Dict, phone_number: Optional[str], temp_phone_id: str):
        """Release proxy assignments for failed account creation attempts."""
        identifier = phone_number or temp_phone_id
        pool = await self._get_proxy_pool_manager()

        if pool and assigned_proxy.get('source') == 'proxy_pool':
            try:
                await pool.release_proxy(identifier)
                logger.info(f"Released proxy assignment for {identifier}")
            except Exception as e:
                logger.warning(f"Failed to release proxy for {identifier}: {e}")

        # Clean local cache for both temp and phone identifiers
        if identifier in self.account_proxies:
            self.account_proxies.pop(identifier, None)
        if temp_phone_id in self.account_proxies:
            self.account_proxies.pop(temp_phone_id, None)

    async def _record_proxy_failure(self, assigned_proxy: Optional[Dict], phone_number: Optional[str]):
        """Mark proxy as failed/cooldown to avoid immediate reuse after Telegram errors."""
        if not assigned_proxy:
            return

        proxy_key = f"{assigned_proxy.get('ip')}:{assigned_proxy.get('port')}"
        logger.warning(f"Marking proxy {proxy_key} as failed for {phone_number}")

        pool = await self._get_proxy_pool_manager()
        if pool and assigned_proxy.get('source') == 'proxy_pool':
            try:
                await pool.release_proxy(phone_number)
            except Exception as e:
                logger.warning(f"Failed to release proxy after failure: {e}")
        else:
            self.proxy_manager.mark_proxy_failed(assigned_proxy)

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

    def _validate_provider_config(self, provider: str, country: str, api_key: Optional[str]) -> Optional[Dict[str, str]]:
        """Validate provider selection, country availability, and API key presence."""
        if provider not in self.phone_provider.providers:
            supported = ", ".join(sorted(self.phone_provider.providers.keys()))
            return {
                'success': False,
                'error': f"Unsupported phone provider '{provider}'. Choose one of: {supported}"
            }

        provider_config = self.phone_provider.providers.get(provider, {})
        supported_countries = provider_config.get('countries', [])
        if supported_countries and country not in supported_countries:
            return {
                'success': False,
                'error': f"Country '{country}' not supported by {provider}. Try one of: {', '.join(supported_countries)}"
            }

        if not api_key:
            return {
                'success': False,
                'error': f"Phone provider API key is required. Get it from your {provider} account dashboard."
            }

        return None

    def _preflight_number_inventory(self, count: int, config: Dict) -> Dict[str, Any]:
        """Best-effort check that a provider can supply the requested number of phone numbers."""
        country = config.get('country', 'US')
        provider = config.get('phone_provider', 'sms-activate')
        api_key = config.get('provider_api_key')

        validation = self._validate_provider_config(provider, country, api_key)
        if validation:
            return validation

        check_result = self.phone_provider.check_inventory(provider, country, api_key, count)
        if not check_result.get('success'):
            return {
                'success': False,
                'error': check_result.get('error', 'Phone provider inventory preflight failed')
            }

        available = check_result.get('available')
        warning = check_result.get('warning')

        if available is not None and available < count:
            return {
                'success': False,
                'error': (
                    f"Only {available} numbers available from {provider} for {country}, "
                    f"but {count} requested. Reduce the batch size or switch providers."
                )
            }

        if warning:
            logger.warning(warning)

        return {'success': True}

    def _get_delay_range(self, config: Dict, realistic_timing: bool) -> Tuple[float, float]:
        """Return (min_delay, max_delay) for inter-account waits."""
        delay_config = config.get('inter_account_delay') or {}
        if realistic_timing:
            default_min, default_max = 30.0, 60.0
        else:
            default_min, default_max = 5.0, 5.0

        min_delay = float(delay_config.get('min', default_min))
        max_delay = float(delay_config.get('max', default_max))

        # Ensure sane ordering
        if max_delay < min_delay:
            max_delay = min_delay

        return min_delay, max_delay

    async def _sleep_with_cancellation(self, delay: float):
        """Sleep in short intervals so bulk creation can stop promptly."""
        slept = 0.0
        step = min(1.0, delay)
        while slept < delay and self.creation_active:
            await asyncio.sleep(step)
            slept += step

    async def start_bulk_creation(self, count: int, config: Dict) -> List[Dict]:
        """Start bulk account creation."""
        self.creation_active = True
        results = []
        self.creation_stats['total_attempted'] = 0
        self.creation_stats['total_successful'] = 0
        self.creation_stats['total_failed'] = 0

        logger.info(f"Starting bulk creation of {count} accounts")

        inventory_check = self._preflight_number_inventory(count, config)
        if not inventory_check.get('success'):
            error = inventory_check.get('error', 'Phone number inventory check failed')
            logger.error(error)
            self.creation_active = False
            return [{'success': False, 'error': error}]

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
                min_delay, max_delay = self._get_delay_range(config, config.get('realistic_timing', False))
                delay = random.uniform(min_delay, max_delay)
                self._notify_progress(i+1, count, f"Waiting {delay:.0f}s before next account...")
                await self._sleep_with_cancellation(delay)

        self.creation_active = False
        return results
    
    def stop_creation(self):
        """Stop the creation process."""
        self.creation_active = False

    async def create_new_account(self, config: Dict) -> Dict[str, Any]:
        """Create a single new Telegram account with proxy pool integration."""
        temp_phone_id = f"temp_{int(time.time() * 1000)}"
        assigned_proxy = None
        phone_data: Optional[Dict[str, Any]] = None
        phone_number: Optional[str] = None
        client: Optional[Client] = None
        creation_success = False
        previous_creation_active = self.creation_active
        self.creation_active = True

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

            country = config.get('country', 'US')
            provider = config.get('phone_provider', 'sms-activate')
            api_key = config.get('provider_api_key')

            provider_validation = self._validate_provider_config(provider, country, api_key)
            if provider_validation:
                return provider_validation

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

            phone_data = await asyncio.to_thread(self.phone_provider.get_number, provider, country, api_key)
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
                await self._record_proxy_failure(assigned_proxy, phone_number)
                return {
                    'success': False,
                    'error': f"⏱️ Rate limit reached. Telegram requires waiting {e.value} seconds. Try again later."
                }
            except PhoneNumberInvalid as e:
                await self._record_proxy_failure(assigned_proxy, phone_number)
                return {
                    'success': False,
                    'error': translate_error(e, "sending verification code")
                }
            except Exception as e:
                await self._record_proxy_failure(assigned_proxy, phone_number)
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
                await self._record_proxy_failure(assigned_proxy, phone_number)
                return {
                    'success': False,
                    'error': translate_error(e, "signing in")
                }
            except PhoneCodeInvalid as e:
                await self._record_proxy_failure(assigned_proxy, phone_number)
                return {
                    'success': False,
                    'error': translate_error(e, "verifying code")
                }
            except PhoneCodeExpired as e:
                await self._record_proxy_failure(assigned_proxy, phone_number)
                return {
                    'success': False,
                    'error': translate_error(e, "verifying code")
                }
            except Exception as e:
                await self._record_proxy_failure(assigned_proxy, phone_number)
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
                'is_warmed_up': bool(config.get('is_warmed_up', False)),
                'warmup_stage': 'pending',
                'messages_sent': 0,
                'last_active': datetime.now().isoformat(),
                'api_id': config.get('api_id'),
                'api_hash': config.get('api_hash')
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
            creation_success = True
            return {'success': True, 'account': account_info, 'message': '✅ Account created successfully!'}

        except Exception as e:
            logger.error(f"Account creation failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': translate_error(e, "account creation")
            }
        finally:
            # Restore prior creation flag so manual single runs don't leave it stuck
            self.creation_active = previous_creation_active

            # Disconnect client regardless of outcome
            if client:
                try:
                    await client.disconnect()
                except Exception as e:
                    logger.warning(f"Failed to disconnect client: {e}")

            # Release or mark proxy failures when creation did not complete
            if not creation_success and assigned_proxy:
                await self._record_proxy_failure(assigned_proxy, phone_number or temp_phone_id)
                await self._release_proxy_assignment(assigned_proxy, phone_number, temp_phone_id)

            # Cancel phone number order when creation fails mid-flow
            if not creation_success and phone_data:
                try:
                    await asyncio.to_thread(
                        self.phone_provider.cancel_number,
                        phone_data.get('provider'),
                        phone_data.get('id'),
                        config.get('provider_api_key')
                    )
                except Exception as e:
                    logger.warning(f"Failed to cancel phone order: {e}")

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
            if not self.creation_active:
                return None

            sms_code = await asyncio.to_thread(
                self.phone_provider.get_sms_code,
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
            await self._sleep_with_cancellation(check_delay)

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

            # STEP 2: Profile photo (if specified) - with stealth update/skip when already applied
            if config.get("profile_photo"):
                photo_delay = self.anti_detection.simulate_profile_setup(session_id, "photo")
                await asyncio.sleep(photo_delay)

                try:
                    # Use duplicate-aware photo update to avoid unnecessary profile churn
                    await self._set_profile_photo_stealth(client, config["profile_photo"],
                                                         allow_skip=True)
                    logger.info("📸 Profile photo set (stealth-aware mode)")
                except Exception as e:
                    logger.warning(f"Failed to set profile photo: {e}")

            # STEP 3: Bio setup
            bio_delay = self.anti_detection.simulate_profile_setup(session_id, "bio")
            await asyncio.sleep(bio_delay)
            await self._set_profile_bio(client, config)

        except Exception as e:
            logger.error(f"Profile setup failed: {e}")

    def _generate_realistic_name(self, country: str) -> Tuple[str, str]:
        """Generate a realistic name for the given country with regional variety."""
        regional_names = {
            "US": {
                "first": ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles",
                          "Emily", "Sophia", "Ava", "Olivia", "Isabella", "Mia", "Charlotte", "Amelia", "Harper", "Evelyn"],
                "last": ["Smith", "Johnson", "Williams", "Jones", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor",
                         "Anderson", "Martin", "Thompson", "Garcia", "Martinez", "Robinson", "Clark", "Rodriguez", "Lewis", "Lee"],
            },
            "RU": {
                "first": ["Alexander", "Dmitry", "Sergey", "Andrey", "Alexey", "Anna", "Maria", "Elena", "Olga", "Natalia"],
                "last": ["Ivanov", "Petrov", "Sidorov", "Smirnov", "Kuznetsov", "Volkov", "Fedorov", "Morozov", "Sokolov", "Popov"],
            },
            "BR": {
                "first": ["João", "Gabriel", "Miguel", "Arthur", "Maria", "Ana", "Julia", "Mariana", "Beatriz", "Laura"],
                "last": ["Silva", "Santos", "Oliveira", "Souza", "Rodrigues", "Almeida", "Costa", "Gomes", "Martins", "Carvalho"],
            },
            "IN": {
                "first": ["Aarav", "Vihaan", "Vivaan", "Aditya", "Ananya", "Aadhya", "Pari", "Diya", "Myra", "Isha"],
                "last": ["Sharma", "Verma", "Singh", "Patel", "Gupta", "Khan", "Reddy", "Nair", "Kapoor", "Joshi"],
            },
            "ES": {
                "first": ["Alejandro", "Daniel", "Pablo", "Adrián", "Lucas", "Lucía", "Sofía", "Martina", "Emma", "Julia"],
                "last": ["García", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Fernández", "Díaz", "Moreno", "Muñoz"],
            },
            "JP": {
                "first": ["Haruto", "Yuto", "Sota", "Yuki", "Hina", "Yui", "Sakura", "Mio", "Rin", "Mei"],
                "last": ["Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe", "Ito", "Yamamoto", "Nakamura", "Kobayashi", "Kato"],
            },
            "AU": {
                "first": ["Jack", "Noah", "William", "Olivia", "Isla", "Charlotte", "Amelia", "Evie", "Lucas", "Liam"],
                "last": ["Smith", "Jones", "Williams", "Brown", "Wilson", "Taylor", "Johnson", "Martin", "Anderson", "Thompson"],
            },
        }

        pool = regional_names.get(country.upper()) or regional_names.get("US")
        return random.choice(pool["first"]), random.choice(pool["last"])

    async def _generate_and_set_username(self, client: Client, max_attempts: int = 25):
        """
        Generate and set a username with improved collision detection and iteration.
        
        Features:
        - Multiple candidate generation strategies
        - Increased retry pool (25 attempts vs 10)
        - Varied username patterns to reduce collisions
        - Detailed logging of collision attempts
        - Fallback to simpler patterns on repeated failures
        
        Args:
            client: Pyrogram client
            max_attempts: Maximum username generation attempts
        """
        try:
            me = await client.get_me()
            base = (me.first_name or "user").lower().replace(" ", "_")
            base = ''.join(c for c in base if c.isalnum() or c == '_')[:10]  # Sanitize
            
            last_error: Optional[Exception] = None
            collision_count = 0
            
            # Strategy 1: base + 5-digit random (attempts 1-10)
            for attempt in range(1, min(11, max_attempts + 1)):
                candidate = f"{base}_{random.randint(10000, 99999)}"
                try:
                    await client.set_username(candidate)
                    logger.info(
                        f"✓ Username set to {candidate} "
                        f"(strategy: base+5digits, attempt {attempt}, collisions: {collision_count})"
                    )
                    return
                except UsernameOccupied:
                    collision_count += 1
                    logger.debug(f"Username {candidate} occupied (collision #{collision_count})")
                    last_error = UsernameOccupied("Username occupied")
                    continue
                except UsernameInvalid as exc:
                    logger.debug(f"Username {candidate} invalid: {exc}")
                    last_error = exc
                    continue
            
            # Strategy 2: base + timestamp fragment (attempts 11-15)
            for attempt in range(11, min(16, max_attempts + 1)):
                timestamp_fragment = str(int(datetime.now().timestamp()))[-6:]
                candidate = f"{base}{timestamp_fragment}"
                try:
                    await client.set_username(candidate)
                    logger.info(
                        f"✓ Username set to {candidate} "
                        f"(strategy: base+timestamp, attempt {attempt}, collisions: {collision_count})"
                    )
                    return
                except (UsernameOccupied, UsernameInvalid) as exc:
                    collision_count += 1
                    last_error = exc
                    continue
            
            # Strategy 3: random word + number (attempts 16-25)
            random_words = ["cool", "pro", "smart", "tech", "dev", "user", "ace", "star", "neo", "zen"]
            for attempt in range(16, max_attempts + 1):
                word = random.choice(random_words)
                candidate = f"{word}_{random.randint(1000, 9999)}_{base[:4]}"
                try:
                    await client.set_username(candidate)
                    logger.info(
                        f"✓ Username set to {candidate} "
                        f"(strategy: word+num+base, attempt {attempt}, collisions: {collision_count})"
                    )
                    return
                except (UsernameOccupied, UsernameInvalid) as exc:
                    collision_count += 1
                    last_error = exc
                    continue
            
            # All attempts exhausted
            logger.error(
                f"❌ Failed to set username after {max_attempts} attempts "
                f"({collision_count} collisions). Last error: {last_error}"
            )
            
            # Log to audit if available
            try:
                from accounts.account_audit_log import get_audit_log, AuditEvent, AuditEventType
                audit = get_audit_log()
                audit.log_event(AuditEvent(
                    event_id=None,
                    phone_number=me.phone_number or "unknown",
                    event_type=AuditEventType.USERNAME_COLLISION,
                    timestamp=datetime.now(),
                    username_attempted=base,
                    username_success=False,
                    error_message=f"Failed after {max_attempts} attempts, {collision_count} collisions",
                    metadata={'collision_count': collision_count, 'last_error': str(last_error)}
                ))
            except Exception as e:
                logger.debug(f"Could not log username collision to audit: {e}")
                
        except Exception as e:
            logger.warning(f"Failed to set username: {e}")

    def _load_photo_hashes(self) -> set:
        """Load persisted profile photo hashes to prevent duplicate uploads."""
        try:
            if self._photo_hash_file.exists():
                with open(self._photo_hash_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('hashes', []))
        except Exception as exc:
            logger.warning(f"Failed to load photo hash cache: {exc}")
        return set()

    def _save_photo_hashes(self):
        """Persist profile photo hashes for reuse across sessions."""
        try:
            with open(self._photo_hash_file, 'w') as f:
                json.dump({'hashes': list(self._applied_photo_hashes)}, f, indent=2)
        except Exception as exc:
            logger.warning(f"Failed to persist photo hash cache: {exc}")

    async def _set_profile_photo_stealth(self, client: Client, photo_path: str, allow_skip: bool = False):
        """Set profile photo with validation and stealth mode."""
        if not hasattr(self, "_applied_photo_hashes"):
            self._applied_photo_hashes = set()

        photo_file = Path(photo_path)
        
        # Validate photo exists
        if not photo_file.exists():
            raise FileNotFoundError(f"Profile photo {photo_path} does not exist")
        
        # Validate photo format
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
        if photo_file.suffix.lower() not in valid_extensions:
            raise ValueError(f"Invalid photo format: {photo_file.suffix}. Must be one of {valid_extensions}")
        
        # Validate photo size (max 10MB for Telegram)
        max_size_mb = 10
        file_size_mb = photo_file.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(f"Photo too large: {file_size_mb:.1f}MB (max {max_size_mb}MB)")
        
        # Validate image is readable
        try:
            from PIL import Image
            with Image.open(photo_file) as img:
                # Validate dimensions (min 160x160, max 2560x2560 recommended)
                width, height = img.size
                if width < 160 or height < 160:
                    logger.warning(f"Photo dimensions too small: {width}x{height} (min 160x160 recommended)")
                if width > 5000 or height > 5000:
                    raise ValueError(f"Photo dimensions too large: {width}x{height} (max 5000x5000)")
        except ImportError:
            logger.warning("PIL not available, skipping image validation")
        except Exception as e:
            raise ValueError(f"Invalid image file: {e}")

        photo_hash = hashlib.sha256(photo_file.read_bytes()).hexdigest()
        if allow_skip and photo_hash in self._applied_photo_hashes:
            logger.info("Profile photo already applied for this session; skipping to avoid churn")
            return

        await client.set_profile_photo(photo=photo_path)
        self._applied_photo_hashes.add(photo_hash)
        self._save_photo_hashes()

    async def _set_profile_bio(self, client: Client, config: Dict):
        """Populate the account bio with regionalized defaults when provided."""
        bio_text = config.get("bio")
        persona_template = config.get("persona_template")
        persona_templates = config.get("persona_templates") or {}
        persona = config.get("persona")
        if not bio_text:
            region = config.get("country", "US").upper()
            templates = {
                "US": "Explorer. Building connections.",
                "RU": "Исследую новое. Открыт к общению.",
                "IN": "Here to collaborate and learn.",
                "BR": "Conectando pessoas e ideias.",
                "ES": "Compartiendo y descubriendo novedades.",
            }
            if persona_templates:
                candidate = persona_templates.get(region) or persona_templates.get("default")
                if candidate:
                    bio_text = candidate.format(region=region, persona=persona or "")

            if not bio_text and persona_template:
                bio_text = persona_template.format(region=region, persona=persona or "")

            if not bio_text:
                bio_text = templates.get(region, "Open to new conversations.")

        # Sanitize bio text for safety
        from utils.input_validation import sanitize_html
        bio_text = sanitize_html(bio_text)[:70]  # Telegram bio limit
        
        try:
            await client.update_profile(bio=bio_text)
            logger.info("✏️ Bio configured")
        except Exception as exc:
            logger.warning(f"Failed to set bio: {exc}")
    
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
                    proxy_used, device_fingerprint, api_id, api_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_info['phone_number'],
                account_info['session_name'],
                account_info.get('status', 'active'),
                account_info['created_at'],
                account_info.get('last_active', datetime.now().isoformat()),
                account_info.get('messages_sent', 0),
                int(account_info.get('is_warmed_up', False)),
                account_info.get('warmup_stage', 'pending'),
                str(account_info.get('proxy', '')),
                str(account_info.get('device_fingerprint', '')),
                account_info.get('api_id'),
                account_info.get('api_hash')
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ ACTUALLY saved account {account_info['phone_number']} to database")
            
        except Exception as e:
            logger.error(f"Failed to save account to database: {e}", exc_info=True)
            raise
    
    def _register_active_resources(
        self, 
        session_id: str, 
        proxy: Optional[Dict] = None,
        phone_data: Optional[Dict] = None,
        client: Optional[Client] = None
    ):
        """Register active resources for centralized cleanup on cancellation."""
        if session_id not in self._active_resources:
            self._active_resources[session_id] = {}
        
        if proxy:
            self._active_resources[session_id]['proxy'] = proxy
        if phone_data:
            self._active_resources[session_id]['phone_data'] = phone_data
        if client:
            self._active_resources[session_id]['client'] = client
    
    async def _cleanup_session_resources(self, session_id: str, reason: str = "cleanup"):
        """
        Centralized cleanup of all resources for a session.
        
        Ensures:
        - Proxy is released back to pool
        - Phone number is cancelled with provider
        - Client connection is properly closed
        
        Args:
            session_id: Session identifier
            reason: Reason for cleanup (for logging)
        """
        async with self._cleanup_lock:
            if session_id not in self._active_resources:
                return
            
            resources = self._active_resources[session_id]
            cleanup_results = []
            
            # 1. Close client connection
            client = resources.get('client')
            if client:
                try:
                    await client.stop()
                    cleanup_results.append("✓ Client connection closed")
                except Exception as e:
                    cleanup_results.append(f"✗ Client close error: {e}")
                    logger.warning(f"Failed to close client for {session_id}: {e}")
            
            # 2. Cancel phone number with provider
            phone_data = resources.get('phone_data')
            if phone_data:
                try:
                    provider = phone_data.get('provider')
                    number_id = phone_data.get('id')
                    api_key = phone_data.get('api_key')
                    
                    if provider and number_id and api_key:
                        success = self.phone_provider.cancel_number(provider, number_id, api_key)
                        if success:
                            cleanup_results.append(f"✓ Phone number cancelled ({provider})")
                        else:
                            cleanup_results.append(f"✗ Phone cancellation failed ({provider})")
                    else:
                        cleanup_results.append("⚠ Incomplete phone data for cancellation")
                except Exception as e:
                    cleanup_results.append(f"✗ Phone cancel error: {e}")
                    logger.warning(f"Failed to cancel phone for {session_id}: {e}")
            
            # 3. Release proxy back to pool
            proxy = resources.get('proxy')
            if proxy:
                try:
                    # If using proxy pool manager
                    if self._proxy_pool_manager:
                        phone_number = resources.get('phone_number')
                        if phone_number:
                            await self._proxy_pool_manager.release_proxy(phone_number)
                            cleanup_results.append("✓ Proxy released to pool")
                    else:
                        # Mark proxy as available in basic manager
                        self.proxy_manager.mark_proxy_used(proxy)
                        cleanup_results.append("✓ Proxy marked as available")
                except Exception as e:
                    cleanup_results.append(f"✗ Proxy release error: {e}")
                    logger.warning(f"Failed to release proxy for {session_id}: {e}")
            
            # Remove from active resources
            del self._active_resources[session_id]
            
            logger.info(
                f"🧹 Cleaned up session {session_id} ({reason}):\n"
                + "\n".join(f"   {result}" for result in cleanup_results)
            )
    
    async def cancel_all_active_sessions(self):
        """Cancel all active account creation sessions and clean up resources."""
        self.creation_active = False
        
        session_ids = list(self._active_resources.keys())
        if not session_ids:
            logger.info("No active sessions to cancel")
            return
        
        logger.info(f"🛑 Cancelling {len(session_ids)} active account creation session(s)")
        
        # Cleanup all sessions concurrently
        tasks = [
            self._cleanup_session_resources(session_id, reason="cancellation")
            for session_id in session_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if not isinstance(r, Exception))
        error_count = len(results) - success_count
        
        logger.info(
            f"✅ Cancellation complete: {success_count} successful, {error_count} errors"
        )
            
