"""
Persistent Connection Manager - Ensures accounts ALWAYS stay logged in.
Critical for one-time use phone numbers - if disconnected, account is lost forever.
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Dict, Optional

from pyrogram import Client

logger = logging.getLogger(__name__)


class PersistentConnectionManager:
    """Manages persistent connections for accounts - ensures they NEVER disconnect."""

    def __init__(self):
        self.monitored_clients: Dict[str, Dict] = {}  # phone_number -> client info
        self.reconnect_tasks: Dict[str, asyncio.Task] = {}
        self.connection_check_interval = 30  # Check every 30 seconds
        self.max_reconnect_attempts = 10
        self.reconnect_delays = [5, 10, 15, 30, 60, 120, 300, 600, 900, 1800]  # Exponential backoff
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None

    async def start_monitoring(self):
        """Start the connection monitoring loop."""
        if self.is_monitoring:
            logger.warning("Connection monitoring already running")
            return

        self.is_monitoring = True
        logger.info("🔄 Starting persistent connection monitoring")

        self.monitor_task = asyncio.create_task(self._monitor_connections())

    async def stop_monitoring(self):
        """Stop the connection monitoring loop."""
        self.is_monitoring = False
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        for phone, task in list(self.reconnect_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            self.reconnect_tasks.pop(phone, None)
        logger.info("🛑 Stopped persistent connection monitoring")

    async def _monitor_connections(self):
        """Continuously monitor all connections and auto-reconnect if needed."""
        while self.is_monitoring:
            try:
                for phone_number, client_info in list(self.monitored_clients.items()):
                    client = client_info.get("client")
                    if not client:
                        continue

                    # Check if client is connected
                    is_connected = client.is_connected if hasattr(client, "is_connected") else False

                    if not is_connected:
                        logger.warning(
                            f"⚠️ Account {phone_number} disconnected! "
                            f"Attempting immediate reconnect..."
                        )
                        await self._reconnect_client(phone_number, client_info)
                    else:
                        # Update last seen
                        client_info["last_seen"] = datetime.now()
                        client_info["reconnect_attempts"] = 0  # Reset on successful connection

                # Sleep before next check
                await asyncio.sleep(self.connection_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in connection monitoring: {e}")
                await asyncio.sleep(self.connection_check_interval)

    async def register_client(
        self, phone_number: str, client: Client, reconnect_callback: Optional[Callable] = None
    ):
        """Register a client for persistent connection monitoring."""
        self.monitored_clients[phone_number] = {
            "client": client,
            "phone_number": phone_number,
            "registered_at": datetime.now(),
            "last_seen": datetime.now(),
            "reconnect_attempts": 0,
            "reconnect_callback": reconnect_callback,
            "is_reconnecting": False,
        }
        logger.info(f"✅ Registered {phone_number} for persistent connection monitoring")

    async def unregister_client(self, phone_number: str):
        """Unregister a client from monitoring."""
        if phone_number in self.monitored_clients:
            # Cancel any ongoing reconnect task
            if phone_number in self.reconnect_tasks:
                task = self.reconnect_tasks.pop(phone_number)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            del self.monitored_clients[phone_number]
            logger.info(f"Unregistered {phone_number} from connection monitoring")

    async def _reconnect_client(self, phone_number: str, client_info: Dict):
        """Reconnect a disconnected client."""
        if client_info.get("is_reconnecting", False):
            return  # Already reconnecting

        client_info["is_reconnecting"] = True
        reconnect_attempts = client_info.get("reconnect_attempts", 0)

        if reconnect_attempts >= self.max_reconnect_attempts:
            logger.error(
                f"❌ Max reconnect attempts reached for {phone_number}. Manual intervention required."
            )
            client_info["is_reconnecting"] = False
            return

        # Calculate delay (exponential backoff)
        delay = self.reconnect_delays[min(reconnect_attempts, len(self.reconnect_delays) - 1)]

        logger.info(
            f"🔄 Reconnecting {phone_number} (attempt {reconnect_attempts + 1}/{self.max_reconnect_attempts}) in {delay}s..."
        )

        # Wait before reconnecting
        await asyncio.sleep(delay)

        try:
            client = client_info["client"]

            # Try to reconnect
            if hasattr(client, "connect"):
                await client.connect()
                logger.info(f"✅ Successfully reconnected {phone_number}")
                client_info["reconnect_attempts"] = 0
                client_info["is_reconnecting"] = False
                client_info["last_seen"] = datetime.now()
            else:
                # If connect method doesn't exist, try to restart
                if hasattr(client, "start"):
                    await client.start()
                    logger.info(f"✅ Successfully restarted {phone_number}")
                    client_info["reconnect_attempts"] = 0
                    client_info["is_reconnecting"] = False
                    client_info["last_seen"] = datetime.now()
                else:
                    raise Exception("No reconnect method available")

            # Call reconnect callback if provided
            if client_info.get("reconnect_callback"):
                try:
                    await client_info["reconnect_callback"](phone_number, client)
                except Exception as e:
                    logger.warning(f"Reconnect callback failed for {phone_number}: {e}")

        except Exception as e:
            logger.error(
                f"❌ Reconnection attempt {reconnect_attempts + 1} failed for {phone_number}: {e}"
            )
            client_info["reconnect_attempts"] += 1
            client_info["is_reconnecting"] = False

            # Schedule next reconnect attempt
            if client_info["reconnect_attempts"] < self.max_reconnect_attempts:
                reconnect_task = asyncio.create_task(
                    self._reconnect_client(phone_number, client_info)
                )
                self.reconnect_tasks[phone_number] = reconnect_task
            else:
                logger.error(
                    f"❌ CRITICAL: {phone_number} failed to reconnect after {self.max_reconnect_attempts} attempts. Account may be lost!"
                )

    def get_connection_status(self, phone_number: str) -> Optional[Dict]:
        """Get connection status for an account."""
        if phone_number not in self.monitored_clients:
            return None

        client_info = self.monitored_clients[phone_number]
        client = client_info.get("client")

        is_connected = False
        if client and hasattr(client, "is_connected"):
            is_connected = client.is_connected

        return {
            "phone_number": phone_number,
            "is_connected": is_connected,
            "is_reconnecting": client_info.get("is_reconnecting", False),
            "reconnect_attempts": client_info.get("reconnect_attempts", 0),
            "last_seen": client_info.get("last_seen"),
            "registered_at": client_info.get("registered_at"),
        }

    def get_all_statuses(self) -> Dict[str, Dict]:
        """Get connection status for all monitored accounts."""
        return {phone: self.get_connection_status(phone) for phone in self.monitored_clients.keys()}
