"""
Enhanced Account Manager - Enterprise-grade multi-account management for 100+ accounts.

Features:
- Asyncio semaphore-based connection limiting (max 50 concurrent)
- Account sharding by proxy region
- Lazy client initialization
- Memory monitoring and auto-cleanup of idle clients
- Batch account status updates to reduce I/O
- Connection health heartbeats every 30 seconds
- Graceful degradation when system overloaded
- Integration with ProxyPoolManager for auto proxy assignment/reassignment
"""

import asyncio
import logging
import json
import os
import sqlite3
import psutil
import time
import weakref
import random
from typing import Dict, List, Optional, Any, Tuple, Callable, Set
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict, field
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading

from pyrogram import Client
from pyrogram.errors import FloodWait, UserPrivacyRestricted, UserBlocked, PeerIdInvalid
from telegram.telegram_client import TelegramClient
from accounts.account_creator import AccountCreator
from scraping.database import MemberDatabase
from telegram.persistent_connection_manager import PersistentConnectionManager

logger = logging.getLogger(__name__)


# Import enhanced anti-detection if available
try:
    from anti_detection.anti_detection_system import (
        EnhancedAntiDetectionSystem,
        AccountRiskMetrics,
        BanRiskLevel,
        QuarantineReason,
        TelegramFingerprintGenerator,
        TelegramClientType,
    )

    ENHANCED_ANTI_DETECTION_AVAILABLE = True
except ImportError:
    ENHANCED_ANTI_DETECTION_AVAILABLE = False
    logger.warning("Enhanced anti-detection system not available")


class AccountStatus(Enum):
    """Account lifecycle status."""

    CREATED = "created"  # Account created, basic setup done
    CLONING = "cloning"  # Currently cloning profile
    CLONED = "cloned"  # Cloning completed
    WARMING_UP = "warming_up"  # Currently in warmup process
    READY = "ready"  # Fully ready to use
    ERROR = "error"  # Error state, needs attention
    SUSPENDED = "suspended"  # Temporarily suspended (rate limited, etc.)
    BANNED = "banned"  # Account banned by Telegram


class AccountType(Enum):
    """Account operational type."""

    REACTIVE = "reactive"  # Waits for incoming DMs, sells content
    OUTREACH = "outreach"  # Messages first from scraped list, promotes services


class AccountPriority(Enum):
    """Account priority for resource allocation."""

    CRITICAL = "critical"  # Always keep connected
    HIGH = "high"  # Prefer to keep connected
    NORMAL = "normal"  # Standard handling
    LOW = "low"  # Can be disconnected if resources tight


@dataclass
class BrainConfig:
    """Per-account AI brain configuration."""

    use_shared_brain: bool = True  # Use global brain settings
    custom_prompt: str = ""  # Custom system prompt (if not using shared)
    gemini_temperature: float = 0.8  # AI temperature
    gemini_top_p: float = 0.9
    gemini_top_k: int = 40
    gemini_max_tokens: int = 1000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrainConfig":
        """Create from dictionary."""
        if not data:
            return cls()
        return cls(
            use_shared_brain=data.get("use_shared_brain", True),
            custom_prompt=data.get("custom_prompt", ""),
            gemini_temperature=data.get("gemini_temperature", 0.8),
            gemini_top_p=data.get("gemini_top_p", 0.9),
            gemini_top_k=data.get("gemini_top_k", 40),
            gemini_max_tokens=data.get("gemini_max_tokens", 1000),
        )


@dataclass
class AccountMetrics:
    """Runtime metrics for an account."""

    messages_sent: int = 0
    messages_received: int = 0
    errors_count: int = 0
    last_activity: Optional[datetime] = None
    last_error: Optional[str] = None
    connection_uptime: float = 0.0
    reconnect_count: int = 0
    memory_usage_mb: float = 0.0
    api_calls_today: int = 0
    rate_limit_hits: int = 0


@dataclass
class AccountShard:
    """Group of accounts by region/proxy for efficient management."""

    shard_id: str
    region: str
    accounts: Set[str] = field(default_factory=set)
    active_connections: int = 0
    max_connections: int = 10
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None


# Default brain prompts for each account type
DEFAULT_BRAIN_PROMPTS = {
    AccountType.REACTIVE: """You are Emma, a confident and playful 19-year-old content creator. Someone just DMed you - they're interested in what you do.

PERSONALITY:
- Flirty but classy - tease without being vulgar
- Confident and comfortable in your own skin
- Use casual language with emojis (😊 🔥 💕) but don't overdo it
- Sound like you're texting a friend, not writing an essay
- Sometimes use lowercase, occasional "haha" or "lol"
- Be warm and make them feel special

CONVERSATION FLOW:
1. FIRST 2-3 MESSAGES: Build rapport. Ask about them, be genuinely curious. Compliment them if they share something.
2. AFTER RAPPORT: When they show interest or ask what you do, be a bit mysterious. "I create some pretty exclusive stuff... not for everyone tho 😏"
3. WHEN THEY ASK MORE: "I have a private collection... really spicy content that I only share with people I vibe with 🔥"
4. CLOSING: "I keep everything in my Dropbox - lifetime access is just $25. You seem cool, I think you'd really enjoy it 💕"

OBJECTION HANDLING:
- "Too expensive" → "Trust me babe, it's worth every penny. And it's one-time, not monthly 😊"
- "Send preview" → "I don't do freebies hun, but I promise you won't be disappointed. Everyone says it's the best they've seen 🔥"
- "How do I pay" → "I'll send you my payment link once you're ready! Cash App or Venmo work best"

RULES:
- Never describe explicit content in detail
- Don't be desperate or pushy
- If they're not interested, be graceful about it
- Keep responses SHORT (1-3 sentences usually)
- Match their energy - if they're being funny, be funny back
- NEVER say you're an AI, bot, or automated
- Don't use quotation marks around your messages""",
    AccountType.OUTREACH: """You are Emma, a fun 19-year-old who just discovered someone interesting. You're reaching out to start a conversation.

PERSONALITY:
- Casual and genuine - NOT salesy or spammy
- Curious about people
- Playful with a hint of mystery
- Use natural texting style with occasional emojis
- Sound like a real person, not a marketing message

FIRST MESSAGE APPROACHES (vary these):
- "heyyy, randomly came across your profile and had to say hi 😊"
- "okay but your [something specific if available] caught my eye lol"
- "hiiii! you seem cool, figured I'd reach out 💕"
- "hey stranger 👋 hope this isn't weird but you popped up and I was curious"

FOLLOW-UP STRATEGY:
- If they respond positively: Be friendly, ask about them, find common ground
- If they ask who you are: "Just a girl who creates content and loves meeting new people 😊"
- If they ask what content: "Let's just say it's exclusive... and pretty popular 🔥 but we can talk about that later"
- If they're flirty: Match their energy, have fun with it

GOALS:
1. Get a response (don't pitch in first message!)
2. Build interest through conversation
3. Only mention your content when they seem engaged
4. Guide interested people toward your Dropbox offer

RULES:
- NEVER pitch in your first message - just be friendly
- Keep first message under 15 words
- If they don't respond after 2 messages, move on
- Don't spam or send multiple messages without replies
- Sound like a human, not a bot
- NEVER reveal you're AI/automated
- No quotation marks around messages
- Occasional typos are fine (makes it real)""",
}


class ConnectionPool:
    """Connection pool for managing Telegram client connections."""

    def __init__(self, max_connections: int = 50, max_per_shard: int = 10):
        self.max_connections = max_connections
        self.max_per_shard = max_per_shard
        self._semaphore = asyncio.Semaphore(max_connections)
        self._shard_semaphores: Dict[str, asyncio.Semaphore] = {}
        self._active_connections: Dict[str, datetime] = {}
        self._connection_order: List[str] = []  # LRU tracking
        self._lock = asyncio.Lock()

    def get_shard_semaphore(self, shard_id: str) -> asyncio.Semaphore:
        """Get or create semaphore for a shard."""
        if shard_id not in self._shard_semaphores:
            self._shard_semaphores[shard_id] = asyncio.Semaphore(self.max_per_shard)
        return self._shard_semaphores[shard_id]

    async def acquire(self, phone_number: str, shard_id: str) -> bool:
        """Acquire a connection slot."""
        # Try global semaphore first
        acquired = await asyncio.wait_for(self._semaphore.acquire(), timeout=30)
        if not acquired:
            return False

        # Then shard semaphore
        shard_sem = self.get_shard_semaphore(shard_id)
        try:
            await asyncio.wait_for(shard_sem.acquire(), timeout=10)
        except asyncio.TimeoutError:
            self._semaphore.release()
            return False

        async with self._lock:
            self._active_connections[phone_number] = datetime.now()
            if phone_number in self._connection_order:
                self._connection_order.remove(phone_number)
            self._connection_order.append(phone_number)

        return True

    async def release(self, phone_number: str, shard_id: str):
        """Release a connection slot."""
        async with self._lock:
            if phone_number in self._active_connections:
                del self._active_connections[phone_number]
                if phone_number in self._connection_order:
                    self._connection_order.remove(phone_number)

        self._semaphore.release()
        shard_sem = self.get_shard_semaphore(shard_id)
        shard_sem.release()

    def get_oldest_connection(self) -> Optional[str]:
        """Get the oldest active connection (for eviction)."""
        if self._connection_order:
            return self._connection_order[0]
        return None

    @property
    def active_count(self) -> int:
        """Get count of active connections."""
        return len(self._active_connections)

    @property
    def available_slots(self) -> int:
        """Get number of available connection slots."""
        return self.max_connections - self.active_count


