"""
Service Container - Dependency injection and service management.
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ai.gemini_service import GeminiService
from anti_detection.anti_detection_system import AntiDetectionSystem
from core.config_manager import ConfigurationManager
from integrations.api_key_manager import APIKeyManager
from scraping.database import MemberDatabase

# TelegramClient will be imported lazily in the factory method

logger = logging.getLogger(__name__)


class EventSystem:
    """Simple event system for decoupled communication."""

    def __init__(self):
        self._subscribers: Dict[str, List[callable]] = {}

    def subscribe(self, event_type: str, callback: callable):
        """Subscribe to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def publish(self, event_type: str, data=None):
        """Publish an event to all subscribers."""
        if event_type in self._subscribers:
            for callback in self._subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in event callback for {event_type}: {e}")


# Abstract base classes for dependency injection and loose coupling
class IService(ABC):
    """Abstract base class for all services."""

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the service."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the service."""
        pass


class IMessageService(IService):
    """Abstract interface for message handling services."""

    @abstractmethod
    async def send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a chat."""
        pass

    @abstractmethod
    async def receive_message(self, message: Any) -> None:
        """Handle incoming message."""
        pass


class IAIService(IService):
    """Abstract interface for AI services."""

    @abstractmethod
    async def generate_response(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Generate AI response for a message."""
        pass

    @abstractmethod
    def update_configuration(self, config: Dict[str, Any]) -> None:
        """Update AI service configuration."""
        pass


