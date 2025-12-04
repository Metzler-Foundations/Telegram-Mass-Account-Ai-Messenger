#!/usr/bin/env python3
"""
Proxy Pool Manager - Enterprise-grade proxy management with 15-endpoint feed system.

Features:
- Auto-fetch from 15 proxy endpoints (Primary, Secondary, Obscure feeds)
- Filter for US-based SOCKS5 proxies
- Health checking with response time tracking
- Auto-assign proxy to accounts on creation
- Auto-reassign when proxy dies
- Proxy scoring system (latency, uptime, fraud score)
- Connection pooling per proxy
- Geographic clustering for account consistency
"""

import asyncio
import aiohttp
import logging
import json
import re
import socket
import time
import hashlib
import random
import sqlite3
import base64
import shutil
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import threading

logger = logging.getLogger(__name__)

# Import cryptography for secure credential storage
try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("cryptography not available - proxy credentials will not be encrypted")


class ProxyCredentialManager:
    """Secure proxy credential encryption/decryption manager."""

    def __init__(self):
        self._cipher = None
        self._init_cipher()

    def _init_cipher(self):
        """Initialize encryption cipher with secure key."""
        if not CRYPTOGRAPHY_AVAILABLE:
            logger.warning("Cryptography not available - proxy credentials will be stored in plain text")
            return

        try:
            # Try to get key from secure storage
            key = self._get_or_create_encryption_key()
            self._cipher = Fernet(key)
            logger.info("Proxy credential encryption initialized")
        except Exception as e:
            logger.error(f"Failed to initialize proxy credential encryption: {e}")
            self._cipher = None

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for proxy credentials."""
        try:
            # Try OS keyring first
            import keyring
            keyring_service = "telegram_bot_proxy_credentials"
            stored_key = keyring.get_password(keyring_service, "encryption_key")

            if stored_key:
                return base64.urlsafe_b64decode(stored_key)

            # Generate new key
            key = Fernet.generate_key()
            keyring.set_password(keyring_service, "encryption_key", base64.urlsafe_b64encode(key).decode())
            logger.info("Generated new proxy credential encryption key")
            return key

        except ImportError:
            logger.warning("keyring not available for proxy credentials")
        except Exception as e:
            logger.warning(f"Failed to use keyring for proxy credentials: {e}")

        # Fallback to secure directory
        try:
            import platformdirs
            config_dir = Path(platformdirs.user_config_dir("telegram_bot", "telegram_bot"))
            config_dir.mkdir(parents=True, exist_ok=True)

            key_file = config_dir / "proxy_encryption_key.bin"

            if key_file.exists():
                with open(key_file, 'rb') as f:
                    key = f.read()
                    if len(key) == 44:  # Fernet key length
                        return key

            # Generate new key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)

            # Set restrictive permissions
            try:
                import stat
                key_file.chmod(stat.S_IRUSR | stat.S_IWUSR)
            except Exception:
                pass  # Ignore permission setting failures on some systems

            logger.info(f"Stored proxy encryption key in secure directory: {config_dir}")
            return key

        except Exception as e:
            logger.error(f"Failed to create secure proxy key storage: {e}")

        # Last resort - generate key but don't store (not recommended)
        logger.warning("Using ephemeral proxy encryption key - NOT RECOMMENDED")
        return Fernet.generate_key()

    def encrypt_credential(self, credential: str) -> str:
        """Encrypt a credential string."""
        if not self._cipher or not credential:
            return credential

        try:
            return self._cipher.encrypt(credential.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt proxy credential: {e}")
            return credential

    def decrypt_credential(self, encrypted_credential: str) -> str:
        """Decrypt a credential string."""
        if not self._cipher or not encrypted_credential:
            return encrypted_credential

        try:
            return self._cipher.decrypt(encrypted_credential.encode()).decode()
        except (InvalidToken, Exception) as e:
            logger.warning(f"Failed to decrypt proxy credential (may be stored in plain text): {e}")
            return encrypted_credential  # Return as-is if decryption fails


class ProxyProtocol(Enum):
    """Supported proxy protocols."""
    HTTP = "http"
    HTTPS = "https"
    SOCKS4 = "socks4"
    SOCKS5 = "socks5"


class ProxyTier(Enum):
    """Proxy quality tiers."""
    PREMIUM = "premium"      # <100ms, 99%+ uptime
    STANDARD = "standard"    # <500ms, 95%+ uptime
    ECONOMY = "economy"      # <1000ms, 90%+ uptime
    LOW = "low"              # >1000ms or <90% uptime


class ProxyStatus(Enum):
    """Proxy status."""
    ACTIVE = "active"
    TESTING = "testing"
    FAILED = "failed"
    COOLDOWN = "cooldown"
    BLACKLISTED = "blacklisted"


@dataclass
class ProxyEndpoint:
    """Proxy feed endpoint configuration."""
    name: str
    url: str
    feed_type: str  # "primary", "secondary", "obscure"
    poll_interval: int  # seconds
    parser: str  # "text", "json", "json_monosans", "json_hookzof"
    country_filter: Optional[str] = "US"
    protocol_filter: Optional[str] = "socks5"
    last_poll: Optional[datetime] = None
    success_count: int = 0
    failure_count: int = 0


@dataclass
class Proxy:
    """Individual proxy with full metadata."""
    ip: str
    port: int
    protocol: ProxyProtocol = ProxyProtocol.SOCKS5
    username: Optional[str] = None
    password: Optional[str] = None
    country: str = "US"
    city: Optional[str] = None
    isp: Optional[str] = None
    
    # Performance metrics
    latency_ms: float = 0.0
    uptime_percent: float = 100.0
    success_count: int = 0
    failure_count: int = 0
    last_check: Optional[datetime] = None
    last_used: Optional[datetime] = None
    
    # Scoring
    score: float = 100.0
    tier: ProxyTier = ProxyTier.STANDARD
    fraud_score: float = 0.0
    
    # Status
    status: ProxyStatus = ProxyStatus.TESTING
    assigned_account: Optional[str] = None
    cooldown_until: Optional[datetime] = None
    
    # Source tracking
    source_endpoint: Optional[str] = None
    first_seen: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validate proxy data after initialization."""
        self._validate_proxy_data()

    def _validate_proxy_data(self):
        """Validate proxy data and raise exceptions for invalid data."""
        try:
            from user_helpers import ValidationHelper

            # Validate and normalize IP address (remove leading zeros from octets)
            import ipaddress
            try:
                # Normalize IP by removing leading zeros (e.g., 192.168.001.01 -> 192.168.1.1)
                if self.ip and '.' in self.ip:
                    normalized_ip = '.'.join(str(int(octet)) for octet in self.ip.split('.'))
                    self.ip = normalized_ip
                ipaddress.ip_address(self.ip)
            except (ValueError, AttributeError):
                raise ValueError(f"Invalid IP address: {self.ip}")

            # Validate port
            if not isinstance(self.port, int) or not (1 <= self.port <= 65535):
                raise ValueError(f"Invalid port number: {self.port} (must be 1-65535)")

            # Validate protocol
            if not isinstance(self.protocol, ProxyProtocol):
                raise ValueError(f"Invalid protocol: {self.protocol}")

            # Validate country code
            if self.country and len(self.country) != 2:
                logger.warning(f"Country code should be 2 characters: {self.country}")

            # Validate latency
            if self.latency_ms < 0:
                raise ValueError(f"Latency cannot be negative: {self.latency_ms}")

            # Validate uptime percentage
            if not (0.0 <= self.uptime_percent <= 100.0):
                raise ValueError(f"Uptime percentage must be 0-100: {self.uptime_percent}")

            # Validate score
            if not (0.0 <= self.score <= 100.0):
                raise ValueError(f"Score must be 0-100: {self.score}")

        except ImportError:
            # Skip validation if ValidationHelper not available
            logger.warning("ValidationHelper not available, skipping proxy validation")
        except Exception as e:
            logger.error(f"Proxy validation failed: {e}")
            raise

    @property
    def proxy_key(self) -> str:
        """Unique key for this proxy."""
        return f"{self.ip}:{self.port}"
    
    @property
    def url(self) -> str:
        """Get proxy URL string."""
        if self.username and self.password:
            return f"{self.protocol.value}://{self.username}:{self.password}@{self.ip}:{self.port}"
        return f"{self.protocol.value}://{self.ip}:{self.port}"
    
    @property
    def pyrogram_dict(self) -> Dict:
        """Get Pyrogram-compatible proxy dict."""
        proxy_dict = {
            "scheme": self.protocol.value,
            "hostname": self.ip,
            "port": self.port
        }
        if self.username:
            proxy_dict["username"] = self.username
        if self.password:
            proxy_dict["password"] = self.password
        return proxy_dict
    
    def update_score(self):
        """Recalculate proxy score based on metrics."""
        score = 100.0
        
        # Latency penalty (0-30 points)
        if self.latency_ms > 2000:
            score -= 30
        elif self.latency_ms > 1000:
            score -= 20
        elif self.latency_ms > 500:
            score -= 10
        elif self.latency_ms > 200:
            score -= 5
        
        # Uptime bonus/penalty (-20 to +10)
        if self.uptime_percent >= 99:
            score += 10
        elif self.uptime_percent >= 95:
            score += 5
        elif self.uptime_percent < 90:
            score -= 20
        elif self.uptime_percent < 95:
            score -= 10
        
        # Fraud score penalty (0-30 points)
        score -= self.fraud_score * 30
        
        # Success rate factor
        total_attempts = self.success_count + self.failure_count
        if total_attempts > 0:
            success_rate = self.success_count / total_attempts
            if success_rate < 0.5:
                score -= 25
            elif success_rate < 0.8:
                score -= 15
            elif success_rate < 0.9:
                score -= 5
        
        self.score = max(0, min(100, score))
        
        # Determine tier
        if self.score >= 90 and self.latency_ms < 100:
            self.tier = ProxyTier.PREMIUM
        elif self.score >= 70 and self.latency_ms < 500:
            self.tier = ProxyTier.STANDARD
        elif self.score >= 50:
            self.tier = ProxyTier.ECONOMY
        else:
            self.tier = ProxyTier.LOW
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        data = asdict(self)
        data['protocol'] = self.protocol.value
        data['tier'] = self.tier.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Proxy':
        """Create from dictionary."""
        data['protocol'] = ProxyProtocol(data.get('protocol', 'socks5'))
        data['tier'] = ProxyTier(data.get('tier', 'standard'))
        data['status'] = ProxyStatus(data.get('status', 'testing'))
        return cls(**data)