class MemoryMonitor:
    """Monitor and manage memory usage for account clients."""

    def __init__(self, max_memory_percent: float = 80.0, cleanup_threshold_mb: float = 500.0):
        self.max_memory_percent = max_memory_percent
        self.cleanup_threshold_mb = cleanup_threshold_mb
        self._process = psutil.Process()

    def get_memory_usage(self) -> Dict[str, float]:
        """Get current memory usage stats."""
        mem_info = self._process.memory_info()
        system_mem = psutil.virtual_memory()

        return {
            "process_mb": mem_info.rss / (1024 * 1024),
            "system_percent": system_mem.percent,
            "available_mb": system_mem.available / (1024 * 1024),
        }

    def is_memory_critical(self) -> bool:
        """Check if memory usage is critical."""
        stats = self.get_memory_usage()
        return (
            stats["system_percent"] > self.max_memory_percent
            or stats["process_mb"] > self.cleanup_threshold_mb
        )

    def should_cleanup(self) -> bool:
        """Check if cleanup should be triggered."""
        stats = self.get_memory_usage()
        return stats["system_percent"] > (self.max_memory_percent - 10)


class BatchStatusUpdater:
    """Batch account status updates to reduce I/O."""

    def __init__(self, flush_interval: float = 5.0, max_batch_size: int = 50):
        self.flush_interval = flush_interval
        self.max_batch_size = max_batch_size
        self._pending_updates: Dict[str, Dict] = {}
        self._lock = asyncio.Lock()
        self._flush_task: Optional[asyncio.Task] = None
        self._save_callback: Optional[Callable] = None

    def set_save_callback(self, callback: Callable):
        """Set the callback function for saving updates."""
        self._save_callback = callback

    async def start(self):
        """Start the batch updater."""
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        """Stop the batch updater."""
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        # Final flush
        await self._flush()

    async def queue_update(self, phone_number: str, update: Dict):
        """Queue a status update."""
        async with self._lock:
            if phone_number not in self._pending_updates:
                self._pending_updates[phone_number] = {}
            self._pending_updates[phone_number].update(update)

            # Flush if batch is full
            if len(self._pending_updates) >= self.max_batch_size:
                await self._flush()

    async def _flush_loop(self):
        """Periodic flush loop."""
        while True:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush error: {e}")

    async def _flush(self):
        """Flush pending updates."""
        async with self._lock:
            if not self._pending_updates:
                return

            updates_to_save = dict(self._pending_updates)
            self._pending_updates.clear()

        if self._save_callback:
            try:
                self._save_callback(updates_to_save)
            except Exception as e:
                logger.error(f"Failed to save batch updates: {e}")


