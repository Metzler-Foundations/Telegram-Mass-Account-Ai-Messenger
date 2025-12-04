import asyncio
import logging
import sqlite3
import re
import shutil
import random
import hashlib
import json
import secrets
from contextlib import contextmanager
from typing import List, Dict, Optional, Tuple, Set, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict, deque
import threading
import time
import psutil
from dataclasses import dataclass, asdict
import statistics
import math
from enum import Enum

from pyrogram import Client
from pyrogram.types import ChatMember, Chat, Message, User, Reaction, Poll
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter, ChatType
from pyrogram.errors import (
    FloodWait, UserPrivacyRestricted, UserBlocked, PeerIdInvalid,
    UserDeactivated, UserBannedInChannel, ChatWriteForbidden,
    AuthKeyInvalid, SessionPasswordNeeded, PhoneCodeInvalid,
    PhoneCodeExpired, BadRequest
)

logger = logging.getLogger(__name__)


def _linear_regression(x, y):
    """
    Calculate simple linear regression slope.
    Compatible fallback for Python < 3.10 (statistics.linear_regression was added in 3.10).
    
    Returns:
        tuple: (slope, intercept)
    """
    try:
        # Try using the built-in function (Python 3.10+)
        return statistics.linear_regression(x, y)
    except AttributeError:
        # Fallback for Python < 3.10
        n = len(x)
        if n < 2:
            return (0.0, 0.0)
        
        x_list = list(x)
        y_list = list(y)
        
        sum_x = sum(x_list)
        sum_y = sum(y_list)
        sum_xy = sum(x_list[i] * y_list[i] for i in range(n))
        sum_x2 = sum(xi ** 2 for xi in x_list)
        
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return (0.0, sum_y / n if n > 0 else 0.0)
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        return (slope, intercept)


class ScrapingRisk(Enum):
    """Risk levels for scraping operations."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AccountHealth(Enum):
    """Account health status."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
    CRITICAL = "critical"
    BANNED = "banned"


@dataclass
class SessionMetrics:
    """Real-time session performance metrics."""
    account_id: str
    requests_per_minute: float = 0.0
    error_rate: float = 0.0
    avg_response_time: float = 0.0
    last_activity: datetime = None
    health_score: float = 100.0
    risk_level: ScrapingRisk = ScrapingRisk.SAFE
    ban_probability: float = 0.0

    def update_health_score(self):
        """Update health score based on metrics."""
        score = 100.0

        # Penalize high error rates
        if self.error_rate > 0.5:
            score -= 50
        elif self.error_rate > 0.2:
            score -= 25
        elif self.error_rate > 0.1:
            score -= 10

        # Penalize high request rates
        if self.requests_per_minute > 30:
            score -= 20
        elif self.requests_per_minute > 20:
            score -= 10

        # Penalize slow responses (potential blocks)
        if self.avg_response_time > 10:
            score -= 15
        elif self.avg_response_time > 5:
            score -= 5

        # Penalize high ban probability
        score -= self.ban_probability * 100

        self.health_score = max(0, min(100, score))

    def calculate_risk_level(self) -> ScrapingRisk:
        """Calculate current risk level."""
        if self.health_score < 20 or self.ban_probability > 0.8:
            return ScrapingRisk.CRITICAL
        elif self.health_score < 40 or self.ban_probability > 0.6:
            return ScrapingRisk.HIGH
        elif self.health_score < 60 or self.ban_probability > 0.4:
            return ScrapingRisk.MEDIUM
        elif self.health_score < 80 or self.ban_probability > 0.2:
            return ScrapingRisk.LOW
        else:
            return ScrapingRisk.SAFE


@dataclass
class GeographicProfile:
    """Geographic profile for IP rotation."""
    country_code: str
    timezone: str
    language: str
    user_agent: str
    ip_range: str = ""
    proxy_quality: float = 1.0  # 1.0 = excellent, 0.0 = poor

    def get_behavioral_delay(self) -> float:
        """Get human-like delay based on geographic profile."""
        base_delay = random.uniform(1.0, 3.0)

        # Adjust for timezone (people in different timezones behave differently)
        timezone_factor = abs(int(self.timezone.split('+')[1].split(':')[0]) / 12) if '+' in self.timezone else 0
        timezone_adjustment = timezone_factor * 0.5

        # Language factor (some languages have different typing speeds)
        language_factors = {
            'en': 1.0, 'es': 0.9, 'fr': 0.95, 'de': 0.85,
            'ru': 0.8, 'zh': 0.75, 'ja': 0.7, 'ar': 0.9
        }
        lang_code = self.language.split('_')[0]
        language_factor = language_factors.get(lang_code, 1.0)

        return base_delay * language_factor + timezone_adjustment


