"""
Telegram Worker - Thread-based Telegram client operations.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from pyrogram.errors import AuthKeyUnregistered

from ai.gemini_service import GeminiService
from monitoring.performance_monitor import NetworkRecoveryManager, RateLimiter
from telegram.telegram_client import TelegramClient

if TYPE_CHECKING:
    from monitoring.performance_monitor import NetworkRecoveryManager  # noqa: F811

logger = logging.getLogger(__name__)

# Constants (should be imported from main, but avoiding circular imports)
TELEGRAM_MESSAGE_TIMEOUT = 30  # seconds


class WorkerSignals(QObject):
    """Signals for the worker thread."""

    log_message = pyqtSignal(str)
    status_update = pyqtSignal(str, str)  # message, color
    auth_required = pyqtSignal()
    auth_success = pyqtSignal()
    auth_failed = pyqtSignal(str)
    auth_failed_unregistered = pyqtSignal(str)  # New signal for session revocation


class TelegramWorker(QThread):
    """Worker thread for running Telegram client operations."""

    def __init__(
        self,
        telegram_client: TelegramClient,
        gemini_service: GeminiService,
        rate_limiter: RateLimiter = None,
        network_recovery: NetworkRecoveryManager = None,
    ):
        super().__init__()
        self.telegram_client = telegram_client
        self.gemini_service = gemini_service
        self.rate_limiter = rate_limiter or RateLimiter()
        self.network_recovery = network_recovery or NetworkRecoveryManager()
        self.signals = WorkerSignals()
        self.running = False
        self.connection_attempts = 0
        self.max_connection_attempts = 10

    def run(self):
        """Run the Telegram client in a separate thread."""
        try:
            self.running = True
            asyncio.run(self._run_client())
        except Exception as e:
            self.signals.log_message.emit(f"❌ Worker thread error: {e}")
            self.signals.status_update.emit(f"Error: {str(e)}", "red")

    async def _run_client(self):
        """Initialize and run the Telegram client."""
        while self.running and self.connection_attempts < self.max_connection_attempts:
            try:
                self.signals.status_update.emit("Initializing Telegram client...", "orange")

                # Check if we should attempt recovery
                if self.connection_attempts > 0:
                    if not self.network_recovery.should_attempt_recovery("telegram"):
                        self.signals.log_message.emit("Maximum connection attempts exceeded")
                        break

                    delay = self.network_recovery.get_recovery_delay("telegram")
                    if delay > 0:
                        self.signals.log_message.emit(
                            f"Waiting {delay:.1f}s before reconnection attempt"
                        )
                        await asyncio.sleep(delay)

                # Initialize client
                success = await self.telegram_client.initialize()
                if not success:
                    self.connection_attempts += 1
                    self.network_recovery.record_recovery_attempt("telegram")
                    self.signals.log_message.emit(
                        f"Failed to initialize Telegram client (attempt {self.connection_attempts})"
                    )
                    continue

                # Reset recovery state on success
                self.network_recovery.record_successful_connection("telegram")
                self.connection_attempts = 0

                self.signals.auth_success.emit()
                self.signals.status_update.emit("Connected to Telegram", "green")
                self.signals.log_message.emit("Telegram client connected successfully")

                # Start auto-reply if enabled
                if self.gemini_service.is_initialized():
                    await self.telegram_client.start_auto_reply(self._generate_reply)
                    self.signals.log_message.emit("Auto-reply enabled with Gemini AI")
                else:
                    self.signals.log_message.emit("Warning: Gemini service not initialized")

                # Run forever
                await self.telegram_client.run_forever()

            except AuthKeyUnregistered:
                # Session revoked or invalid - DO NOT RETRY
                error_msg = "Session revoked or invalid (AuthKeyUnregistered). Re-login required."
                self.signals.log_message.emit(f"❌ {error_msg}")
                self.signals.status_update.emit("Session Revoked", "red")
                self.signals.auth_failed_unregistered.emit(error_msg)
                self.running = False
                break

            except (asyncio.TimeoutError, ConnectionError, OSError) as e:
                # Network-related errors - attempt recovery
                self.connection_attempts += 1
                self.network_recovery.record_recovery_attempt("telegram")
                self.signals.log_message.emit(
                    f"Network error (attempt {self.connection_attempts}): {e}"
                )
                self.signals.status_update.emit("Network Error: Reconnecting...", "orange")

            except Exception as e:
                # Other errors - don't retry
                self.signals.log_message.emit(f"Telegram client error: {e}")
                self.signals.status_update.emit(f"Error: {str(e)}", "red")
                break

        if self.connection_attempts >= self.max_connection_attempts:
            self.signals.log_message.emit("Failed to connect after maximum attempts")
            self.signals.status_update.emit("Connection Failed", "red")

    def _generate_reply(self, message: str, chat_id: int) -> str:
        """Generate a reply using Gemini AI with rate limiting."""
        try:
            # Check rate limit before generating reply
            if not self.rate_limiter.is_allowed("message"):
                remaining = self.rate_limiter.get_remaining_requests("message")
                backoff_remaining = self.rate_limiter.get_backoff_remaining()
                circuit_remaining = self.rate_limiter.get_circuit_breaker_remaining()

                if backoff_remaining > 0:
                    self.signals.log_message.emit(
                        f"Rate limit backoff active, {backoff_remaining:.0f}s remaining"
                    )
                    return "I'm taking a short break, please try again in a moment."
                elif circuit_remaining > 0:
                    self.signals.log_message.emit(
                        f"Circuit breaker active, {circuit_remaining:.0f}s remaining"
                    )
                    return "I'm experiencing some issues, please try again later."
                else:
                    self.signals.log_message.emit(
                        f"Rate limit exceeded, {remaining} message requests remaining"
                    )
                    return "I'm a bit busy right now, can you ask again in a minute?"

            # Use asyncio.run_coroutine_threadsafe to run in the main event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, create new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            future = asyncio.run_coroutine_threadsafe(
                self.gemini_service.generate_reply(message, chat_id), loop
            )
            reply = future.result(timeout=TELEGRAM_MESSAGE_TIMEOUT)

            if reply:
                self.signals.log_message.emit(f"Generated reply for chat {chat_id}")
                return reply
            else:
                self.signals.log_message.emit(f"Failed to generate reply for chat {chat_id}")
                return ""

        except asyncio.TimeoutError:
            self.signals.log_message.emit(f"Timeout generating reply for chat {chat_id}")
            return "Sorry, I'm taking too long to think about that."
        except Exception as e:
            self.signals.log_message.emit(f"Error generating reply: {e}")
            return "Sorry, I'm having trouble responding right now."

    def stop(self):
        """Stop the worker thread gracefully."""
        self.running = False
        if hasattr(self, "telegram_client") and self.telegram_client:
            # Stop the client gracefully
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop, create new one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                asyncio.run_coroutine_threadsafe(self.telegram_client.stop(), loop)
            except Exception as e:
                self.signals.log_message.emit(f"Error stopping Telegram client: {e}")

        self.signals.log_message.emit("Stopping Telegram worker thread...")