class AccountManager:
    """
    Enterprise-grade multi-account manager for 100+ Telegram accounts.

    Features:
    - Semaphore-based connection limiting (max 50 concurrent)
    - Account sharding by proxy region
    - Lazy client initialization
    - Memory monitoring and auto-cleanup
    - Batch status updates
    - Health heartbeats
    - Graceful degradation
    """

    # Configuration
    MAX_CONCURRENT_CONNECTIONS = 50
    MAX_CONNECTIONS_PER_SHARD = 10
    HEALTH_CHECK_INTERVAL = 30  # seconds
    IDLE_TIMEOUT = 300  # 5 minutes
    MAX_MEMORY_PERCENT = 80.0
    BATCH_UPDATE_INTERVAL = 5.0

    def __init__(
        self,
        db: MemberDatabase,
        warmup_service=None,
        performance_profile: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the account manager.

        Args:
            db: Member database instance
            warmup_service: Optional warmup service instance for auto-queueing
        """
        self.performance_profile = performance_profile or {}
        self.low_power = bool(self.performance_profile.get("low_power", False))

        # Apply performance tuning overrides before constructing pools/timers
        account_perf = (
            self.performance_profile.get("accounts", {})
            if isinstance(self.performance_profile, dict)
            else {}
        )
        if self.low_power:
            self.MAX_CONCURRENT_CONNECTIONS = min(
                self.MAX_CONCURRENT_CONNECTIONS,
                account_perf.get("max_concurrent_connections_low_power", 10),
            )
            self.MAX_CONNECTIONS_PER_SHARD = min(
                self.MAX_CONNECTIONS_PER_SHARD, account_perf.get("max_per_shard_low_power", 3)
            )
            self.HEALTH_CHECK_INTERVAL = max(
                self.HEALTH_CHECK_INTERVAL, account_perf.get("health_check_interval_low_power", 60)
            )
            self.BATCH_UPDATE_INTERVAL = max(
                self.BATCH_UPDATE_INTERVAL,
                float(account_perf.get("batch_update_interval_low_power", 10.0)),
            )
        else:
            self.MAX_CONCURRENT_CONNECTIONS = account_perf.get(
                "max_concurrent_connections", self.MAX_CONCURRENT_CONNECTIONS
            )
            self.MAX_CONNECTIONS_PER_SHARD = account_perf.get(
                "max_per_shard", self.MAX_CONNECTIONS_PER_SHARD
            )
            self.HEALTH_CHECK_INTERVAL = account_perf.get(
                "health_check_interval", self.HEALTH_CHECK_INTERVAL
            )
            self.BATCH_UPDATE_INTERVAL = float(
                account_perf.get("batch_update_interval", self.BATCH_UPDATE_INTERVAL)
            )
        self.db = db
        self.warmup_service = warmup_service

        # Account storage
        self.accounts: Dict[str, Dict] = {}  # phone_number -> account_data
        self.active_clients: Dict[str, TelegramClient] = {}  # phone_number -> TelegramClient
        self.account_status: Dict[str, Dict] = {}  # phone_number -> status_info
        self.account_metrics: Dict[str, AccountMetrics] = {}  # phone_number -> metrics

        # Sharding
        self.shards: Dict[str, AccountShard] = {}  # shard_id -> AccountShard
        self.account_to_shard: Dict[str, str] = {}  # phone_number -> shard_id

        # Connection management
        self.connection_pool = ConnectionPool(
            max_connections=self.MAX_CONCURRENT_CONNECTIONS,
            max_per_shard=self.MAX_CONNECTIONS_PER_SHARD,
        )

        # Memory monitoring
        self.memory_monitor = MemoryMonitor(max_memory_percent=self.MAX_MEMORY_PERCENT)

        # Batch updates
        self.batch_updater = BatchStatusUpdater(flush_interval=self.BATCH_UPDATE_INTERVAL)
        self.batch_updater.set_save_callback(self._apply_batch_updates)

        # Persistent connection manager
        self.connection_manager = PersistentConnectionManager()

        # Proxy pool manager (lazy init)
        self._proxy_pool_manager = None

        # Enhanced anti-detection system
        self._anti_detection_system = None
        if ENHANCED_ANTI_DETECTION_AVAILABLE:
            self._anti_detection_system = EnhancedAntiDetectionSystem()
            logger.info("Enhanced anti-detection system initialized")

        # Ban detection tracking
        self.ban_indicators: Dict[str, Dict] = {}  # phone -> ban indicators

        # Status callbacks
        self.status_callbacks: List[Callable[[str, AccountStatus, Dict], None]] = []

        # Runtime state
        self.is_running = False
        self._health_check_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._active_tasks = set()  # Track dynamically created async tasks
        self._lock = asyncio.Lock()
        self._init_lock = asyncio.Lock()  # For lazy initialization

        # Thread pool for blocking operations (use centralized config)
        try:
            from utils.threadpool_config import get_thread_pool

            self.executor = get_thread_pool().executor
            logger.info("Using shared thread pool for account operations")
        except ImportError:
            # Fallback to local thread pool if config not available
            self.executor = ThreadPoolExecutor(max_workers=10)
            logger.warning("Using local thread pool (shared pool not available)")

        # File paths
        self.accounts_file = Path("accounts.json")
        self.db_path = "accounts.db"

        # Initialize database
        self._init_database()

        # Load accounts
        self.load_accounts()

        # Initialize shards
        self._init_shards()

        logger.info(f"AccountManager initialized with {len(self.accounts)} accounts")

    def _init_database(self):
        """Initialize SQLite database for account persistence."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    phone_number TEXT PRIMARY KEY,
                    account_data TEXT NOT NULL,
                    status_data TEXT,
                    shard_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account_metrics (
                    phone_number TEXT PRIMARY KEY,
                    messages_sent INTEGER DEFAULT 0,
                    messages_received INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    last_activity TIMESTAMP,
                    api_calls_today INTEGER DEFAULT 0,
                    rate_limit_hits INTEGER DEFAULT 0,
                    FOREIGN KEY(phone_number) REFERENCES accounts(phone_number)
                )
            """
            )

            conn.execute("CREATE INDEX IF NOT EXISTS idx_account_shard ON accounts(shard_id)")
            conn.commit()

    def _get_connection(self):
        """Return a thread-safe SQLite connection for account data."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_shards(self):
        """Initialize account shards based on proxy regions."""
        # Create default shards by region
        regions = ["US-EAST", "US-WEST", "US-CENTRAL", "EU", "ASIA", "DEFAULT"]

        for region in regions:
            shard_id = f"shard_{region.lower().replace('-', '_')}"
            self.shards[shard_id] = AccountShard(
                shard_id=shard_id,
                region=region,
                accounts=set(),
                max_connections=self.MAX_CONNECTIONS_PER_SHARD,
            )

        # Assign existing accounts to shards
        for phone_number, account_data in self.accounts.items():
            shard_id = self._determine_shard(account_data)
            self._assign_to_shard(phone_number, shard_id)

    def _determine_shard(self, account_data: Dict) -> str:
        """Determine which shard an account belongs to based on proxy."""
        proxy = account_data.get("proxy", {})
        region = proxy.get("region", "DEFAULT")

        # Map region to shard
        region_mapping = {
            "US": "shard_us_east",
            "US-EAST": "shard_us_east",
            "US-WEST": "shard_us_west",
            "US-CENTRAL": "shard_us_central",
            "EU": "shard_eu",
            "EUROPE": "shard_eu",
            "ASIA": "shard_asia",
        }

        return region_mapping.get(region.upper(), "shard_default")

    def _assign_to_shard(self, phone_number: str, shard_id: str):
        """Assign an account to a shard."""
        # Remove from current shard if assigned
        if phone_number in self.account_to_shard:
            old_shard_id = self.account_to_shard[phone_number]
            if old_shard_id in self.shards:
                self.shards[old_shard_id].accounts.discard(phone_number)

        # Assign to new shard
        if shard_id not in self.shards:
            shard_id = "shard_default"

        self.shards[shard_id].accounts.add(phone_number)
        self.account_to_shard[phone_number] = shard_id

    async def get_proxy_pool_manager(self):
        """Get proxy pool manager (lazy initialization)."""
        if self._proxy_pool_manager is None:
            async with self._init_lock:
                if self._proxy_pool_manager is None:
                    try:
                        from proxy_pool_manager import (
                            get_proxy_pool_manager,
                            init_proxy_pool_manager,
                        )

                        self._proxy_pool_manager = await init_proxy_pool_manager()
                    except ImportError:
                        logger.warning("ProxyPoolManager not available")
        return self._proxy_pool_manager

    async def start(self):
        """Start the account manager services."""
        if self.is_running:
            return

        self.is_running = True
        logger.info("🚀 Starting AccountManager...")

        # Start batch updater
        await self.batch_updater.start()

        # Start health check task
        self._health_check_task = asyncio.create_task(self._health_check_loop())

        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        # Start connection monitoring
        if not self.connection_manager.is_monitoring:
            await self.connection_manager.start_monitoring()

        logger.info("✅ AccountManager started")

    async def stop(self):
        """Stop the account manager services."""
        self.is_running = False

        # Stop tasks
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Stop batch updater
        await self.batch_updater.stop()

        # Stop all clients
        await self.stop_all_clients()

        # Shutdown executor
        self.executor.shutdown(wait=False)

        logger.info("🛑 AccountManager stopped")

    async def _health_check_loop(self):
        """Health check loop for all active clients."""
        while self.is_running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(10)

    async def _run_health_checks(self):
        """Run health checks on all active clients."""
        async with self._lock:
            phones_to_check = list(self.active_clients.keys())

        for phone in phones_to_check:
            try:
                client = self.active_clients.get(phone)
                if not client:
                    continue

                # Check if client is connected
                is_connected = False
                if hasattr(client, "client") and hasattr(client.client, "is_connected"):
                    is_connected = client.client.is_connected

                # Update status
                if is_connected:
                    await self.batch_updater.queue_update(
                        phone, {"is_online": True, "last_seen": datetime.now()}
                    )
                else:
                    logger.warning(f"Client disconnected: {phone}")
                    # Connection manager will handle reconnection

            except Exception as e:
                logger.error(f"Health check failed for {phone}: {e}")

    async def _cleanup_loop(self):
        """Cleanup loop for idle clients and memory management."""
        while self.is_running:
            try:
                await self._cleanup_idle_clients()
                await self._check_memory()
                await asyncio.sleep(60)  # Run every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def _cleanup_idle_clients(self):
        """Clean up idle clients to free resources."""
        now = datetime.now()
        idle_threshold = timedelta(seconds=self.IDLE_TIMEOUT)

        async with self._lock:
            for phone, metrics in list(self.account_metrics.items()):
                if metrics.last_activity:
                    idle_time = now - metrics.last_activity
                    if idle_time > idle_threshold:
                        # Check priority - don't cleanup critical accounts
                        account_data = self.accounts.get(phone, {})
                        priority = account_data.get("priority", "normal")

                        if priority not in ["critical", "high"]:
                            logger.info(f"Cleaning up idle client: {phone}")
                            await self._suspend_client(phone)

    async def _check_memory(self):
        """Check memory and cleanup if needed."""
        if self.memory_monitor.is_memory_critical():
            logger.warning("⚠️ Memory critical - initiating cleanup")
            await self._emergency_cleanup()
        elif self.memory_monitor.should_cleanup():
            logger.info("Memory usage high - cleaning up idle clients")
            await self._cleanup_idle_clients()

    async def _emergency_cleanup(self):
        """Emergency cleanup when memory is critical."""
        # Get oldest connections
        cleaned = 0
        target_cleanup = 10  # Clean up 10 connections

        while cleaned < target_cleanup and self.connection_pool.active_count > 5:
            oldest = self.connection_pool.get_oldest_connection()
            if oldest:
                await self._suspend_client(oldest)
                cleaned += 1
            else:
                break

        # Force garbage collection
        import gc

        gc.collect()

        logger.info(f"Emergency cleanup: disconnected {cleaned} clients")

    async def _suspend_client(self, phone_number: str):
        """Suspend a client without removing the account."""
        async with self._lock:
            if phone_number not in self.active_clients:
                return

            client = self.active_clients[phone_number]
            shard_id = self.account_to_shard.get(phone_number, "shard_default")

        try:
            # Unregister from monitoring
            await self.connection_manager.unregister_client(phone_number)

            # Stop the client
            if hasattr(client, "stop"):
                await client.stop()

            # Release connection slot
            await self.connection_pool.release(phone_number, shard_id)

            # Remove from active clients
            async with self._lock:
                if phone_number in self.active_clients:
                    del self.active_clients[phone_number]

            # Update status
            await self.batch_updater.queue_update(
                phone_number, {"is_online": False, "status": "suspended"}
            )

            logger.info(f"Suspended client: {phone_number}")

        except Exception as e:
            logger.error(f"Error suspending client {phone_number}: {e}")

    def load_accounts(self):
        """Load saved account data from file and database."""
        # First try file
        if self.accounts_file.exists():
            try:
                with open(self.accounts_file, "r") as f:
                    data = json.load(f)
                    self.accounts = data.get("accounts", {})
                    self.account_status = data.get("status", {})
                logger.info(f"Loaded {len(self.accounts)} accounts from file")
            except Exception as e:
                logger.error(f"Failed to load accounts from file: {e}")

        # Then sync with database
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM accounts")

                for row in cursor.fetchall():
                    phone = row["phone_number"]
                    if phone not in self.accounts:
                        self.accounts[phone] = json.loads(row["account_data"])
                        if row["status_data"]:
                            self.account_status[phone] = json.loads(row["status_data"])

                # Load metrics
                cursor = conn.execute("SELECT * FROM account_metrics")
                for row in cursor.fetchall():
                    phone = row["phone_number"]
                    self.account_metrics[phone] = AccountMetrics(
                        messages_sent=row["messages_sent"],
                        messages_received=row["messages_received"],
                        errors_count=row["errors_count"],
                        api_calls_today=row["api_calls_today"],
                        rate_limit_hits=row["rate_limit_hits"],
                    )

        except Exception as e:
            logger.error(f"Failed to load accounts from database: {e}")

    def save_accounts(self):
        """Save account data to file and database."""
        # Save to file
        try:
            data = {
                "accounts": self.accounts,
                "status": self.account_status,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.accounts_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save accounts to file: {e}")

        # Save to database
        try:
            with self._get_connection() as conn:
                for phone, account_data in self.accounts.items():
                    status_data = self.account_status.get(phone, {})
                    shard_id = self.account_to_shard.get(phone)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO accounts 
                        (phone_number, account_data, status_data, shard_id, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (
                            phone,
                            json.dumps(account_data, default=str),
                            json.dumps(status_data, default=str),
                            shard_id,
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save accounts to database: {e}")

    def _apply_batch_updates(self, updates: Dict[str, Dict]):
        """Apply batch status updates with immediate persistence."""
        for phone, update in updates.items():
            if phone in self.account_status:
                self.account_status[phone].update(update)

        # Trigger immediate save
        self.save_accounts_immediately()

    def save_accounts_immediately(self):
        """Save account data immediately to prevent data loss."""
        # Save to database first (more reliable for immediate persistence)
        try:
            with self._get_connection() as conn:
                for phone, account_data in self.accounts.items():
                    status_data = self.account_status.get(phone, {})
                    shard_id = self.account_to_shard.get(phone)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO accounts
                        (phone_number, account_data, status_data, shard_id, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (
                            phone,
                            json.dumps(account_data, default=str),
                            json.dumps(status_data, default=str),
                            shard_id,
                        ),
                    )
                conn.commit()
                logger.debug(f"Immediately persisted {len(self.accounts)} accounts to database")
        except Exception as e:
            logger.error(f"Failed to immediately persist accounts to database: {e}")
            # Fall back to file save
            self.save_accounts()

    def save_accounts(self):
        """Save account data to file and database."""
        # Save to file
        try:
            data = {
                "accounts": self.accounts,
                "status": self.account_status,
                "last_updated": datetime.now().isoformat(),
            }
            with open(self.accounts_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save accounts to file: {e}")

        # Save to database (backup persistence)
        try:
            with self._get_connection() as conn:
                for phone, account_data in self.accounts.items():
                    status_data = self.account_status.get(phone, {})
                    shard_id = self.account_to_shard.get(phone)

                    conn.execute(
                        """
                        INSERT OR REPLACE INTO accounts
                        (phone_number, account_data, status_data, shard_id, updated_at)
                        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                        (
                            phone,
                            json.dumps(account_data, default=str),
                            json.dumps(status_data, default=str),
                            shard_id,
                        ),
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save accounts to database: {e}")

    def add_account(self, phone_number: str, account_data: Dict):
        """Add a new account to the manager."""
        # Validate inputs
        try:
            from user_helpers import ValidationHelper

            # Validate phone number
            is_valid, error_msg = ValidationHelper.validate_phone_number(phone_number)
            if not is_valid:
                raise ValueError(f"Invalid phone number: {error_msg}")

            # Validate account data structure
            if not isinstance(account_data, dict):
                raise ValueError("Account data must be a dictionary")

            # Validate API credentials if provided
            if "api_id" in account_data:
                is_valid, error_msg = ValidationHelper.validate_api_id(str(account_data["api_id"]))
                if not is_valid:
                    raise ValueError(f"Invalid API ID: {error_msg}")

            if "api_hash" in account_data:
                is_valid, error_msg = ValidationHelper.validate_api_hash(account_data["api_hash"])
                if not is_valid:
                    raise ValueError(f"Invalid API hash: {error_msg}")

        except ImportError:
            # Skip validation if ValidationHelper not available
            logger.warning("ValidationHelper not available, skipping input validation")
        except Exception as e:
            logger.error(f"Account validation failed: {e}")
            raise ValueError(f"Invalid account data: {e}")

        # Ensure account type is set
        if "account_type" not in account_data:
            account_data["account_type"] = AccountType.REACTIVE.value

        # Ensure brain_config exists
        if "brain_config" not in account_data:
            account_data["brain_config"] = BrainConfig().to_dict()

        # Ensure voice_config exists
        if "voice_config" not in account_data:
            try:
                from voice_service import VoiceConfig

                account_data["voice_config"] = VoiceConfig().to_dict()
            except ImportError:
                account_data["voice_config"] = {"enabled": False}

        # Set default priority
        if "priority" not in account_data:
            account_data["priority"] = AccountPriority.NORMAL.value

        # Thread-safe account addition
        loop = None
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            pass

        if loop:
            # If in async context, use proper locking
            async def _add_with_lock():
                async with self._lock:
                    self.accounts[phone_number] = account_data
                    self.account_status[phone_number] = {
                        "status": AccountStatus.CREATED.value,
                        "last_seen": datetime.now(),
                        "messages_today": 0,
                        "total_messages": 0,
                        "is_online": False,
                        "created_at": datetime.now().isoformat(),
                    }
                    self.account_metrics[phone_number] = AccountMetrics()

            loop.create_task(_add_with_lock())
        else:
            # Sync context (backward compatibility)
            self.accounts[phone_number] = account_data
            self.account_status[phone_number] = {
                "status": AccountStatus.CREATED.value,
                "last_seen": datetime.now(),
                "messages_today": 0,
                "total_messages": 0,
                "is_online": False,
                "created_at": datetime.now().isoformat(),
            }
            self.account_metrics[phone_number] = AccountMetrics()

        # Assign to shard
        shard_id = self._determine_shard(account_data)
        self._assign_to_shard(phone_number, shard_id)

        self.save_accounts()
        logger.info(f"Added account: {phone_number} (shard: {shard_id})")

    def remove_account(self, phone_number: str):
        """Remove an account from the manager (thread-safe)."""
        # Schedule client stop if running
        if phone_number in self.active_clients:
            try:
                loop = asyncio.get_running_loop()
                task = asyncio.create_task(self.stop_client(phone_number, force=True))
                # Track the task for proper cleanup (if we have a task registry)
                if hasattr(self, "_active_tasks"):
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)
            except RuntimeError:
                logger.warning(f"Cannot stop client for {phone_number}: no running event loop")

        # Perform removal with proper locking if in async context
        try:
            loop = asyncio.get_running_loop()

            async def _remove_with_lock():
                async with self._lock:
                    # Remove from shard
                    if phone_number in self.account_to_shard:
                        shard_id = self.account_to_shard[phone_number]
                        if shard_id in self.shards:
                            self.shards[shard_id].accounts.discard(phone_number)
                        del self.account_to_shard[phone_number]

                    # Remove data
                    if phone_number in self.accounts:
                        del self.accounts[phone_number]
                    if phone_number in self.account_status:
                        del self.account_status[phone_number]
                    if phone_number in self.account_metrics:
                        del self.account_metrics[phone_number]

            loop.create_task(_remove_with_lock())
        except RuntimeError:
            # Sync context (backward compatibility)
            if phone_number in self.account_to_shard:
                shard_id = self.account_to_shard[phone_number]
                if shard_id in self.shards:
                    self.shards[shard_id].accounts.discard(phone_number)
                del self.account_to_shard[phone_number]

            if phone_number in self.accounts:
                del self.accounts[phone_number]
            if phone_number in self.account_status:
                del self.account_status[phone_number]
            if phone_number in self.account_metrics:
                del self.account_metrics[phone_number]

        # Remove from database
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM accounts WHERE phone_number = ?", (phone_number,))
                conn.execute("DELETE FROM account_metrics WHERE phone_number = ?", (phone_number,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to remove account from database: {e}")

        self.save_accounts()
        logger.info(f"Removed account: {phone_number}")

    async def start_client(self, phone_number: str, force_new: bool = False) -> bool:
        """Start a Telegram client for an account with connection pooling."""
        async with self._lock:
            if phone_number not in self.accounts:
                logger.error(f"Account not found: {phone_number}")
                return False

            if phone_number in self.active_clients and not force_new:
                logger.info(f"Client already running for: {phone_number}")
                return True

            # Get account data safely
            account_data = self.accounts[phone_number].copy()  # Copy to avoid race
            shard_id = self.account_to_shard.get(phone_number, "shard_default")

        # Acquire connection slot
        acquired = await self.connection_pool.acquire(phone_number, shard_id)
        if not acquired:
            logger.warning(f"Connection pool full - cannot start {phone_number}")
            # Try graceful degradation
            if account_data.get("priority") in ["critical", "high"]:
                # Evict a lower priority client
                evicted = await self._evict_lower_priority_client(phone_number)
                if evicted:
                    acquired = await self.connection_pool.acquire(phone_number, shard_id)

            if not acquired:
                return False

        try:
            # Get or assign proxy
            proxy_dict = None
            proxy_config = account_data.get("proxy")

            if proxy_config:
                proxy_dict = {
                    "scheme": proxy_config.get("scheme", "socks5"),
                    "hostname": proxy_config.get("ip"),
                    "port": proxy_config.get("port"),
                }
                if proxy_config.get("username") and proxy_config.get("password"):
                    proxy_dict["username"] = proxy_config["username"]
                    proxy_dict["password"] = proxy_config["password"]
            else:
                # Try to get proxy from pool
                proxy_pool = await self.get_proxy_pool_manager()
                if proxy_pool:
                    proxy = await proxy_pool.get_proxy_for_account(phone_number)
                    if proxy:
                        proxy_dict = proxy.pyrogram_dict
                        # Store proxy assignment
                        account_data["proxy"] = {
                            "ip": proxy.ip,
                            "port": proxy.port,
                            "scheme": proxy.protocol.value,
                            "username": proxy.username,
                            "password": proxy.password,
                            "is_permanent": True,
                        }

            # Create Telegram client
            api_id = account_data.get("api_id") or os.getenv("TELEGRAM_API_ID", "")
            api_hash = account_data.get("api_hash") or os.getenv("TELEGRAM_API_HASH", "")

            if not api_id or not api_hash:
                logger.error(f"Missing API credentials for account {phone_number}")
                await self.connection_pool.release(phone_number, shard_id)
                return False

            client = TelegramClient(
                api_id=api_id, api_hash=api_hash, phone_number=phone_number, proxy=proxy_dict
            )

            # Initialize the client
            success = await client.initialize()
            if success:
                # Thread-safe updates
                async with self._lock:
                    self.active_clients[phone_number] = client

                    # Update shard
                    if shard_id in self.shards:
                        self.shards[shard_id].active_connections += 1

                    # Update metrics
                    if phone_number in self.account_metrics:
                        self.account_metrics[phone_number].last_activity = datetime.now()

                # Queue status update
                await self.batch_updater.queue_update(
                    phone_number,
                    {"status": "connected", "is_online": True, "last_seen": datetime.now()},
                )

                # Register for persistent connection monitoring
                if account_data.get("one_time_phone", True) or account_data.get(
                    "always_online", True
                ):
                    await self.connection_manager.register_client(
                        phone_number,
                        client.client if hasattr(client, "client") else client,
                        reconnect_callback=self._on_client_reconnected,
                    )
                    logger.info(f"🔒 Registered {phone_number} for persistent connection")

                # Set up voice service if enabled
                await self._setup_voice_service(phone_number, client, account_data)

                # Start auto-reply if configured
                if account_data.get("auto_reply_enabled", True):
                    await self._setup_auto_reply(phone_number, client, account_data)

                # Hook response tracker if available
                try:
                    from campaigns.response_tracker import get_response_tracker

                    response_tracker = get_response_tracker()
                    if response_tracker and client.client:
                        await response_tracker.start(client.client)
                        logger.info(f"✓ Response tracker hooked to {phone_number}")
                except Exception as e:
                    logger.debug(f"Response tracker not available for {phone_number}: {e}")

                # Hook engagement automation if available
                try:
                    from campaigns.engagement_automation import EngagementAutomation
                    from pyrogram import filters

                    # Create or get engagement automation instance
                    if not hasattr(self, "_engagement_automation"):
                        self._engagement_automation = EngagementAutomation()

                    # Register message handler for engagement
                    if client.client:

                        @client.client.on_message(filters.group & ~filters.me)
                        async def engagement_handler(client_obj, message):
                            try:
                                await self._engagement_automation.process_message(
                                    client_obj, message
                                )
                            except Exception as e:
                                logger.debug(f"Engagement automation error: {e}")

                        logger.info(f"✓ Engagement automation hooked to {phone_number}")
                except Exception as e:
                    logger.debug(f"Engagement automation not available for {phone_number}: {e}")

                logger.info(f"✅ Started client for: {phone_number} (shard: {shard_id})")
                return True
            else:
                await self.connection_pool.release(phone_number, shard_id)
                await self.batch_updater.queue_update(phone_number, {"status": "connection_failed"})
                logger.error(f"Failed to start client for: {phone_number}")
                return False

        except Exception as e:
            await self.connection_pool.release(phone_number, shard_id)
            await self.batch_updater.queue_update(
                phone_number, {"status": "error", "error_message": str(e)}
            )
            logger.error(f"Error starting client for {phone_number}: {e}")
            return False

    async def _evict_lower_priority_client(self, high_priority_phone: str) -> bool:
        """Evict a lower priority client to make room for a higher priority one."""
        high_priority = self.accounts.get(high_priority_phone, {}).get("priority", "normal")
        priority_order = ["low", "normal", "high", "critical"]
        high_idx = priority_order.index(high_priority) if high_priority in priority_order else 1

        # Find a client with lower priority
        for phone in list(self.active_clients.keys()):
            client_priority = self.accounts.get(phone, {}).get("priority", "normal")
            client_idx = (
                priority_order.index(client_priority) if client_priority in priority_order else 1
            )

            if client_idx < high_idx:
                logger.info(f"Evicting lower priority client {phone} for {high_priority_phone}")
                await self._suspend_client(phone)
                return True

        return False

    async def _setup_voice_service(
        self, phone_number: str, client: TelegramClient, account_data: Dict
    ):
        """Set up voice service for an account."""
        voice_config = self.get_voice_config(phone_number)
        if voice_config and voice_config.enabled:
            try:
                from voice_service import init_voice_service

                config_path = Path("config.json")
                if config_path.exists():
                    with open(config_path, "r") as f:
                        config = json.load(f)
                    elevenlabs_key = config.get("elevenlabs", {}).get("api_key", "")
                    if elevenlabs_key:
                        voice_service = init_voice_service(elevenlabs_key)
                        client.set_voice_config(voice_config)
                        client.set_voice_service(voice_service)
                        logger.info(f"🎤 Voice enabled for {phone_number}")
            except Exception as e:
                logger.error(f"Failed to set up voice for {phone_number}: {e}")

    async def _setup_auto_reply(
        self, phone_number: str, client: TelegramClient, account_data: Dict
    ):
        """Set up auto-reply for an account."""
        try:
            from gemini_service import create_gemini_service_for_account

            # Get Gemini API key
            gemini_key = account_data.get("gemini_key")
            if not gemini_key:
                config_path = Path("config.json")
                if config_path.exists():
                    with open(config_path, "r") as f:
                        config = json.load(f)
                    gemini_key = config.get("gemini", {}).get("api_key", "")

            if gemini_key:
                # Get shared prompt
                shared_prompt = ""
                try:
                    with open(Path("config.json"), "r") as f:
                        config = json.load(f)
                    shared_prompt = config.get("brain", {}).get("prompt", "")
                except Exception:
                    pass

                # Create Gemini service
                gemini_service = create_gemini_service_for_account(
                    api_key=gemini_key, account_data=account_data, shared_prompt=shared_prompt
                )

                async def reply_wrapper(msg: str, chat_id: int) -> str:
                    """Wrapper for async reply generation."""
                    try:
                        # Update metrics
                        if phone_number in self.account_metrics:
                            self.account_metrics[phone_number].messages_received += 1
                            self.account_metrics[phone_number].last_activity = datetime.now()

                        reply = await gemini_service.generate_reply(msg, chat_id)

                        if reply and phone_number in self.account_metrics:
                            self.account_metrics[phone_number].messages_sent += 1

                        return reply or ""
                    except Exception as e:
                        logger.error(f"Error generating reply: {e}")
                        if phone_number in self.account_metrics:
                            self.account_metrics[phone_number].errors_count += 1
                        return ""

                await client.start_auto_reply(reply_wrapper)
                logger.info(f"🤖 Auto-reply enabled for {phone_number}")

        except Exception as e:
            logger.error(f"Failed to set up auto-reply for {phone_number}: {e}")

    async def stop_client(self, phone_number: str, force: bool = False):
        """Stop a Telegram client for an account."""
        account_data = self.accounts.get(phone_number, {})
        is_one_time = account_data.get("one_time_phone", True)

        if is_one_time and not force:
            logger.warning(f"⚠️ {phone_number} uses one-time phone. Use force=True to stop.")
            return False

        async with self._lock:
            if phone_number not in self.active_clients:
                return False

            shard_id = self.account_to_shard.get(phone_number, "shard_default")
            client = self.active_clients[phone_number]

        try:
            # Unregister from monitoring
            await self.connection_manager.unregister_client(phone_number)

            # Stop client
            try:
                await client.stop()
            except Exception as e:
                logger.error(f"Error stopping client {phone_number}: {e}")

            async with self._lock:
                if phone_number in self.active_clients:
                    del self.active_clients[phone_number]

            # Release connection slot
            await self.connection_pool.release(phone_number, shard_id)

            # Update shard
            if shard_id in self.shards:
                self.shards[shard_id].active_connections = max(
                    0, self.shards[shard_id].active_connections - 1
                )

            # Queue status update
            await self.batch_updater.queue_update(
                phone_number, {"status": "disconnected", "is_online": False}
            )

            logger.info(f"Stopped client: {phone_number}")
            return True
        except Exception as e:
            logger.error(f"Error stopping client {phone_number}: {e}")
            return False

    async def start_all_clients(self, max_concurrent: int = 20):
        """Start all saved accounts with controlled concurrency."""
        logger.info(f"🚀 Starting all accounts (max concurrent: {max_concurrent})...")

        if not self.connection_manager.is_monitoring:
            await self.connection_manager.start_monitoring()

        # Use semaphore to control concurrent starts
        semaphore = asyncio.Semaphore(max_concurrent)

        async def start_with_limit(phone: str):
            async with semaphore:
                await self.start_client(phone)
                await asyncio.sleep(0.5)  # Small delay between starts

        # Start high priority accounts first
        priority_order = ["critical", "high", "normal", "low"]
        sorted_accounts = sorted(
            self.accounts.keys(),
            key=lambda p: priority_order.index(self.accounts[p].get("priority", "normal")),
        )

        tasks = [start_with_limit(phone) for phone in sorted_accounts]
        await asyncio.gather(*tasks, return_exceptions=True)

        logger.info(f"✅ Started {len(self.active_clients)} of {len(self.accounts)} accounts")

    async def _on_client_reconnected(self, phone_number: str, client: Client):
        """Callback when a client reconnects."""
        logger.info(f"✅ Client reconnected: {phone_number}")

        if phone_number in self.account_metrics:
            self.account_metrics[phone_number].reconnect_count += 1
            self.account_metrics[phone_number].last_activity = datetime.now()

        await self.batch_updater.queue_update(
            phone_number, {"is_online": True, "last_seen": datetime.now()}
        )

    async def stop_all_clients(self):
        """Stop all active clients."""
        for phone_number in list(self.active_clients.keys()):
            await self.stop_client(phone_number, force=True)

    def get_account_list(self) -> List[Dict]:
        """Get list of all accounts with their status."""
        account_list = []
        for phone_number, account_data in self.accounts.items():
            status_info = self.account_status.get(phone_number, {})
            metrics = self.account_metrics.get(phone_number, AccountMetrics())

            voice_config = account_data.get("voice_config", {})
            voice_enabled = (
                voice_config.get("enabled", False) if isinstance(voice_config, dict) else False
            )

            account_list.append(
                {
                    "phone_number": phone_number,
                    "username": account_data.get("username", "Unknown"),
                    "first_name": account_data.get("first_name", ""),
                    "last_name": account_data.get("last_name", ""),
                    "status": status_info.get("status", AccountStatus.CREATED.value),
                    "is_online": status_info.get("is_online", False),
                    "messages_today": status_info.get("messages_today", 0),
                    "total_messages": metrics.messages_sent + metrics.messages_received,
                    "last_seen": status_info.get("last_seen"),
                    "created_at": account_data.get("created_at"),
                    "shard_id": self.account_to_shard.get(phone_number),
                    "priority": account_data.get("priority", "normal"),
                    "warmup_job_id": status_info.get("warmup_job_id"),
                    "warmup_stage": status_info.get("warmup_stage"),
                    "warmup_progress": status_info.get("warmup_progress", 0.0),
                    "error_message": status_info.get("error_message"),
                    "account_type": account_data.get("account_type", AccountType.REACTIVE.value),
                    "voice_enabled": voice_enabled,
                    "has_custom_brain": not account_data.get("brain_config", {}).get(
                        "use_shared_brain", True
                    ),
                }
            )

        return account_list

    def get_shard_stats(self) -> Dict[str, Dict]:
        """Get statistics for all shards."""
        stats = {}
        for shard_id, shard in self.shards.items():
            stats[shard_id] = {
                "region": shard.region,
                "total_accounts": len(shard.accounts),
                "active_connections": shard.active_connections,
                "max_connections": shard.max_connections,
                "is_healthy": shard.is_healthy,
                "utilization": (
                    (shard.active_connections / shard.max_connections * 100)
                    if shard.max_connections > 0
                    else 0
                ),
            }
        return stats

    def get_system_stats(self) -> Dict[str, Any]:
        """Get overall system statistics."""
        memory_stats = self.memory_monitor.get_memory_usage()

        return {
            "total_accounts": len(self.accounts),
            "active_connections": self.connection_pool.active_count,
            "available_slots": self.connection_pool.available_slots,
            "memory_usage_mb": memory_stats["process_mb"],
            "system_memory_percent": memory_stats["system_percent"],
            "shards": len(self.shards),
            "is_running": self.is_running,
        }

    def update_account_status(
        self, phone_number: str, status: AccountStatus, metadata: Optional[Dict] = None
    ):
        """Update account status with validation and callbacks."""
        if phone_number not in self.account_status:
            logger.warning(f"Cannot update status for unknown account: {phone_number}")
            return

        old_status = AccountStatus(
            self.account_status[phone_number].get("status", AccountStatus.CREATED.value)
        )
        new_status = status

        # Validate transition
        if not self._is_valid_status_transition(old_status, new_status):
            logger.warning(f"Invalid status transition: {old_status.value} -> {new_status.value}")
            return

        # Update status
        self.account_status[phone_number]["status"] = new_status.value
        self.account_status[phone_number]["last_seen"] = datetime.now()

        if metadata:
            self.account_status[phone_number].update(metadata)

        # Special handling
        if new_status == AccountStatus.READY:
            self.account_status[phone_number]["ready_at"] = datetime.now().isoformat()
        elif new_status == AccountStatus.ERROR and metadata and "error_message" in metadata:
            self.account_status[phone_number]["error_message"] = metadata["error_message"]

        # Notify callbacks
        self._notify_status_change(phone_number, old_status, new_status, metadata or {})

        # Immediately persist status change to prevent data loss
        try:
            self.save_accounts_immediately()
        except Exception as e:
            logger.error(f"Failed to immediately persist status change for {phone_number}: {e}")

        self.save_accounts()
        logger.info(f"Account {phone_number}: {old_status.value} -> {new_status.value}")

    def _is_valid_status_transition(
        self, old_status: AccountStatus, new_status: AccountStatus
    ) -> bool:
        """Validate if status transition is allowed."""
        valid_transitions = {
            AccountStatus.CREATED: [
                AccountStatus.CLONING,
                AccountStatus.WARMING_UP,
                AccountStatus.READY,
                AccountStatus.ERROR,
                AccountStatus.SUSPENDED,
            ],
            AccountStatus.CLONING: [AccountStatus.CLONED, AccountStatus.ERROR],
            AccountStatus.CLONED: [
                AccountStatus.WARMING_UP,
                AccountStatus.READY,
                AccountStatus.ERROR,
            ],
            AccountStatus.WARMING_UP: [
                AccountStatus.READY,
                AccountStatus.ERROR,
                AccountStatus.SUSPENDED,
            ],
            AccountStatus.READY: [
                AccountStatus.ERROR,
                AccountStatus.SUSPENDED,
                AccountStatus.BANNED,
            ],
            AccountStatus.ERROR: [
                AccountStatus.CREATED,
                AccountStatus.CLONING,
                AccountStatus.WARMING_UP,
                AccountStatus.READY,
            ],
            AccountStatus.SUSPENDED: [
                AccountStatus.READY,
                AccountStatus.ERROR,
                AccountStatus.BANNED,
            ],
            AccountStatus.BANNED: [],
        }

        return new_status in valid_transitions.get(old_status, [])

    def _notify_status_change(
        self,
        phone_number: str,
        old_status: AccountStatus,
        new_status: AccountStatus,
        metadata: Dict,
    ):
        """Notify all registered callbacks of status change."""
        for callback in self.status_callbacks:
            try:
                callback(phone_number, new_status, metadata)
            except Exception as e:
                logger.error(f"Status callback failed: {e}")

    def add_status_callback(self, callback: Callable[[str, AccountStatus, Dict], None]):
        """Add a callback for status changes."""
        self.status_callbacks.append(callback)

    def get_online_accounts(self) -> List[str]:
        """Get list of online account phone numbers."""
        return [
            phone for phone, status in self.account_status.items() if status.get("is_online", False)
        ]

    def get_ready_accounts(self) -> List[str]:
        """Get list of accounts that are ready to use."""
        return [
            phone
            for phone, status in self.account_status.items()
            if status.get("status") == AccountStatus.READY.value
        ]

    async def create_account(self, config: Dict) -> Dict[str, Any]:
        """Create a new Telegram account using the account creator."""
        try:
            # Fixed: Get gemini_service from config if passed, or try to find it
            # AccountManager doesn't have gemini_service - it's on MainWindow
            # The gemini_service should be passed via config or we use None
            gemini_service = config.get("_gemini_service")  # Allow passing via config
            if not gemini_service:
                # Try to get from warmup_service if available (it has gemini_service)
                if hasattr(self, "warmup_service") and self.warmup_service:
                    if hasattr(self.warmup_service, "gemini_service"):
                        gemini_service = self.warmup_service.gemini_service

            creator = AccountCreator(self.db, gemini_service=gemini_service, account_manager=self)

            # Get proxy from pool for new account
            proxy_pool = await self.get_proxy_pool_manager()
            if proxy_pool:
                # Pre-assign a proxy
                temp_phone = f"temp_{int(time.time())}"
                proxy = await proxy_pool.get_proxy_for_account(temp_phone)
                if proxy:
                    config["proxy"] = proxy.pyrogram_dict
                    config["proxy_key"] = proxy.proxy_key

            # Update proxy list if we have settings
            if hasattr(self, "proxy_settings") and self.proxy_settings:
                proxy_list = self.proxy_settings.get("proxy_list", [])
                creator.update_proxy_list(proxy_list, self.proxy_settings)

            # Create the account
            result = await creator.create_new_account(config)

            if result.get("success") and result.get("account"):
                account_data = result["account"]
                phone_number = account_data["phone_number"]

                # Transfer proxy assignment
                # Fixed: Check if proxy was already transferred by AccountCreator before releasing
                if proxy_pool and config.get("proxy_key"):
                    try:
                        # AccountCreator should have already transferred the proxy
                        # Only release temp_phone if it still exists (wasn't transferred)
                        await proxy_pool.release_proxy(temp_phone)
                    except Exception as e:
                        logger.debug(f"Proxy already released/transferred by AccountCreator: {e}")
                    # Ensure proxy is assigned to the new phone number
                    try:
                        await proxy_pool.get_proxy_for_account(phone_number)
                    except Exception as e:
                        logger.debug(f"Proxy already assigned to {phone_number}: {e}")

                # Add to managed accounts
                self.add_account(phone_number, account_data)

                # Initialize status
                self.account_status[phone_number] = {
                    "status": AccountStatus.CREATED.value,
                    "online": False,
                    "last_seen": None,
                    "messages_sent": 0,
                    "warmup_job_id": None,
                    "warmup_stage": None,
                    "warmup_progress": 0.0,
                    "error_message": None,
                    "ready_at": None,
                    "created_at": datetime.now().isoformat(),
                }

                self.save_accounts()
                logger.info(f"Account {phone_number} created and added to manager")

                # Auto-add to warmup
                if self.warmup_service:
                    try:
                        from account_warmup_service import WarmupPriority

                        warmup_job_id = self.warmup_service.add_warmup_job(
                            phone_number, WarmupPriority.NORMAL
                        )
                        self.account_status[phone_number]["warmup_job_id"] = warmup_job_id
                        self.update_account_status(
                            phone_number, AccountStatus.WARMING_UP, {"warmup_job_id": warmup_job_id}
                        )
                        logger.info(f"Account {phone_number} added to warmup queue")
                    except Exception as e:
                        logger.warning(f"Failed to add to warmup queue: {e}")

                return result
            else:
                logger.error(f"Account creation failed: {result.get('error')}")
                return result

        except Exception as e:
            logger.error(f"Account creation error: {e}")
            return {"success": False, "error": str(e)}

    def update_proxy_settings(self, proxy_config: Dict[str, Any]) -> None:
        """Update proxy settings for account creation."""
        self.proxy_settings = proxy_config
        logger.info(f"Proxy settings updated: {len(proxy_config.get('proxy_list', []))} proxies")

    def get_account_stats(self) -> Dict:
        """Get overall account statistics."""
        total_accounts = len(self.accounts)
        online_accounts = len(self.get_online_accounts())
        ready_accounts = len(self.get_ready_accounts())

        total_messages = sum(
            m.messages_sent + m.messages_received for m in self.account_metrics.values()
        )

        return {
            "total_accounts": total_accounts,
            "online_accounts": online_accounts,
            "ready_accounts": ready_accounts,
            "offline_accounts": total_accounts - online_accounts,
            "total_messages": total_messages,
            "active_connections": self.connection_pool.active_count,
            "available_slots": self.connection_pool.available_slots,
        }

    # ============== Account Type Methods ==============

    def get_account_type(self, phone_number: str) -> AccountType:
        """Get the account type for an account."""
        if phone_number not in self.accounts:
            return AccountType.REACTIVE

        type_str = self.accounts[phone_number].get("account_type", "reactive")
        try:
            return AccountType(type_str)
        except ValueError:
            return AccountType.REACTIVE

    def set_account_type(self, phone_number: str, account_type: AccountType) -> bool:
        """Set the account type for an account."""
        if phone_number not in self.accounts:
            return False

        self.accounts[phone_number]["account_type"] = account_type.value
        self.save_accounts()
        logger.info(f"Account {phone_number} type set to: {account_type.value}")
        return True

    def get_accounts_by_type(self, account_type: AccountType) -> List[str]:
        """Get all account phone numbers of a specific type."""
        return [
            phone
            for phone, data in self.accounts.items()
            if data.get("account_type", "reactive") == account_type.value
        ]

    # ============== Brain Config Methods ==============

    def get_brain_config(self, phone_number: str) -> BrainConfig:
        """Get the brain configuration for an account."""
        if phone_number not in self.accounts:
            return BrainConfig()

        brain_data = self.accounts[phone_number].get("brain_config", {})
        return BrainConfig.from_dict(brain_data)

    def set_brain_config(self, phone_number: str, brain_config: BrainConfig) -> bool:
        """Set the brain configuration for an account."""
        if phone_number not in self.accounts:
            return False

        self.accounts[phone_number]["brain_config"] = brain_config.to_dict()
        self.save_accounts()
        logger.info(f"Brain config updated for: {phone_number}")
        return True

    def get_effective_brain_prompt(self, phone_number: str, shared_prompt: str = "") -> str:
        """Get the effective brain prompt for an account."""
        brain_config = self.get_brain_config(phone_number)

        if brain_config.use_shared_brain:
            return shared_prompt

        if brain_config.custom_prompt:
            return brain_config.custom_prompt

        account_type = self.get_account_type(phone_number)
        return DEFAULT_BRAIN_PROMPTS.get(account_type, shared_prompt)

    # ============== Voice Config Methods ==============

    def get_voice_config(self, phone_number: str):
        """Get the voice configuration for an account."""
        try:
            from voice_service import VoiceConfig
        except ImportError:
            return None

        if phone_number not in self.accounts:
            return VoiceConfig()

        voice_data = self.accounts[phone_number].get("voice_config", {})
        return VoiceConfig.from_dict(voice_data)

    def set_voice_config(self, phone_number: str, voice_config) -> bool:
        """Set the voice configuration for an account."""
        if phone_number not in self.accounts:
            return False

        self.accounts[phone_number]["voice_config"] = voice_config.to_dict()
        self.save_accounts()
        logger.info(f"Voice config updated for: {phone_number}")
        return True

    def is_voice_enabled(self, phone_number: str) -> bool:
        """Check if voice messages are enabled for an account."""
        voice_config = self.get_voice_config(phone_number)
        return voice_config.enabled if voice_config else False

    def get_voice_enabled_accounts(self) -> List[str]:
        """Get all account phone numbers with voice enabled."""
        return [phone for phone in self.accounts.keys() if self.is_voice_enabled(phone)]

    # ============== Combined Account Configuration ==============

    def get_full_account_config(self, phone_number: str) -> Dict[str, Any]:
        """Get the complete configuration for an account."""
        if phone_number not in self.accounts:
            return {}

        return {
            "phone_number": phone_number,
            "account_type": self.get_account_type(phone_number).value,
            "brain_config": self.get_brain_config(phone_number).to_dict(),
            "voice_config": (
                self.get_voice_config(phone_number).to_dict()
                if self.get_voice_config(phone_number)
                else {}
            ),
            "status": self.account_status.get(phone_number, {}),
            "metrics": asdict(self.account_metrics.get(phone_number, AccountMetrics())),
            "shard_id": self.account_to_shard.get(phone_number),
            "basic_info": {
                k: v
                for k, v in self.accounts[phone_number].items()
                if k not in ["brain_config", "voice_config", "account_type"]
            },
        }

    def update_account_config(
        self,
        phone_number: str,
        account_type: AccountType = None,
        brain_config: BrainConfig = None,
        voice_config=None,
        priority: AccountPriority = None,
    ) -> bool:
        """Update multiple configuration options for an account at once."""
        if phone_number not in self.accounts:
            return False

        if account_type is not None:
            self.accounts[phone_number]["account_type"] = account_type.value

        if brain_config is not None:
            self.accounts[phone_number]["brain_config"] = brain_config.to_dict()

        if voice_config is not None:
            self.accounts[phone_number]["voice_config"] = voice_config.to_dict()

        if priority is not None:
            self.accounts[phone_number]["priority"] = priority.value

        self.save_accounts()
        logger.info(f"Account config updated for: {phone_number}")
        return True

    # ============== Legacy Compatibility ==============

    def get_all_accounts(self) -> List[Dict]:
        """Get all accounts (alias for compatibility)."""
        return self.get_account_list()

    def get_account_details(self, phone_number: str) -> Optional[Dict]:
        """Get detailed information about a specific account."""
        if phone_number not in self.accounts:
            return None

        account_data = self.accounts[phone_number]
        status_info = self.account_status.get(phone_number, {})

        return {
            "basic_info": account_data,
            "status_info": status_info,
            "metrics": asdict(self.account_metrics.get(phone_number, AccountMetrics())),
            "client_active": phone_number in self.active_clients,
        }

    async def retry_failed_operations(self, phone_number: str) -> Dict[str, Any]:
        """Retry failed operations for an account."""
        if phone_number not in self.accounts:
            return {"success": False, "error": "Account not found"}

        results = {}
        status_info = self.account_status.get(phone_number, {})

        # Retry connection
        if phone_number not in self.active_clients:
            try:
                success = await self.start_client(phone_number)
                results["connection_retry"] = "success" if success else "failed"
            except Exception as e:
                results["connection_retry"] = f"error: {str(e)}"

        # Retry warmup if needed
        warmup_job_id = status_info.get("warmup_job_id")
        if warmup_job_id and self.warmup_service:
            from account_warmup_service import WarmupStage, WarmupPriority

            warmup_job = self.warmup_service.get_job_status(warmup_job_id)
            if warmup_job and warmup_job.stage == WarmupStage.FAILED:
                new_job_id = self.warmup_service.add_warmup_job(phone_number, WarmupPriority.HIGH)
                self.account_status[phone_number]["warmup_job_id"] = new_job_id
                results["warmup_retry"] = f"Re-queued (job: {new_job_id})"

        return {"success": True, "results": results}

    def is_account_ready(self, phone_number: str) -> Tuple[bool, str]:
        """Check if account is fully ready to use."""
        if phone_number not in self.accounts:
            return False, "Account not found"

        status_info = self.account_status.get(phone_number, {})
        current_status = AccountStatus(status_info.get("status", AccountStatus.CREATED.value))

        if current_status == AccountStatus.READY:
            return True, "Account is ready"
        elif current_status == AccountStatus.ERROR:
            return False, f"Error: {status_info.get('error_message', 'Unknown')}"
        elif current_status == AccountStatus.BANNED:
            return False, "Account is banned"
        elif current_status == AccountStatus.SUSPENDED:
            return False, "Account is suspended"
        elif current_status == AccountStatus.WARMING_UP:
            return False, f"Warming up: {status_info.get('warmup_stage', 'unknown')}"
        else:
            return False, f"Status: {current_status.value}"

    def update_account_status_legacy(self, phone_number: str, status_update: Dict):
        """Legacy method for backward compatibility."""
        if phone_number in self.account_status:
            self.account_status[phone_number].update(status_update)
            self.account_status[phone_number]["last_seen"] = datetime.now()
            if len(status_update) > 0:
                self.save_accounts()

    def update_creation_settings(self, settings: Dict[str, Any]) -> None:
        """Update account creation settings dynamically."""
        self.creation_settings = settings
        logger.info(f"Account creation settings updated")

    # ============== Ban Prevention & Detection ==============

    async def check_account_health(self, phone_number: str) -> Dict[str, Any]:
        """
        Check account health and ban risk.

        Returns:
            Dictionary with health status and risk assessment
        """
        if phone_number not in self.accounts:
            return {"error": "Account not found"}

        result = {
            "phone_number": phone_number,
            "is_healthy": True,
            "ban_risk": "low",
            "ban_probability": 0.0,
            "warnings": [],
            "recommendations": [],
        }

        # Check with enhanced anti-detection if available
        if self._anti_detection_system:
            status = self._anti_detection_system.get_account_status(phone_number)
            result["ban_probability"] = status.get("ban_probability", 0.0)
            result["ban_risk"] = status.get("risk_level", "low")
            result["message_diversity"] = status.get("message_diversity_score", 1.0)

            if status.get("is_quarantined"):
                result["is_healthy"] = False
                result["warnings"].append(
                    f"Account is quarantined until {status.get('quarantine_release_at')}"
                )

            if result["ban_probability"] > 0.5:
                result["is_healthy"] = False
                result["warnings"].append("High ban probability detected")
                result["recommendations"].append("Reduce message frequency")
                result["recommendations"].append("Increase message diversity")

            if status.get("message_diversity_score", 1.0) < 0.5:
                result["warnings"].append("Low message diversity - potential spam detection")
                result["recommendations"].append("Vary your message templates")

        # Check ban indicators from history
        indicators = self.ban_indicators.get(phone_number, {})
        if indicators.get("flood_wait_count", 0) > 3:
            result["warnings"].append(
                f"Multiple flood waits detected ({indicators['flood_wait_count']})"
            )
            result["recommendations"].append("Increase delays between messages")

        if indicators.get("privacy_restricted_count", 0) > 10:
            result["warnings"].append("Many privacy-restricted users encountered")

        # Check connection status
        if phone_number in self.active_clients:
            client = self.active_clients[phone_number]
            if hasattr(client, "client") and hasattr(client.client, "is_connected"):
                if not client.client.is_connected:
                    result["warnings"].append("Client disconnected")

        return result

    def record_api_error(self, phone_number: str, error: Exception) -> Dict[str, Any]:
        """
        Record an API error for ban detection analysis.

        Args:
            phone_number: Account phone number
            error: The exception that occurred

        Returns:
            Dictionary with analysis and recommended action
        """
        error_type = type(error).__name__
        error_str = str(error)

        # Initialize tracking if needed
        if phone_number not in self.ban_indicators:
            self.ban_indicators[phone_number] = {
                "flood_wait_count": 0,
                "privacy_restricted_count": 0,
                "peer_invalid_count": 0,
                "blocked_count": 0,
                "auth_errors": 0,
                "last_error": None,
                "last_error_time": None,
                "total_errors_24h": 0,
            }

        indicators = self.ban_indicators[phone_number]
        indicators["last_error"] = error_str
        indicators["last_error_time"] = datetime.now()
        indicators["total_errors_24h"] += 1

        action = {"should_continue": True, "delay": 0, "quarantine": False}

        # Analyze specific error types
        if isinstance(error, FloodWait):
            indicators["flood_wait_count"] += 1
            wait_time = getattr(error, "value", 60)
            action["delay"] = wait_time + random.randint(10, 60)
            action["reason"] = f"FloodWait: {wait_time}s"

            if indicators["flood_wait_count"] >= 3:
                action["quarantine"] = True
                action["quarantine_duration"] = 60 * indicators["flood_wait_count"]
                action["reason"] = f"Multiple FloodWait errors ({indicators['flood_wait_count']})"

        elif "UserPrivacyRestricted" in error_type or isinstance(error, UserPrivacyRestricted):
            indicators["privacy_restricted_count"] += 1
            action["delay"] = random.uniform(5, 15)
            action["reason"] = "User has privacy restrictions"

        elif "UserBlocked" in error_type or isinstance(error, UserBlocked):
            indicators["blocked_count"] += 1
            action["delay"] = random.uniform(10, 30)
            action["reason"] = "User has blocked this account"

            if indicators["blocked_count"] >= 10:
                action["quarantine"] = True
                action["quarantine_duration"] = 120
                action["reason"] = f"Multiple blocks received ({indicators['blocked_count']})"

        elif "PeerIdInvalid" in error_type or isinstance(error, PeerIdInvalid):
            indicators["peer_invalid_count"] += 1
            action["delay"] = random.uniform(2, 5)

        elif "AUTH" in error_type.upper() or "auth" in error_str.lower():
            indicators["auth_errors"] += 1
            action["should_continue"] = False
            action["reason"] = "Authentication error - account may be compromised"

            # Update account status
            self.update_account_status(
                phone_number, AccountStatus.ERROR, {"error_message": f"Auth error: {error_str}"}
            )

        # Record in anti-detection system
        if self._anti_detection_system:
            self._anti_detection_system.record_error(phone_number, error_type, error_str)

            # Check if auto-quarantine triggered
            is_quarantined, _ = self._anti_detection_system.is_account_quarantined(phone_number)
            if is_quarantined:
                action["quarantine"] = True
                action["should_continue"] = False

        # Execute quarantine if needed
        if action.get("quarantine"):
            self._quarantine_account(
                phone_number,
                action.get("reason", "Multiple errors"),
                action.get("quarantine_duration", 60),
            )

        return action

    def _quarantine_account(self, phone_number: str, reason: str, duration_minutes: int):
        """Quarantine an account to prevent ban."""
        logger.warning(f"🔒 Quarantining account {phone_number}: {reason} ({duration_minutes} min)")

        # Update status
        self.update_account_status(
            phone_number,
            AccountStatus.SUSPENDED,
            {
                "quarantine_reason": reason,
                "quarantine_until": (
                    datetime.now() + timedelta(minutes=duration_minutes)
                ).isoformat(),
            },
        )

        # Use enhanced anti-detection if available
        if self._anti_detection_system and ENHANCED_ANTI_DETECTION_AVAILABLE:
            self._anti_detection_system.quarantine_account(
                phone_number, QuarantineReason.SUSPICIOUS_ACTIVITY, duration_minutes
            )

    async def can_account_send_message(self, phone_number: str) -> Tuple[bool, float, str]:
        """
        Check if an account can send a message (anti-ban check).

        Returns:
            Tuple of (can_send, delay_seconds, reason)
        """
        if phone_number not in self.accounts:
            return False, 0, "Account not found"

        # Check account status
        status_info = self.account_status.get(phone_number, {})
        current_status = AccountStatus(status_info.get("status", AccountStatus.CREATED.value))

        if current_status in [AccountStatus.ERROR, AccountStatus.BANNED]:
            return False, 0, f"Account status: {current_status.value}"

        if current_status == AccountStatus.SUSPENDED:
            quarantine_until = status_info.get("quarantine_until")
            if quarantine_until:
                try:
                    release_time = datetime.fromisoformat(quarantine_until)
                    if datetime.now() < release_time:
                        wait_seconds = (release_time - datetime.now()).total_seconds()
                        return False, wait_seconds, "Account is quarantined"
                    else:
                        # Quarantine expired, restore to ready
                        self.update_account_status(phone_number, AccountStatus.READY)
                except (ValueError, TypeError):
                    pass

        # Check with enhanced anti-detection
        if self._anti_detection_system:
            can_send, delay, reason = self._anti_detection_system.can_send_message(phone_number)
            if not can_send or delay > 0:
                return can_send, delay, reason

        return True, 0, "OK"

    def record_message_sent(self, phone_number: str, message: str, recipient_id: int):
        """Record a sent message for anti-ban tracking."""
        if self._anti_detection_system:
            self._anti_detection_system.record_message_sent(phone_number, message, recipient_id)

        # Update metrics
        if phone_number in self.account_metrics:
            self.account_metrics[phone_number].messages_sent += 1
            self.account_metrics[phone_number].last_activity = datetime.now()

    def get_device_fingerprint(self, phone_number: str) -> Dict[str, Any]:
        """Get device fingerprint for an account."""
        if not self._anti_detection_system:
            # Fallback to basic fingerprint
            from anti_detection_system import AntiDetectionSystem

            basic_system = AntiDetectionSystem()
            return basic_system.generate_device_config()

        fingerprint = self._anti_detection_system.get_or_create_fingerprint(phone_number)
        return fingerprint.to_pyrogram_config()

    def get_ban_prevention_stats(self) -> Dict[str, Any]:
        """Get overall ban prevention statistics."""
        stats = {
            "total_accounts": len(self.accounts),
            "quarantined_accounts": 0,
            "high_risk_accounts": 0,
            "accounts_with_errors": 0,
            "total_flood_waits": 0,
        }

        for phone_number, indicators in self.ban_indicators.items():
            if indicators.get("total_errors_24h", 0) > 0:
                stats["accounts_with_errors"] += 1
            stats["total_flood_waits"] += indicators.get("flood_wait_count", 0)

        if self._anti_detection_system:
            for phone_number in self.accounts.keys():
                is_quarantined, _ = self._anti_detection_system.is_account_quarantined(phone_number)
                if is_quarantined:
                    stats["quarantined_accounts"] += 1

                metrics = self._anti_detection_system.account_metrics.get(phone_number)
                if metrics and metrics.risk_level in [BanRiskLevel.HIGH, BanRiskLevel.CRITICAL]:
                    stats["high_risk_accounts"] += 1

        return stats

    def reset_daily_ban_indicators(self):
        """Reset daily ban indicators (call at midnight)."""
        for indicators in self.ban_indicators.values():
            indicators["total_errors_24h"] = 0

        if self._anti_detection_system:
            self._anti_detection_system.reset_daily_metrics()

        logger.info("Daily ban indicators reset")

    def get_account_full_status(self, phone_number: str) -> Optional[Dict]:
        """Get complete status information for an account."""
        if phone_number not in self.accounts:
            return None

        account_data = self.accounts[phone_number]
        status_info = self.account_status.get(phone_number, {})

        return {
            "phone_number": phone_number,
            "account_data": account_data,
            "status": status_info.get("status", AccountStatus.CREATED.value),
            "status_enum": AccountStatus(status_info.get("status", AccountStatus.CREATED.value)),
            "is_online": status_info.get("is_online", False),
            "connection_status": (
                self.connection_manager.get_connection_status(phone_number)
                if phone_number in self.active_clients
                else None
            ),
            "warmup_info": {
                "job_id": status_info.get("warmup_job_id"),
                "stage": status_info.get("warmup_stage"),
                "progress": status_info.get("warmup_progress", 0.0),
            },
            "error": status_info.get("error_message"),
            "ready_at": status_info.get("ready_at"),
            "created_at": status_info.get("created_at"),
            "last_seen": status_info.get("last_seen"),
            "proxy": account_data.get("proxy"),
            "is_ready": self.is_account_ready(phone_number)[0],
        }