class EliteAntiDetectionSystem:
    """Elite anti-detection system with machine learning optimization."""

    def __init__(self, db_path: str = "anti_detection.db"):
        """Initialize the elite anti-detection system."""
        self.db_path = db_path
        self.session_metrics: Dict[str, SessionMetrics] = {}
        self.geographic_profiles: Dict[str, GeographicProfile] = {}
        self.request_history: deque = deque(maxlen=10000)
        self.behavioral_patterns: Dict[str, List[float]] = defaultdict(list)
        self.risk_thresholds = {
            ScrapingRisk.SAFE: 0.1,
            ScrapingRisk.LOW: 0.25,
            ScrapingRisk.MEDIUM: 0.5,
            ScrapingRisk.HIGH: 0.75,
            ScrapingRisk.CRITICAL: 0.9
        }
        self._load_geographic_profiles()
        self._init_database()
        self._start_health_monitoring()

    def _init_database(self):
        """Initialize anti-detection database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS session_metrics (
                    account_id TEXT PRIMARY KEY,
                    requests_per_minute REAL DEFAULT 0,
                    error_rate REAL DEFAULT 0,
                    avg_response_time REAL DEFAULT 0,
                    last_activity TIMESTAMP,
                    health_score REAL DEFAULT 100,
                    risk_level TEXT DEFAULT 'safe',
                    ban_probability REAL DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS request_history (
                    id INTEGER PRIMARY KEY,
                    account_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    request_type TEXT,
                    response_time REAL,
                    success BOOLEAN,
                    error_type TEXT,
                    ip_address TEXT,
                    user_agent TEXT
                )
            ''')

            conn.execute('''
                CREATE TABLE IF NOT EXISTS behavioral_patterns (
                    account_id TEXT,
                    pattern_type TEXT,
                    value REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (account_id, pattern_type, timestamp)
                )
            ''')

    def _load_geographic_profiles(self):
        """Load geographic profiles for IP rotation."""
        # Predefined profiles for major regions
        profiles = {
            "us_east": GeographicProfile(
                country_code="US", timezone="UTC-5", language="en_US",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            ),
            "us_west": GeographicProfile(
                country_code="US", timezone="UTC-8", language="en_US",
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            ),
            "eu_central": GeographicProfile(
                country_code="DE", timezone="UTC+1", language="de_DE",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0"
            ),
            "eu_west": GeographicProfile(
                country_code="GB", timezone="UTC+0", language="en_GB",
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            ),
            "asia_east": GeographicProfile(
                country_code="JP", timezone="UTC+9", language="ja_JP",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "asia_south": GeographicProfile(
                country_code="IN", timezone="UTC+5:30", language="hi_IN",
                user_agent="Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36"
            )
        }
        self.geographic_profiles.update(profiles)

    def _start_health_monitoring(self):
        """Start real-time health monitoring."""
        import threading
        self.monitoring_active = True
        self.monitor_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        self.monitor_thread.start()

    def _health_monitor_loop(self):
        """Continuous health monitoring loop."""
        while self.monitoring_active:
            try:
                self._update_all_metrics()
                self._detect_anomalies()
                self._predictive_risk_analysis()
                time.sleep(30)  # Update every 30 seconds
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                time.sleep(60)

    def _update_all_metrics(self):
        """Update metrics for all active sessions."""
        for account_id, metrics in self.session_metrics.items():
            metrics.update_health_score()
            metrics.risk_level = metrics.calculate_risk_level()
            self._persist_metrics(account_id, metrics)

    def _detect_anomalies(self):
        """Detect anomalous behavior patterns."""
        for account_id, metrics in self.session_metrics.items():
            # Check for sudden spikes in error rates
            if len(self.behavioral_patterns[account_id]) > 10:
                recent_errors = [p for p in self.behavioral_patterns[account_id][-10:] if p > 0.1]
                if len(recent_errors) > 5:  # More than 50% errors in last 10 requests
                    logger.warning(f"Anomaly detected for {account_id}: High error rate")
                    metrics.ban_probability += 0.1
                    metrics.update_health_score()

    def _predictive_risk_analysis(self):
        """Predictive risk analysis using statistical modeling."""
        for account_id, metrics in self.session_metrics.items():
            if len(self.behavioral_patterns[account_id]) < 20:
                continue

            # Calculate trend in error rates
            recent_errors = self.behavioral_patterns[account_id][-20:]
            if len(recent_errors) >= 10:
                trend = _linear_regression(range(len(recent_errors)), recent_errors)[0]

                # If error rate is trending upward, increase ban probability
                if trend > 0.001:
                    metrics.ban_probability = min(1.0, metrics.ban_probability + 0.05)
                    logger.info(f"Increasing ban probability for {account_id}: trend={trend:.4f}")

    def _persist_metrics(self, account_id: str, metrics: SessionMetrics):
        """Persist metrics to database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO session_metrics
                    (account_id, requests_per_minute, error_rate, avg_response_time,
                     last_activity, health_score, risk_level, ban_probability, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    account_id, metrics.requests_per_minute, metrics.error_rate,
                    metrics.avg_response_time, metrics.last_activity, metrics.health_score,
                    metrics.risk_level.value, metrics.ban_probability, datetime.now()
                ))
        except Exception as e:
            logger.error(f"Failed to persist metrics for {account_id}: {e}")

    def record_request(self, account_id: str, request_type: str, response_time: float,
                      success: bool, error_type: str = None, ip_address: str = None,
                      user_agent: str = None):
        """Record a request for analytics."""
        timestamp = datetime.now()

        # Update session metrics
        if account_id not in self.session_metrics:
            self.session_metrics[account_id] = SessionMetrics(account_id)

        metrics = self.session_metrics[account_id]
        metrics.requests_per_minute = self._calculate_rpm(account_id)
        metrics.last_activity = timestamp

        # Update error rate
        recent_requests = [r for r in self.request_history if r['account_id'] == account_id][-100:]
        if recent_requests:
            error_count = sum(1 for r in recent_requests if not r['success'])
            metrics.error_rate = error_count / len(recent_requests)

        # Update response time (exponential moving average)
        if metrics.avg_response_time == 0:
            metrics.avg_response_time = response_time
        else:
            metrics.avg_response_time = 0.1 * response_time + 0.9 * metrics.avg_response_time

        # Store behavioral pattern
        error_value = 1.0 if not success else 0.0
        self.behavioral_patterns[account_id].append(error_value)

        # Store request history
        self.request_history.append({
            'account_id': account_id,
            'timestamp': timestamp,
            'request_type': request_type,
            'response_time': response_time,
            'success': success,
            'error_type': error_type,
            'ip_address': ip_address,
            'user_agent': user_agent
        })

        # Persist to database
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT INTO request_history
                    (account_id, request_type, response_time, success, error_type, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, request_type, response_time, success, error_type, ip_address, user_agent))
        except Exception as e:
            logger.error(f"Failed to persist request history: {e}")

    def _calculate_rpm(self, account_id: str) -> float:
        """Calculate requests per minute for an account."""
        cutoff = datetime.now() - timedelta(minutes=1)
        recent_requests = [
            r for r in self.request_history
            if r['account_id'] == account_id and r['timestamp'] > cutoff
        ]
        return len(recent_requests)

    def get_optimal_delay(self, account_id: str, geographic_profile: str = None) -> float:
        """Calculate optimal delay using machine learning."""
        base_delay = 2.0  # Base 2 second delay

        if account_id in self.session_metrics:
            metrics = self.session_metrics[account_id]

            # Adjust based on health score
            health_factor = (100 - metrics.health_score) / 100  # 0 to 1
            base_delay += health_factor * 5  # Add up to 5 seconds for poor health

            # Adjust based on risk level
            risk_multipliers = {
                ScrapingRisk.SAFE: 1.0,
                ScrapingRisk.LOW: 1.2,
                ScrapingRisk.MEDIUM: 1.5,
                ScrapingRisk.HIGH: 2.0,
                ScrapingRisk.CRITICAL: 3.0
            }
            base_delay *= risk_multipliers.get(metrics.risk_level, 1.0)

        # Add geographic behavioral delay
        if geographic_profile and geographic_profile in self.geographic_profiles:
            geo_delay = self.geographic_profiles[geographic_profile].get_behavioral_delay()
            base_delay += geo_delay

        # Add randomization (±25%)
        randomization = random.uniform(0.75, 1.25)
        final_delay = base_delay * randomization

        return max(1.0, final_delay)  # Minimum 1 second delay

    def should_rotate_account(self, account_id: str) -> bool:
        """Determine if account should be rotated based on risk analysis."""
        if account_id not in self.session_metrics:
            return False

        metrics = self.session_metrics[account_id]

        # Rotate if health score is critically low
        if metrics.health_score < 30:
            return True

        # Rotate if ban probability is high
        if metrics.ban_probability > 0.7:
            return True

        # Rotate if error rate is consistently high
        recent_errors = self.behavioral_patterns[account_id][-50:]
        if len(recent_errors) >= 20:
            avg_error_rate = sum(recent_errors) / len(recent_errors)
            if avg_error_rate > 0.3:  # 30% error rate
                return True

        return False

    def get_account_health(self, account_id: str) -> AccountHealth:
        """Get account health status."""
        if account_id not in self.session_metrics:
            return AccountHealth.GOOD  # Assume good if no data

        metrics = self.session_metrics[account_id]

        if metrics.health_score >= 90:
            return AccountHealth.EXCELLENT
        elif metrics.health_score >= 75:
            return AccountHealth.GOOD
        elif metrics.health_score >= 50:
            return AccountHealth.FAIR
        elif metrics.health_score >= 25:
            return AccountHealth.POOR
        else:
            return AccountHealth.CRITICAL

    def load_metrics_from_db(self, account_id: str):
        """Load metrics from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute('SELECT * FROM session_metrics WHERE account_id = ?',
                                 (account_id,)).fetchone()
                if row:
                    metrics = SessionMetrics(
                        account_id=row[0],
                        requests_per_minute=row[1],
                        error_rate=row[2],
                        avg_response_time=row[3],
                        last_activity=datetime.fromisoformat(row[4]) if row[4] else None,
                        health_score=row[5],
                        ban_probability=row[7]
                    )
                    metrics.risk_level = ScrapingRisk(row[6]) if row[6] else ScrapingRisk.SAFE
                    self.session_metrics[account_id] = metrics
        except Exception as e:
            logger.error(f"Failed to load metrics for {account_id}: {e}")

    def shutdown(self):
        """Shutdown the anti-detection system."""
        self.monitoring_active = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join(timeout=5)


class DistributedScrapingCoordinator:
    """Coordinates scraping across multiple accounts and sessions."""

    def __init__(self, anti_detection_system: EliteAntiDetectionSystem):
        """Initialize the distributed scraping coordinator."""
        self.anti_detection = anti_detection_system
        self.active_sessions: Dict[str, Dict] = {}
        self.session_pool: Dict[str, List[str]] = defaultdict(list)  # geo_region -> account_ids
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.worker_tasks: Set[asyncio.Task] = set()
        self.max_concurrent_workers = 5

    async def initialize_session_pool(self, account_manager):
        """Initialize the session pool with available accounts."""
        try:
            if not account_manager:
                logger.warning("No account manager provided for session pool initialization")
                return

            # Get available accounts from the account manager
            available_accounts = account_manager.get_account_list() if hasattr(account_manager, 'get_account_list') else []

            for account in available_accounts:
                phone_number = account.get('phone_number')
                if phone_number:
                    # Determine geographic region based on phone number
                    region = self._determine_geographic_region(phone_number)

                    # Get or create client for this account
                    if hasattr(account_manager, 'active_clients') and phone_number in account_manager.active_clients:
                        client = account_manager.active_clients[phone_number]
                        # Get the actual Pyrogram client
                        if hasattr(client, 'client'):
                            actual_client = client.client
                        else:
                            actual_client = client
                    else:
                        # Try to get client directly from account manager
                        actual_client = getattr(account_manager, 'get_client', lambda x: None)(phone_number)

                    if actual_client:
                        self.session_pool[phone_number] = actual_client
                        logger.info(f"Added account {phone_number} to session pool (region: {region})")

            logger.info(f"Session pool initialized with {len(self.session_pool)} accounts")

        except Exception as e:
            logger.error(f"Failed to initialize session pool: {e}")

    def _determine_geographic_region(self, phone_number: str) -> str:
        """Determine geographic region from phone number."""
        phone_str = str(phone_number).replace('+', '')

        # Simple region detection based on country codes
        if phone_str.startswith(('1', '001')):  # US/Canada
            return 'us_east'  # Default to east coast
        elif phone_str.startswith(('44', '0044')):  # UK
            return 'eu_west'
        elif phone_str.startswith(('49', '0049')):  # Germany
            return 'eu_central'
        elif phone_str.startswith(('81', '0081')):  # Japan
            return 'asia_east'
        elif phone_str.startswith(('91', '0091')):  # India
            return 'asia_south'
        elif phone_str.startswith(('7', '007')):  # Russia
            return 'eu_east'
        else:
            return 'us_east'  # Default fallback

    async def distribute_scraping_task(self, task: Dict) -> Dict:
        """Distribute a scraping task across optimal sessions."""
        # Select best account based on health, geography, and current load
        best_account = await self._select_optimal_account(task)

        if not best_account:
            return {'success': False, 'error': 'No suitable accounts available'}

        # Queue task for the selected account
        await self.task_queue.put({
            'account_id': best_account,
            'task': task,
            'priority': task.get('priority', 1)
        })

        return {'success': True, 'account_id': best_account}

    async def _select_optimal_account(self, task: Dict) -> Optional[str]:
        """Select the optimal account for a task."""
        target_region = task.get('geographic_region', 'us_east')

        # Get accounts for the target region
        candidates = self.session_pool.get(target_region, [])

        if not candidates:
            # Fall back to any available account
            candidates = [acc for region_accounts in self.session_pool.values()
                         for acc in region_accounts]

        if not candidates:
            return None

        # Score candidates based on health, current load, and task requirements
        best_account = None
        best_score = -1

        for account_id in candidates:
            if account_id not in self.active_sessions:
                continue

            health = self.anti_detection.get_account_health(account_id)
            current_load = len([t for t in self.worker_tasks
                              if not t.done() and getattr(t, 'account_id', None) == account_id])

            # Calculate score (higher is better)
            health_score = {
                AccountHealth.EXCELLENT: 100,
                AccountHealth.GOOD: 75,
                AccountHealth.FAIR: 50,
                AccountHealth.POOR: 25,
                AccountHealth.CRITICAL: 0
            }.get(health, 0)

            load_penalty = current_load * 20  # Penalize loaded accounts
            final_score = health_score - load_penalty

            if final_score > best_score:
                best_score = final_score
                best_account = account_id

        return best_account

    async def start_workers(self):
        """Start worker tasks for processing the queue."""
        for i in range(self.max_concurrent_workers):
            task = asyncio.create_task(self._worker_loop())
            task.worker_id = i
            self.worker_tasks.add(task)

    async def _worker_loop(self):
        """Worker loop for processing tasks."""
        while True:
            try:
                # Get task from queue with timeout
                try:
                    task_data = await asyncio.wait_for(self.task_queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    continue

                account_id = task_data['account_id']
                task = task_data['task']

                # Execute task
                result = await self._execute_task(account_id, task)

                # Mark task as done
                self.task_queue.task_done()

                # Small delay to prevent overwhelming
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)  # Back off on errors

    async def _execute_task(self, account_id: str, task: Dict) -> Dict:
        """Execute a scraping task."""
        task_type = task.get('type')
        start_time = time.time()

        try:
            if task_type == 'scrape_channel':
                # This would call the actual scraping logic
                result = await self._scrape_channel_task(account_id, task)
            elif task_type == 'analyze_member':
                result = await self._analyze_member_task(account_id, task)
            else:
                result = {'success': False, 'error': f'Unknown task type: {task_type}'}

            # Record metrics
            response_time = time.time() - start_time
            self.anti_detection.record_request(
                account_id=account_id,
                request_type=task_type,
                response_time=response_time,
                success=result.get('success', False),
                error_type=result.get('error')
            )

            return result

        except Exception as e:
            # Record error
            response_time = time.time() - start_time
            self.anti_detection.record_request(
                account_id=account_id,
                request_type=task_type,
                response_time=response_time,
                success=False,
                error_type=str(e)
            )
            return {'success': False, 'error': str(e)}

    async def _scrape_channel_task(self, account_id: str, task: Dict) -> Dict:
        """Execute channel scraping task."""
        channel_id = task.get('channel_id')
        if not channel_id:
            return {'success': False, 'error': 'No channel_id provided'}

        logger.info(f"Scraping channel {channel_id} with account {account_id}")

        scraper = getattr(self, "member_scraper", None)
        if scraper and hasattr(scraper, "scrape_channel_members"):
            return await scraper.scrape_channel_members(
                channel_id,
                analyze_messages=task.get('analyze_messages', True),
                use_elite_scraping=task.get('use_elite_scraping', False)
            )

        if hasattr(self, "elite_scraper"):
            return await self.elite_scraper.scrape_channel_comprehensive(
                channel_id,
                techniques=['direct_members', 'message_history', 'reaction_analysis']
                if task.get('analyze_messages', True)
                else ['direct_members'],
                max_depth=2
            )

        return {'success': False, 'error': 'No scraping backend configured'}

    async def _analyze_member_task(self, account_id: str, task: Dict) -> Dict:
        """Execute member analysis task."""
        user_id = task.get('user_id')
        if not user_id:
            return {'success': False, 'error': 'No user_id provided'}

        logger.info(f"Analyzing member {user_id} with account {account_id}")

        analyzer = getattr(self, "member_scraper", None)
        if analyzer and hasattr(analyzer, "db"):
            profile = analyzer.db.get_member(user_id)
            if profile:
                return {
                    'success': True,
                    'user_id': user_id,
                    'analysis_complete': True,
                    'score': profile.get('engagement_score'),
                    'last_seen': profile.get('last_seen'),
                }

        return {'success': False, 'error': 'Member analysis backend not configured'}


class MemberDatabase:
    """Database manager for storing member information."""

    def __init__(self, db_path: str = "members.db"):
        """Initialize the member database.

        Args:
            db_path: Path to the SQLite database file
        """
        import threading
        self.db_path = db_path
        self._connection_pool = {}  # Thread-local connection pool
        self._connection_pool_size = 5  # Maximum connections per thread
        self._lock = threading.Lock()  # Lock for thread-safe operations
        self._write_lock = threading.Lock()  # Exclusive lock for write operations
        self.init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection from the pool.

        Note: SQLite connections are not thread-safe. This method uses proper
        thread-local connections with WAL mode for safe concurrent access.

        Returns:
            SQLite connection object
        """
        import threading
        thread_id = threading.get_ident()

        # Use lock to ensure thread-safe access to connection pool
        with self._lock:
            if thread_id not in self._connection_pool:
                self._connection_pool[thread_id] = []

            # Get existing connection for this thread
            connections = self._connection_pool[thread_id]
            if connections:
                conn = connections.pop()
                # Check if connection is still valid
                try:
                    conn.execute("SELECT 1")
                    return conn
                except sqlite3.Error:
                    # Connection is stale, close it and create new one
                    try:
                        conn.close()
                    except (sqlite3.Error, OSError, AttributeError) as e:
                        logger.debug(f"Error closing stale connection: {e}")
                    # Fall through to create new connection

            # Create new connection for this thread only
            # Remove check_same_thread=False and rely on thread-local usage
            if len(connections) < self._connection_pool_size:
                conn = sqlite3.connect(self.db_path)  # Remove check_same_thread=False
                conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
                conn.execute("PRAGMA synchronous=NORMAL")  # Balance performance and safety
                conn.execute("PRAGMA cache_size=1000")  # Increase cache size
                conn.execute("PRAGMA temp_store=MEMORY")  # Store temp tables in memory
                # Enable foreign key constraints
                conn.execute("PRAGMA foreign_keys=ON")
                return conn

        # Pool is full for this thread, create temporary connection
        # This should be rare and is still thread-safe since it's used immediately
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=1000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _return_connection(self, conn: sqlite3.Connection):
        """Return a connection to the pool.

        Args:
            conn: Connection to return
        """
        import threading
        thread_id = threading.get_ident()

        # Use lock to ensure thread-safe access to connection pool
        with self._lock:
            if thread_id not in self._connection_pool:
                self._connection_pool[thread_id] = []

            connections = self._connection_pool[thread_id]
            if len(connections) < self._connection_pool_size:
                try:
                    # Test connection before returning to pool
                    conn.execute("SELECT 1").fetchone()
                    connections.append(conn)
                except sqlite3.Error:
                    # Connection is bad, don't return to pool
                    try:
                        conn.close()
                    except (sqlite3.Error, OSError, AttributeError) as e:
                        logger.debug(f"Error closing bad connection: {e}")
            else:
                # Pool is full, close connection
                try:
                    conn.close()
                except (sqlite3.Error, OSError, AttributeError) as e:
                    logger.debug(f"Error closing connection when pool is full: {e}")

    @contextmanager
    def connection(self, write_operation: bool = False) -> sqlite3.Connection:
        """Context manager for database connections with proper locking.

        Args:
            write_operation: If True, acquires exclusive write lock for thread safety

        Yields:
            SQLite connection object
        """
        if write_operation:
            # For write operations, acquire exclusive lock to prevent concurrent writes
            self._write_lock.acquire()

        conn = self._get_connection()
        try:
            yield conn
        finally:
            self._return_connection(conn)
            if write_operation:
                self._write_lock.release()

    def execute_read(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a read-only query with proper connection handling.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            SQLite cursor object
        """
        with self.connection(write_operation=False) as conn:
            return conn.execute(query, params)

    def execute_write(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a write query with proper locking and transaction handling.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            SQLite cursor object
        """
        with self.connection(write_operation=True) as conn:
            cursor = conn.execute(query, params)
            conn.commit()  # Ensure transaction is committed
            return cursor

    def init_database(self):
        """Initialize the database schema with migration support."""
        # Create migrations table if it doesn't exist
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            ''')

            # Check current schema version
            cursor = conn.execute('SELECT MAX(version) FROM schema_migrations')
            current_version = cursor.fetchone()[0] or 0

            # Apply migrations
            self._apply_migrations(conn, current_version)

    def _apply_migrations(self, conn, current_version):
        """Apply database migrations with automatic backup."""
        migrations = [
            (1, "Initial schema", self._migration_1_initial_schema),
            (2, "Add backup support", self._migration_2_add_backup_support),
            (3, "Add performance indexes", self._migration_3_add_indexes),
            (4, "Add threat detection", self._migration_4_add_threat_detection),
            (5, "Add scalability indexes", self._migration_5_scalability_indexes),
            (6, "Add pagination indexes", self._migration_6_pagination_indexes),
        ]

        # Check if we have any migrations to apply
        pending_migrations = [m for m in migrations if m[0] > current_version]
        if not pending_migrations:
            return  # No migrations to apply

        # Create backup before applying migrations
        backup_path = self._create_pre_migration_backup(current_version)
        if backup_path:
            logger.info(f"Created pre-migration backup: {backup_path}")
        else:
            logger.warning("Failed to create pre-migration backup - proceeding with caution")

        for version, description, migration_func in migrations:
            if version > current_version:
                try:
                    logger.info(f"Applying migration {version}: {description}")
                    migration_func(conn)
                    conn.execute('INSERT INTO schema_migrations (version, description) VALUES (?, ?)',
                               (version, description))
                    logger.info(f"Successfully applied migration {version}")
                except Exception as e:
                    logger.error(f"Failed to apply migration {version}: {e}")
                    logger.error(f"Database may be in inconsistent state. Restore from backup: {backup_path}")
                    raise

    def _create_pre_migration_backup(self, current_version: int) -> Optional[str]:
        """Create a backup before applying migrations.

        Args:
            current_version: Current database schema version

        Returns:
            Path to backup file, or None if backup failed
        """
        try:
            from datetime import datetime
            import shutil
            from pathlib import Path

            # Create backups directory
            backup_dir = Path(self.db_path).parent / "backups"
            backup_dir.mkdir(exist_ok=True)

            # Generate backup filename with timestamp and version
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"members_db_v{current_version}_backup_{timestamp}.db"
            backup_path = backup_dir / backup_filename

            # Create database backup
            shutil.copy2(self.db_path, backup_path)

            # Verify backup integrity
            if self._verify_backup_integrity(str(backup_path)):
                logger.info(f"Database backup created successfully: {backup_path}")
                return str(backup_path)
            else:
                logger.error("Backup integrity check failed")
                # Remove corrupted backup
                try:
                    backup_path.unlink()
                except (OSError, FileNotFoundError):
                    # Ignore errors when trying to remove corrupted backup
                    pass
                return None

        except Exception as e:
            logger.error(f"Failed to create pre-migration backup: {e}")
            return None

    def _verify_backup_integrity(self, backup_path: str) -> bool:
        """Verify that the backup database is valid and accessible.

        Args:
            backup_path: Path to backup database file

        Returns:
            True if backup is valid, False otherwise
        """
        try:
            with sqlite3.connect(backup_path) as conn:
                # Try to execute a simple query to verify database integrity
                cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                count = cursor.fetchone()[0]
                logger.debug(f"Backup verification: found {count} tables")
                return True
        except Exception as e:
            logger.error(f"Backup integrity verification failed: {e}")
            return False

    def _migration_1_initial_schema(self, conn):
        """Initial database schema."""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY,
                channel_id TEXT UNIQUE,
                title TEXT,
                member_count INTEGER,
                scraped_at TIMESTAMP,
                is_private BOOLEAN
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY,
                user_id INTEGER UNIQUE,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                phone TEXT,
                joined_at TIMESTAMP,
                last_seen TIMESTAMP,
                status TEXT,
                activity_score INTEGER DEFAULT 0,
                channel_id TEXT,
                FOREIGN KEY(channel_id) REFERENCES channels(channel_id)
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS member_activity (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                activity_type TEXT,
                timestamp TIMESTAMP,
                channel_id TEXT,
                FOREIGN KEY(user_id) REFERENCES members(user_id),
                FOREIGN KEY(channel_id) REFERENCES channels(channel_id)
            )
        ''')

    def _migration_2_add_backup_support(self, conn):
        """Add backup metadata table."""
        conn.execute('''
            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                backup_type TEXT,
                file_path TEXT,
                record_count INTEGER,
                status TEXT
            )
        ''')

    def _migration_3_add_indexes(self, conn):
        """Add performance indexes."""
        # Optimized indexes for query performance
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_user_id ON members(user_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_channel ON members(channel_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_username ON members(username)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_status ON members(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_threat_score ON members(threat_score)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_activity_score ON members(activity_score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_last_seen ON members(last_seen DESC)')

        conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_user ON member_activity(user_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_channel ON member_activity(channel_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON member_activity(timestamp DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_type ON member_activity(activity_type)')

        # Composite indexes for complex queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_channel_activity ON members(channel_id, activity_score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_channel_status ON members(channel_id, status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_activity_user_timestamp ON member_activity(user_id, timestamp DESC)')
    
    def _migration_4_add_threat_detection(self, conn):
        """Add threat detection fields."""
        # Add threat detection columns to members table
        try:
            conn.execute('ALTER TABLE members ADD COLUMN threat_score INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            conn.execute('ALTER TABLE members ADD COLUMN is_admin BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute('ALTER TABLE members ADD COLUMN is_moderator BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute('ALTER TABLE members ADD COLUMN is_owner BOOLEAN DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute('ALTER TABLE members ADD COLUMN message_count INTEGER DEFAULT 0')
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute('ALTER TABLE members ADD COLUMN last_message_date TIMESTAMP')
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute('ALTER TABLE members ADD COLUMN is_safe_target BOOLEAN DEFAULT 1')
        except sqlite3.OperationalError:
            pass
        
        try:
            conn.execute('ALTER TABLE members ADD COLUMN threat_reasons TEXT')
        except sqlite3.OperationalError:
            pass
        
        # Add indexes for threat detection
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_threat_score ON members(threat_score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_safe_target ON members(is_safe_target)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_message_count ON members(message_count DESC)')
    
    def _migration_5_scalability_indexes(self, conn):
        """Add scalability indexes for 100+ account operations."""
        # Composite index for safe target queries by channel
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_channel_safe ON members(channel_id, is_safe_target)')
        
        # Index for threat score filtering
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_threat_filter ON members(threat_score, is_safe_target)')
        
        # Index for last_seen queries (recent activity)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_last_seen ON members(last_seen DESC)')
        
        # Composite index for channel + activity score (common query pattern)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_channel_activity ON members(channel_id, activity_score DESC)')
        
        # Composite index for channel + last_seen (recent members in channel)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_channel_recent ON members(channel_id, last_seen DESC)')
        
        # Index for username lookups (common in DM campaigns)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_username ON members(username)')
        
        # Index for user_id lookups across channels
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_user_channel ON members(user_id, channel_id)')
        
        # Add database statistics table for monitoring
        conn.execute('''
            CREATE TABLE IF NOT EXISTS db_statistics (
                id INTEGER PRIMARY KEY,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                table_name TEXT,
                row_count INTEGER,
                index_count INTEGER,
                page_count INTEGER,
                freelist_count INTEGER
            )
        ''')
        
        # Add batch operation log for tracking bulk operations
        conn.execute('''
            CREATE TABLE IF NOT EXISTS batch_operations (
                id INTEGER PRIMARY KEY,
                operation_type TEXT,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                records_processed INTEGER DEFAULT 0,
                records_success INTEGER DEFAULT 0,
                records_failed INTEGER DEFAULT 0,
                status TEXT DEFAULT 'running',
                error_message TEXT
            )
        ''')
        
        # Enable auto_vacuum for better space reclamation
        conn.execute('PRAGMA auto_vacuum = INCREMENTAL')
    
    def _migration_6_pagination_indexes(self, conn):
        """Add indexes optimized for pagination queries."""
        # Index for scraped_at (common for ORDER BY in pagination)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_scraped_at ON members(scraped_at DESC)')
        
        # Composite index for channel + scraped_at (paginated channel members)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_channel_scraped ON members(channel_id, scraped_at DESC)')
        
        # Index for activity_score DESC (top members queries)
        conn.execute('CREATE INDEX IF NOT EXISTS idx_members_activity_desc ON members(activity_score DESC)')
        
        # Optimize LIMIT/OFFSET queries with covering indexes
        # This helps avoid table lookups when using pagination
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_members_pagination_cover 
            ON members(channel_id, activity_score DESC, user_id, username, first_name)
        ''')
        
        logger.info("Applied migration 6: pagination indexes")

    def create_backup(self, backup_type: str = "manual") -> str:
        """Create a backup of the database.

        Args:
            backup_type: Type of backup (manual, auto, etc.)

        Returns:
            Path to the backup file
        """

        # Create backups directory
        backup_dir = Path("backups")
        backup_dir.mkdir(exist_ok=True)

        # Generate backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"members_backup_{timestamp}.db"
        backup_path = backup_dir / backup_filename

        try:
            # Close any existing connections and create backup
            # SQLite backup requires exclusive access
            shutil.copy2(self.db_path, backup_path)

            # Record backup in database
            with sqlite3.connect(self.db_path) as conn:
                # Get record counts
                channel_count = conn.execute('SELECT COUNT(*) FROM channels').fetchone()[0]
                member_count = conn.execute('SELECT COUNT(*) FROM members').fetchone()[0]
                activity_count = conn.execute('SELECT COUNT(*) FROM member_activity').fetchone()[0]

                total_records = channel_count + member_count + activity_count

                conn.execute('''
                    INSERT INTO backups (backup_type, file_path, record_count, status)
                    VALUES (?, ?, ?, ?)
                ''', (backup_type, str(backup_path), total_records, 'completed'))

            logger.info(f"Database backup created: {backup_path} ({total_records} records)")
            return str(backup_path)

        except Exception as e:
            logger.error(f"Failed to create database backup: {e}")
            # Try to record failed backup
            try:
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute('''
                        INSERT INTO backups (backup_type, file_path, status)
                        VALUES (?, ?, ?)
                    ''', (backup_type, str(backup_path), 'failed'))
            except Exception:
                pass  # Ignore secondary errors
            raise

    def restore_from_backup(self, backup_path: str) -> bool:
        """Restore database from backup.

        Args:
            backup_path: Path to the backup file

        Returns:
            True if successful
        """
        backup_file = Path(backup_path)
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        # Create backup of current database before restore
        current_backup = self.create_backup("pre_restore")

        try:
            # Close connections and restore
            shutil.copy2(backup_path, self.db_path)

            # Verify restoration
            with sqlite3.connect(self.db_path) as conn:
                # Check if tables exist
                tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                table_names = [t[0] for t in tables]

                required_tables = ['channels', 'members', 'member_activity', 'schema_migrations']
                for table in required_tables:
                    if table not in table_names:
                        raise ValueError(f"Restored database missing table: {table}")

            logger.info(f"Database restored from backup: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore database from backup: {e}")
            # Try to restore from pre-restore backup
            try:
                shutil.copy2(current_backup, self.db_path)
                logger.info("Restored from pre-restore backup due to restore failure")
            except Exception:
                logger.error("Failed to restore from pre-restore backup")
            raise

    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 10):
        """Clean up old backup files.

        Args:
            keep_days: Keep backups from last N days
            keep_count: Keep at least N most recent backups
        """
        from datetime import datetime, timedelta

        backup_dir = Path("backups")
        if not backup_dir.exists():
            return

        # Get all backup files
        backup_files = list(backup_dir.glob("members_backup_*.db"))
        if not backup_files:
            return

        # Sort by modification time (newest first)
        backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # Keep most recent backups
        files_to_keep = backup_files[:keep_count]

        # Also keep backups from last N days
        cutoff_date = datetime.now() - timedelta(days=keep_days)
        for backup_file in backup_files[keep_count:]:
            file_mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)
            if file_mtime > cutoff_date:
                files_to_keep.append(backup_file)

        # Remove duplicates and old files
        files_to_keep = list(set(files_to_keep))
        files_to_delete = [f for f in backup_files if f not in files_to_keep]

        for old_file in files_to_delete:
            try:
                old_file.unlink()
                logger.info(f"Cleaned up old backup: {old_file}")
            except Exception as e:
                logger.warning(f"Failed to delete old backup {old_file}: {e}")

    def save_channel(self, channel_id: str, title: str, member_count: int, is_private: bool):
        """Save channel information to database with transaction handling."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.connection() as conn:
                    conn.execute("BEGIN TRANSACTION")
                    try:
                        conn.execute('''
                            INSERT OR REPLACE INTO channels
                            (channel_id, title, member_count, scraped_at, is_private)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (channel_id, title, member_count, datetime.now(), is_private))
                        conn.execute("COMMIT")
                        
                        # Record performance metrics
                        from utils import app_context
                        app_context.record_db_query()
                        
                        return  # Success
                    except sqlite3.Error as e:
                        conn.execute("ROLLBACK")
                        raise
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    logger.error(f"Error saving channel {channel_id} after {attempt + 1} attempts: {e}")
                    # Record error metrics
                    from utils import app_context
                    app_context.record_db_query(error=True)
                    raise
            except Exception as e:
                logger.error(f"Unexpected error saving channel {channel_id}: {e}")
                # Record error metrics
                from utils import app_context
                app_context.record_db_query(error=True)
                raise

    def save_member(self, user_id: int, username: str, first_name: str, last_name: str,
                   phone: str, joined_at: datetime, last_seen: datetime, status: str,
                   channel_id: str, activity_score: int = 0, threat_score: int = 0,
                   is_admin: bool = False, is_moderator: bool = False, is_owner: bool = False,
                   message_count: int = 0, last_message_date: datetime = None,
                   is_safe_target: bool = True, threat_reasons: str = None):
        """Save member information to database with thread-safe transaction handling."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.connection(write_operation=True) as conn:
                    # Check if member exists to preserve threat data if not updating
                    cursor = conn.execute('SELECT threat_score, is_safe_target, threat_reasons FROM members WHERE user_id = ?', (user_id,))
                    existing = cursor.fetchone()

                    if existing:
                        # Preserve threat data if not explicitly updating
                        if threat_score == 0:
                            threat_score = existing[0]
                        if is_safe_target is True and existing[1] is not None:
                            is_safe_target = bool(existing[1])
                        if threat_reasons is None:
                            threat_reasons = existing[2]

                    conn.execute('''
                        INSERT OR REPLACE INTO members
                        (user_id, username, first_name, last_name, phone, joined_at, last_seen, status, channel_id,
                         activity_score, threat_score, is_admin, is_moderator, is_owner, message_count,
                         last_message_date, is_safe_target, threat_reasons)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (user_id, username, first_name, last_name, phone, joined_at, last_seen, status, channel_id,
                          activity_score, threat_score, is_admin, is_moderator, is_owner, message_count,
                          last_message_date, is_safe_target, threat_reasons))
                    return  # Success (transaction committed by context manager)
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    logger.error(f"Error saving member {user_id} after {attempt + 1} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error saving member {user_id}: {e}")
                raise

    def log_activity(self, user_id: int, activity_type: str, channel_id: str):
        """Log member activity with transaction handling."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.connection() as conn:
                    conn.execute("BEGIN TRANSACTION")
                    try:
                        conn.execute('''
                            INSERT INTO member_activity (user_id, activity_type, timestamp, channel_id)
                            VALUES (?, ?, ?, ?)
                        ''', (user_id, activity_type, datetime.now(), channel_id))
                        conn.execute("COMMIT")
                        return  # Success
                    except sqlite3.Error as e:
                        conn.execute("ROLLBACK")
                        raise
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    logger.error(f"Error logging activity for user {user_id} after {attempt + 1} attempts: {e}")
                    raise
            except Exception as e:
                logger.error(f"Unexpected error logging activity for user {user_id}: {e}")
                raise

    def get_members_by_activity(self, channel_id: str, limit: int = None) -> List[Dict]:
        """Get members sorted by activity score (most active first)."""
        with self.connection() as conn:
            # Use prepared statement for better performance
            if limit:
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, last_name, phone, joined_at, last_seen, status, activity_score
                    FROM members
                    WHERE channel_id = ?
                    ORDER BY activity_score DESC, last_seen DESC
                    LIMIT ?
                ''', (channel_id, limit))
            else:
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, last_name, phone, joined_at, last_seen, status, activity_score
                    FROM members
                    WHERE channel_id = ?
                    ORDER BY activity_score DESC, last_seen DESC
                ''', (channel_id,))

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_channel_stats(self, channel_id: str) -> Dict:
        """Get statistics for a channel."""
        with self.connection() as conn:
            # Optimized single query to get all stats at once
            yesterday = datetime.now() - timedelta(days=1)

            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_members,
                    COUNT(CASE WHEN activity_score > 0 THEN 1 END) as active_members,
                    (
                        SELECT COUNT(DISTINCT user_id)
                        FROM member_activity
                        WHERE channel_id = ? AND timestamp > ?
                    ) as recent_activity
                FROM members
                WHERE channel_id = ?
            ''', (channel_id, yesterday, channel_id))

            row = cursor.fetchone()
            total = row[0]
            active = row[1]
            recent = row[2]

            return {
                'total_members': total,
                'active_members': active,
                'recent_activity': recent,
                'inactive_members': total - active
            }

    def get_all_channels(self) -> List[Dict]:
        """Get all stored channels."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('SELECT * FROM channels ORDER BY scraped_at DESC')
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_all_members(self, channel_id: Optional[str] = None) -> List[Dict]:
        """Get all members, optionally filtered by channel_id.
        
        WARNING: This loads ALL members into memory. For large datasets, use get_members_paginated() instead.
        """
        with sqlite3.connect(self.db_path) as conn:
            if channel_id:
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, last_name, phone, joined_at, last_seen, status, activity_score, channel_id
                    FROM members
                    WHERE channel_id = ?
                    ORDER BY activity_score DESC, last_seen DESC
                ''', (channel_id,))
            else:
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, last_name, phone, joined_at, last_seen, status, activity_score, channel_id
                    FROM members
                    ORDER BY activity_score DESC, last_seen DESC
                ''')
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_members_paginated(
        self,
        page: int = 1,
        page_size: int = 100,
        channel_id: Optional[str] = None,
        filters: Optional[Dict] = None
    ) -> Tuple[List[Dict], int]:
        """
        Get members with pagination for efficient loading.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of members per page
            channel_id: Optional channel filter
            filters: Optional filters dict with keys:
                - has_username: bool
                - min_activity_score: int
                - is_safe_target: bool
                - search_text: str (searches username, first_name, last_name)
        
        Returns:
            Tuple of (members_list, total_count)
        """
        with sqlite3.connect(self.db_path) as conn:
            # Build WHERE clause
            where_clauses = []
            params = []
            
            if channel_id:
                where_clauses.append("channel_id = ?")
                params.append(channel_id)
            
            if filters:
                if filters.get('has_username'):
                    where_clauses.append("username IS NOT NULL AND username != ''")
                
                if filters.get('min_activity_score') is not None:
                    where_clauses.append("activity_score >= ?")
                    params.append(filters['min_activity_score'])
                
                if filters.get('is_safe_target') is not None:
                    where_clauses.append("is_safe_target = ?")
                    params.append(1 if filters['is_safe_target'] else 0)
                
                if filters.get('search_text'):
                    where_clauses.append("(username LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
                    search = f"%{filters['search_text']}%"
                    params.extend([search, search, search])
            
            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
            
            # Get total count
            count_query = f"SELECT COUNT(*) FROM members WHERE {where_sql}"
            cursor = conn.execute(count_query, params)
            total_count = cursor.fetchone()[0]
            
            # Get paginated data
            offset = (page - 1) * page_size
            data_query = f'''
                SELECT 
                    user_id, username, first_name, last_name, phone, 
                    joined_at, last_seen, status, activity_score, channel_id,
                    threat_score, is_safe_target, message_count
                FROM members
                WHERE {where_sql}
                ORDER BY activity_score DESC, last_seen DESC
                LIMIT ? OFFSET ?
            '''
            cursor = conn.execute(data_query, params + [page_size, offset])
            columns = [desc[0] for desc in cursor.description]
            members = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            logger.debug(f"Retrieved page {page} of members ({len(members)} items, {total_count} total)")
            return members, total_count
    
    def get_safe_targets(self, channel_id: str, limit: int = None) -> List[Dict]:
        """Get safe members for messaging (threats filtered out).

        Args:
            channel_id: Channel identifier
            limit: Maximum number of members to return

        Returns:
            List of safe member dictionaries
        """
        with self.connection() as conn:
            if limit:
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, last_name, phone, joined_at, last_seen, 
                           status, activity_score, threat_score, message_count, channel_id, is_safe_target
                    FROM members
                    WHERE channel_id = ? AND is_safe_target = 1
                    ORDER BY activity_score DESC, threat_score ASC
                    LIMIT ?
                ''', (channel_id, limit))
            else:
                cursor = conn.execute('''
                    SELECT user_id, username, first_name, last_name, phone, joined_at, last_seen,
                           status, activity_score, threat_score, message_count, channel_id, is_safe_target
                    FROM members
                    WHERE channel_id = ? AND is_safe_target = 1
                    ORDER BY activity_score DESC, threat_score ASC
                ''', (channel_id,))
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    # ============== Batch Operations for Scalability ==============
    
    def save_members_batch(self, members: List[Dict], channel_id: str) -> Dict[str, int]:
        """Save multiple members in a single batch operation.
        
        Args:
            members: List of member dictionaries
            channel_id: Channel identifier
            
        Returns:
            Dictionary with success/failure counts
        """
        if not members:
            return {'success': 0, 'failed': 0, 'total': 0}
        
        batch_id = None
        success_count = 0
        failed_count = 0
        
        try:
            with self.connection() as conn:
                # Start batch tracking
                cursor = conn.execute('''
                    INSERT INTO batch_operations (operation_type, records_processed)
                    VALUES ('save_members_batch', ?)
                ''', (len(members),))
                batch_id = cursor.lastrowid
                conn.commit()
                
                # Use transaction for atomicity
                conn.execute("BEGIN TRANSACTION")
                
                try:
                    for member in members:
                        try:
                            conn.execute('''
                                INSERT OR REPLACE INTO members
                                (user_id, username, first_name, last_name, phone, joined_at, last_seen, 
                                 status, channel_id, activity_score, threat_score, is_admin, is_moderator, 
                                 is_owner, message_count, last_message_date, is_safe_target, threat_reasons)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                member.get('user_id'),
                                member.get('username'),
                                member.get('first_name'),
                                member.get('last_name'),
                                member.get('phone'),
                                member.get('joined_at'),
                                member.get('last_seen'),
                                member.get('status'),
                                channel_id,
                                member.get('activity_score', 0),
                                member.get('threat_score', 0),
                                member.get('is_admin', False),
                                member.get('is_moderator', False),
                                member.get('is_owner', False),
                                member.get('message_count', 0),
                                member.get('last_message_date'),
                                member.get('is_safe_target', True),
                                member.get('threat_reasons')
                            ))
                            success_count += 1
                        except sqlite3.Error as e:
                            logger.warning(f"Failed to save member {member.get('user_id')}: {e}")
                            failed_count += 1
                    
                    conn.execute("COMMIT")
                    
                    # Update batch tracking
                    if batch_id:
                        conn.execute('''
                            UPDATE batch_operations 
                            SET completed_at = CURRENT_TIMESTAMP, records_success = ?, records_failed = ?, status = 'completed'
                            WHERE id = ?
                        ''', (success_count, failed_count, batch_id))
                        conn.commit()
                    
                except Exception as e:
                    conn.execute("ROLLBACK")
                    if batch_id:
                        conn.execute('''
                            UPDATE batch_operations 
                            SET completed_at = CURRENT_TIMESTAMP, status = 'failed', error_message = ?
                            WHERE id = ?
                        ''', (str(e), batch_id))
                        conn.commit()
                    raise
                    
        except Exception as e:
            logger.error(f"Batch save failed: {e}")
            
        return {
            'success': success_count,
            'failed': failed_count,
            'total': len(members),
            'batch_id': batch_id
        }
    
    def update_members_batch(self, updates: List[Dict]) -> Dict[str, int]:
        """Update multiple members in a single batch operation.
        
        Args:
            updates: List of dictionaries with 'user_id' and fields to update
            
        Returns:
            Dictionary with success/failure counts
        """
        if not updates:
            return {'success': 0, 'failed': 0, 'total': 0}
        
        success_count = 0
        failed_count = 0
        
        try:
            with self.connection() as conn:
                conn.execute("BEGIN TRANSACTION")
                
                try:
                    for update in updates:
                        user_id = update.get('user_id')
                        if not user_id:
                            failed_count += 1
                            continue
                        
                        # Build dynamic update query
                        fields = []
                        values = []
                        for key, value in update.items():
                            if key != 'user_id':
                                fields.append(f"{key} = ?")
                                values.append(value)
                        
                        if fields:
                            values.append(user_id)
                            query = f"UPDATE members SET {', '.join(fields)} WHERE user_id = ?"
                            try:
                                conn.execute(query, values)
                                success_count += 1
                            except sqlite3.Error as e:
                                logger.warning(f"Failed to update member {user_id}: {e}")
                                failed_count += 1
                    
                    conn.execute("COMMIT")
                except Exception as e:
                    conn.execute("ROLLBACK")
                    raise
                    
        except Exception as e:
            logger.error(f"Batch update failed: {e}")
            
        return {'success': success_count, 'failed': failed_count, 'total': len(updates)}

    def get_member_by_id(self, user_id: int) -> Optional[Dict]:
        """Get a single member by user ID efficiently with all related data."""
        with self.connection() as conn:
            cursor = conn.execute('''
                SELECT
                    m.user_id, m.username, m.first_name, m.last_name, m.phone,
                    m.joined_at, m.last_seen, m.status, m.activity_score,
                    m.threat_score, m.is_safe_target, m.message_count, m.channel_id,
                    mp.profile_quality_score,
                    bi.messaging_potential_score, bi.messaging_potential_category,
                    bi.best_contact_time, bi.timezone_estimate
                FROM members m
                LEFT JOIN member_profiles mp ON m.user_id = mp.user_id
                LEFT JOIN member_behavioral_insights bi ON m.user_id = bi.user_id
                WHERE m.user_id = ?
            ''', (user_id,))

            row = cursor.fetchone()
            if row:
                columns = [desc[0] for desc in cursor.description]
                return dict(zip(columns, row))
            return None

    def get_members_batch(self, user_ids: List[int]) -> List[Dict]:
        """Get multiple members by user IDs in a single query.
        
        Args:
            user_ids: List of user IDs to fetch
            
        Returns:
            List of member dictionaries
        """
        if not user_ids:
            return []
        
        with self.connection() as conn:
            placeholders = ','.join(['?' for _ in user_ids])
            cursor = conn.execute(f'''
                SELECT user_id, username, first_name, last_name, phone, joined_at, last_seen,
                       status, activity_score, threat_score, message_count, channel_id, is_safe_target
                FROM members
                WHERE user_id IN ({placeholders})
            ''', user_ids)
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    # ============== Database Maintenance ==============
    
    def vacuum_database(self) -> bool:
        """Run vacuum to reclaim space and optimize database.
        
        Returns:
            True if successful
        """
        try:
            # Vacuum requires exclusive access, use dedicated connection
            conn = sqlite3.connect(self.db_path)
            conn.execute("VACUUM")
            conn.close()
            logger.info("Database vacuum completed successfully")
            return True
        except Exception as e:
            logger.error(f"Database vacuum failed: {e}")
            return False
    
    def incremental_vacuum(self, pages: int = 100) -> bool:
        """Run incremental vacuum to reclaim some space.
        
        Args:
            pages: Number of pages to free
            
        Returns:
            True if successful
        """
        try:
            with self.connection() as conn:
                conn.execute(f"PRAGMA incremental_vacuum({pages})")
            return True
        except Exception as e:
            logger.error(f"Incremental vacuum failed: {e}")
            return False
    
    def analyze_tables(self) -> bool:
        """Analyze tables to update query planner statistics.
        
        Returns:
            True if successful
        """
        try:
            with self.connection() as conn:
                conn.execute("ANALYZE")
            logger.info("Database analyze completed")
            return True
        except Exception as e:
            logger.error(f"Database analyze failed: {e}")
            return False
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics for monitoring.
        
        Returns:
            Dictionary with database statistics
        """
        stats = {}
        
        try:
            with self.connection() as conn:
                # Get row counts
                for table in ['members', 'channels', 'member_activity', 'batch_operations']:
                    try:
                        cursor = conn.execute(f'SELECT COUNT(*) FROM {table}')
                        stats[f'{table}_count'] = cursor.fetchone()[0]
                    except sqlite3.OperationalError:
                        stats[f'{table}_count'] = 0
                
                # Get page info
                cursor = conn.execute('PRAGMA page_count')
                stats['page_count'] = cursor.fetchone()[0]
                
                cursor = conn.execute('PRAGMA page_size')
                stats['page_size'] = cursor.fetchone()[0]
                
                cursor = conn.execute('PRAGMA freelist_count')
                stats['freelist_count'] = cursor.fetchone()[0]
                
                # Calculate approximate size
                stats['db_size_mb'] = (stats['page_count'] * stats['page_size']) / (1024 * 1024)
                
                # Get index info
                cursor = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'")
                stats['index_count'] = cursor.fetchone()[0]
                
                # Get WAL mode status
                cursor = conn.execute('PRAGMA journal_mode')
                stats['journal_mode'] = cursor.fetchone()[0]
                
                # Get cache size
                cursor = conn.execute('PRAGMA cache_size')
                stats['cache_size'] = cursor.fetchone()[0]
                
                # Save stats to tracking table
                try:
                    conn.execute('''
                        INSERT INTO db_statistics (table_name, row_count, index_count, page_count, freelist_count)
                        VALUES ('summary', ?, ?, ?, ?)
                    ''', (stats.get('members_count', 0), stats['index_count'], 
                          stats['page_count'], stats['freelist_count']))
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # Table might not exist yet
                
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            
        return stats
    
    def schedule_maintenance(self, vacuum_interval_hours: int = 24):
        """Schedule periodic database maintenance.
        
        Args:
            vacuum_interval_hours: Hours between vacuum operations
        """
        def maintenance_loop():
            while True:
                try:
                    time.sleep(vacuum_interval_hours * 3600)
                    self.incremental_vacuum(500)  # Free up to 500 pages
                    self.analyze_tables()
                    logger.info("Scheduled database maintenance completed")
                except Exception as e:
                    logger.error(f"Scheduled maintenance failed: {e}")
        
        import threading
        maintenance_thread = threading.Thread(target=maintenance_loop, daemon=True)
        maintenance_thread.start()
        logger.info(f"Database maintenance scheduled every {vacuum_interval_hours} hours")
    
    def cleanup_connection_pool(self):
        """Clean up all connections in the pool."""
        with self._lock:
            for thread_id, connections in list(self._connection_pool.items()):
                for conn in connections:
                    try:
                        conn.close()
                    except Exception:
                        pass
                self._connection_pool[thread_id] = []
        logger.info("Connection pool cleaned up")
    
    def get_pool_stats(self) -> Dict[str, int]:
        """Get connection pool statistics.
        
        Returns:
            Dictionary with pool statistics
        """
        with self._lock:
            total_connections = sum(len(conns) for conns in self._connection_pool.values())
            thread_count = len(self._connection_pool)
        
        return {
            'total_connections': total_connections,
            'thread_count': thread_count,
            'max_per_thread': self._connection_pool_size
        }


class ThreatDetector:
    """Advanced threat detection system for identifying risky members."""

    def __init__(self, tuning: Optional[Dict[str, Any]] = None):
        """Initialize threat detector."""
        self.threat_keywords = [
            'admin', 'moderator', 'mod', 'owner', 'creator',
            'security', 'report', 'spam', 'ban', 'kick',
            'enforcement', 'compliance', 'violation'
        ]
        
        self.suspicious_patterns = [
            r'admin', r'mod', r'owner', r'creator',
            r'security', r'enforcement', r'compliance'
        ]

        self.weight_config = {
            'owner': 100,
            'admin': 80,
            'moderator': 60,
            'very_active': 40,
            'active': 20,
            'regular': 10,
            'very_recent': 30,
            'recent': 15,
            'suspicious_pattern': 25,
            'verified': 20,
            'premium': 10,
            'has_photo': 5
        }
        if tuning and isinstance(tuning, dict):
            overrides = tuning.get('weights', {})
            if overrides:
                logger.info(
                    "Applying threat-detector weight overrides: %s",
                    {k: overrides[k] for k in sorted(overrides.keys())}
                )
            self.weight_config.update(overrides)

        self.safe_threshold = (tuning or {}).get('safe_threshold', 50)
        logger.debug(
            "Threat detector initialized with safe_threshold=%s and %d weights",
            self.safe_threshold,
            len(self.weight_config)
        )
    
    def calculate_threat_score(self, member: ChatMember, message_count: int = 0,
                               is_admin: bool = False, is_moderator: bool = False,
                               is_owner: bool = False, last_message_days: int = None) -> Tuple[int, List[str]]:
        """Calculate threat score for a member.
        
        Returns:
            Tuple of (threat_score, threat_reasons)
        """
        threat_score = 0
        reasons = []
        weights = self.weight_config
        
        # Owner is highest threat
        if is_owner or member.status == ChatMemberStatus.OWNER:
            threat_score += weights.get('owner', 100)
            reasons.append("Channel/Group Owner")
        
        # Admin is high threat
        if is_admin or member.status == ChatMemberStatus.ADMINISTRATOR:
            threat_score += weights.get('admin', 80)
            reasons.append("Administrator")
        
        # Moderator is medium-high threat
        if is_moderator:
            threat_score += weights.get('moderator', 60)
            reasons.append("Moderator")
        
        # Very active users (likely to report)
        if message_count > 100:
            threat_score += weights.get('very_active', 40)
            reasons.append(f"Very active ({message_count} messages)")
        elif message_count > 50:
            threat_score += weights.get('active', 20)
            reasons.append(f"Active user ({message_count} messages)")
        elif message_count > 20:
            threat_score += weights.get('regular', 10)
            reasons.append(f"Regular poster ({message_count} messages)")
        
        # Recent activity (more likely to notice and report)
        if last_message_days is not None and last_message_days <= 1:
            threat_score += weights.get('very_recent', 30)
            reasons.append("Very recent activity")
        elif last_message_days is not None and last_message_days <= 7:
            threat_score += weights.get('recent', 15)
            reasons.append("Recent activity")
        
        # Check username for suspicious patterns
        username = member.user.username or ""
        first_name = member.user.first_name or ""
        full_name = f"{first_name} {member.user.last_name or ''}".lower()
        
        for pattern in self.suspicious_patterns:
            if re.search(pattern, username.lower()) or re.search(pattern, full_name):
                threat_score += weights.get('suspicious_pattern', 25)
                reasons.append("Suspicious username/name pattern")
                break
        
        # Verified accounts (more likely to report)
        if getattr(member.user, 'is_verified', False):
            threat_score += weights.get('verified', 20)
            reasons.append("Verified account")
        
        # Premium users (more engaged, more likely to report)
        if getattr(member.user, 'is_premium', False):
            threat_score += weights.get('premium', 10)
            reasons.append("Premium user")
        
        # Accounts with profile photos (more engaged)
        if getattr(member.user, 'photo', None):
            threat_score += weights.get('has_photo', 5)

        return threat_score, reasons
    
    def is_safe_target(self, threat_score: int, reasons: List[str]) -> bool:
        """Determine if member is safe to target.
        
        Args:
            threat_score: Calculated threat score
            reasons: List of threat reasons
            
        Returns:
            True if safe to target, False otherwise
        """
        # High threat score = not safe
        if threat_score >= self.safe_threshold:
            return False
        
        # Has admin/mod/owner status = not safe
        admin_keywords = ['owner', 'administrator', 'moderator']
        if any(keyword in ' '.join(reasons).lower() for keyword in admin_keywords):
            return False
        
        return True


class ComprehensiveDataExtractor:
    """Extracts and analyzes ALL available data from Telegram members."""

    def __init__(self):
        """Initialize the comprehensive data extractor."""
        self.profile_analyzers = {}
        self.activity_analyzers = {}
        self.network_analyzers = {}
        self._init_analyzers()

    def _init_analyzers(self):
        """Initialize all data analysis modules."""
        # Profile photo analysis
        try:
            import cv2
            import pytesseract
            from PIL import Image
            import numpy as np
            self.profile_analyzers['ocr'] = self._analyze_profile_photo_ocr
            self.profile_analyzers['metadata'] = self._analyze_profile_photo_metadata
        except ImportError:
            logger.warning("Profile photo analysis not available - install opencv-python, pytesseract, pillow")

        # Bio analysis
        try:
            import nltk
            from textblob import TextBlob
            self.profile_analyzers['sentiment'] = self._analyze_bio_sentiment
            self.profile_analyzers['keywords'] = self._analyze_bio_keywords
        except ImportError:
            logger.warning("Bio analysis not available - install nltk, textblob")

        # Activity pattern recognition
        self.activity_analyzers['temporal'] = self._analyze_temporal_patterns
        self.activity_analyzers['frequency'] = self._analyze_message_frequency
        self.activity_analyzers['engagement'] = self._analyze_engagement_patterns

        # Network analysis
        self.network_analyzers['connections'] = self._analyze_connection_network
        self.network_analyzers['influence'] = self._analyze_influence_score

    async def extract_comprehensive_member_data(self, client: Client, user: User,
                                               channel_context: Dict = None) -> Dict[str, Any]:
        """Extract ALL available data about a member.

        Returns comprehensive member profile with advanced analysis.
        """
        base_data = await self._extract_basic_telegram_data(client, user)

        # Enhanced data extraction
        enhanced_data = {
            'profile_analysis': await self._analyze_profile_comprehensive(client, user),
            'activity_patterns': await self._analyze_activity_patterns(client, user, channel_context),
            'network_analysis': await self._analyze_network_connections(client, user),
            'behavioral_insights': await self._analyze_behavioral_patterns(client, user),
            'risk_assessment': await self._assess_member_risks(client, user),
            'messaging_potential': await self._assess_messaging_potential(client, user),
            'extraction_timestamp': datetime.now(),
            'data_completeness_score': 0.0  # Will be calculated
        }

        # Merge all data
        comprehensive_profile = {**base_data, **enhanced_data}

        # Calculate data completeness
        comprehensive_profile['data_completeness_score'] = self._calculate_completeness_score(comprehensive_profile)

        return comprehensive_profile

    async def _extract_basic_telegram_data(self, client: Client, user: User) -> Dict[str, Any]:
        """Extract all basic Telegram API data fields."""
        # Extract all available User fields
        user_data = {
            'user_id': user.id,
            'is_bot': user.is_bot,
            'is_deleted': getattr(user, 'is_deleted', False),
            'is_verified': getattr(user, 'is_verified', False),
            'is_restricted': getattr(user, 'is_restricted', False),
            'is_scam': getattr(user, 'is_scam', False),
            'is_fake': getattr(user, 'is_fake', False),
            'is_premium': getattr(user, 'is_premium', False),
            'first_name': user.first_name,
            'last_name': user.last_name,
            'username': user.username,
            'phone_number': getattr(user, 'phone_number', None),
            'profile_photo_id': getattr(getattr(user, 'photo', None), 'big_file_id', None) if hasattr(user, 'photo') else None,
            'photo_small_id': getattr(getattr(user, 'photo', ''), 'small_file_id', None) if hasattr(user, 'photo') else None,
            'status': str(getattr(user, 'status', 'unknown')),
            'last_online_date': getattr(user, 'last_online_date', None),
            'next_offline_date': getattr(user, 'next_offline_date', None),
            'language_code': getattr(user, 'language_code', None),
            'region_code': getattr(user, 'region_code', None),
            'dc_id': getattr(user, 'dc_id', None),
            'emoji_status': getattr(getattr(user, 'emoji_status', None), 'custom_emoji_id', None),
            'bio': getattr(user, 'bio', None),
            'restrictions': getattr(user, 'restrictions', []),
            'mention': user.mention if hasattr(user, 'mention') else None,
        }

        # Extract additional fields that might be available
        try:
            # Try to get full user profile
            full_user = await client.get_users(user.id)
            if full_user and hasattr(full_user, 'bio'):
                user_data['bio'] = full_user.bio
            if full_user and hasattr(full_user, 'common_chats_count'):
                user_data['common_chats_count'] = full_user.common_chats_count
        except Exception as e:
            logger.debug(f"Could not get extended user data for {user.id}: {e}")

        return user_data

    async def _analyze_profile_comprehensive(self, client: Client, user: User) -> Dict[str, Any]:
        """Comprehensive profile analysis."""
        analysis = {
            'photo_analysis': {},
            'bio_analysis': {},
            'name_analysis': {},
            'username_analysis': {},
            'account_age_analysis': {}
        }

        # Profile photo analysis
        if hasattr(user, 'photo') and user.photo:
            analysis['photo_analysis'] = await self._analyze_profile_photo(client, user.photo)

        # Bio analysis
        if hasattr(user, 'bio') and user.bio:
            analysis['bio_analysis'] = self._analyze_bio_comprehensive(user.bio)

        # Name analysis
        analysis['name_analysis'] = self._analyze_name_patterns(user.first_name, user.last_name)

        # Username analysis
        if user.username:
            analysis['username_analysis'] = self._analyze_username_patterns(user.username)

        # Account age estimation
        analysis['account_age_analysis'] = self._estimate_account_age(user.id)

        return analysis

    async def _analyze_profile_photo(self, client: Client, photo) -> Dict[str, Any]:
        """Advanced profile photo analysis."""
        analysis = {
            'has_photo': True,
            'photo_metadata': {},
            'ocr_text': '',
            'visual_features': {},
            'quality_score': 0.0
        }

        try:
            # Download photo for analysis
            photo_path = await client.download_media(photo.big_file_id, file_name=f"temp_{photo.big_file_id}.jpg")

            if photo_path and 'ocr' in self.profile_analyzers:
                analysis['ocr_text'] = self.profile_analyzers['ocr'](photo_path)

            if photo_path and 'metadata' in self.profile_analyzers:
                analysis['photo_metadata'] = self.profile_analyzers['metadata'](photo_path)

            # Calculate quality score
            analysis['quality_score'] = self._calculate_photo_quality_score(analysis)

            # Clean up
            if photo_path:
                import os
                try:
                    os.remove(photo_path)
                except (OSError, FileNotFoundError):
                    # Ignore cleanup errors
                    pass

        except Exception as e:
            logger.debug(f"Photo analysis failed: {e}")
            analysis['has_photo'] = False

        return analysis

    def _analyze_profile_photo_ocr(self, photo_path: str) -> str:
        """Extract text from profile photo using OCR."""
        try:
            import cv2
            import pytesseract
            from PIL import Image

            # Load image
            image = cv2.imread(photo_path)
            if image is None:
                return ""

            # Preprocessing for better OCR
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            # Apply threshold to get better contrast
            _, threshold = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # OCR
            text = pytesseract.image_to_string(threshold, lang='eng')

            # Clean up text
            text = ' '.join(text.split())  # Remove extra whitespace

            return text[:500]  # Limit length

        except Exception as e:
            logger.debug(f"OCR analysis failed: {e}")
            return ""

    def _analyze_profile_photo_metadata(self, photo_path: str) -> Dict[str, Any]:
        """Extract metadata from profile photo."""
        metadata = {}

        try:
            from PIL import Image
            import os

            # Get file size
            metadata['file_size'] = os.path.getsize(photo_path)

            # Open image and get dimensions
            with Image.open(photo_path) as img:
                metadata['width'] = img.width
                metadata['height'] = img.height
                metadata['format'] = img.format
                metadata['mode'] = img.mode

                # Check if it's animated
                metadata['is_animated'] = hasattr(img, 'is_animated') and img.is_animated

                # Color analysis
                if img.mode in ['RGB', 'RGBA']:
                    # Get dominant colors
                    img.thumbnail((100, 100))
                    colors = img.getcolors(100 * 100)
                    if colors:
                        # Sort by frequency and get top 5
                        colors.sort(key=lambda x: x[0], reverse=True)
                        metadata['dominant_colors'] = colors[:5]

        except Exception as e:
            logger.debug(f"Metadata analysis failed: {e}")

        return metadata

    def _calculate_photo_quality_score(self, analysis: Dict) -> float:
        """Calculate photo quality score."""
        score = 0.5  # Base score

        # Higher score for having OCR text (suggests text/logos)
        if analysis.get('ocr_text', '').strip():
            score += 0.2

        # Higher score for larger images
        metadata = analysis.get('photo_metadata', {})
        if metadata.get('width', 0) > 200 and metadata.get('height', 0) > 200:
            score += 0.1

        # Lower score for very small files (likely default/empty photos)
        if metadata.get('file_size', 0) < 1000:
            score -= 0.3

        return max(0.0, min(1.0, score))

    def _analyze_bio_comprehensive(self, bio: str) -> Dict[str, Any]:
        """Comprehensive bio analysis."""
        analysis = {
            'length': len(bio),
            'word_count': len(bio.split()),
            'language': 'unknown',
            'sentiment': {'polarity': 0.0, 'subjectivity': 0.0},
            'keywords': [],
            'hashtags': [],
            'mentions': [],
            'urls': [],
            'emojis': [],
            'categories': []
        }

        # Extract patterns
        analysis['hashtags'] = re.findall(r'#\w+', bio)
        analysis['mentions'] = re.findall(r'@\w+', bio)
        analysis['urls'] = re.findall(r'https?://[^\s]+', bio)
        analysis['emojis'] = re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', bio)

        # Sentiment analysis
        if 'sentiment' in self.profile_analyzers:
            analysis['sentiment'] = self.profile_analyzers['sentiment'](bio)

        # Keyword extraction
        if 'keywords' in self.profile_analyzers:
            analysis['keywords'] = self.profile_analyzers['keywords'](bio)

        # Language detection
        analysis['language'] = self._detect_language(bio)

        # Categorization
        analysis['categories'] = self._categorize_bio(bio)

        return analysis

    def _analyze_bio_sentiment(self, bio: str) -> Dict[str, float]:
        """Analyze bio sentiment."""
        try:
            from textblob import TextBlob

            blob = TextBlob(bio)
            return {
                'polarity': blob.sentiment.polarity,  # -1 to 1
                'subjectivity': blob.sentiment.subjectivity  # 0 to 1
            }
        except (ImportError, AttributeError, Exception) as e:
            logger.debug(f"Bio sentiment analysis failed: {e}")
            return {'polarity': 0.0, 'subjectivity': 0.5}

    def _analyze_bio_keywords(self, bio: str) -> List[str]:
        """Extract keywords from bio."""
        try:
            import nltk
            from nltk.corpus import stopwords
            from nltk.tokenize import word_tokenize

            # Download required NLTK data if needed
            try:
                stopwords.words('english')
            except LookupError:
                nltk.download('stopwords')
                nltk.download('punkt')

            # Tokenize and clean
            tokens = word_tokenize(bio.lower())
            stop_words = set(stopwords.words('english'))
            keywords = [word for word in tokens if word.isalnum() and word not in stop_words and len(word) > 2]

            # Get most common keywords
            from collections import Counter
            counter = Counter(keywords)
            return [word for word, count in counter.most_common(10)]

        except (ImportError, LookupError, AttributeError, Exception) as e:
            # Fallback: simple word extraction
            logger.debug(f"Advanced keyword analysis failed: {e}")
            words = re.findall(r'\b\w{3,}\b', bio.lower())
            return list(set(words))[:10]

    def _detect_language(self, text: str) -> str:
        """Detect language of text."""
        try:
            from langdetect import detect
            return detect(text)
        except (ImportError, Exception) as e:
            # Fallback based on common patterns
            logger.debug(f"Language detection failed: {e}")
            if any(ord(char) > 127 for char in text):
                return "non_english"
            return "english"

    def _categorize_bio(self, bio: str) -> List[str]:
        """Categorize bio content."""
        categories = []
        bio_lower = bio.lower()

        # Business/professional
        if any(word in bio_lower for word in ['business', 'company', 'entrepreneur', 'professional', 'ceo', 'founder']):
            categories.append('business')

        # Technology
        if any(word in bio_lower for word in ['tech', 'developer', 'programmer', 'coder', 'software', 'engineer']):
            categories.append('technology')

        # Creative
        if any(word in bio_lower for word in ['artist', 'designer', 'creative', 'photographer', 'musician']):
            categories.append('creative')

        # Gaming
        if any(word in bio_lower for word in ['gamer', 'gaming', 'game', 'player']):
            categories.append('gaming')

        # Sports
        if any(word in bio_lower for word in ['football', 'basketball', 'soccer', 'sport', 'fitness']):
            categories.append('sports')

        # Education
        if any(word in bio_lower for word in ['student', 'teacher', 'professor', 'university', 'school']):
            categories.append('education')

        return categories if categories else ['general']

    def _analyze_name_patterns(self, first_name: str, last_name: str) -> Dict[str, Any]:
        """Analyze name patterns."""
        analysis = {
            'name_length': len((first_name or '') + (last_name or '')),
            'has_last_name': bool(last_name),
            'name_complexity': 0,
            'likely_gender': 'unknown',
            'cultural_origin': 'unknown'
        }

        full_name = f"{first_name or ''} {last_name or ''}".strip()

        # Name complexity (more unique characters = more complex)
        unique_chars = len(set(full_name.lower()))
        analysis['name_complexity'] = unique_chars / max(len(full_name), 1)

        # Simple gender detection based on common patterns
        if first_name:
            first_lower = first_name.lower()
            if first_lower.endswith(('a', 'e', 'i', 'y')) and len(first_name) > 2:
                analysis['likely_gender'] = 'female'
            elif first_lower.endswith(('o', 'r', 'k', 'd')) and len(first_name) > 2:
                analysis['likely_gender'] = 'male'

        return analysis

    def _analyze_username_patterns(self, username: str) -> Dict[str, Any]:
        """Analyze username patterns."""
        analysis = {
            'length': len(username),
            'has_numbers': bool(re.search(r'\d', username)),
            'has_underscores': '_' in username,
            'has_dots': '.' in username,
            'pattern_type': 'unknown',
            'likely_category': 'personal'
        }

        # Pattern recognition
        if re.match(r'^\w{1,8}\d{1,4}$', username):
            analysis['pattern_type'] = 'name_with_numbers'
        elif re.match(r'^\w+_\w+$', username):
            analysis['pattern_type'] = 'two_words_underscore'
        elif re.match(r'^\w+\.\w+$', username):
            analysis['pattern_type'] = 'two_words_dot'
        elif re.match(r'^\d+', username):
            analysis['pattern_type'] = 'starts_with_number'

        # Category detection
        username_lower = username.lower()
        if any(word in username_lower for word in ['bot', 'admin', 'support', 'official']):
            analysis['likely_category'] = 'official'
        elif any(word in username_lower for word in ['news', 'media', 'press']):
            analysis['likely_category'] = 'media'
        elif any(word in username_lower for word in ['store', 'shop', 'sell', 'buy']):
            analysis['likely_category'] = 'business'

        return analysis

    def _estimate_account_age(self, user_id: int) -> Dict[str, Any]:
        """Estimate account age from user ID."""
        # Telegram user IDs are sequential and can give rough age estimates
        # Lower IDs = older accounts
        base_id = 1000000000  # Approximate base for modern accounts

        if user_id < base_id:
            estimated_days = (base_id - user_id) / 10000  # Rough estimation
            creation_date = datetime.now() - timedelta(days=estimated_days)
        else:
            # Newer accounts - estimate based on distance from base
            days_since_base = (user_id - base_id) / 50000  # Rough estimation
            creation_date = datetime(2015, 1, 1) + timedelta(days=days_since_base)

        return {
            'estimated_creation_date': creation_date,
            'account_age_days': (datetime.now() - creation_date).days,
            'account_age_years': (datetime.now() - creation_date).days / 365,
            'confidence': 'low'  # This is a very rough estimation
        }

    async def _analyze_activity_patterns(self, client: Client, user: User,
                                       channel_context: Dict = None) -> Dict[str, Any]:
        """Analyze user's activity patterns with real data processing."""
        patterns = {
            'message_frequency': {},
            'temporal_patterns': {},
            'engagement_patterns': {},
            'channel_participation': {}
        }

        # Get message history for analysis
        message_timestamps = []
        message_types = []
        engagement_metrics = {
            'replies_received': 0,
            'reactions_received': 0,
            'forwards': 0,
            'media_shares': 0
        }

        try:
            # Analyze recent messages (limit for performance)
            async for message in client.get_chat_history(channel_context['id'], limit=200):
                if message.from_user and message.from_user.id == user.id:
                    message_timestamps.append(message.date)

                    # Categorize message types
                    if message.reply_to_message:
                        message_types.append('reply')
                        engagement_metrics['replies_received'] += 1
                    elif message.photo or message.video or message.document:
                        message_types.append('media')
                        engagement_metrics['media_shares'] += 1
                    elif message.forward_date:
                        message_types.append('forward')
                        engagement_metrics['forwards'] += 1
                    else:
                        message_types.append('text')

                    # Count reactions (if available)
                    if hasattr(message, 'reactions') and message.reactions:
                        engagement_metrics['reactions_received'] += sum(
                            reaction.count for reaction in message.reactions.reactions
                        )

        except Exception as e:
            logger.debug(f"Could not analyze message history for activity patterns: {e}")

        # Analyze temporal patterns
        patterns['temporal_patterns'] = self._analyze_temporal_patterns_real(message_timestamps)

        # Analyze message frequency
        patterns['message_frequency'] = self._analyze_message_frequency_real(message_timestamps, len(message_types))

        # Analyze engagement patterns
        patterns['engagement_patterns'] = self._analyze_engagement_patterns_real(engagement_metrics, len(message_types))

        return patterns

    def _analyze_temporal_patterns_real(self, timestamps: List[datetime]) -> Dict[str, Any]:
        """Analyze real temporal activity patterns."""
        if not timestamps:
            return {
                'active_hours': [],
                'active_days': [],
                'timezone_estimate': 'unknown',
                'activity_consistency': 0.0
            }

        # Extract hour and day patterns
        hours = [ts.hour for ts in timestamps]
        days = [ts.weekday() for ts in timestamps]  # 0=Monday, 6=Sunday

        # Find most active hours (top 3)
        hour_counts = {}
        for hour in hours:
            hour_counts[hour] = hour_counts.get(hour, 0) + 1

        active_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        active_hours = [hour for hour, count in active_hours]

        # Find most active days
        day_counts = {}
        for day in days:
            day_counts[day] = day_counts.get(day, 0) + 1

        active_days = sorted(day_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        active_days = [day for day, count in active_days]

        # Estimate timezone (rough based on active hours)
        avg_hour = sum(hours) / len(hours) if hours else 12
        if 6 <= avg_hour <= 10:  # Morning active
            timezone_estimate = "UTC+8 to UTC+12"  # Asia
        elif 12 <= avg_hour <= 16:  # Afternoon active
            timezone_estimate = "UTC+0 to UTC+4"  # Europe/Africa
        elif 18 <= avg_hour <= 22:  # Evening active
            timezone_estimate = "UTC-8 to UTC-4"  # Americas
        else:
            timezone_estimate = "UTC-12 to UTC+14"  # Various

        # Calculate consistency (how evenly distributed activity is)
        if len(timestamps) > 1:
            # Sort timestamps and calculate gaps
            sorted_ts = sorted(timestamps)
            gaps = [(sorted_ts[i+1] - sorted_ts[i]).total_seconds() / 3600 for i in range(len(sorted_ts)-1)]
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                std_gap = statistics.stdev(gaps) if len(gaps) > 1 else 0
                consistency = 1 / (1 + std_gap / max(avg_gap, 1))  # Normalize to 0-1
            else:
                consistency = 0.5
        else:
            consistency = 0.0

        return {
            'active_hours': active_hours,
            'active_days': active_days,
            'timezone_estimate': timezone_estimate,
            'activity_consistency': min(1.0, consistency),
            'total_messages_analyzed': len(timestamps)
        }

    def _analyze_message_frequency_real(self, timestamps: List[datetime], total_messages: int) -> Dict[str, Any]:
        """Analyze real message frequency patterns."""
        if not timestamps:
            return {
                'messages_per_day': 0,
                'messages_per_week': 0,
                'burst_patterns': False,
                'consistency_score': 0.0
            }

        # Calculate time span
        if len(timestamps) > 1:
            sorted_ts = sorted(timestamps)
            time_span_days = (sorted_ts[-1] - sorted_ts[0]).total_seconds() / 86400
            time_span_days = max(time_span_days, 1)  # At least 1 day
        else:
            time_span_days = 1

        messages_per_day = total_messages / time_span_days
        messages_per_week = messages_per_day * 7

        # Detect burst patterns (messages clustered in short time)
        burst_patterns = False
        if len(timestamps) > 3:
            sorted_ts = sorted(timestamps)
            # Check for messages within 5-minute windows
            for i in range(len(sorted_ts) - 2):
                window_messages = [ts for ts in sorted_ts[i:i+5]
                                 if (ts - sorted_ts[i]).total_seconds() < 300]  # 5 minutes
                if len(window_messages) >= 3:
                    burst_patterns = True
                    break

        # Calculate consistency (coefficient of variation of inter-message times)
        if len(timestamps) > 2:
            sorted_ts = sorted(timestamps)
            intervals = [(sorted_ts[i+1] - sorted_ts[i]).total_seconds()
                        for i in range(len(sorted_ts)-1)]
            if intervals:
                mean_interval = sum(intervals) / len(intervals)
                variance = sum((i - mean_interval) ** 2 for i in intervals) / len(intervals)
                std_dev = variance ** 0.5
                consistency_score = 1 / (1 + (std_dev / max(mean_interval, 1)))
            else:
                consistency_score = 0.5
        else:
            consistency_score = 0.0

        return {
            'messages_per_day': messages_per_day,
            'messages_per_week': messages_per_week,
            'burst_patterns': burst_patterns,
            'consistency_score': consistency_score,
            'time_span_days': time_span_days
        }

    def _analyze_engagement_patterns_real(self, engagement_metrics: Dict, total_messages: int) -> Dict[str, Any]:
        """Analyze real engagement patterns."""
        if total_messages == 0:
            return {
                'response_rate': 0.0,
                'conversation_length': 0,
                'interaction_types': [],
                'engagement_score': 0.0
            }

        # Calculate engagement rates
        reply_rate = engagement_metrics.get('replies_received', 0) / total_messages
        reaction_rate = engagement_metrics.get('reactions_received', 0) / total_messages
        forward_rate = engagement_metrics.get('forwards', 0) / total_messages
        media_rate = engagement_metrics.get('media_shares', 0) / total_messages

        # Determine interaction types
        interaction_types = []
        if reply_rate > 0.1:
            interaction_types.append('conversational')
        if reaction_rate > 0.2:
            interaction_types.append('reaction-prone')
        if forward_rate > 0.1:
            interaction_types.append('content_sharer')
        if media_rate > 0.3:
            interaction_types.append('visual_content_creator')

        if not interaction_types:
            interaction_types = ['neutral']

        # Calculate engagement score (weighted combination)
        engagement_score = (
            reply_rate * 0.4 +      # Conversations are most valuable
            reaction_rate * 0.3 +   # Reactions show engagement
            media_rate * 0.2 +      # Media sharing shows activity
            forward_rate * 0.1      # Forwarding shows network activity
        )

        # Estimate conversation length based on reply patterns
        if reply_rate > 0.2:
            conversation_length = "long"
        elif reply_rate > 0.1:
            conversation_length = "medium"
        elif reply_rate > 0.05:
            conversation_length = "short"
        else:
            conversation_length = "minimal"

        return {
            'response_rate': reply_rate,
            'conversation_length': conversation_length,
            'interaction_types': interaction_types,
            'engagement_score': min(1.0, engagement_score),
            'detailed_metrics': {
                'reply_rate': reply_rate,
                'reaction_rate': reaction_rate,
                'forward_rate': forward_rate,
                'media_rate': media_rate
            }
        }

    def _analyze_temporal_patterns(self, user: User) -> Dict[str, Any]:
        """Analyze temporal activity patterns."""
        # This would require historical message data
        # For now, return basic structure
        return {
            'active_hours': [],  # Hours when most active
            'active_days': [],   # Days when most active
            'timezone_estimate': 'unknown',
            'activity_consistency': 0.0  # 0-1 scale
        }

    def _analyze_message_frequency(self, user: User) -> Dict[str, Any]:
        """Analyze message frequency patterns."""
        return {
            'messages_per_day': 0,
            'messages_per_week': 0,
            'burst_patterns': False,
            'consistency_score': 0.0
        }

    def _analyze_engagement_patterns(self, user: User) -> Dict[str, Any]:
        """Analyze engagement patterns."""
        return {
            'response_rate': 0.0,
            'conversation_length': 0,
            'interaction_types': [],
            'engagement_score': 0.0
        }

    async def _analyze_network_connections(self, client: Client, user: User) -> Dict[str, Any]:
        """Analyze user's network connections with real data."""
        connections = {
            'common_chats_count': getattr(user, 'common_chats_count', 0),
            'mutual_contacts': [],
            'group_memberships': [],
            'influence_score': 0.0,
            'network_centrality': 0.0,
            'community_membership': []
        }

        try:
            # Get common chats (groups/channels user shares with us)
            common_chats = []
            async for chat in client.get_common_chats(user.id):
                chat_info = {
                    'id': chat.id,
                    'title': chat.title,
                    'type': chat.type.value if hasattr(chat.type, 'value') else str(chat.type),
                    'member_count': getattr(chat, 'members_count', 0),
                    'is_admin': False  # Would need to check permissions
                }
                common_chats.append(chat_info)

            connections['common_chats_count'] = len(common_chats)
            connections['group_memberships'] = common_chats

            # Analyze network centrality (how connected they are)
            total_members = sum(chat.get('member_count', 0) for chat in common_chats)
            avg_group_size = total_members / max(len(common_chats), 1)

            # Centrality score based on group count and sizes
            centrality_score = min(1.0, (len(common_chats) * 0.3 + avg_group_size * 0.001))

            connections['network_centrality'] = centrality_score

            # Calculate influence score based on network position
            influence_factors = {
                'group_count': len(common_chats),
                'avg_group_size': avg_group_size,
                'admin_positions': sum(1 for chat in common_chats if chat.get('is_admin', False)),
                'large_groups': sum(1 for chat in common_chats if chat.get('member_count', 0) > 1000)
            }

            # Influence formula: weighted combination of network factors
            influence_score = (
                min(1.0, influence_factors['group_count'] / 10) * 0.4 +  # Group diversity
                min(1.0, influence_factors['avg_group_size'] / 10000) * 0.3 +  # Group size influence
                min(1.0, influence_factors['admin_positions'] / 5) * 0.2 +  # Leadership positions
                min(1.0, influence_factors['large_groups'] / 3) * 0.1   # Large community presence
            )

            connections['influence_score'] = influence_score

            # Determine community membership categories
            communities = []
            if any(chat.get('member_count', 0) > 50000 for chat in common_chats):
                communities.append('mass_community')
            if any('tech' in chat.get('title', '').lower() for chat in common_chats):
                communities.append('technology')
            if any('business' in chat.get('title', '').lower() or 'entrepreneur' in chat.get('title', '').lower() for chat in common_chats):
                communities.append('business')
            if any('gaming' in chat.get('title', '').lower() for chat in common_chats):
                communities.append('gaming')

            if not communities:
                communities = ['general']

            connections['community_membership'] = communities

        except Exception as e:
            logger.debug(f"Network analysis failed for user {user.id}: {e}")

        return connections

    def _analyze_connection_network(self, user: User) -> Dict[str, Any]:
        """Analyze connection network."""
        return {
            'estimated_network_size': 0,
            'connection_quality_score': 0.0,
            'network_diversity': 0.0
        }

    def _analyze_influence_score(self, user: User) -> float:
        """Calculate influence score based on various factors."""
        score = 0.0

        # Premium users have higher influence
        if getattr(user, 'is_premium', False):
            score += 0.3

        # Verified users have high influence
        if getattr(user, 'is_verified', False):
            score += 0.4

        # Username indicates professionalism
        if user.username and len(user.username) > 5:
            score += 0.1

        # Bio length suggests engagement
        if hasattr(user, 'bio') and user.bio and len(user.bio) > 20:
            score += 0.1

        # Profile photo suggests active account
        if hasattr(user, 'photo'):
            score += 0.1

        return min(1.0, score)

    async def _analyze_behavioral_patterns(self, client: Client, user: User) -> Dict[str, Any]:
        """Analyze behavioral patterns with real data processing."""
        # Gather data for analysis
        user_data = {
            'has_username': bool(user.username),
            'has_bio': bool(getattr(user, 'bio', None)),
            'is_verified': getattr(user, 'is_verified', False),
            'is_premium': getattr(user, 'is_premium', False),
            'has_photo': bool(getattr(user, 'photo', None)),
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'username': user.username or ''
        }

        # Analyze account type
        account_type = self._predict_account_type(user_data)

        # Analyze activity level based on available data
        activity_level = self._assess_activity_level(user_data)

        # Analyze engagement style
        engagement_style = self._predict_engagement_style(user_data)

        # Determine communication preferences
        communication_preferences = self._analyze_communication_preferences(user_data)

        # Calculate behavioral score
        behavioral_score = self._calculate_behavioral_score(user_data, account_type, activity_level)

        return {
            'account_type_prediction': account_type,
            'activity_level': activity_level,
            'engagement_style': engagement_style,
            'communication_preferences': communication_preferences,
            'behavioral_score': behavioral_score,
            'analysis_factors': user_data
        }

    def _predict_account_type(self, user_data: Dict) -> str:
        """Predict account type based on profile characteristics."""
        score_business = 0
        score_bot = 0
        score_personal = 0

        # Business indicators
        if user_data['is_verified']:
            score_business += 3
        if user_data['has_bio'] and len(user_data['has_bio']) > 50:
            score_business += 2
        if 'company' in (user_data['bio'] or '').lower() or 'business' in (user_data['bio'] or '').lower():
            score_business += 3
        if user_data['is_premium']:
            score_business += 1
        if len((user_data['first_name'] + user_data['last_name']).strip()) > 20:
            score_business += 1  # Company names tend to be longer

        # Bot indicators
        if 'bot' in user_data['username'].lower():
            score_bot += 5
        if not user_data['has_photo']:
            score_bot += 2
        if not user_data['first_name'] and not user_data['last_name']:
            score_bot += 3
        if len(user_data['username']) < 5:
            score_bot += 1

        # Personal indicators (default)
        score_personal = 5  # Base personal score
        if user_data['has_photo']:
            score_personal += 1
        if user_data['first_name'] or user_data['last_name']:
            score_personal += 2
        if user_data['has_bio'] and len(user_data['has_bio']) < 100:
            score_personal += 1

        # Determine winner
        scores = {
            'business': score_business,
            'bot': score_bot,
            'personal': score_personal
        }

        return max(scores.items(), key=lambda x: x[1])[0]

    def _assess_activity_level(self, user_data: Dict) -> str:
        """Assess activity level based on profile completeness and engagement indicators."""
        activity_score = 0

        # Profile completeness indicators
        if user_data['has_username']:
            activity_score += 2
        if user_data['has_photo']:
            activity_score += 2
        if user_data['has_bio']:
            activity_score += 2
        if user_data['first_name'] or user_data['last_name']:
            activity_score += 1
        if user_data['is_premium']:
            activity_score += 1
        if user_data['is_verified']:
            activity_score += 1

        # Categorize
        if activity_score >= 7:
            return 'high'
        elif activity_score >= 4:
            return 'medium'
        else:
            return 'low'

    def _predict_engagement_style(self, user_data: Dict) -> str:
        """Predict engagement style based on profile characteristics."""
        # This would be enhanced with message analysis, but for now use profile indicators
        if user_data['is_verified'] or user_data['is_premium']:
            return 'active'  # Verified/premium users tend to be more engaged
        elif user_data['has_bio'] and len(user_data['has_bio']) > 30:
            return 'interactive'  # Detailed bio suggests communicative personality
        elif user_data['has_photo'] and user_data['has_username']:
            return 'active'  # Complete profile suggests active user
        else:
            return 'passive'

    def _analyze_communication_preferences(self, user_data: Dict) -> List[str]:
        """Analyze communication preferences based on profile."""
        preferences = []

        # Language preferences (would be enhanced with actual language detection)
        if user_data.get('language_code'):
            preferences.append(f"language:{user_data['language_code']}")

        # Content type preferences based on bio keywords
        bio_text = (user_data.get('bio') or '').lower()
        if any(word in bio_text for word in ['tech', 'developer', 'programmer', 'coder']):
            preferences.append('technical_content')
        if any(word in bio_text for word in ['business', 'entrepreneur', 'startup']):
            preferences.append('business_content')
        if any(word in bio_text for word in ['art', 'design', 'creative', 'photography']):
            preferences.append('creative_content')
        if any(word in bio_text for word in ['gaming', 'gamer', 'game']):
            preferences.append('gaming_content')

        # Communication style preferences
        if user_data['is_verified']:
            preferences.append('professional_communication')
        if user_data['has_photo']:
            preferences.append('visual_communication')
        if len(user_data.get('bio') or '') > 50:
            preferences.append('detailed_communication')

        return preferences if preferences else ['general_communication']

    def _calculate_behavioral_score(self, user_data: Dict, account_type: str,
                                  activity_level: str) -> float:
        """Calculate overall behavioral score."""
        score = 0.5  # Base score

        # Account type weighting
        type_weights = {
            'personal': 1.0,
            'business': 1.2,
            'bot': 0.3
        }
        score *= type_weights.get(account_type, 1.0)

        # Activity level weighting
        activity_weights = {
            'high': 1.3,
            'medium': 1.0,
            'low': 0.7
        }
        score *= activity_weights.get(activity_level, 1.0)

        # Profile completeness bonus
        completeness_factors = sum([
            user_data['has_username'],
            user_data['has_photo'],
            user_data['has_bio'],
            bool(user_data['first_name'] or user_data['last_name'])
        ])
        completeness_bonus = completeness_factors * 0.1
        score += completeness_bonus

        # Premium/verified bonus
        if user_data['is_premium']:
            score += 0.1
        if user_data['is_verified']:
            score += 0.2

        return min(1.0, max(0.0, score))

    async def _assess_member_risks(self, client: Client, user: User) -> Dict[str, Any]:
        """Assess various risks associated with the member using comprehensive analysis."""
        risk_factors = []
        risk_scores = {
            'ban_risk': 0.0,
            'spam_risk': 0.0,
            'bot_risk': 0.0,
            'scam_risk': 0.0
        }

        # Analyze user characteristics for different risk types
        user_chars = {
            'is_verified': getattr(user, 'is_verified', False),
            'is_premium': getattr(user, 'is_premium', False),
            'has_photo': bool(getattr(user, 'photo', None)),
            'has_bio': bool(getattr(user, 'bio', None)),
            'has_username': bool(user.username),
            'username_length': len(user.username or ''),
            'bio_length': len(getattr(user, 'bio', '') or ''),
            'first_name': user.first_name or '',
            'last_name': user.last_name or '',
            'is_bot': user.is_bot
        }

        # Bot risk assessment
        if user_chars['is_bot']:
            risk_scores['bot_risk'] = 1.0
            risk_factors.append('confirmed_bot_account')

        if not user_chars['has_photo']:
            risk_scores['bot_risk'] += 0.3
            risk_factors.append('no_profile_photo')

        if not user_chars['first_name'] and not user_chars['last_name']:
            risk_scores['bot_risk'] += 0.4
            risk_factors.append('no_name_provided')

        if 'bot' in (user.username or '').lower():
            risk_scores['bot_risk'] += 0.8
            risk_factors.append('bot_in_username')

        # Spam risk assessment
        if user_chars['bio_length'] > 200:
            risk_scores['spam_risk'] += 0.2
            risk_factors.append('excessively_long_bio')

        if user_chars['username_length'] < 4:
            risk_scores['spam_risk'] += 0.3
            risk_factors.append('suspiciously_short_username')

        spam_keywords = ['free', 'earn', 'money', 'cash', 'bitcoin', 'crypto', 'investment', 'guaranteed']
        bio_text = (getattr(user, 'bio', '') or '').lower()
        if any(keyword in bio_text for keyword in spam_keywords):
            risk_scores['spam_risk'] += 0.4
            risk_factors.append('spam_keywords_in_bio')

        # Scam risk assessment
        scam_indicators = ['invest', 'trading', 'forex', 'binary', 'options', 'guarantee', 'profit']
        if any(indicator in bio_text for indicator in scam_indicators):
            risk_scores['scam_risk'] += 0.5
            risk_factors.append('investment_scam_indicators')

        # Check for suspicious links in bio
        import re
        urls = re.findall(r'https?://[^\s]+', bio_text)
        if len(urls) > 2:
            risk_scores['scam_risk'] += 0.3
            risk_factors.append('multiple_links_in_bio')

        # Ban risk assessment (users likely to report)
        if user_chars['is_verified']:
            risk_scores['ban_risk'] += 0.4
            risk_factors.append('verified_account')

        if user_chars['is_premium']:
            risk_scores['ban_risk'] += 0.2
            risk_factors.append('premium_account')

        if user_chars['bio_length'] > 100:
            risk_scores['ban_risk'] += 0.1
            risk_factors.append('detailed_bio')

        # Overall risk score (weighted average)
        weights = {
            'ban_risk': 0.5,    # Most important - can get you banned
            'spam_risk': 0.3,   # Important - spam reports
            'bot_risk': 0.15,   # Less important but suspicious
            'scam_risk': 0.05   # Least important but still relevant
        }

        overall_risk = sum(risk_scores[risk_type] * weights[risk_type] for risk_type in risk_scores)

        return {
            'ban_risk': min(1.0, risk_scores['ban_risk']),
            'spam_risk': min(1.0, risk_scores['spam_risk']),
            'bot_risk': min(1.0, risk_scores['bot_risk']),
            'scam_risk': min(1.0, risk_scores['scam_risk']),
            'overall_risk_score': min(1.0, overall_risk),
            'risk_factors': risk_factors,
            'risk_level': self._categorize_risk_level(overall_risk)
        }

    def _categorize_risk_level(self, risk_score: float) -> str:
        """Categorize risk level based on score."""
        if risk_score >= 0.7:
            return 'critical'
        elif risk_score >= 0.5:
            return 'high'
        elif risk_score >= 0.3:
            return 'medium'
        elif risk_score >= 0.1:
            return 'low'
        else:
            return 'safe'

    async def _assess_messaging_potential(self, client: Client, user: User) -> Dict[str, Any]:
        """Assess how suitable this member is for messaging with comprehensive analysis."""
        # Gather all relevant data for assessment
        user_data = {
            'user_id': user.id,
            'has_username': bool(user.username),
            'has_bio': bool(getattr(user, 'bio', None)),
            'is_verified': getattr(user, 'is_verified', False),
            'is_premium': getattr(user, 'is_premium', False),
            'has_photo': bool(getattr(user, 'photo', None)),
            'bio_length': len(getattr(user, 'bio', '') or ''),
            'profile_completeness': 0.0  # Will be calculated
        }

        # Calculate profile completeness
        completeness_factors = [
            user_data['has_username'],
            user_data['has_photo'],
            user_data['has_bio'] and user_data['bio_length'] > 10,
            bool(user.first_name or user.last_name)
        ]
        user_data['profile_completeness'] = sum(completeness_factors) / len(completeness_factors)

        # Assess openness to messaging (response likelihood)
        openness_score = self._calculate_openness_score(user_data)

        # Assess engagement level
        engagement_score = self._calculate_engagement_score(user_data)

        # Assess contact value
        value_score = self._calculate_value_score(user_data)

        # Combined messaging potential score
        messaging_potential = (openness_score * 0.4 + engagement_score * 0.4 + value_score * 0.2)

        # Determine recommendation category
        if messaging_potential >= 0.7:
            recommendation = 'high'
        elif messaging_potential >= 0.4:
            recommendation = 'medium'
        else:
            recommendation = 'low'

        # Estimate best contact time (would be enhanced with activity pattern analysis)
        best_contact_time = self._estimate_best_contact_time(user_data)

        return {
            'openness_score': openness_score,
            'engagement_score': engagement_score,
            'value_score': value_score,
            'messaging_potential_score': messaging_potential,
            'messaging_recommendation': recommendation,
            'best_contact_time': best_contact_time,
            'assessment_factors': {
                'profile_completeness': user_data['profile_completeness'],
                'verification_status': user_data['is_verified'],
                'premium_status': user_data['is_premium'],
                'bio_engagement': user_data['bio_length'] > 20
            }
        }

    def _calculate_openness_score(self, user_data: Dict) -> float:
        """Calculate how open this user is to receiving messages."""
        score = 0.5  # Base score

        # Premium users are more likely to respond
        if user_data['is_premium']:
            score += 0.2

        # Verified users are more professional and responsive
        if user_data['is_verified']:
            score += 0.3

        # Users with detailed bios are more likely to be communicative
        if user_data['bio_length'] > 50:
            score += 0.1

        # Complete profiles suggest active, responsive users
        if user_data['profile_completeness'] > 0.75:
            score += 0.1

        # Users with photos are more engaged
        if user_data['has_photo']:
            score += 0.1

        return min(1.0, score)

    def _calculate_engagement_score(self, user_data: Dict) -> float:
        """Calculate user's engagement level."""
        score = 0.3  # Base score

        # Profile completeness indicates engagement
        score += user_data['profile_completeness'] * 0.3

        # Premium users are more engaged
        if user_data['is_premium']:
            score += 0.2

        # Verified users show higher engagement
        if user_data['is_verified']:
            score += 0.2

        # Bio length suggests content creation engagement
        if user_data['bio_length'] > 20:
            score += 0.1

        return min(1.0, score)

    def _calculate_value_score(self, user_data: Dict) -> float:
        """Calculate the value of this contact for messaging."""
        score = 0.2  # Base score

        # Verified accounts have higher value
        if user_data['is_verified']:
            score += 0.4

        # Premium users have higher value
        if user_data['is_premium']:
            score += 0.2

        # Complete profiles suggest higher quality contacts
        if user_data['profile_completeness'] > 0.75:
            score += 0.2

        # Users with detailed bios may have more value
        if user_data['bio_length'] > 30:
            score += 0.1

        return min(1.0, score)

    def _estimate_best_contact_time(self, user_data: Dict) -> str:
        """Estimate the best time to contact this user."""
        # This is a simplified estimation - would be enhanced with activity pattern data
        # For now, make educated guesses based on profile characteristics

        if user_data['is_verified']:
            # Verified/professional accounts might prefer business hours
            return "business_hours"  # 9 AM - 6 PM in their timezone
        elif user_data['is_premium']:
            # Premium users might be more active
            return "evening_hours"  # 6 PM - 10 PM in their timezone
        elif user_data['profile_completeness'] > 0.75:
            # Highly complete profiles suggest active users
            return "peak_hours"  # 10 AM - 9 PM in their timezone
        else:
            # Default to general active hours
            return "general_active"

    def _calculate_completeness_score(self, profile: Dict) -> float:
        """Calculate data completeness score."""
        total_fields = 0
        filled_fields = 0

        def count_fields(obj, path=""):
            nonlocal total_fields, filled_fields
            if isinstance(obj, dict):
                for key, value in obj.items():
                    total_fields += 1
                    if value is not None and value != "" and value != [] and value != {}:
                        filled_fields += 1
                    count_fields(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    count_fields(item, f"{path}[{i}]")

        count_fields(profile)

        return filled_fields / max(total_fields, 1)


class EliteDataAccessLayer:
    """Standardized data access layer for comprehensive member data."""

    def __init__(self, db: MemberDatabase):
        """Initialize data access layer."""
        self.db = db
        self._init_extended_schema()

    def _init_extended_schema(self):
        """Initialize extended database schema for comprehensive data."""
        with self.db.connection() as conn:
            # Extended member profiles table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS member_profiles (
                    user_id INTEGER PRIMARY KEY,
                    comprehensive_data TEXT,  -- JSON blob of full profile
                    profile_quality_score REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_version INTEGER DEFAULT 1
                )
            ''')

            # Activity patterns table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS member_activity_patterns (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    pattern_type TEXT,  -- temporal, frequency, engagement
                    pattern_data TEXT,  -- JSON data
                    confidence_score REAL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES members(user_id)
                )
            ''')

            # Network connections table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS member_network (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER,
                    connection_type TEXT,  -- mutual_contacts, group_overlaps, etc.
                    connected_user_id INTEGER,
                    connection_strength REAL,
                    metadata TEXT,  -- JSON additional data
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES members(user_id)
                )
            ''')

            # Behavioral insights table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS member_behavioral_insights (
                    user_id INTEGER PRIMARY KEY,
                    account_type_prediction TEXT,
                    activity_level TEXT,
                    engagement_style TEXT,
                    communication_preferences TEXT,  -- JSON
                    behavioral_score REAL,
                    messaging_potential_score REAL,
                    messaging_potential_category TEXT,
                    best_contact_time TEXT,
                    timezone_estimate TEXT,
                    language_prediction TEXT,
                    last_analyzed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES members(user_id)
                )
            ''')

            # Scraping analytics table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS scraping_analytics (
                    id INTEGER PRIMARY KEY,
                    channel_id TEXT,
                    scrape_session_id TEXT,
                    technique_used TEXT,
                    members_found INTEGER,
                    data_quality_avg REAL,
                    duration_seconds REAL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def store_comprehensive_profile(self, user_id: int, comprehensive_data: Dict):
        """Store comprehensive member profile data."""
        import json

        profile_quality = comprehensive_data.get('data_completeness_score', 0)

        with self.db.connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO member_profiles
                (user_id, comprehensive_data, profile_quality_score, data_version)
                VALUES (?, ?, ?, 1)
            ''', (user_id, json.dumps(comprehensive_data), profile_quality))

    def get_comprehensive_profile(self, user_id: int) -> Optional[Dict]:
        """Retrieve comprehensive member profile."""
        import json

        with self.db.connection() as conn:
            cursor = conn.execute('''
                SELECT comprehensive_data FROM member_profiles
                WHERE user_id = ?
            ''', (user_id,))

            row = cursor.fetchone()
            if row:
                return json.loads(row[0])

        return None

    def store_activity_patterns(self, user_id: int, patterns: Dict):
        """Store activity pattern analysis."""
        import json

        with self.db.connection() as conn:
            for pattern_type, pattern_data in patterns.items():
                confidence = pattern_data.get('confidence', 0.5)
                conn.execute('''
                    INSERT OR REPLACE INTO member_activity_patterns
                    (user_id, pattern_type, pattern_data, confidence_score)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, pattern_type, json.dumps(pattern_data), confidence))

    def get_activity_patterns(self, user_id: int) -> Dict[str, Dict]:
        """Retrieve activity patterns for a member."""
        import json

        patterns = {}
        with self.db.connection() as conn:
            cursor = conn.execute('''
                SELECT pattern_type, pattern_data, confidence_score
                FROM member_activity_patterns
                WHERE user_id = ?
            ''', (user_id,))

            for row in cursor.fetchall():
                patterns[row[0]] = json.loads(row[1])
                patterns[row[0]]['confidence'] = row[2]

        return patterns

    def store_network_connections(self, user_id: int, connections: List[Dict]):
        """Store network connection data."""
        import json

        with self.db.connection() as conn:
            for connection in connections:
                conn.execute('''
                    INSERT OR REPLACE INTO member_network
                    (user_id, connection_type, connected_user_id, connection_strength, metadata)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    connection.get('type', 'unknown'),
                    connection.get('connected_user_id'),
                    connection.get('strength', 0.5),
                    json.dumps(connection.get('metadata', {}))
                ))

    def get_network_connections(self, user_id: int) -> List[Dict]:
        """Retrieve network connections for a member."""
        import json

        connections = []
        with self.db.connection() as conn:
            cursor = conn.execute('''
                SELECT connection_type, connected_user_id, connection_strength, metadata
                FROM member_network
                WHERE user_id = ?
                ORDER BY connection_strength DESC
            ''', (user_id,))

            for row in cursor.fetchall():
                connection = {
                    'type': row[0],
                    'connected_user_id': row[1],
                    'strength': row[2],
                    'metadata': json.loads(row[3]) if row[3] else {}
                }
                connections.append(connection)

        return connections

    def store_behavioral_insights(self, user_id: int, insights: Dict):
        """Store behavioral analysis insights."""
        import json

        with self.db.connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO member_behavioral_insights
                (user_id, account_type_prediction, activity_level, engagement_style,
                 communication_preferences, behavioral_score, messaging_potential_score,
                 messaging_potential_category, best_contact_time, timezone_estimate, language_prediction)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                insights.get('account_type_prediction'),
                insights.get('activity_level'),
                insights.get('engagement_style'),
                json.dumps(insights.get('communication_preferences', [])),
                insights.get('behavioral_score', 0),
                insights.get('messaging_potential', {}).get('score', 0),
                insights.get('messaging_potential', {}).get('category'),
                insights.get('best_contact_time'),
                insights.get('timezone_estimate'),
                insights.get('language_prediction')
            ))

    def get_behavioral_insights(self, user_id: int) -> Optional[Dict]:
        """Retrieve behavioral insights for a member."""
        import json

        with self.db.connection() as conn:
            cursor = conn.execute('''
                SELECT account_type_prediction, activity_level, engagement_style,
                       communication_preferences, behavioral_score, messaging_potential_score,
                       messaging_potential_category, best_contact_time, timezone_estimate, language_prediction
                FROM member_behavioral_insights
                WHERE user_id = ?
            ''', (user_id,))

            row = cursor.fetchone()
            if row:
                return {
                    'account_type_prediction': row[0],
                    'activity_level': row[1],
                    'engagement_style': row[2],
                    'communication_preferences': json.loads(row[3]) if row[3] else [],
                    'behavioral_score': row[4],
                    'messaging_potential': {
                        'score': row[5],
                        'category': row[6]
                    },
                    'best_contact_time': row[7],
                    'timezone_estimate': row[8],
                    'language_prediction': row[9]
                }

        return None

    def get_members_for_messaging(self, channel_id: str, criteria: Dict = None, limit: int = None, offset: int = 0) -> List[Dict]:
        """Get members optimized for messaging based on comprehensive data. Supports pagination for large datasets."""
        criteria = criteria or {}

        min_quality = criteria.get('min_profile_quality', 0.3)
        min_messaging_potential = criteria.get('min_messaging_potential', 0.5)
        max_risk = criteria.get('max_risk_score', 50)
        preferred_timezone = criteria.get('preferred_timezone')

        with self.db.connection() as conn:
            query = '''
                SELECT
                    m.user_id, m.username, m.first_name, m.last_name,
                    mp.profile_quality_score,
                    bi.messaging_potential_score, bi.messaging_potential_category,
                    bi.best_contact_time, bi.timezone_estimate,
                    m.threat_score, m.is_safe_target
                FROM members m
                LEFT JOIN member_profiles mp ON m.user_id = mp.user_id
                LEFT JOIN member_behavioral_insights bi ON m.user_id = bi.user_id
                WHERE m.channel_id = ?
                AND m.is_safe_target = 1
                AND m.threat_score < ?
                AND (mp.profile_quality_score IS NULL OR mp.profile_quality_score >= ?)
                AND (bi.messaging_potential_score IS NULL OR bi.messaging_potential_score >= ?)
            '''

            params = [channel_id, max_risk, min_quality, min_messaging_potential]

            if preferred_timezone:
                query += " AND (bi.timezone_estimate = ? OR bi.timezone_estimate IS NULL)"
                params.append(preferred_timezone)

            query += " ORDER BY bi.messaging_potential_score DESC, mp.profile_quality_score DESC"

            # Add pagination
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor = conn.execute(query, params)

            members = []
            for row in cursor.fetchall():
                member = {
                    'user_id': row[0],
                    'username': row[1],
                    'first_name': row[2],
                    'last_name': row[3],
                    'profile_quality': row[4] or 0,
                    'messaging_potential_score': row[5] or 0,
                    'messaging_potential_category': row[6] or 'unknown',
                    'best_contact_time': row[7],
                    'timezone_estimate': row[8],
                    'threat_score': row[9],
                    'is_safe_target': bool(row[10])
                }
                members.append(member)

            return members

    def get_channel_analytics(self, channel_id: str) -> Dict:
        """Get comprehensive analytics for a channel."""
        with self.db.connection() as conn:
            # Get member statistics
            cursor = conn.execute('''
                SELECT
                    COUNT(*) as total_members,
                    AVG(mp.profile_quality_score) as avg_quality,
                    AVG(bi.messaging_potential_score) as avg_messaging_potential,
                    COUNT(CASE WHEN bi.messaging_potential_category = 'high' THEN 1 END) as high_potential_count,
                    AVG(m.threat_score) as avg_threat_score,
                    COUNT(CASE WHEN m.is_safe_target = 1 THEN 1 END) as safe_targets
                FROM members m
                LEFT JOIN member_profiles mp ON m.user_id = mp.user_id
                LEFT JOIN member_behavioral_insights bi ON m.user_id = bi.user_id
                WHERE m.channel_id = ?
            ''', (channel_id,))

            row = cursor.fetchone()

            # Get scraping session stats
            cursor = conn.execute('''
                SELECT
                    COUNT(DISTINCT scrape_session_id) as total_sessions,
                    AVG(members_found) as avg_members_per_session,
                    AVG(data_quality_avg) as avg_session_quality,
                    MAX(timestamp) as last_scraped
                FROM scraping_analytics
                WHERE channel_id = ?
            ''', (channel_id,))

            scrape_row = cursor.fetchone()

            return {
                'member_stats': {
                    'total_members': row[0] or 0,
                    'avg_profile_quality': row[1] or 0,
                    'avg_messaging_potential': row[2] or 0,
                    'high_potential_count': row[3] or 0,
                    'avg_threat_score': row[4] or 0,
                    'safe_targets_count': row[5] or 0
                },
                'scraping_stats': {
                    'total_sessions': scrape_row[0] or 0,
                    'avg_members_per_session': scrape_row[1] or 0,
                    'avg_session_quality': scrape_row[2] or 0,
                    'last_scraped': scrape_row[3]
                }
            }

    def store_scraping_analytics(self, channel_id: str, session_id: str,
                                technique: str, members_found: int,
                                avg_quality: float, duration: float):
        """Store scraping session analytics."""
        with self.db.connection() as conn:
            conn.execute('''
                INSERT INTO scraping_analytics
                (channel_id, scrape_session_id, technique_used, members_found,
                 data_quality_avg, duration_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (channel_id, session_id, technique, members_found, avg_quality, duration))


class EliteMemberScraper:
    """Elite member scraper with comprehensive data extraction and zero-risk operation."""

    def __init__(self, db: MemberDatabase, anti_detection: EliteAntiDetectionSystem,
                 data_extractor: ComprehensiveDataExtractor):
        """Initialize the elite member scraper."""
        self.db = db
        self.anti_detection = anti_detection
        self.data_extractor = data_extractor
        self.scraping_active = False
        self.session_pool = {}
        self.results_cache = {}
        self._init_advanced_scraping()

    async def initialize_session_pool(self, account_manager):
        """Initialize the session pool with available accounts."""
        try:
            if not account_manager:
                logger.warning("No account manager provided for session pool initialization")
                return

            # Get available accounts from the account manager
            available_accounts = account_manager.get_account_list() if hasattr(account_manager, 'get_account_list') else []

            for account in available_accounts:
                phone_number = account.get('phone_number')
                if phone_number:
                    # Determine geographic region based on phone number
                    region = self._determine_geographic_region(phone_number)

                    # Get or create client for this account
                    if hasattr(account_manager, 'active_clients') and phone_number in account_manager.active_clients:
                        client = account_manager.active_clients[phone_number]
                        # Get the actual Pyrogram client
                        if hasattr(client, 'client'):
                            actual_client = client.client
                        else:
                            actual_client = client
                    else:
                        # Try to get client directly from account manager
                        actual_client = getattr(account_manager, 'get_client', lambda x: None)(phone_number)

                    if actual_client:
                        self.session_pool[phone_number] = actual_client
                        logger.info(f"Added account {phone_number} to session pool (region: {region})")

            logger.info(f"Session pool initialized with {len(self.session_pool)} accounts")

        except Exception as e:
            logger.error(f"Failed to initialize session pool: {e}")

    def _determine_geographic_region(self, phone_number: str) -> str:
        """Determine geographic region from phone number."""
        phone_str = str(phone_number).replace('+', '')

        # Simple region detection based on country codes
        if phone_str.startswith(('1', '001')):  # US/Canada
            return 'us_east'  # Default to east coast
        elif phone_str.startswith(('44', '0044')):  # UK
            return 'eu_west'
        elif phone_str.startswith(('49', '0049')):  # Germany
            return 'eu_central'
        elif phone_str.startswith(('81', '0081')):  # Japan
            return 'asia_east'
        elif phone_str.startswith(('91', '0091')):  # India
            return 'asia_south'
        elif phone_str.startswith(('7', '007')):  # Russia
            return 'eu_east'
        else:
            return 'us_east'  # Default fallback

    def _init_advanced_scraping(self):
        """Initialize advanced scraping capabilities."""
        self.scraping_techniques = {
            'direct_members': self._scrape_direct_members,
            'message_history': self._scrape_via_message_history,
            'reaction_analysis': self._scrape_via_reactions,
            'poll_participants': self._scrape_via_polls,
            'media_analysis': self._scrape_via_media,
            'forward_analysis': self._scrape_via_forwards,
            'contact_analysis': self._scrape_via_contacts
        }

    async def scrape_channel_comprehensive(self, channel_identifier: str,
                                         techniques: List[str] = None,
                                         max_depth: int = 3) -> Dict[str, Any]:
        """Comprehensive channel scraping using multiple techniques."""

        # Validate inputs
        try:
            from user_helpers import ValidationHelper

            # Validate channel identifier
            if not channel_identifier or not isinstance(channel_identifier, str):
                raise ValueError("Channel identifier is required and must be a string")

            channel_identifier = channel_identifier.strip()
            if not channel_identifier:
                raise ValueError("Channel identifier cannot be empty")

            # Validate max_depth
            if not isinstance(max_depth, int) or max_depth < 1 or max_depth > 10:
                raise ValueError("max_depth must be an integer between 1 and 10")

            # Validate techniques
            if techniques is not None:
                if not isinstance(techniques, list):
                    raise ValueError("techniques must be a list or None")
                valid_techniques = ['direct_members', 'message_history', 'reaction_analysis',
                                  'poll_participants', 'media_shares', 'forward_sources', 'contact_sync']
                for technique in techniques:
                    if technique not in valid_techniques:
                        raise ValueError(f"Invalid technique: {technique}. Valid options: {valid_techniques}")

        except ImportError:
            # Skip validation if ValidationHelper not available
            logger.warning("ValidationHelper not available, skipping input validation")
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            return {'success': False, 'error': f'Invalid input: {e}'}

        if techniques is None:
            techniques = ['direct_members', 'message_history', 'reaction_analysis']

        self.scraping_active = True
        results = {
            'channel_info': {},
            'members_found': {},
            'scraping_stats': {},
            'success': False,
            'error': None
        }

        try:
            # Get channel information safely
            channel_info = await self._get_channel_info_safe(channel_identifier)
            if not channel_info:
                return {'success': False, 'error': 'Cannot access channel'}

            results['channel_info'] = channel_info

            # Execute scraping techniques
            for technique in techniques:
                if not self.scraping_active:
                    break

                if technique in self.scraping_techniques:
                    logger.info(f"🔍 Executing {technique} scraping...")
                    technique_results = await self.scraping_techniques[technique](channel_info, max_depth)
                    results['members_found'][technique] = technique_results

                    # Apply optimal delay based on anti-detection system
                    await self._apply_intelligent_delay()

            # Consolidate and deduplicate results
            all_members = self._consolidate_member_data(results['members_found'])
            results['final_member_count'] = len(all_members)

            # Store comprehensive data
            await self._store_comprehensive_member_data(all_members, channel_info['id'])

            # Calculate statistics
            results['scraping_stats'] = self._calculate_scraping_statistics(results['members_found'])
            results['success'] = True

        except Exception as e:
            logger.error(f"Comprehensive scraping failed: {e}")
            results['error'] = str(e)
        finally:
            self.scraping_active = False

        return results

    async def _get_channel_info_safe(self, channel_identifier: str) -> Optional[Dict]:
        """Get channel information with maximum safety."""
        # Use the healthiest available session
        client = await self._get_optimal_client()
        if not client:
            return None

        start_time = time.time()
        success = False
        error_type = None

        try:
            # Get chat with retry logic
            chat = await client.get_chat(channel_identifier)

            # Validate it's a suitable channel
            if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                return None

            channel_info = {
                'id': chat.id,
                'title': chat.title,
                'type': chat.type.value,
                'member_count': getattr(chat, 'members_count', 0),
                'is_private': not chat.username,
                'username': chat.username,
                'description': getattr(chat, 'description', ''),
                'permissions': getattr(chat, 'permissions', {}),
                'linked_chat_id': getattr(chat, 'linked_chat', None)
            }

            success = True
            return channel_info

        except Exception as e:
            error_type = type(e).__name__
            logger.warning(f"Failed to get channel info: {e}")
            return None

        finally:
            # Record request metrics
            response_time = time.time() - start_time
            account_id = getattr(client, '_account_id', 'unknown')
            self.anti_detection.record_request(
                account_id=account_id,
                request_type='get_channel_info',
                response_time=response_time,
                success=success,
                error_type=error_type
            )

    async def _get_optimal_client(self) -> Optional[Client]:
        """Get the optimal client for scraping operations."""
        # If we have a session pool, use the healthiest account
        if self.session_pool:
            best_account = None
            best_health = AccountHealth.CRITICAL

            for account_id in self.session_pool.keys():
                health = self.anti_detection.get_account_health(account_id)
                if health.value > best_health.value:  # Higher enum value = better health
                    best_health = health
                    best_account = account_id

            if best_account and best_account in self.session_pool:
                return self.session_pool[best_account]

        # Fallback: Use the main client from the base scraper
        if hasattr(self, 'client') and self.client:
            return self.client

        return None

    async def _scrape_direct_members(self, channel_info: Dict, max_depth: int) -> List[Dict]:
        """Scrape members using direct member list access."""
        members = []
        client = await self._get_optimal_client()
        if not client:
            return members

        try:
            # Try different member access methods
            access_methods = [
                (ChatMembersFilter.SEARCH, None),
                (ChatMembersFilter.ADMINISTRATORS, None),
                (ChatMembersFilter.BANNED, None),
                (ChatMembersFilter.RESTRICTED, None)
            ]

            for filter_type, query in access_methods:
                if not self.scraping_active:
                    break

                try:
                    async for member in client.get_chat_members(channel_info['id'], filter=filter_type, query=query):
                        if not self.scraping_active:
                            break

                        # Extract comprehensive data
                        member_data = await self.data_extractor.extract_comprehensive_member_data(
                            client, member.user, channel_info
                        )

                        # Add channel context
                        member_data['channel_id'] = channel_info['id']
                        member_data['member_status'] = member.status.value if hasattr(member.status, 'value') else str(member.status)
                        member_data['joined_date'] = getattr(member, 'joined_date', None)

                        members.append(member_data)

                        # Rate limiting
                        await self._apply_intelligent_delay()

                        if len(members) >= 1000:  # Limit for safety
                            break

                except Exception as e:
                    logger.debug(f"Member access method {filter_type} failed: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Direct member scraping failed: {e}")

        return members

    async def _scrape_via_message_history(self, channel_info: Dict, max_messages: int = 10000) -> List[Dict]:
        """Scrape members by analyzing message history."""
        members = {}
        client = await self._get_optimal_client()
        if not client:
            return []

        try:
            messages_analyzed = 0

            async for message in client.get_chat_history(channel_info['id'], limit=max_messages):
                if not self.scraping_active:
                    break

                # Extract member from message
                if message.from_user and message.from_user.id:
                    user_id = message.from_user.id

                    if user_id not in members:
                        # Extract comprehensive data
                        member_data = await self.data_extractor.extract_comprehensive_member_data(
                            client, message.from_user, channel_info
                        )

                        # Add message context
                        member_data['first_message_date'] = message.date
                        member_data['message_count'] = 0
                        member_data['last_message_date'] = message.date
                        member_data['channel_id'] = channel_info['id']

                        members[user_id] = member_data
                    else:
                        # Update existing member data
                        member = members[user_id]
                        member['message_count'] += 1
                        if message.date > member['last_message_date']:
                            member['last_message_date'] = message.date

                messages_analyzed += 1

                # Rate limiting
                if messages_analyzed % 100 == 0:
                    await self._apply_intelligent_delay()

        except Exception as e:
            logger.warning(f"Message history scraping failed: {e}")

        return list(members.values())

    async def _scrape_via_reactions(self, channel_info: Dict, max_messages: int = 5000) -> List[Dict]:
        """Scrape members who have reacted to messages."""
        members = {}
        client = await self._get_optimal_client()
        if not client:
            return []

        try:
            messages_processed = 0
            async for message in client.get_chat_history(channel_info['id'], limit=max_messages):
                if not self.scraping_active:
                    break

                if hasattr(message, 'reactions') and message.reactions:
                    # Process each reaction type
                    for reaction in message.reactions.reactions:
                        if hasattr(reaction, 'recent_reactions') and reaction.recent_reactions:
                            # Recent reactions include user information
                            for recent_reaction in reaction.recent_reactions:
                                if hasattr(recent_reaction, 'user') and recent_reaction.user:
                                    user = recent_reaction.user
                                    user_id = user.id

                                    if user_id not in members:
                                        # Extract comprehensive data
                                        member_data = await self.data_extractor.extract_comprehensive_member_data(
                                            client, user, channel_info
                                        )
                                        member_data['channel_id'] = channel_info['id']
                                        member_data['discovered_via'] = 'reactions'
                                        member_data['reaction_count'] = 1
                                        members[user_id] = member_data
                                    else:
                                        # Increment reaction count
                                        members[user_id]['reaction_count'] += 1

                messages_processed += 1
                if messages_processed % 50 == 0:
                    await self._apply_intelligent_delay()

        except Exception as e:
            logger.warning(f"Reaction scraping failed: {e}")

        return list(members.values())

    async def _scrape_via_polls(self, channel_info: Dict, max_messages: int = 1000) -> List[Dict]:
        """Scrape members who have voted in polls."""
        members = {}
        client = await self._get_optimal_client()
        if not client:
            return []

        try:
            async for message in client.get_chat_history(channel_info['id'], limit=max_messages):
                if not self.scraping_active:
                    break

                if hasattr(message, 'poll') and message.poll:
                    # Try to get poll voters (requires admin permissions)
                    try:
                        poll_results = await client.get_poll_vote_count(message.id, channel_info['id'])
                        if poll_results and hasattr(poll_results, 'voters'):
                            for voter in poll_results.voters:
                                if hasattr(voter, 'user') and voter.user:
                                    user_id = voter.user.id
                                    if user_id not in members:
                                        member_data = await self.data_extractor.extract_comprehensive_member_data(
                                            client, voter.user, channel_info
                                        )
                                        member_data['channel_id'] = channel_info['id']
                                        member_data['discovered_via'] = 'polls'
                                        member_data['poll_votes'] = 1
                                        members[user_id] = member_data
                                    else:
                                        members[user_id]['poll_votes'] += 1
                    except Exception as e:
                        # Poll voting data might not be accessible
                        logger.debug(f"Could not get poll voters: {e}")

                await self._apply_intelligent_delay()

        except Exception as e:
            logger.warning(f"Poll scraping failed: {e}")

        return list(members.values())

    async def _scrape_via_media(self, channel_info: Dict, max_messages: int = 2000) -> List[Dict]:
        """Scrape members by analyzing media content."""
        members = {}
        client = await self._get_optimal_client()
        if not client:
            return []

        try:
            media_types = {'photo': 0, 'video': 0, 'document': 0, 'audio': 0, 'voice': 0}

            async for message in client.get_chat_history(channel_info['id'], limit=max_messages):
                if not self.scraping_active:
                    break

                # Look for media messages
                if message.photo:
                    media_types['photo'] += 1
                    media_type = 'photo'
                elif message.video:
                    media_types['video'] += 1
                    media_type = 'video'
                elif message.document:
                    media_types['document'] += 1
                    media_type = 'document'
                elif message.audio:
                    media_types['audio'] += 1
                    media_type = 'audio'
                elif hasattr(message, 'voice') and message.voice:
                    media_types['voice'] += 1
                    media_type = 'voice'
                else:
                    continue

                if message.from_user:
                    user_id = message.from_user.id
                    if user_id not in members:
                        member_data = await self.data_extractor.extract_comprehensive_member_data(
                            client, message.from_user, channel_info
                        )
                        member_data['channel_id'] = channel_info['id']
                        member_data['discovered_via'] = 'media'
                        member_data['media_types_shared'] = {media_type: 1}
                        member_data['total_media_shared'] = 1
                        members[user_id] = member_data
                    else:
                        # Update media sharing stats
                        if 'media_types_shared' not in members[user_id]:
                            members[user_id]['media_types_shared'] = {}
                        if media_type not in members[user_id]['media_types_shared']:
                            members[user_id]['media_types_shared'][media_type] = 0
                        members[user_id]['media_types_shared'][media_type] += 1
                        members[user_id]['total_media_shared'] += 1

                await self._apply_intelligent_delay()

        except Exception as e:
            logger.warning(f"Media scraping failed: {e}")

        return list(members.values())

    async def _scrape_via_forwards(self, channel_info: Dict, max_messages: int = 3000) -> List[Dict]:
        """Scrape members by analyzing forwarded messages."""
        members = {}
        client = await self._get_optimal_client()
        if not client:
            return []

        try:
            forward_sources = {}  # Track where forwards come from

            async for message in client.get_chat_history(channel_info['id'], limit=max_messages):
                if not self.scraping_active:
                    break

                # Check for forwarded messages
                if hasattr(message, 'forward_from') and message.forward_from:
                    user_id = message.forward_from.id
                    if user_id not in members:
                        member_data = await self.data_extractor.extract_comprehensive_member_data(
                            client, message.forward_from, channel_info
                        )
                        member_data['channel_id'] = channel_info['id']
                        member_data['discovered_via'] = 'forwards'
                        member_data['forward_count'] = 1
                        member_data['forward_sources'] = [channel_info['id']]  # Simplified
                        members[user_id] = member_data
                    else:
                        members[user_id]['forward_count'] += 1
                        if channel_info['id'] not in members[user_id]['forward_sources']:
                            members[user_id]['forward_sources'].append(channel_info['id'])

                # Also check for forwarded from channels
                elif hasattr(message, 'forward_from_chat') and message.forward_from_chat:
                    # This is forwarded from a channel, could be useful for network analysis
                    forward_chat_id = message.forward_from_chat.id
                    if forward_chat_id not in forward_sources:
                        forward_sources[forward_chat_id] = {
                            'title': getattr(message.forward_from_chat, 'title', 'Unknown'),
                            'count': 1
                        }
                    else:
                        forward_sources[forward_chat_id]['count'] += 1

                await self._apply_intelligent_delay()

        except Exception as e:
            logger.warning(f"Forward analysis scraping failed: {e}")

        return list(members.values())

    async def _scrape_via_contacts(self, channel_info: Dict, max_messages: int = 1000) -> List[Dict]:
        """Scrape members by analyzing shared contacts and mentions."""
        members = {}
        client = await self._get_optimal_client()
        if not client:
            return []

        try:
            async for message in client.get_chat_history(channel_info['id'], limit=max_messages):
                if not self.scraping_active:
                    break

                # Check for contact shares
                if hasattr(message, 'contact') and message.contact:
                    # Shared contact reveals another member
                    if hasattr(message.contact, 'user_id') and message.contact.user_id:
                        contact_user_id = message.contact.user_id
                        if contact_user_id not in members:
                            # Create a minimal user object from contact info
                            fake_user = type('User', (), {
                                'id': contact_user_id,
                                'first_name': getattr(message.contact, 'first_name', ''),
                                'last_name': getattr(message.contact, 'last_name', ''),
                                'username': getattr(message.contact, 'username', None),
                                'phone_number': getattr(message.contact, 'phone_number', None)
                            })()

                            member_data = await self.data_extractor.extract_comprehensive_member_data(
                                client, fake_user, channel_info
                            )
                            member_data['channel_id'] = channel_info['id']
                            member_data['discovered_via'] = 'contacts'
                            member_data['contact_shared'] = True
                            members[contact_user_id] = member_data

                # Check for user mentions in text
                if hasattr(message, 'text') and message.text:
                    # Extract mentioned usernames
                    import re
                    mentions = re.findall(r'@(\w+)', message.text)
                    for username in mentions:
                        # Note: This doesn't give us user IDs directly
                        # Would need additional API calls to resolve usernames
                        pass

                await self._apply_intelligent_delay()

        except Exception as e:
            logger.warning(f"Contact analysis scraping failed: {e}")

        return list(members.values())

    async def _apply_intelligent_delay(self):
        """Apply intelligent delay based on anti-detection system."""
        # Get optimal delay for current account
        account_id = 'default'  # Would be set properly in real implementation
        delay = self.anti_detection.get_optimal_delay(account_id)

        # Add randomization
        actual_delay = delay * random.uniform(0.8, 1.2)

        await asyncio.sleep(actual_delay)

    def _consolidate_member_data(self, technique_results: Dict) -> List[Dict]:
        """Consolidate and deduplicate member data from all techniques."""
        all_members = {}
        technique_stats = {}

        for technique, members in technique_results.items():
            technique_stats[technique] = len(members)

            for member in members:
                user_id = member['user_id']

                if user_id not in all_members:
                    # First time seeing this member
                    all_members[user_id] = member
                    all_members[user_id]['discovery_techniques'] = [technique]
                else:
                    # Merge data from multiple techniques
                    existing = all_members[user_id]

                    # Merge discovery techniques
                    if technique not in existing['discovery_techniques']:
                        existing['discovery_techniques'].append(technique)

                    # Merge message counts
                    if 'message_count' in member and 'message_count' in existing:
                        existing['message_count'] = max(existing['message_count'], member['message_count'])

                    # Take earliest first message date
                    if 'first_message_date' in member and 'first_message_date' in existing:
                        if member['first_message_date'] < existing['first_message_date']:
                            existing['first_message_date'] = member['first_message_date']

                    # Take latest last message date
                    if 'last_message_date' in member and 'last_message_date' in existing:
                        if member['last_message_date'] > existing['last_message_date']:
                            existing['last_message_date'] = member['last_message_date']

        logger.info(f"Consolidated {len(all_members)} unique members from {len(technique_results)} techniques")
        return list(all_members.values())

    async def _store_comprehensive_member_data(self, members: List[Dict], channel_id: int):
        """Store comprehensive member data with advanced analysis using the data access layer."""
        data_layer = EliteDataAccessLayer(self.db)

        for member in members:
            try:
                # Store basic member info
                self.db.save_member(
                    user_id=member['user_id'],
                    username=member.get('username'),
                    first_name=member.get('first_name'),
                    last_name=member.get('last_name'),
                    phone=getattr(member, 'phone_number', None),
                    joined_at=member.get('joined_date'),
                    last_seen=member.get('last_online_date'),
                    status=member.get('member_status', 'member'),
                    channel_id=str(channel_id),
                    activity_score=member.get('activity_score', 0),
                    threat_score=member.get('risk_assessment', {}).get('overall_risk_score', 0) * 100,
                    is_safe_target=member.get('risk_assessment', {}).get('overall_risk_score', 0) < 0.5,
                    threat_reasons=json.dumps(member.get('risk_assessment', {}).get('risk_factors', [])),
                    message_count=member.get('message_count', 0),
                    last_message_date=member.get('last_message_date')
                )

                # Store comprehensive profile data
                data_layer.store_comprehensive_profile(member['user_id'], member)

                # Store activity patterns if available
                activity_patterns = member.get('activity_patterns', {})
                if activity_patterns:
                    data_layer.store_activity_patterns(member['user_id'], activity_patterns)

                # Store network connections if available
                network_data = member.get('network_analysis', {})
                if network_data.get('group_memberships'):
                    connections = []
                    for group in network_data['group_memberships']:
                        connections.append({
                            'type': 'group_membership',
                            'connected_user_id': None,  # Group, not user
                            'strength': 0.8,
                            'metadata': {'group_info': group}
                        })
                    data_layer.store_network_connections(member['user_id'], connections)

                # Store behavioral insights
                behavioral_data = member.get('behavioral_insights', {})
                if behavioral_data:
                    data_layer.store_behavioral_insights(member['user_id'], behavioral_data)

                logger.debug(f"Stored comprehensive data for member {member['user_id']}")

            except Exception as e:
                logger.error(f"Failed to store comprehensive data for member {member['user_id']}: {e}")

    def _calculate_scraping_statistics(self, technique_results: Dict) -> Dict:
        """Calculate comprehensive scraping statistics."""
        stats = {
            'techniques_used': len(technique_results),
            'total_members_found': 0,
            'technique_breakdown': {},
            'average_data_completeness': 0.0,
            'unique_members': 0
        }

        all_members = []
        for technique, members in technique_results.items():
            stats['technique_breakdown'][technique] = len(members)
            stats['total_members_found'] += len(members)
            all_members.extend(members)

        # Calculate unique members
        unique_ids = set(member['user_id'] for member in all_members)
        stats['unique_members'] = len(unique_ids)

        # Calculate average data completeness
        completeness_scores = [member.get('data_completeness_score', 0) for member in all_members]
        if completeness_scores:
            stats['average_data_completeness'] = sum(completeness_scores) / len(completeness_scores)

        return stats

    def stop_scraping(self):
        """Stop all scraping operations."""
        self.scraping_active = False
        logger.info("Elite member scraping stopped")


class MemberScraper:
    """Advanced Telegram member scraper with comprehensive threat detection and elite anti-detection."""

    def __init__(self, client: Client, db: MemberDatabase, anti_detection: EliteAntiDetectionSystem = None,
                 threat_config: Optional[Dict[str, Any]] = None):
        """Initialize the member scraper.

        Args:
            client: Pyrogram client instance
            db: Member database instance
            anti_detection: Elite anti-detection system (optional)
        """
        self.client = self._resolve_pyrogram_client(client)
        self.db = db
        self.scraping_active = False
        self.threat_detector = ThreatDetector(threat_config)
        self.scraped_user_ids = set()  # Track already scraped users

        # Elite systems integration
        self.anti_detection = anti_detection or EliteAntiDetectionSystem()
        self.data_extractor = ComprehensiveDataExtractor()
        self.elite_scraper = EliteMemberScraper(db, self.anti_detection, self.data_extractor)

    @staticmethod
    def _resolve_pyrogram_client(client):
        """Ensure we have a raw Pyrogram Client instance."""
        if client is None:
            raise ValueError("MemberScraper requires a valid Pyrogram client.")

        if hasattr(client, "get_client"):
            resolved = client.get_client()
            if resolved:
                client = resolved

        required_methods = ("get_chat", "get_chat_members", "get_chat_history")
        for method in required_methods:
            if not hasattr(client, method):
                raise ValueError("MemberScraper requires a Pyrogram Client instance.")

        return client

    def parse_channel_url(self, url: str) -> Optional[str]:
        """Parse Telegram channel/group URL to get channel identifier.

        Args:
            url: Telegram URL (e.g., https://t.me/channelname, @channelname, channelname)

        Returns:
            Channel identifier or None if invalid
        """
        # Handle various URL formats
        patterns = [
            r'https?://t\.me/([a-zA-Z0-9_]+)',  # https://t.me/channel
            r'@([a-zA-Z0-9_]+)',                # @channel
            r'^([a-zA-Z0-9_]+)$'                # channel
        ]

        for pattern in patterns:
            match = re.search(pattern, url.strip())
            if match:
                return match.group(1)

        return None

    async def scrape_channel_members(self, channel_identifier: str, progress_callback=None,
                                    analyze_messages: bool = True, max_messages: int = 10000,
                                    use_elite_scraping: bool = False) -> Dict:
        """Advanced scraping of ALL members from a channel/group, including hidden ones.

        Uses multiple techniques:
        1. Direct member list (if accessible)
        2. Message history analysis (finds all users who posted)
        3. Reaction analysis (finds users who reacted)
        4. Admin/mod detection
        5. Threat scoring and filtering

        Args:
            channel_identifier: Channel username/ID
            progress_callback: Optional callback for progress updates
            analyze_messages: Whether to analyze message history to find hidden members
            max_messages: Maximum messages to analyze (for performance)
            use_elite_scraping: Whether to use elite comprehensive scraping with zero-risk guarantees

        Returns:
            Dict with scraping results
        """
        # Use elite scraping if requested
        if use_elite_scraping:
            return await self.elite_scraper.scrape_channel_comprehensive(
                channel_identifier,
                techniques=['direct_members', 'message_history', 'reaction_analysis', 'media_analysis'] if analyze_messages else ['direct_members'],
                max_depth=3
            )

        try:
            self.scraping_active = True
            self.scraped_user_ids.clear()
            members_scraped = 0
            message_analysis = {}
            admins_found = set()

            # Get chat information with retry logic
            chat = None
            for attempt in range(3):
                try:
                    chat = await self.client.get_chat(channel_identifier)
                    break
                except (ConnectionError, asyncio.TimeoutError) as e:
                    if attempt < 2:
                        logger.warning(f"Failed to get chat info (attempt {attempt + 1}): {e}, retrying...")
                        await asyncio.sleep((2 ** attempt) * random.uniform(1, 3))
                    else:
                        return {'success': False, 'error': f'Cannot access channel after retries: {e}'}
                except Exception as e:
                    return {'success': False, 'error': f'Cannot access channel: {e}'}

            # Check if we can get members
            if chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                return {'success': False, 'error': 'Not a group or channel'}

            # Save channel info
            is_private = chat.has_protected_content or not chat.username
            self.db.save_channel(str(chat.id), chat.title or "Unknown", 0, is_private)

            members_scraped = 0
            admins_found = set()
            message_analysis = {}  # user_id -> {count, last_date}
            
            # METHOD 1: Get administrators (always filter these out)
            logger.info("🔍 Method 1: Scraping administrators...")
            try:
                async for member in self.client.get_chat_members(chat.id, filter=ChatMembersFilter.ADMINISTRATORS):
                    if not self.scraping_active:
                        break
                    admins_found.add(member.user.id)
                    await self._process_member(member, chat.id, is_admin=True, is_owner=(member.status == ChatMemberStatus.OWNER))
                    members_scraped += 1
                    await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Could not get administrators: {e}")

            # METHOD 2: Get all visible members
            logger.info("🔍 Method 2: Scraping visible members...")
            try:
                async for member in self.client.get_chat_members(chat.id, filter=ChatMembersFilter.SEARCH):
                    if not self.scraping_active:
                        break
                    if member.user.id not in self.scraped_user_ids:
                        is_admin = member.user.id in admins_found or member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
                        await self._process_member(member, chat.id, is_admin=is_admin, 
                                                  is_owner=(member.status == ChatMemberStatus.OWNER))
                        members_scraped += 1
                        if progress_callback and members_scraped % 10 == 0:
                            progress_callback(members_scraped)
                        await asyncio.sleep(0.1)
            except Exception as e:
                logger.warning(f"Member list access limited: {e}")

            # METHOD 3: Analyze message history to find ALL users who posted (including hidden members)
            if analyze_messages:
                logger.info("🔍 Method 3: Analyzing message history to find hidden members...")
                try:
                    message_count = 0
                    async for message in self.client.get_chat_history(chat.id, limit=max_messages):
                        if not self.scraping_active:
                            break
                        
                        if message.from_user and message.from_user.id:
                            user_id = message.from_user.id
                            
                            # Track message activity
                            if user_id not in message_analysis:
                                message_analysis[user_id] = {
                                    'count': 0,
                                    'last_date': message.date,
                                    'user': message.from_user
                                }
                            message_analysis[user_id]['count'] += 1
                            if message.date > message_analysis[user_id]['last_date']:
                                message_analysis[user_id]['last_date'] = message.date
                            
                            # If we haven't seen this user yet, add them
                            if user_id not in self.scraped_user_ids:
                                # Create a ChatMember-like object from User
                                fake_member = type('ChatMember', (), {
                                    'user': message.from_user,
                                    'status': ChatMemberStatus.MEMBER
                                })()
                                
                                is_admin = user_id in admins_found
                                await self._process_member(fake_member, chat.id, is_admin=is_admin,
                                                          message_count=message_analysis[user_id]['count'],
                                                          last_message_date=message_analysis[user_id]['last_date'])
                                members_scraped += 1
                                if progress_callback and members_scraped % 10 == 0:
                                    progress_callback(members_scraped)
                        
                        message_count += 1
                        if message_count % 100 == 0:
                            await asyncio.sleep(0.2)  # Rate limiting for message fetching
                        else:
                            await asyncio.sleep(0.05)
                            
                except Exception as e:
                    logger.warning(f"Message history analysis limited: {e}")

            # METHOD 4: Update message counts and threat scores for all found members
            logger.info("🔍 Method 4: Updating threat scores and filtering...")
            await self._update_threat_scores(chat.id, message_analysis, admins_found)

            # Update member count
            stats = self.db.get_channel_stats(str(chat.id))
            self.db.save_channel(str(chat.id), chat.title or "Unknown", stats['total_members'], is_private)

            # Get final stats
            safe_targets = self.db.get_safe_targets(str(chat.id))
            threats_filtered = stats['total_members'] - len(safe_targets)

            return {
                'success': True,
                'channel_id': str(chat.id),
                'channel_title': chat.title,
                'members_scraped': members_scraped,
                'safe_targets': len(safe_targets),
                'threats_filtered': threats_filtered,
                'is_private': is_private
            }

        except Exception as e:
            logger.error(f"Error scraping channel {channel_identifier}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            partial = {
                'success': False,
                'error': str(e),
                'members_scraped': locals().get('members_scraped', 0),
                'channel_id': str(chat.id) if 'chat' in locals() and chat else None,
                'partial_results': {
                    'admins_found': list(locals().get('admins_found', [])),
                    'message_analysis_sample': list(locals().get('message_analysis', {}).items())[:10],
                },
            }
            return partial
        finally:
            self.scraping_active = False

    async def _process_member(self, member: ChatMember, channel_id: str, is_admin: bool = False,
                             is_owner: bool = False, message_count: int = 0, last_message_date: datetime = None):
        """Process and save a member with threat detection."""
        user_id = member.user.id
        
        # Skip if already processed
        if user_id in self.scraped_user_ids:
            return
        
        self.scraped_user_ids.add(user_id)
        
        # Calculate activity score
        activity_score = self._calculate_activity_score(member, message_count)
        
        # Calculate threat score
        last_message_days = None
        if last_message_date:
            last_message_days = (datetime.now() - last_message_date).days
        
        threat_score, threat_reasons = self.threat_detector.calculate_threat_score(
            member, message_count, is_admin, False, is_owner, last_message_days
        )
        
        # Determine if safe target
        is_safe = self.threat_detector.is_safe_target(threat_score, threat_reasons)
        
        # Save member
        joined_at = datetime.now()  # Approximation
        last_seen = self._estimate_last_seen(member, last_message_date)
        
        self.db.save_member(
            user_id=user_id,
            username=member.user.username,
            first_name=member.user.first_name,
            last_name=member.user.last_name,
            phone=getattr(member.user, 'phone', None),
            joined_at=joined_at,
            last_seen=last_seen,
            status=member.status.value if hasattr(member.status, 'value') else str(member.status),
            channel_id=str(channel_id),
            activity_score=activity_score,
            threat_score=threat_score,
            is_admin=is_admin,
            is_moderator=False,  # Will be updated if detected
            is_owner=is_owner,
            message_count=message_count,
            last_message_date=last_message_date,
            is_safe_target=is_safe,
            threat_reasons=', '.join(threat_reasons) if threat_reasons else None
        )
    
    async def _update_threat_scores(self, channel_id: str, message_analysis: Dict, admins_found: set):
        """Update threat scores for all members based on message analysis."""
        # Get all members for this channel
        all_members = self.db.get_all_members(str(channel_id))
        
        for member_data in all_members:
            user_id = member_data['user_id']
            
            # Update message count if we have data
            if user_id in message_analysis:
                msg_data = message_analysis[user_id]
                message_count = msg_data['count']
                last_message_date = msg_data['last_date']
                
                # Recalculate threat score with updated message data
                # We need to reconstruct member status
                is_admin = member_data.get('is_admin', False) or user_id in admins_found
                is_owner = member_data.get('is_owner', False)
                
                last_message_days = (datetime.now() - last_message_date).days if last_message_date else None
                
                # Create a minimal member object for threat calculation
                fake_member = type('ChatMember', (), {
                    'user': type('User', (), {
                        'id': user_id,
                        'username': member_data.get('username'),
                        'first_name': member_data.get('first_name'),
                        'last_name': member_data.get('last_name'),
                        'is_verified': False,
                        'is_premium': False,
                        'photo': None
                    })(),
                    'status': ChatMemberStatus.ADMINISTRATOR if is_admin else ChatMemberStatus.MEMBER
                })()
                
                threat_score, threat_reasons = self.threat_detector.calculate_threat_score(
                    fake_member, message_count, is_admin, False, is_owner, last_message_days
                )
                
                is_safe = self.threat_detector.is_safe_target(threat_score, threat_reasons)
                
                # Update member with new threat data
                self.db.save_member(
                    user_id=user_id,
                    username=member_data.get('username'),
                    first_name=member_data.get('first_name'),
                    last_name=member_data.get('last_name'),
                    phone=member_data.get('phone'),
                    joined_at=member_data.get('joined_at'),
                    last_seen=member_data.get('last_seen'),
                    status=member_data.get('status'),
                    channel_id=str(channel_id),
                    activity_score=member_data.get('activity_score', 0),
                    threat_score=threat_score,
                    is_admin=is_admin,
                    is_moderator=member_data.get('is_moderator', False),
                    is_owner=is_owner,
                    message_count=message_count,
                    last_message_date=last_message_date,
                    is_safe_target=is_safe,
                    threat_reasons=', '.join(threat_reasons) if threat_reasons else None
                )

    def _calculate_activity_score(self, member: ChatMember, message_count: int = 0) -> int:
        """Calculate activity score for a member."""
        score = 0

        # Base score by status
        if member.status == ChatMemberStatus.OWNER:
            score += 100
        elif member.status == ChatMemberStatus.ADMINISTRATOR:
            score += 50
        elif member.status == ChatMemberStatus.MEMBER:
            score += 10

        # Bonus for message activity
        if message_count > 0:
            score += min(message_count, 50)  # Cap at 50

        # Bonus for username (more likely to be active)
        if member.user.username:
            score += 5

        # Bonus for profile completeness
        if member.user.first_name:
            score += 2
        if member.user.last_name:
            score += 1

        return score

    def _estimate_last_seen(self, member: ChatMember, last_message_date: datetime = None) -> datetime:
        """Estimate when member was last seen."""
        if last_message_date:
            return last_message_date
        
        # This is an approximation - Telegram doesn't provide exact last seen
        base_time = datetime.now()

        # Administrators and owners are likely more active
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
            return base_time - timedelta(hours=1)
        elif member.status == ChatMemberStatus.MEMBER:
            return base_time - timedelta(days=1)
        else:
            return base_time - timedelta(days=7)

    def stop_scraping(self):
        """Stop the scraping process."""
        self.scraping_active = False

    def get_safe_targets(self, channel_id: str, limit: int = None) -> List[Dict]:
        """Get safe members for messaging (threats filtered out).

        Args:
            channel_id: Channel identifier
            limit: Maximum number of members to return

        Returns:
            List of safe member dictionaries
        """
        return self.db.get_safe_targets(channel_id, limit)

    def get_member_targets(self, channel_id: str, min_activity: int = 0, limit: int = None, 
                          only_safe: bool = True) -> List[Dict]:
        """Get members suitable for messaging based on activity criteria.

        Args:
            channel_id: Channel identifier
            min_activity: Minimum activity score
            limit: Maximum number of members to return
            only_safe: Only return safe targets (threats filtered out)

        Returns:
            List of member dictionaries
        """
        if only_safe:
            members = self.get_safe_targets(channel_id, limit)
        else:
            members = self.db.get_members_by_activity(channel_id, limit)

        # Filter by minimum activity
        if min_activity > 0:
            members = [m for m in members if m.get('activity_score', 0) >= min_activity]

        return members