class IDatabaseService(IService):
    """Abstract interface for database services."""

    @abstractmethod
    def save_data(self, table: str, data: Dict[str, Any]) -> bool:
        """Save data to database."""
        pass

    @abstractmethod
    def get_data(
        self, table: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve data from database."""
        pass

    @abstractmethod
    def create_backup(self) -> str:
        """Create database backup."""
        pass


class IAntiDetectionService(IService):
    """Abstract interface for anti-detection services."""

    @abstractmethod
    def apply_stealth_measures(self) -> None:
        """Apply anti-detection measures."""
        pass

    @abstractmethod
    def randomize_behavior(self) -> Dict[str, Any]:
        """Generate randomized behavior parameters."""
        pass


class ServiceContainer:
    """Dependency injection container for managing service dependencies."""

    def __init__(self):
        self._services: Dict[str, Any] = {}
        self._singletons: Dict[str, Any] = {}
        self._factories: Dict[str, callable] = {}

    def register(self, interface: type, implementation: type, singleton: bool = True):
        """Register a service implementation."""
        service_name = interface.__name__
        if singleton:
            self._singletons[service_name] = None
        self._factories[service_name] = implementation

    def register_instance(self, interface: type, instance: Any):
        """Register a pre-created service instance."""
        service_name = interface.__name__
        self._singletons[service_name] = instance

    def resolve(self, interface: type) -> Any:
        """Resolve a service instance."""
        service_name = interface.__name__

        # Return singleton if it exists
        if service_name in self._singletons and self._singletons[service_name] is not None:
            return self._singletons[service_name]

        # Create new instance if factory exists
        if service_name in self._factories:
            implementation = self._factories[service_name]
            instance = implementation()

            # Store as singleton if registered as such
            if service_name in self._singletons:
                self._singletons[service_name] = instance

            return instance

        raise ValueError(f"Service {service_name} not registered")

    def has_service(self, interface: type) -> bool:
        """Check if a service is registered."""
        service_name = interface.__name__
        return service_name in self._factories or service_name in self._singletons

    async def initialize_all_services(self) -> bool:
        """Initialize all registered services."""
        success = True
        for service_name, instance in self._singletons.items():
            if instance is not None and hasattr(instance, "initialize"):
                try:
                    if asyncio.iscoroutinefunction(instance.initialize):
                        result = await instance.initialize()
                    else:
                        result = instance.initialize()
                    if not result:
                        logger.error(f"Failed to initialize service {service_name}")
                        success = False
                except Exception as e:
                    logger.error(f"Error initializing service {service_name}: {e}")
                    success = False

        return success

    async def shutdown_all_services(self) -> None:
        """Shutdown all registered services."""
        for service_name, instance in self._singletons.items():
            if instance is not None and hasattr(instance, "shutdown"):
                try:
                    if asyncio.iscoroutinefunction(instance.shutdown):
                        await instance.shutdown()
                    else:
                        instance.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down service {service_name}: {e}")


# Adapter classes to implement interfaces and reduce coupling
class TelegramMessageService(IMessageService):
    """Adapter for Telegram message service."""

    def __init__(self, telegram_client=None):
        self._telegram_client = telegram_client

    async def initialize(self) -> bool:
        """Initialize the message service."""
        if self._telegram_client:
            return await self._telegram_client.initialize()
        return False

    async def shutdown(self) -> None:
        """Shutdown the message service."""
        if self._telegram_client and hasattr(self._telegram_client, "shutdown"):
            await self._telegram_client.shutdown()

    async def send_message(self, chat_id: int, text: str) -> bool:
        """Send a message to a chat."""
        if self._telegram_client:
            return await self._telegram_client.send_message(chat_id, text)
        return False

    async def receive_message(self, message: Any) -> None:
        """Handle incoming message."""
        if self._telegram_client:
            await self._telegram_client.receive_message(message)


class GeminiAIService(IAIService):
    """Adapter for Gemini AI service."""

    def __init__(self, gemini_service=None, api_key_manager=None):
        self._gemini_service = gemini_service
        self.api_key_manager = api_key_manager or APIKeyManager()

    async def initialize(self) -> bool:
        """Initialize the AI service."""
        # GeminiService initializes itself in __init__, so just check if it exists
        return self._gemini_service is not None

    async def shutdown(self) -> None:
        """Shutdown the AI service."""
        if self._gemini_service and hasattr(self._gemini_service, "shutdown"):
            await self._gemini_service.shutdown()

    async def generate_response(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Generate AI response for a message."""
        if self._gemini_service:
            chat_id = context.get("chat_id", 0) if context else 0
            return await self._gemini_service.generate_reply(message, chat_id)
        return None

    def update_configuration(self, config: Dict[str, Any]) -> None:
        """Update AI service configuration."""
        if "api_key" in config and config["api_key"].strip():
            # Add/update API key through the manager
            self.api_key_manager.add_api_key("gemini", config["api_key"].strip())

            # Get the validated key for the service
            validated_key = self.api_key_manager.get_api_key("gemini")
            if validated_key and self._gemini_service:
                self._gemini_service.update_api_key(validated_key)

        if self._gemini_service:
            if "brain_prompt" in config:
                self._gemini_service.set_brain_prompt(config["brain_prompt"])


class SQLiteDatabaseService(IDatabaseService):
    """Adapter for SQLite database service."""

    def __init__(self, db_service=None):
        self._db_service = db_service

    async def initialize(self) -> bool:
        """Initialize the database service."""
        if self._db_service:
            try:
                self._db_service.init_database()
                return True
            except Exception as e:
                logger.error(f"Failed to initialize database: {e}")
                return False
        return False

    async def shutdown(self) -> None:
        """Shutdown the database service."""
        # SQLite doesn't need explicit shutdown
        pass

    def save_data(self, table: str, data: Dict[str, Any]) -> bool:
        """Save data to database."""
        if self._db_service:
            try:
                method_name = f"save_{table.rstrip('s')}"  # save_member, save_channel, etc.
                if hasattr(self._db_service, method_name):
                    method = getattr(self._db_service, method_name)
                    method(**data)
                    return True
                else:
                    logger.error(f"Unknown table method: {method_name}")
                    return False
            except Exception as e:
                logger.error(f"Failed to save data to {table}: {e}")
                return False
        return False

    def get_data(
        self, table: str, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve data from database."""
        if self._db_service:
            try:
                method_name = f"get_{table}"  # get_members_by_activity, etc.
                if hasattr(self._db_service, method_name):
                    method = getattr(self._db_service, method_name)
                    if filters:
                        return method(**filters)
                    else:
                        return method()
                else:
                    logger.error(f"Unknown table method: {method_name}")
                    return []
            except Exception as e:
                logger.error(f"Failed to get data from {table}: {e}")
                return []
        return []

    def create_backup(self) -> str:
        """Create database backup."""
        if self._db_service:
            try:
                return self._db_service.create_backup()
            except Exception as e:
                logger.error(f"Failed to create database backup: {e}")
                return ""
        return ""


class AntiDetectionServiceAdapter(IAntiDetectionService):
    """Adapter for anti-detection service."""

    def __init__(self, anti_detection_service=None):
        self._anti_detection_service = anti_detection_service

    async def initialize(self) -> bool:
        """Initialize the anti-detection service."""
        if self._anti_detection_service:
            try:
                self._anti_detection_service.activate()
                return True
            except Exception as e:
                logger.error(f"Failed to initialize anti-detection service: {e}")
                return False
        return False

    async def shutdown(self) -> None:
        """Shutdown the anti-detection service."""
        # Anti-detection service doesn't need explicit shutdown
        pass

    def apply_stealth_measures(self) -> None:
        """Apply anti-detection measures."""
        if self._anti_detection_service:
            self._anti_detection_service.apply_stealth_measures()

    def randomize_behavior(self) -> Dict[str, Any]:
        """Generate randomized behavior parameters."""
        if self._anti_detection_service:
            return self._anti_detection_service.randomize_behavior()
        return {}


class ServiceFactory:
    """Factory helpers for constructing service adapters."""

    @staticmethod
    def create_telegram_client(config_manager: ConfigurationManager) -> TelegramMessageService:
        # Lazy import TelegramClient to avoid startup hangs
        TelegramClient = None
        try:
            from telegram.telegram_client import TelegramClient
        except Exception as e:
            logger.warning(f"TelegramClient import failed, using fallback: {e}")

        # Get API credentials from secrets manager
        api_id = config_manager.get_telegram_api_id() or os.getenv("TELEGRAM_API_ID", "")
        api_hash = config_manager.get_telegram_api_hash() or os.getenv("TELEGRAM_API_HASH", "")

        if not api_id or not api_hash:
            logger.warning(
                "Telegram API credentials not configured. "
                "Please set them in Settings > API & Auth or environment variables (TELEGRAM_API_ID, TELEGRAM_API_HASH)."
            )
            # Create a fallback client
            if TelegramClient:
                telegram_client = TelegramClient(
                    api_id="",  # Empty credentials will cause graceful failure
                    api_hash="",
                    phone_number="",
                )
            else:
                logger.error("TelegramClient not available due to import issues")
                # Create a mock client for when Pyrogram import fails
                telegram_client = None
        else:
            # Get phone number from config
            telegram_cfg = config_manager.get("telegram", {})
            phone_number = telegram_cfg.get("phone_number", "")
            telegram_client = TelegramClient(
                api_id=api_id, api_hash=api_hash, phone_number=phone_number
            )
        return TelegramMessageService(telegram_client)

    @staticmethod
    def create_ai_service(config_manager: ConfigurationManager) -> GeminiAIService:
        # Get API key from secrets manager or environment
        api_key = config_manager.get_gemini_api_key() or os.getenv("GEMINI_API_KEY", "") or ""

        if not api_key:
            logger.warning("Gemini API key not configured, creating service without API key")
            # Create a minimal service that won't try to initialize Gemini
            gemini_service = GeminiService("", performance=config_manager.get("performance", {}))
            ai_adapter = GeminiAIService(gemini_service, APIKeyManager())
            return ai_adapter

        performance_cfg = config_manager.get("performance", {})
        gemini_service = GeminiService(api_key, performance=performance_cfg)
        ai_adapter = GeminiAIService(gemini_service, APIKeyManager())
        ai_adapter.update_configuration({"api_key": api_key})
        return ai_adapter

    @staticmethod
    def create_database_service(config_manager: ConfigurationManager) -> SQLiteDatabaseService:
        db_path = config_manager.get("database_path", "members.db")
        member_db = MemberDatabase(db_path)
        return SQLiteDatabaseService(member_db)

    @staticmethod
    def create_anti_detection_service(
        config_manager: ConfigurationManager,
    ) -> AntiDetectionServiceAdapter:
        anti_detection_service = AntiDetectionSystem()
        return AntiDetectionServiceAdapter(anti_detection_service)