class ProxyPoolManager:
    """
    Enterprise-grade proxy pool manager with multi-feed ingestion.
    
    Implements the full 15-endpoint proxy feed system with:
    - Primary Feed (5-10 min polling): High quality, fresh proxies
    - Secondary Feed (30-60 min polling): Rich metadata, stable proxies  
    - Obscure Feed (variable polling): Unsaturated, niche sources
    """
    
    # Primary Feed Endpoints (poll every 5-10 minutes)
    PRIMARY_ENDPOINTS = [
        ProxyEndpoint(
            name="proxifly_us",
            url="https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/countries/US/data.txt",
            feed_type="primary",
            poll_interval=300,  # 5 min
            parser="text",
            country_filter="US"
        ),
        ProxyEndpoint(
            name="proxifly_socks5",
            url="https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/socks5/data.txt",
            feed_type="primary",
            poll_interval=300,
            parser="text",
            protocol_filter="socks5"
        ),
        ProxyEndpoint(
            name="clearproxy",
            url="https://raw.githubusercontent.com/ClearProxy/checked-proxy-list/main/socks5/raw/all.txt",
            feed_type="primary",
            poll_interval=420,  # 7 min
            parser="text"
        ),
        ProxyEndpoint(
            name="vakhov",
            url="https://vakhov.github.io/fresh-proxy-list/socks5.txt",
            feed_type="primary",
            poll_interval=600,  # 10 min
            parser="text"
        ),
    ]
    
    # Secondary Feed Endpoints (poll every 30-60 minutes)
    SECONDARY_ENDPOINTS = [
        ProxyEndpoint(
            name="monosans_json",
            url="https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/proxies.json",
            feed_type="secondary",
            poll_interval=1800,  # 30 min
            parser="json_monosans"
        ),
        ProxyEndpoint(
            name="hookzof_text",
            url="https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
            feed_type="secondary",
            poll_interval=2700,  # 45 min
            parser="text"
        ),
        ProxyEndpoint(
            name="hookzof_telegram",
            url="https://raw.githubusercontent.com/hookzof/socks5_list/master/tg/socks.json",
            feed_type="secondary",
            poll_interval=3600,  # 60 min
            parser="json_hookzof"
        ),
    ]
    
    # Obscure Feed Endpoints (variable polling for unsaturated sources)
    OBSCURE_ENDPOINTS = [
        ProxyEndpoint(
            name="zloi_hideip",
            url="https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt",
            feed_type="obscure",
            poll_interval=900,  # 15 min
            parser="text"
        ),
        ProxyEndpoint(
            name="prxchk",
            url="https://raw.githubusercontent.com/prxchk/proxy-list/main/socks5.txt",
            feed_type="obscure",
            poll_interval=900,
            parser="text"
        ),
        ProxyEndpoint(
            name="sunny9577",
            url="https://sunny9577.github.io/proxy-scraper/generated/socks5_proxies.txt",
            feed_type="obscure",
            poll_interval=1200,  # 20 min
            parser="text"
        ),
        ProxyEndpoint(
            name="breakingtechfr",
            url="https://raw.githubusercontent.com/BreakingTechFr/Proxy_Free/main/proxies/socks5.txt",
            feed_type="obscure",
            poll_interval=1200,
            parser="text"
        ),
        ProxyEndpoint(
            name="murongpig",
            url="https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/socks5.txt",
            feed_type="obscure",
            poll_interval=1500,  # 25 min
            parser="text"
        ),
        ProxyEndpoint(
            name="ercindedeoglu",
            url="https://raw.githubusercontent.com/ErcinDedeoglu/proxies/main/proxies/socks5.txt",
            feed_type="obscure",
            poll_interval=1500,
            parser="text"
        ),
        ProxyEndpoint(
            name="hyperbeats",
            url="https://raw.githubusercontent.com/HyperBeats/proxy-list/main/socks5.txt",
            feed_type="obscure",
            poll_interval=1800,  # 30 min
            parser="text"
        ),
        ProxyEndpoint(
            name="javadbazokar",
            url="https://raw.githubusercontent.com/javadbazokar/PROXY-List/main/socks5.txt",
            feed_type="obscure",
            poll_interval=1800,
            parser="text"
        ),
        ProxyEndpoint(
            name="roosterkid",
            url="https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
            feed_type="obscure",
            poll_interval=2100,  # 35 min
            parser="text"
        ),
    ]
    
    def __init__(self, db_path: str = "proxy_pool.db", config_path: str = "config.json"):
        """Initialize the proxy pool manager."""
        self.db_path = db_path
        self.config_path = config_path
        self.credential_manager = ProxyCredentialManager()
        self._last_backup_error: Optional[str] = None

        # Proxy storage
        self.proxies: Dict[str, Proxy] = {}  # proxy_key -> Proxy
        self.available_proxies: Set[str] = set()  # Keys of unassigned, active proxies
        self.assigned_proxies: Dict[str, str] = {}  # account_phone -> proxy_key
        
        # Endpoint management
        self.endpoints: List[ProxyEndpoint] = (
            self.PRIMARY_ENDPOINTS + 
            self.SECONDARY_ENDPOINTS + 
            self.OBSCURE_ENDPOINTS
        )
        
        # Runtime state
        self.is_running = False
        self.poll_tasks: Dict[str, asyncio.Task] = {}
        self.health_check_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None
        self._fetch_semaphore = asyncio.Semaphore(5)
        
        # Configuration (defaults)
        self.config = {
            'min_score': 30,              # Minimum score to use proxy
            'health_check_interval': 60,   # Seconds between health checks
            'max_failures': 5,             # Max failures before blacklist
            'cooldown_duration': 300,      # Seconds in cooldown after failure
            'test_url': 'https://api.telegram.org',
            'test_timeout': 10,
            'max_concurrent_checks': 20,
            'prefer_us_proxies': True,
            'auto_reassign': True,
            'max_active_proxies': 10000,  # Maximum proxies to keep in pool
            'min_score_threshold': 30,    # Minimum score to keep proxy
            'max_fraud_score': 0.75,      # Maximum fraud score allowed
            'auto_cleanup_enabled': True, # Enable automatic cleanup
            'health_check_batch_size': 50, # Proxies to check per batch
            'batch_delay': 2.0,           # Seconds between batches
        }
        
        # Load config from file if available
        self._load_config_from_file()
        
        # Thread pool for blocking operations (use centralized config)
        try:
            from utils.threadpool_config import get_thread_pool
            self.executor = get_thread_pool().executor
            logger.info("Using shared thread pool for proxy operations")
        except ImportError:
            # Fallback to local thread pool if config not available
            self.executor = ThreadPoolExecutor(max_workers=30)
            logger.warning("Using local thread pool (shared pool not available)")
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        # Initialize connection pool if available
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool
            self._connection_pool = get_pool(self.db_path)
            logger.info("Using connection pool for proxy database")
        except ImportError:
            logger.warning("Connection pool not available, using direct sqlite3 connections")
        except Exception as e:
            logger.warning(f"Failed to initialize connection pool: {e}")
        
        # Statistics
        self.stats = {
            'total_fetched': 0,
            'total_validated': 0,
            'total_failed': 0,
            'endpoints_polled': 0,
            'last_full_poll': None,
        }
        
        # Initialize database
        self._init_database()

        # Verify database health and rotate a checksum-backed snapshot for recovery
        if not self._verify_database_integrity():
            logger.warning("Proxy database integrity check failed; writes may be unsafe until repaired")
        else:
            self._create_integrity_checked_backup()
    
    def _get_connection(self):
        """Get a database connection (using pool if available).
        
        Returns:
            Context manager for database connection
        """
        if self._connection_pool:
            return self._connection_pool.get_connection()
        else:
            # Fallback to direct connection
            return self._get_connection()

        # Restore persisted statistics so historical health is not lost between restarts
        self._load_stats()

        # Migrate proxy credentials to encrypted storage if needed
        self._migrate_proxy_credentials()

        # Load existing proxies
        self._load_proxies()
        
        logger.info(f"ProxyPoolManager initialized with {len(self.endpoints)} endpoints, {len(self.proxies)} proxies loaded")
    
    def _load_config_from_file(self):
        """Load configuration from config.json if available."""
        try:
            import json
            from pathlib import Path
            
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    file_config = json.load(f)
                
                # Update config from proxy_pool section
                if 'proxy_pool' in file_config:
                    proxy_pool_config = file_config['proxy_pool']
                    
                    # Update configuration values
                    if 'max_active_proxies' in proxy_pool_config:
                        self.config['max_active_proxies'] = proxy_pool_config['max_active_proxies']
                    if 'min_score_threshold' in proxy_pool_config:
                        self.config['min_score_threshold'] = proxy_pool_config['min_score_threshold']
                    if 'max_fraud_score' in proxy_pool_config:
                        self.config['max_fraud_score'] = proxy_pool_config['max_fraud_score']
                    if 'auto_cleanup_enabled' in proxy_pool_config:
                        self.config['auto_cleanup_enabled'] = proxy_pool_config['auto_cleanup_enabled']
                    if 'health_check_batch_size' in proxy_pool_config:
                        self.config['health_check_batch_size'] = proxy_pool_config['health_check_batch_size']
                    if 'health_check_interval' in proxy_pool_config:
                        self.config['health_check_interval'] = proxy_pool_config['health_check_interval']
                    if 'batch_delay' in proxy_pool_config:
                        self.config['batch_delay'] = proxy_pool_config.get('batch_delay', 2.0)
                    
                    logger.info(f"Loaded proxy pool configuration from {self.config_path}")
                    logger.info(f"  Max active proxies: {self.config['max_active_proxies']}")
                    logger.info(f"  Min score threshold: {self.config['min_score_threshold']}")
                    logger.info(f"  Max fraud score: {self.config['max_fraud_score']}")
                    logger.info(f"  Auto cleanup: {self.config['auto_cleanup_enabled']}")
        except Exception as e:
            logger.warning(f"Failed to load config from file, using defaults: {e}")

    @staticmethod
    def _hash_file(path: Path) -> Optional[str]:
        """Compute a SHA256 hash for a file."""
        try:
            digest = hashlib.sha256()
            with open(path, 'rb') as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except Exception as exc:
            logger.error(f"Failed to hash file {path}: {exc}")
            return None

    def _verify_database_integrity(self, db_path: Optional[Path] = None) -> bool:
        """Run PRAGMA integrity_check to ensure the proxy database is readable."""
        target = Path(db_path) if db_path else Path(self.db_path)
        if not target.exists():
            return True

        try:
            with sqlite3.connect(target) as conn:
                result = conn.execute("PRAGMA integrity_check").fetchone()
                if result and result[0].lower() == "ok":
                    return True
                logger.error(f"Proxy DB integrity check failed for {target}: {result}")
        except Exception as exc:
            logger.error(f"Proxy DB integrity check error for {target}: {exc}")
        return False

    def _create_integrity_checked_backup(self) -> Optional[Path]:
        """Create a proxy DB backup with checksum verification and prune old snapshots."""
        db_file = Path(self.db_path)
        if not db_file.exists():
            return None

        backup_dir = db_file.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"proxy_pool_{timestamp}.db"

        try:
            shutil.copy2(db_file, backup_path)
            original_hash = self._hash_file(db_file)
            backup_hash = self._hash_file(backup_path)

            if not original_hash or not backup_hash or original_hash != backup_hash:
                raise ValueError("Backup checksum mismatch")

            if not self._verify_database_integrity(backup_path):
                raise ValueError("Backup failed integrity check")

            self._prune_old_backups(backup_dir, keep=5)
            logger.info(f"Created integrity-checked proxy DB backup at {backup_path}")
            self._last_backup_error = None
            return backup_path
        except Exception as exc:
            self._last_backup_error = str(exc)
            logger.error(f"Failed to create proxy DB backup: {exc}")
            try:
                backup_path.unlink(missing_ok=True)
            except Exception:
                pass
        return None

    @staticmethod
    def _prune_old_backups(backup_dir: Path, keep: int = 5):
        """Keep only the most recent N backups to avoid unbounded growth."""
        try:
            backups = sorted(backup_dir.glob("proxy_pool_*.db"), reverse=True)
            for stale in backups[keep:]:
                stale.unlink()
                logger.info(f"Removed old proxy DB backup: {stale}")
        except Exception as exc:
            logger.warning(f"Failed to prune old proxy DB backups: {exc}")

    def _init_database(self):
        """Initialize the proxy database."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS proxies (
                    proxy_key TEXT PRIMARY KEY,
                    ip TEXT NOT NULL,
                    port INTEGER NOT NULL,
                    protocol TEXT DEFAULT 'socks5',
                    username TEXT,
                    password TEXT,
                    country TEXT DEFAULT 'US',
                    city TEXT,
                    isp TEXT,
                    latency_ms REAL DEFAULT 0,
                    uptime_percent REAL DEFAULT 100,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    last_check TIMESTAMP,
                    last_used TIMESTAMP,
                    score REAL DEFAULT 100,
                    tier TEXT DEFAULT 'standard',
                    fraud_score REAL DEFAULT 0,
                    status TEXT DEFAULT 'testing',
                    assigned_account TEXT,
                    cooldown_until TIMESTAMP,
                    source_endpoint TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS proxy_assignments (
                    account_phone TEXT PRIMARY KEY,
                    proxy_key TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_permanent BOOLEAN DEFAULT 1,
                    FOREIGN KEY(proxy_key) REFERENCES proxies(proxy_key)
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS proxy_health_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    proxy_key TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    latency_ms REAL,
                    success BOOLEAN,
                    error_message TEXT,
                    FOREIGN KEY(proxy_key) REFERENCES proxies(proxy_key)
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS proxy_pool_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    total_fetched INTEGER DEFAULT 0,
                    total_validated INTEGER DEFAULT 0,
                    total_failed INTEGER DEFAULT 0,
                    endpoints_polled INTEGER DEFAULT 0,
                    last_full_poll TIMESTAMP
                )
            ''')
            conn.execute("INSERT OR IGNORE INTO proxy_pool_stats (id) VALUES (1)")

            # Indexes for efficient queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_status ON proxies(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_score ON proxies(score DESC)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_fraud_score ON proxies(fraud_score)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_last_check ON proxies(last_check)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_country ON proxies(country)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_assigned ON proxies(assigned_account)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_tier ON proxies(tier)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_latency ON proxies(latency_ms)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_last_used ON proxies(last_used DESC)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_protocol ON proxies(protocol)')
            
            # Composite index for common query patterns
            conn.execute('CREATE INDEX IF NOT EXISTS idx_proxy_status_score ON proxies(status, score DESC)')

            conn.commit()

    def _load_stats(self):
        """Load persisted pool statistics so historical health is retained."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("SELECT * FROM proxy_pool_stats WHERE id = 1")
                row = cursor.fetchone()
                if row:
                    self.stats['total_fetched'] = row['total_fetched'] or 0
                    self.stats['total_validated'] = row['total_validated'] or 0
                    self.stats['total_failed'] = row['total_failed'] or 0
                    self.stats['endpoints_polled'] = row['endpoints_polled'] or 0
                    self.stats['last_full_poll'] = (
                        datetime.fromisoformat(row['last_full_poll'])
                        if row['last_full_poll'] else None
                    )
                    logger.info(
                        "Restored proxy pool stats: fetched=%s validated=%s failed=%s",
                        self.stats['total_fetched'],
                        self.stats['total_validated'],
                        self.stats['total_failed'],
                    )
        except Exception as exc:
            logger.warning(f"Could not load proxy pool stats: {exc}")

    def _persist_stats(self):
        """Persist pool statistics to disk for restart continuity."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    '''
                        INSERT INTO proxy_pool_stats (id, total_fetched, total_validated, total_failed, endpoints_polled, last_full_poll)
                        VALUES (1, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            total_fetched=excluded.total_fetched,
                            total_validated=excluded.total_validated,
                            total_failed=excluded.total_failed,
                            endpoints_polled=excluded.endpoints_polled,
                            last_full_poll=excluded.last_full_poll
                    ''',
                    (
                        self.stats['total_fetched'],
                        self.stats['total_validated'],
                        self.stats['total_failed'],
                        self.stats['endpoints_polled'],
                        self.stats['last_full_poll'].isoformat() if self.stats['last_full_poll'] else None,
                    ),
                )
                conn.commit()
        except Exception as exc:
            logger.warning(f"Could not persist proxy pool stats: {exc}")

    def _load_proxies(self):
        """Load proxies from database with optimized query."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                # Only load proxies that meet minimum criteria
                # Load top proxies by score, limit to prevent memory issues
                query = '''
                    SELECT * FROM proxies 
                    WHERE status != ? 
                    AND (score >= ? OR assigned_account IS NOT NULL)
                    AND fraud_score < ?
                    ORDER BY 
                        CASE WHEN assigned_account IS NOT NULL THEN 0 ELSE 1 END,
                        score DESC
                    LIMIT ?
                '''
                cursor = conn.execute(
                    query, 
                    (
                        ProxyStatus.BLACKLISTED.value,
                        self.config['min_score_threshold'],
                        self.config['max_fraud_score'],
                        self.config['max_active_proxies']
                    )
                )
                
                for row in cursor.fetchall():
                    # Decrypt credentials when loading from database
                    decrypted_username = self.credential_manager.decrypt_credential(row['username']) if row['username'] else None
                    decrypted_password = self.credential_manager.decrypt_credential(row['password']) if row['password'] else None

                    proxy = Proxy(
                        ip=row['ip'],
                        port=row['port'],
                        protocol=ProxyProtocol(row['protocol']),
                        username=decrypted_username,
                        password=decrypted_password,
                        country=row['country'] or 'US',
                        city=row['city'],
                        isp=row['isp'],
                        latency_ms=row['latency_ms'] or 0,
                        uptime_percent=row['uptime_percent'] or 100,
                        success_count=row['success_count'] or 0,
                        failure_count=row['failure_count'] or 0,
                        score=row['score'] or 100,
                        tier=ProxyTier(row['tier']) if row['tier'] else ProxyTier.STANDARD,
                        fraud_score=row['fraud_score'] or 0,
                        status=ProxyStatus(row['status']) if row['status'] else ProxyStatus.TESTING,
                        assigned_account=row['assigned_account'],
                        source_endpoint=row['source_endpoint'],
                    )
                    
                    self.proxies[proxy.proxy_key] = proxy
                    
                    if proxy.status == ProxyStatus.ACTIVE and not proxy.assigned_account:
                        self.available_proxies.add(proxy.proxy_key)
                    
                    if proxy.assigned_account:
                        self.assigned_proxies[proxy.assigned_account] = proxy.proxy_key
                
                logger.info(f"Loaded {len(self.proxies)} proxies from database ({len(self.available_proxies)} available)")
                
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
    
    def _save_proxy(self, proxy: Proxy):
        """Save a single proxy to database."""
        try:
            with self._get_connection() as conn:
                # Encrypt credentials before storing
                encrypted_username = self.credential_manager.encrypt_credential(proxy.username) if proxy.username else None
                encrypted_password = self.credential_manager.encrypt_credential(proxy.password) if proxy.password else None

                conn.execute('''
                    INSERT OR REPLACE INTO proxies
                    (proxy_key, ip, port, protocol, username, password, country, city, isp,
                     latency_ms, uptime_percent, success_count, failure_count, last_check, last_used,
                     score, tier, fraud_score, status, assigned_account, cooldown_until, source_endpoint, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (
                    proxy.proxy_key, proxy.ip, proxy.port, proxy.protocol.value,
                    encrypted_username, encrypted_password, proxy.country, proxy.city, proxy.isp,
                    proxy.latency_ms, proxy.uptime_percent, proxy.success_count, proxy.failure_count,
                    proxy.last_check, proxy.last_used, proxy.score, proxy.tier.value, proxy.fraud_score,
                    proxy.status.value, proxy.assigned_account, proxy.cooldown_until, proxy.source_endpoint
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save proxy {proxy.proxy_key}: {e}")

    def _migrate_proxy_credentials(self):
        """Migrate existing proxy credentials to encrypted storage."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('SELECT proxy_key, username, password FROM proxies WHERE username IS NOT NULL OR password IS NOT NULL')

                credentials_to_update = []
                for row in cursor.fetchall():
                    proxy_key = row['proxy_key']
                    username = row['username']
                    password = row['password']

                    # Check if credentials are already encrypted (by trying to decrypt)
                    needs_encryption = False

                    if username:
                        try:
                            self.credential_manager.decrypt_credential(username)
                            # If decryption succeeds, it's likely already encrypted
                        except Exception:
                            needs_encryption = True

                    if password and not needs_encryption:
                        try:
                            self.credential_manager.decrypt_credential(password)
                            # If decryption succeeds, it's likely already encrypted
                        except Exception:
                            needs_encryption = True

                    if needs_encryption:
                        encrypted_username = self.credential_manager.encrypt_credential(username) if username else None
                        encrypted_password = self.credential_manager.encrypt_credential(password) if password else None

                        credentials_to_update.append((encrypted_username, encrypted_password, proxy_key))
                        logger.info(f"Will migrate credentials for proxy {proxy_key}")

                # Update the database with encrypted credentials
                if credentials_to_update:
                    conn.executemany('''
                        UPDATE proxies
                        SET username = ?, password = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE proxy_key = ?
                    ''', credentials_to_update)
                    conn.commit()

                    logger.info(f"Successfully migrated {len(credentials_to_update)} proxy credential sets to encrypted storage")
                else:
                    logger.debug("No proxy credentials needed migration")

        except Exception as e:
            logger.error(f"Failed to migrate proxy credentials: {e}")

    async def start(self):
        """Start the proxy pool manager."""
        if self.is_running:
            logger.warning("ProxyPoolManager already running")
            return
        
        self.is_running = True
        logger.info("🚀 Starting ProxyPoolManager...")
        
        # Start endpoint polling tasks
        for endpoint in self.endpoints:
            task = asyncio.create_task(self._poll_endpoint_loop(endpoint))
            self.poll_tasks[endpoint.name] = task
        
        # Start health check task
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        # Initial fetch from all endpoints
        await self._fetch_all_endpoints()
        
        logger.info(f"✅ ProxyPoolManager started with {len(self.poll_tasks)} polling tasks")
    
    async def stop(self):
        """Stop the proxy pool manager."""
        self.is_running = False
        
        # Cancel all tasks
        for name, task in self.poll_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Shutdown executor
        self.executor.shutdown(wait=False)
        
        logger.info("🛑 ProxyPoolManager stopped")
    
    async def _fetch_all_endpoints(self):
        """Fetch from all endpoints concurrently."""
        logger.info("📡 Fetching from all proxy endpoints...")
        
        tasks = [self._fetch_endpoint(endpoint) for endpoint in self.endpoints]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_new = sum(r for r in results if isinstance(r, int))
        self.stats['last_full_poll'] = datetime.now()
        self._persist_stats()
        
        logger.info(f"✅ Fetched {total_new} new proxies from {len(self.endpoints)} endpoints")
    
    async def _poll_endpoint_loop(self, endpoint: ProxyEndpoint):
        """Polling loop for a single endpoint."""
        while self.is_running:
            try:
                # Check if it's time to poll
                if endpoint.last_poll:
                    time_since_poll = (datetime.now() - endpoint.last_poll).total_seconds()
                    if time_since_poll < endpoint.poll_interval:
                        await asyncio.sleep(endpoint.poll_interval - time_since_poll)
                        continue
                
                # Fetch from endpoint
                new_proxies = await self._fetch_endpoint(endpoint)
                self.stats['endpoints_polled'] += 1
                self._persist_stats()
                
                if new_proxies > 0:
                    logger.info(f"📡 {endpoint.name}: fetched {new_proxies} new proxies")
                
                # Wait for next poll
                await asyncio.sleep(endpoint.poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error polling {endpoint.name}: {e}")
                await asyncio.sleep(60)  # Wait before retry
    
    async def _fetch_endpoint(self, endpoint: ProxyEndpoint) -> int:
        """Fetch proxies from a single endpoint."""
        try:
            async with self._fetch_semaphore:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    async with session.get(endpoint.url) as response:
                        if response.status != 200:
                            endpoint.failure_count += 1
                            logger.warning(f"Failed to fetch {endpoint.name}: HTTP {response.status}")
                        return 0
                    
                    content = await response.text()
                    
                    # Parse based on parser type
                    if endpoint.parser == "text":
                        proxies = self._parse_text_list(content, endpoint)
                    elif endpoint.parser == "json_monosans":
                        proxies = self._parse_monosans_json(content, endpoint)
                    elif endpoint.parser == "json_hookzof":
                        proxies = self._parse_hookzof_json(content, endpoint)
                    else:
                        proxies = self._parse_text_list(content, endpoint)
                    
                    # Update endpoint stats
                    endpoint.last_poll = datetime.now()
                    endpoint.success_count += 1
                    
                    # Add new proxies
                    new_count = 0
                    async with self._lock:
                        for proxy in proxies:
                            if proxy.proxy_key not in self.proxies:
                                proxy.source_endpoint = endpoint.name
                                self.proxies[proxy.proxy_key] = proxy
                                new_count += 1
                                self.stats['total_fetched'] += 1

                    if new_count:
                        self._persist_stats()
                    
                    return new_count
                    
        except Exception as e:
            endpoint.failure_count += 1
            logger.error(f"Error fetching {endpoint.name}: {e}")
            return 0
    
    def _parse_text_list(self, content: str, endpoint: ProxyEndpoint) -> List[Proxy]:
        """Parse text-based proxy list (ip:port format)."""
        proxies = []
        
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Handle various formats
            # Format: ip:port
            # Format: socks5://ip:port
            # Format: ip:port:user:pass
            
            # Remove protocol prefix if present
            if '://' in line:
                parts = line.split('://')
                protocol_str = parts[0].lower()
                line = parts[1]
            else:
                protocol_str = 'socks5'
            
            # Check protocol filter
            if endpoint.protocol_filter and protocol_str != endpoint.protocol_filter:
                continue
            
            try:
                parts = line.split(':')
                if len(parts) >= 2:
                    ip = parts[0]
                    port = int(parts[1])
                    
                    # Validate IP
                    if not self._is_valid_ip(ip):
                        continue
                    
                    # Validate port
                    if not (1 <= port <= 65535):
                        continue
                    
                    username = parts[2] if len(parts) > 2 else None
                    password = parts[3] if len(parts) > 3 else None
                    
                    proxy = Proxy(
                        ip=ip,
                        port=port,
                        protocol=ProxyProtocol(protocol_str),
                        username=username,
                        password=password,
                        country=endpoint.country_filter or 'US'
                    )
                    proxies.append(proxy)
                    
            except (ValueError, IndexError):
                continue
        
        return proxies
    
    def _parse_monosans_json(self, content: str, endpoint: ProxyEndpoint) -> List[Proxy]:
        """Parse Monosans JSON format."""
        proxies = []
        
        try:
            data = json.loads(content)
            
            for item in data:
                # Filter by protocol and country
                protocol = item.get('protocol', '').lower()
                country = item.get('country', {}).get('iso', '') if isinstance(item.get('country'), dict) else ''
                
                if endpoint.protocol_filter and protocol != endpoint.protocol_filter:
                    continue
                
                if endpoint.country_filter and country != endpoint.country_filter:
                    continue
                
                try:
                    proxy = Proxy(
                        ip=item.get('ip'),
                        port=int(item.get('port', 0)),
                        protocol=ProxyProtocol(protocol) if protocol in ['socks5', 'socks4', 'http', 'https'] else ProxyProtocol.SOCKS5,
                        country=country or 'US',
                        city=item.get('city', ''),
                        isp=item.get('isp', ''),
                    )
                    
                    if proxy.ip and proxy.port:
                        proxies.append(proxy)
                        
                except (ValueError, KeyError):
                    continue
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Monosans JSON: {e}")
        
        return proxies
    
    def _parse_hookzof_json(self, content: str, endpoint: ProxyEndpoint) -> List[Proxy]:
        """Parse Hookzof Telegram-specific JSON format."""
        proxies = []
        
        try:
            data = json.loads(content)
            
            # Hookzof format may vary
            items = data if isinstance(data, list) else data.get('proxies', [])
            
            for item in items:
                try:
                    if isinstance(item, str):
                        # String format: ip:port
                        parts = item.split(':')
                        if len(parts) >= 2:
                            proxy = Proxy(
                                ip=parts[0],
                                port=int(parts[1]),
                                protocol=ProxyProtocol.SOCKS5,
                                country=endpoint.country_filter or 'US'
                            )
                            proxies.append(proxy)
                    elif isinstance(item, dict):
                        proxy = Proxy(
                            ip=item.get('ip') or item.get('host'),
                            port=int(item.get('port', 0)),
                            protocol=ProxyProtocol.SOCKS5,
                            country=item.get('country', endpoint.country_filter or 'US'),
                        )
                        if proxy.ip and proxy.port:
                            proxies.append(proxy)
                            
                except (ValueError, KeyError):
                    continue
                    
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Hookzof JSON: {e}")
        
        return proxies
    
    def _is_valid_ip(self, ip: str) -> bool:
        """Validate IP address format."""
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            for part in parts:
                num = int(part)
                if not (0 <= num <= 255):
                    return False
            return True
        except (ValueError, AttributeError):
            return False
    
    async def _health_check_loop(self):
        """Continuous health check loop for all proxies."""
        while self.is_running:
            try:
                await self._run_health_checks()
                await asyncio.sleep(self.config['health_check_interval'])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(30)
    
    async def _run_health_checks(self):
        """Run health checks on proxies in batches with priority."""
        # Prioritize proxies by importance
        now = datetime.now()
        min_check_interval = timedelta(minutes=5)
        
        # Priority 1: Assigned proxies (check every 5 min)
        assigned_proxies = [
            proxy for proxy in self.proxies.values()
            if proxy.assigned_account and proxy.status in [ProxyStatus.ACTIVE, ProxyStatus.TESTING]
            and (not proxy.last_check or (now - proxy.last_check) > min_check_interval)
        ]
        
        # Priority 2: Active unassigned proxies (check every 15 min)
        active_proxies = [
            proxy for proxy in self.proxies.values()
            if not proxy.assigned_account and proxy.status == ProxyStatus.ACTIVE
            and (not proxy.last_check or (now - proxy.last_check) > timedelta(minutes=15))
        ]
        
        # Priority 3: Testing proxies (check once)
        testing_proxies = [
            proxy for proxy in self.proxies.values()
            if proxy.status == ProxyStatus.TESTING and not proxy.last_check
        ]
        
        # Combine in priority order
        proxies_to_check = assigned_proxies + active_proxies[:50] + testing_proxies[:50]
        
        if not proxies_to_check:
            return
        
        # Process in batches
        batch_size = self.config['health_check_batch_size']
        batch_delay = self.config['batch_delay']
        
        for i in range(0, len(proxies_to_check), batch_size):
            batch = proxies_to_check[i:i + batch_size]
            
            # Limit concurrent checks within batch
            semaphore = asyncio.Semaphore(5)  # Max 5 concurrent per batch
            
            async def check_proxy(proxy: Proxy):
                async with semaphore:
                    await self._check_proxy_health(proxy)
            
            tasks = [check_proxy(proxy) for proxy in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            logger.debug(f"Completed health check batch {i//batch_size + 1} ({len(batch)} proxies)")
            
            # Delay between batches to avoid system overload
            if i + batch_size < len(proxies_to_check):
                await asyncio.sleep(batch_delay)
        
        # Update available proxies set
        async with self._lock:
            self.available_proxies = {
                key for key, proxy in self.proxies.items()
                if proxy.status == ProxyStatus.ACTIVE and not proxy.assigned_account
            }
        
        logger.info(f"Health check complete: {len(proxies_to_check)} proxies checked")
    
    async def _check_proxy_health(self, proxy: Proxy):
        """Check health of a single proxy."""
        start_time = time.time()
        success = False
        error_msg = None
        
        try:
            # Test connection through proxy
            connector = aiohttp.TCPConnector(ssl=False)
            
            proxy_url = proxy.url
            
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(
                    self.config['test_url'],
                    proxy=proxy_url,
                    timeout=aiohttp.ClientTimeout(total=self.config['test_timeout'])
                ) as response:
                    if response.status < 500:
                        success = True
                        
        except asyncio.TimeoutError:
            error_msg = "Timeout"
        except aiohttp.ClientError as e:
            error_msg = str(e)[:100]
        except Exception as e:
            error_msg = str(e)[:100]
        
        # Calculate latency
        latency = (time.time() - start_time) * 1000  # ms
        
        # Update proxy metrics
        async with self._lock:
            proxy.last_check = datetime.now()
            
            if success:
                proxy.success_count += 1
                proxy.latency_ms = (proxy.latency_ms * 0.7) + (latency * 0.3)  # Weighted average
                proxy.status = ProxyStatus.ACTIVE
                self.stats['total_validated'] += 1
            else:
                proxy.failure_count += 1
                self.stats['total_failed'] += 1
                
                # Check if should be put in cooldown or blacklisted
                if proxy.failure_count >= self.config['max_failures']:
                    proxy.status = ProxyStatus.BLACKLISTED
                    if proxy.proxy_key in self.available_proxies:
                        self.available_proxies.discard(proxy.proxy_key)
                    
                    # Auto-reassign if this proxy was assigned
                    if proxy.assigned_account and self.config['auto_reassign']:
                        await self._reassign_proxy(proxy.assigned_account)
                else:
                    proxy.status = ProxyStatus.COOLDOWN
                    proxy.cooldown_until = datetime.now() + timedelta(seconds=self.config['cooldown_duration'])
            
            # Update scores
            total_attempts = proxy.success_count + proxy.failure_count
            if total_attempts > 0:
                proxy.uptime_percent = (proxy.success_count / total_attempts) * 100
            
            proxy.update_score()

            # Save to database
            self._save_proxy(proxy)
            self._persist_stats()
        
        # Log health check
        self._log_health_check(proxy, latency, success, error_msg)

    def _log_health_check(self, proxy: Proxy, latency: float, success: bool, error_msg: Optional[str]):
        """Log health check result to database."""
        safe_error = self._sanitize_error_message(error_msg, proxy)
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    INSERT INTO proxy_health_log (proxy_key, latency_ms, success, error_message)
                    VALUES (?, ?, ?, ?)
                ''', (proxy.proxy_key, latency, success, safe_error))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to log health check: {e}")

    @staticmethod
    def _sanitize_error_message(error_msg: Optional[str], proxy: Proxy) -> Optional[str]:
        """Redact credentials and connection strings before persisting errors."""
        if not error_msg:
            return None

        sanitized = str(error_msg)
        for secret in (proxy.username, proxy.password):
            if secret:
                sanitized = sanitized.replace(secret, "***")

        # Strip user:pass@ from URLs
        sanitized = re.sub(r"(\w+://)([^@\s]+)@", r"\1***@", sanitized)
        return sanitized[:200]
    
    async def _cleanup_loop(self):
        """Cleanup loop for expired cooldowns, old logs, and low-quality proxies."""
        error_backoff = 5
        while self.is_running:
            try:
                await self._cleanup_cooldowns()
                await self._cleanup_old_logs()

                # Run proxy cleanup less frequently (every 5 minutes)
                if self.config['auto_cleanup_enabled']:
                    await self._cleanup_low_quality_proxies()

                await asyncio.sleep(60)  # Run every minute
                error_backoff = 5
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(min(error_backoff, 300))
                error_backoff = min(error_backoff * 2, 300)
    
    async def _cleanup_cooldowns(self):
        """Check and reset proxies in cooldown."""
        async with self._lock:
            now = datetime.now()
            for proxy in self.proxies.values():
                if proxy.status == ProxyStatus.COOLDOWN and proxy.cooldown_until:
                    if now >= proxy.cooldown_until:
                        proxy.status = ProxyStatus.TESTING
                        proxy.cooldown_until = None
                        self._save_proxy(proxy)
    
    async def _cleanup_old_logs(self):
        """Clean up old health check logs."""
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    DELETE FROM proxy_health_log 
                    WHERE timestamp < datetime('now', '-7 days')
                ''')
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")
    
    async def _cleanup_low_quality_proxies(self):
        """Remove low-quality proxies to maintain pool limit."""
        try:
            async with self._lock:
                # Count total proxies (excluding blacklisted)
                total_proxies = len(self.proxies)
                max_proxies = self.config['max_active_proxies']
                
                if total_proxies <= max_proxies:
                    return  # No cleanup needed
                
                # Get all proxies that are not assigned
                unassigned_proxies = [
                    proxy for proxy in self.proxies.values()
                    if not proxy.assigned_account
                ]
                
                # Sort by score (lowest first) to remove worst proxies
                unassigned_proxies.sort(key=lambda p: p.score)
                
                # Calculate how many to remove
                to_remove_count = total_proxies - max_proxies
                
                # Also remove proxies below threshold or with high fraud scores
                proxies_to_remove = []
                
                for proxy in unassigned_proxies:
                    if len(proxies_to_remove) >= to_remove_count:
                        break
                    
                    # Remove if below threshold, high fraud score, or failed
                    if (proxy.score < self.config['min_score_threshold'] or
                        proxy.fraud_score >= self.config['max_fraud_score'] or
                        proxy.status == ProxyStatus.FAILED):
                        proxies_to_remove.append(proxy)
                
                # If we still need to remove more, take lowest scoring unassigned proxies
                if len(proxies_to_remove) < to_remove_count:
                    remaining_to_remove = to_remove_count - len(proxies_to_remove)
                    already_marked = set(p.proxy_key for p in proxies_to_remove)
                    
                    for proxy in unassigned_proxies:
                        if len(proxies_to_remove) >= to_remove_count:
                            break
                        if proxy.proxy_key not in already_marked:
                            proxies_to_remove.append(proxy)
                
                # Remove proxies from memory and database
                if proxies_to_remove:
                    removed_keys = []
                    for proxy in proxies_to_remove:
                        removed_keys.append(proxy.proxy_key)
                        
                        # Remove from memory
                        if proxy.proxy_key in self.proxies:
                            del self.proxies[proxy.proxy_key]
                        if proxy.proxy_key in self.available_proxies:
                            self.available_proxies.discard(proxy.proxy_key)
                    
                    # Remove from database
                    with self._get_connection() as conn:
                        conn.executemany(
                            'DELETE FROM proxies WHERE proxy_key = ?',
                            [(key,) for key in removed_keys]
                        )
                        conn.commit()
                    
                    logger.info(
                        f"Cleaned up {len(proxies_to_remove)} low-quality proxies. "
                        f"Pool size: {len(self.proxies)}/{max_proxies}"
                    )
                
        except Exception as e:
            logger.error(f"Failed to cleanup low-quality proxies: {e}")
    
    async def get_proxy_for_account(self, account_phone: str, prefer_tier: ProxyTier = ProxyTier.STANDARD) -> Optional[Proxy]:
        """
        Get a proxy for an account.
        
        If the account already has an assigned proxy, return it.
        Otherwise, assign a new proxy from the pool.
        """
        async with self._lock:
            # Check if account already has a proxy
            if account_phone in self.assigned_proxies:
                proxy_key = self.assigned_proxies[account_phone]
                if proxy_key in self.proxies:
                    proxy = self.proxies[proxy_key]
                    if proxy.status == ProxyStatus.ACTIVE:
                        return proxy
                    else:
                        # Proxy is no longer active, reassign
                        return await self._reassign_proxy(account_phone)
            
            # Find best available proxy
            return await self._assign_new_proxy(account_phone, prefer_tier)
    
    async def _assign_new_proxy(self, account_phone: str, prefer_tier: ProxyTier) -> Optional[Proxy]:
        """Assign a new proxy to an account (with race condition protection)."""
        async with self._lock:
            # Check if account already has assignment (prevent double assignment)
            if account_phone in self.assigned_proxies:
                proxy_key = self.assigned_proxies[account_phone]
                if proxy_key in self.proxies:
                    logger.info(f"Account {account_phone} already has proxy {proxy_key}")
                    return self.proxies[proxy_key]
            
            # Get available proxies sorted by score
            available = [
                self.proxies[key] for key in self.available_proxies
                if key in self.proxies and self.proxies[key].score >= self.config['min_score']
                and self.proxies[key].assigned_account is None  # Ensure not already assigned
            ]
            
            if not available:
                logger.warning(f"No available proxies for account {account_phone}")
                return None
            
            # Sort by score and tier preference
            def sort_key(p):
                tier_bonus = 10 if p.tier == prefer_tier else 0
                us_bonus = 5 if p.country == 'US' and self.config['prefer_us_proxies'] else 0
                return -(p.score + tier_bonus + us_bonus)
            
            available.sort(key=sort_key)
            
            # Assign best proxy atomically with database save
            proxy = available[0]
            
            # Save to database FIRST (inside lock) to prevent race conditions
            # This ensures the assignment is persisted before releasing the lock
            try:
                # Use database transaction for atomicity
                with self._get_connection() as conn:
                    conn.execute('BEGIN EXCLUSIVE')  # Exclusive lock on database
                    try:
                        # Check one more time if proxy is already assigned (race condition check at DB level)
                        cursor = conn.execute(
                            'SELECT account_phone FROM proxy_assignments WHERE proxy_key = ?',
                            (proxy.proxy_key,)
                        )
                        existing = cursor.fetchone()
                        if existing and existing[0] != account_phone:
                            # Proxy was assigned to someone else between our check and now
                            logger.warning(f"Proxy {proxy.proxy_key} was assigned to {existing[0]} during assignment")
                            conn.rollback()
                            return None
                        
                        # Update proxy assigned_account and last_used
                        proxy.assigned_account = account_phone
                        proxy.last_used = datetime.now()
                        
                        # Save proxy state
                        encrypted_username = self.credential_manager.encrypt_credential(proxy.username) if proxy.username else None
                        encrypted_password = self.credential_manager.encrypt_credential(proxy.password) if proxy.password else None
                        
                        conn.execute('''
                            INSERT OR REPLACE INTO proxies
                            (proxy_key, ip, port, protocol, username, password, country, city, isp,
                             latency_ms, uptime_percent, success_count, failure_count, last_check, last_used,
                             score, tier, fraud_score, status, assigned_account, cooldown_until, source_endpoint, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ''', (
                            proxy.proxy_key, proxy.ip, proxy.port, proxy.protocol.value,
                            encrypted_username, encrypted_password, proxy.country, proxy.city, proxy.isp,
                            proxy.latency_ms, proxy.uptime_percent, proxy.success_count, proxy.failure_count,
                            proxy.last_check, proxy.last_used, proxy.score, proxy.tier.value, proxy.fraud_score,
                            proxy.status.value, proxy.assigned_account, proxy.cooldown_until, proxy.source_endpoint
                        ))
                        
                        # Save assignment
                        conn.execute('''
                            INSERT OR REPLACE INTO proxy_assignments (account_phone, proxy_key, is_permanent, is_locked)
                            VALUES (?, ?, 1, 0)
                        ''', (account_phone, proxy.proxy_key))
                        
                        conn.commit()
                        
                        # Update in-memory state AFTER successful database commit
                        self.assigned_proxies[account_phone] = proxy.proxy_key
                        self.available_proxies.discard(proxy.proxy_key)
                        
                    except Exception as e:
                        conn.rollback()
                        raise e
                        
            except Exception as e:
                logger.error(f"Failed to save proxy assignment: {e}")
                return None
        
        logger.info(f"✅ Assigned proxy {proxy.proxy_key} (score: {proxy.score:.1f}) to account {account_phone}")
        
        return proxy
    
    async def _reassign_proxy(self, account_phone: str) -> Optional[Proxy]:
        """Reassign a new proxy to an account whose proxy died."""
        # Check if proxy assignment is locked
        if self.is_proxy_locked(account_phone):
            logger.warning(
                f"🔒 Cannot reassign proxy for {account_phone} - assignment is locked. "
                "Unlock with unlock_proxy_assignment() if reassignment is needed."
            )
            return None
        
        # Remove old assignment
        if account_phone in self.assigned_proxies:
            old_key = self.assigned_proxies[account_phone]
            if old_key in self.proxies:
                self.proxies[old_key].assigned_account = None
                self._save_proxy(self.proxies[old_key])
            del self.assigned_proxies[account_phone]
        
        # Assign new proxy
        new_proxy = await self._assign_new_proxy(account_phone, ProxyTier.STANDARD)
        
        if new_proxy:
            logger.info(f"🔄 Reassigned proxy for account {account_phone}: {new_proxy.proxy_key}")
        else:
            logger.warning(f"⚠️ Failed to reassign proxy for account {account_phone}")
        
        return new_proxy
    
    def _save_assignment(self, account_phone: str, proxy_key: str, is_locked: bool = False):
        """Save proxy assignment to database with optional locking."""
        try:
            with self._get_connection() as conn:
                # Add is_locked column if it doesn't exist
                try:
                    conn.execute('ALTER TABLE proxy_assignments ADD COLUMN is_locked INTEGER DEFAULT 0')
                except sqlite3.OperationalError:
                    pass  # Column already exists
                
                conn.execute('''
                    INSERT OR REPLACE INTO proxy_assignments (account_phone, proxy_key, is_permanent, is_locked)
                    VALUES (?, ?, 1, ?)
                ''', (account_phone, proxy_key, 1 if is_locked else 0))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to save assignment: {e}")
    
    async def lock_proxy_assignment(self, account_phone: str) -> bool:
        """
        Lock the current proxy assignment for an account to prevent reassignment.
        
        Useful for:
        - Critical operations (warmup, campaigns)
        - Long-running sessions
        - Accounts requiring consistent IP
        
        Args:
            account_phone: Phone number to lock assignment for
            
        Returns:
            True if lock was successful
        """
        async with self._lock:
            if account_phone not in self.assigned_proxies:
                logger.warning(f"Cannot lock proxy - no assignment exists for {account_phone}")
                return False
            
            proxy_key = self.assigned_proxies[account_phone]
            
            try:
                with self._get_connection() as conn:
                    # Add is_locked column if needed
                    try:
                        conn.execute('ALTER TABLE proxy_assignments ADD COLUMN is_locked INTEGER DEFAULT 0')
                    except sqlite3.OperationalError:
                        pass
                    
                    conn.execute('''
                        UPDATE proxy_assignments
                        SET is_locked = 1
                        WHERE account_phone = ?
                    ''', (account_phone,))
                    conn.commit()
                
                logger.info(f"🔒 Locked proxy {proxy_key} for account {account_phone}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to lock proxy assignment: {e}")
                return False
    
    async def unlock_proxy_assignment(self, account_phone: str) -> bool:
        """
        Unlock proxy assignment for an account, allowing reassignment.
        
        Args:
            account_phone: Phone number to unlock
            
        Returns:
            True if unlock was successful
        """
        try:
            with self._get_connection() as conn:
                conn.execute('''
                    UPDATE proxy_assignments
                    SET is_locked = 0
                    WHERE account_phone = ?
                ''', (account_phone,))
                conn.commit()
            
            logger.info(f"🔓 Unlocked proxy assignment for account {account_phone}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to unlock proxy assignment: {e}")
            return False
    
    def is_proxy_locked(self, account_phone: str) -> bool:
        """Check if an account's proxy assignment is locked."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT is_locked FROM proxy_assignments
                    WHERE account_phone = ?
                ''', (account_phone,))
                row = cursor.fetchone()
                return bool(row['is_locked']) if row else False
        except Exception as e:
            logger.debug(f"Could not check lock status: {e}")
            return False
    
    async def release_proxy(self, account_phone: str):
        """Release a proxy back to the pool."""
        async with self._lock:
            if account_phone not in self.assigned_proxies:
                return
            
            proxy_key = self.assigned_proxies[account_phone]
            if proxy_key in self.proxies:
                proxy = self.proxies[proxy_key]
                proxy.assigned_account = None
                self._save_proxy(proxy)
                
                if proxy.status == ProxyStatus.ACTIVE:
                    self.available_proxies.add(proxy_key)
            
            del self.assigned_proxies[account_phone]
            
            # Remove from database
            try:
                with self._get_connection() as conn:
                    conn.execute('DELETE FROM proxy_assignments WHERE account_phone = ?', (account_phone,))
                    conn.commit()
            except Exception as e:
                logger.error(f"Failed to remove assignment: {e}")
            
            logger.info(f"Released proxy {proxy_key} from account {account_phone}")
    
    def get_proxy_stats(self) -> Dict[str, Any]:
        """Get proxy pool statistics."""
        total = len(self.proxies)
        active = sum(1 for p in self.proxies.values() if p.status == ProxyStatus.ACTIVE)
        assigned = len(self.assigned_proxies)
        available = len(self.available_proxies)
        
        by_tier = defaultdict(int)
        by_country = defaultdict(int)
        
        for proxy in self.proxies.values():
            if proxy.status == ProxyStatus.ACTIVE:
                by_tier[proxy.tier.value] += 1
                by_country[proxy.country] += 1
        
        avg_score = sum(p.score for p in self.proxies.values()) / total if total > 0 else 0
        avg_latency = sum(p.latency_ms for p in self.proxies.values() if p.latency_ms > 0) / total if total > 0 else 0
        
        return {
            'total': total,
            'active': active,
            'assigned': assigned,
            'available': available,
            'by_tier': dict(by_tier),
            'by_country': dict(by_country),
            'avg_score': round(avg_score, 2),
            'avg_latency_ms': round(avg_latency, 2),
            'endpoints': len(self.endpoints),
            'total_fetched': self.stats['total_fetched'],
            'total_validated': self.stats['total_validated'],
            'last_full_poll': self.stats['last_full_poll'].isoformat() if self.stats['last_full_poll'] else None,
        }
    
    def get_proxies_paginated(
        self, 
        page: int = 1, 
        page_size: int = 100, 
        status_filter: Optional[str] = None,
        tier_filter: Optional[str] = None,
        assigned_only: bool = False,
        active_only: bool = False
    ) -> Tuple[List[Dict], int]:
        """
        Get proxies with pagination and filtering.
        
        Returns:
            Tuple of (proxy_list, total_count)
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                
                # Build query with filters
                where_clauses = []
                params = []
                
                # Status filter
                if status_filter:
                    where_clauses.append("status = ?")
                    params.append(status_filter)
                elif active_only:
                    where_clauses.append("status = ?")
                    params.append(ProxyStatus.ACTIVE.value)
                
                # Tier filter
                if tier_filter:
                    where_clauses.append("tier = ?")
                    params.append(tier_filter)
                
                # Assigned filter
                if assigned_only:
                    where_clauses.append("assigned_account IS NOT NULL")
                
                # Build WHERE clause
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                # Get total count
                count_query = f"SELECT COUNT(*) as count FROM proxies WHERE {where_sql}"
                cursor = conn.execute(count_query, params)
                total_count = cursor.fetchone()['count']
                
                # Get paginated results
                offset = (page - 1) * page_size
                data_query = f"""
                    SELECT * FROM proxies 
                    WHERE {where_sql}
                    ORDER BY 
                        CASE WHEN assigned_account IS NOT NULL THEN 0 ELSE 1 END,
                        score DESC
                    LIMIT ? OFFSET ?
                """
                cursor = conn.execute(data_query, params + [page_size, offset])
                
                # Convert rows to dicts
                proxies = []
                for row in cursor.fetchall():
                    proxy_dict = dict(row)
                    # Decrypt credentials
                    if proxy_dict.get('username'):
                        proxy_dict['username'] = self.credential_manager.decrypt_credential(proxy_dict['username'])
                    if proxy_dict.get('password'):
                        proxy_dict['password'] = self.credential_manager.decrypt_credential(proxy_dict['password'])
                    proxies.append(proxy_dict)
                
                return proxies, total_count
                
        except Exception as e:
            logger.error(f"Failed to get paginated proxies: {e}")
            return [], 0
    
    def get_best_proxies(self, count: int = 10, country: str = "US") -> List[Proxy]:
        """Get the best available proxies."""
        available = [
            p for p in self.proxies.values()
            if p.status == ProxyStatus.ACTIVE and not p.assigned_account
            and (not country or p.country == country)
        ]
        
        available.sort(key=lambda p: -p.score)
        return available[:count]


# Singleton instance
_proxy_pool_manager: Optional[ProxyPoolManager] = None


def get_proxy_pool_manager() -> ProxyPoolManager:
    """Get the singleton ProxyPoolManager instance."""
    global _proxy_pool_manager
    if _proxy_pool_manager is None:
        _proxy_pool_manager = ProxyPoolManager()
    return _proxy_pool_manager


async def init_proxy_pool_manager() -> ProxyPoolManager:
    """Initialize and start the ProxyPoolManager."""
    manager = get_proxy_pool_manager()
    await manager.start()
    return manager
