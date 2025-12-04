"""
Enhanced Anti-Detection System for Telegram Bot Operations.

Features:
- Telegram-specific fingerprinting (TDesktop vs Android vs iOS)
- Session rotation strategy
- Message pattern analysis
- Real-time ban probability calculator
- Automatic account quarantine
- Time-zone aware activity simulation
- Message diversity scoring
"""

import asyncio
import logging
import random
import time
import hashlib
import platform
import psutil
import subprocess
import threading
import sqlite3
import json
import re
from typing import Dict, List, Optional, Any, Tuple, Set, Callable
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import os
import sys
import statistics

logger = logging.getLogger(__name__)


class TelegramClientType(Enum):
    """Telegram client types with distinct fingerprints."""
    TDESKTOP = "tdesktop"
    ANDROID = "android"
    IOS = "ios"
    WEB = "web"
    MACOS = "macos"
    
    
class BanRiskLevel(Enum):
    """Account ban risk levels."""
    SAFE = "safe"              # < 10%
    LOW = "low"                # 10-30%
    MODERATE = "moderate"      # 30-50%
    HIGH = "high"              # 50-70%
    CRITICAL = "critical"      # > 70%
    QUARANTINED = "quarantined"


class QuarantineReason(Enum):
    """Reasons for account quarantine."""
    HIGH_BAN_RISK = "high_ban_risk"
    FLOOD_WAIT = "flood_wait"
    REPEATED_ERRORS = "repeated_errors"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    PATTERN_DETECTED = "pattern_detected"
    MANUAL = "manual"


@dataclass
class TelegramFingerprint:
    """Telegram client fingerprint for device simulation."""
    client_type: TelegramClientType
    device_model: str
    system_version: str
    app_version: str
    lang_code: str
    system_lang_code: str
    layer: int
    api_id: int = 0
    
    # Additional device-specific attributes
    brand: str = ""
    manufacturer: str = ""
    screen_resolution: str = ""
    timezone_offset: int = 0
    
    # Session attributes
    created_at: datetime = field(default_factory=datetime.now)
    last_rotated: datetime = field(default_factory=datetime.now)
    rotation_count: int = 0
    
    def to_pyrogram_config(self) -> Dict:
        """Convert to Pyrogram client configuration."""
        return {
            "device_model": self.device_model,
            "system_version": self.system_version,
            "app_version": self.app_version,
            "lang_code": self.lang_code,
            "system_lang_code": self.system_lang_code
        }
    
    def should_rotate(self, max_days: int = 14) -> bool:
        """Check if fingerprint should be rotated."""
        days_since_rotation = (datetime.now() - self.last_rotated).days
        return days_since_rotation >= max_days


@dataclass
class AccountRiskMetrics:
    """Risk metrics for an account."""
    account_id: str
    ban_probability: float = 0.0
    risk_level: BanRiskLevel = BanRiskLevel.SAFE
    
    # Behavioral metrics
    messages_sent_24h: int = 0
    messages_sent_1h: int = 0
    unique_recipients_24h: int = 0
    error_count_24h: int = 0
    flood_wait_count_24h: int = 0
    
    # Pattern metrics
    message_diversity_score: float = 1.0
    response_pattern_score: float = 1.0
    timing_pattern_score: float = 1.0
    
    # Status
    is_quarantined: bool = False
    quarantine_reason: Optional[QuarantineReason] = None
    quarantine_until: Optional[datetime] = None
    
    # History
    last_activity: Optional[datetime] = None
    last_error: Optional[str] = None
    last_risk_calculation: Optional[datetime] = None
    
    def calculate_ban_probability(self) -> float:
        """Calculate overall ban probability."""
        # Base probability
        prob = 0.0
        
        # Message volume factors
        if self.messages_sent_1h > 50:
            prob += 0.3
        elif self.messages_sent_1h > 30:
            prob += 0.15
        elif self.messages_sent_1h > 20:
            prob += 0.05
        
        if self.messages_sent_24h > 500:
            prob += 0.3
        elif self.messages_sent_24h > 200:
            prob += 0.15
        elif self.messages_sent_24h > 100:
            prob += 0.05
        
        # Diversity factor (low diversity = high risk)
        prob += (1.0 - self.message_diversity_score) * 0.2
        
        # Error factors
        error_rate = self.error_count_24h / max(1, self.messages_sent_24h)
        if error_rate > 0.1:
            prob += 0.2
        elif error_rate > 0.05:
            prob += 0.1
        
        # Flood wait is a strong indicator
        if self.flood_wait_count_24h > 5:
            prob += 0.3
        elif self.flood_wait_count_24h > 2:
            prob += 0.15
        elif self.flood_wait_count_24h > 0:
            prob += 0.05
        
        # Recipient diversity
        if self.unique_recipients_24h > 0:
            recipient_rate = self.messages_sent_24h / self.unique_recipients_24h
            if recipient_rate > 10:  # Spamming same people
                prob += 0.1
        
        # Pattern scores
        prob += (1.0 - self.response_pattern_score) * 0.1
        prob += (1.0 - self.timing_pattern_score) * 0.1
        
        self.ban_probability = min(1.0, max(0.0, prob))
        self._update_risk_level()
        return self.ban_probability
    
    def _update_risk_level(self):
        """Update risk level based on ban probability."""
        if self.is_quarantined:
            self.risk_level = BanRiskLevel.QUARANTINED
        elif self.ban_probability >= 0.7:
            self.risk_level = BanRiskLevel.CRITICAL
        elif self.ban_probability >= 0.5:
            self.risk_level = BanRiskLevel.HIGH
        elif self.ban_probability >= 0.3:
            self.risk_level = BanRiskLevel.MODERATE
        elif self.ban_probability >= 0.1:
            self.risk_level = BanRiskLevel.LOW
        else:
            self.risk_level = BanRiskLevel.SAFE


class SystemFingerprintMasker:
    """Mask system fingerprints to avoid detection."""

    def __init__(self):
        self.original_specs = self._capture_system_specs()

    def _capture_system_specs(self) -> Dict:
        """Capture original system specifications."""
        return {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "architecture": platform.architecture(),
            "python_version": sys.version,
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "disk_usage": psutil.disk_usage('/').total,
            "hostname": platform.node(),
            "mac_address": self._get_mac_address(),
            "timezone": time.tzname,
        }

    def _get_mac_address(self) -> str:
        """Get primary MAC address."""
        try:
            import uuid
            return ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                           for elements in range(0, 8*6, 8)][::-1])
        except (OSError, ValueError):
            return "00:00:00:00:00:00"

    def apply_system_masking(self):
        """Apply system-level masking techniques."""
        try:
            # Modify process name (limited effectiveness on some systems)
            self._modify_process_name()

            # Randomize system-reported values where possible
            self._randomize_system_values()

            # Modify environment variables
            self._modify_environment()

            logger.info("System fingerprint masking applied")

        except Exception as e:
            logger.warning(f"System masking partially failed: {e}")

    def _modify_process_name(self):
        """Attempt to modify process name."""
        try:
            import ctypes
            if platform.system() == "Linux":
                # Try to set process name
                libc = ctypes.CDLL('libc.so.6')
                libc.prctl(15, ctypes.c_char_p(b"Telegram"), 0, 0, 0)
            elif platform.system() == "Windows":
                # Windows process name modification is limited
                pass
        except (OSError, AttributeError, ctypes.ArgumentError):
            pass

    def _randomize_system_values(self):
        """Randomize detectable system values."""
        # Modify environment variables that might be checked
        os.environ["LANG"] = random.choice([
            "en_US.UTF-8", "en_GB.UTF-8", "en_CA.UTF-8",
            "es_ES.UTF-8", "fr_FR.UTF-8", "de_DE.UTF-8"
        ])

        # Randomize some Python environment variables
        if random.random() < 0.3:
            os.environ["PYTHONPATH"] = "/usr/lib/python3/dist-packages"

    def _modify_environment(self):
        """Modify environment to appear more natural."""
        # Remove suspicious environment variables
        suspicious_vars = [
            "LD_PRELOAD", "LD_LIBRARY_PATH", "_MEIPASS", "PYINSTALLER_LAUNCHER"
        ]

        for var in suspicious_vars:
            if var in os.environ:
                del os.environ[var]

        # Add common user environment variables
        if "HOME" not in os.environ:
            os.environ["HOME"] = os.path.expanduser("~")

        if "USER" not in os.environ:
            os.environ["USER"] = os.path.basename(os.path.expanduser("~"))


class NetworkAnomalyDetector:
    """Detect and avoid network-based detection."""

    def __init__(self):
        self.connection_history = []
        self.suspicious_patterns = []
        self.last_connection_time = 0
        self.connection_count = 0

    def monitor_connection(self, connection_info: Dict):
        """Monitor connection patterns for anomalies."""
        current_time = time.time()

        # Track connection frequency
        if self.last_connection_time > 0:
            interval = current_time - self.last_connection_time
            if interval < 1.0:  # Connections too frequent
                self.suspicious_patterns.append({
                    "type": "rapid_connections",
                    "interval": interval,
                    "timestamp": current_time
                })

        self.connection_history.append({
            "timestamp": current_time,
            "info": connection_info
        })

        # Keep only recent history
        cutoff_time = current_time - 3600  # 1 hour
        self.connection_history = [
            conn for conn in self.connection_history
            if conn["timestamp"] > cutoff_time
        ]

        self.last_connection_time = current_time
        self.connection_count += 1

    def should_delay_connection(self) -> float:
        """Determine if connection should be delayed to avoid detection."""
        if len(self.connection_history) < 5:
            return 0.0

        # Check for suspicious patterns
        recent_suspicious = [
            p for p in self.suspicious_patterns
            if time.time() - p["timestamp"] < 300  # Last 5 minutes
        ]

        if recent_suspicious:
            # Exponential backoff
            delay = min(30.0, 2 ** len(recent_suspicious))
            return delay

        return 0.0

    def get_safe_connection_interval(self) -> float:
        """Calculate safe connection interval based on history."""
        if len(self.connection_history) < 10:
            return random.uniform(1.0, 3.0)

        # Analyze connection patterns
        intervals = []
        for i in range(1, len(self.connection_history)):
            interval = (self.connection_history[i]["timestamp"] -
                       self.connection_history[i-1]["timestamp"])
            intervals.append(interval)

        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            # Add some randomization but stay close to average
            return random.uniform(avg_interval * 0.8, avg_interval * 1.2)

        return random.uniform(2.0, 5.0)


class BehavioralPatternSimulator:
    """Simulate human behavioral patterns."""

    def __init__(self):
        self.user_patterns = {
            "message_timing": self._generate_message_timing_pattern(),
            "response_delays": self._generate_response_delay_pattern(),
            "activity_cycles": self._generate_activity_cycles(),
            "typing_patterns": self._generate_typing_patterns()
        }

    def _generate_message_timing_pattern(self) -> List[float]:
        """Generate realistic message timing patterns."""
        # Human messaging follows circadian rhythms
        pattern = []

        for hour in range(24):
            if 9 <= hour <= 17:  # Work hours
                base_activity = random.uniform(0.6, 0.9)
            elif 18 <= hour <= 22:  # Evening
                base_activity = random.uniform(0.7, 1.0)
            elif 23 <= hour or hour <= 2:  # Late night
                base_activity = random.uniform(0.2, 0.5)
            elif 3 <= hour <= 8:  # Early morning
                base_activity = random.uniform(0.1, 0.3)
            else:  # Other times
                base_activity = random.uniform(0.3, 0.6)

            # Add random variation
            activity = base_activity * random.uniform(0.7, 1.3)
            pattern.append(max(0.0, min(1.0, activity)))

        return pattern

    def _generate_response_delay_pattern(self) -> Dict:
        """Generate realistic response delay patterns."""
        return {
            "immediate": {"probability": 0.1, "delay_range": (1, 5)},      # 10% immediate
            "quick": {"probability": 0.3, "delay_range": (10, 60)},        # 30% quick
            "normal": {"probability": 0.4, "delay_range": (60, 300)},      # 40% normal
            "slow": {"probability": 0.15, "delay_range": (300, 900)},     # 15% slow
            "very_slow": {"probability": 0.05, "delay_range": (900, 3600)} # 5% very slow
        }

    def _generate_activity_cycles(self) -> Dict:
        """Generate activity cycles (work, sleep, etc.)."""
        return {
            "work_hours": {"start": 9, "end": 17, "activity_multiplier": 1.2},
            "evening": {"start": 18, "end": 22, "activity_multiplier": 1.0},
            "night": {"start": 23, "end": 6, "activity_multiplier": 0.3},
            "weekends": {"activity_multiplier": 0.8}
        }

    def _generate_typing_patterns(self) -> Dict:
        """Generate realistic typing patterns."""
        return {
            "wpm_range": (40, 80),  # Words per minute
            "error_rate": 0.02,     # 2% chance of typos
            "pause_frequency": 0.1, # 10% chance of thinking pauses
            "correction_rate": 0.05 # 5% chance of corrections
        }

    def get_current_activity_level(self) -> float:
        """Get current activity level based on time."""
        current_hour = datetime.now().hour
        current_day = datetime.now().weekday()

        # Base activity from time pattern
        base_activity = self.user_patterns["message_timing"][current_hour]

        # Apply day modifiers
        if current_day >= 5:  # Weekend
            base_activity *= self.user_patterns["activity_cycles"]["weekends"]["activity_multiplier"]

        # Apply current period modifiers
        for period, config in self.user_patterns["activity_cycles"].items():
            if isinstance(config, dict) and "start" in config:
                if config["start"] <= current_hour < config["end"]:
                    base_activity *= config["activity_multiplier"]
                    break

        return max(0.0, min(1.0, base_activity))

    def get_realistic_response_delay(self, message_urgency: float = 0.5) -> float:
        """Get realistic response delay based on message urgency."""
        patterns = self.user_patterns["response_delays"]

        # Adjust probabilities based on urgency
        if message_urgency > 0.8:  # Very urgent
            patterns["immediate"]["probability"] = 0.4
            patterns["quick"]["probability"] = 0.4
        elif message_urgency < 0.2:  # Not urgent
            patterns["very_slow"]["probability"] = 0.2
            patterns["slow"]["probability"] = 0.3
        
        # Select delay pattern
        rand = random.random()
        cumulative_prob = 0.0

        for pattern_name, pattern_data in patterns.items():
            cumulative_prob += pattern_data["probability"]
            if rand <= cumulative_prob:
                delay_min, delay_max = pattern_data["delay_range"]
                return random.uniform(delay_min, delay_max)

        # Fallback
        return random.uniform(30, 120)

    def simulate_human_error(self, text: str) -> str:
        """Occasionally introduce human-like errors."""
        if random.random() > self.user_patterns["typing_patterns"]["error_rate"]:
            return text

        # Simulate a typo
        words = text.split()
        if len(words) < 2:
            return text

        # Pick a random word to modify
        word_idx = random.randint(0, len(words) - 1)
        word = words[word_idx]

        if len(word) < 3:
            return text

        # Simple typo: swap two adjacent characters
        char_idx = random.randint(0, len(word) - 2)
        word_list = list(word)
        word_list[char_idx], word_list[char_idx + 1] = word_list[char_idx + 1], word_list[char_idx]
        words[word_idx] = ''.join(word_list)

        return ' '.join(words)


class AntiDetectionSystem:
    """Comprehensive anti-detection system."""

    def __init__(self):
        self.system_masker = SystemFingerprintMasker()
        self.network_monitor = NetworkAnomalyDetector()
        self.behavior_simulator = BehavioralPatternSimulator()
        self.detection_events = []
        self.is_active = False

    def activate(self):
        """Activate all anti-detection measures."""
        try:
            self.is_active = True

            # Apply system masking
            self.system_masker.apply_system_masking()

            # Start background monitoring
            self._start_background_monitoring()

            logger.info("Anti-detection system activated")

        except Exception as e:
            logger.error(f"Failed to activate anti-detection system: {e}")

    def deactivate(self):
        """Deactivate anti-detection measures."""
        self.is_active = False
        logger.info("Anti-detection system deactivated")

    def update_settings(self, settings: Dict):
        """Update anti-detection settings dynamically."""
        try:
            # Update behavioral simulator settings
            if 'min_delay' in settings:
                # Update the delay ranges in behavioral patterns
                delay_patterns = self.behavior_simulator.user_patterns["response_delays"]
                for pattern_name, pattern_data in delay_patterns.items():
                    if pattern_name == "immediate":
                        pattern_data["delay_range"] = (settings['min_delay'], settings['min_delay'] + 2)
                    elif pattern_name == "quick":
                        pattern_data["delay_range"] = (settings['min_delay'] + 2, min(settings.get('max_delay', 30), settings['min_delay'] + 20))
                    elif pattern_name == "normal":
                        pattern_data["delay_range"] = (settings['min_delay'] + 10, settings.get('max_delay', 30))
                    elif pattern_name == "slow":
                        pattern_data["delay_range"] = (settings.get('max_delay', 30), settings.get('max_delay', 30) + 200)
                    elif pattern_name == "very_slow":
                        pattern_data["delay_range"] = (settings.get('max_delay', 30) + 200, settings.get('max_delay', 30) + 800)

            # Update network monitor settings
            if 'messages_per_hour' in settings:
                # This affects connection frequency monitoring
                self.network_monitor.max_connections_per_hour = settings['messages_per_hour']

            # Update online simulation
            if 'online_simulation' in settings:
                self.online_simulation_enabled = settings['online_simulation']

            # Update enabled status
            if 'enabled' in settings:
                if settings['enabled'] and not self.is_active:
                    self.activate()
                elif not settings['enabled'] and self.is_active:
                    self.deactivate()

            logger.info(f"Anti-detection settings updated: {settings}")

        except Exception as e:
            logger.error(f"Failed to update anti-detection settings: {e}")

    def _start_background_monitoring(self):
        """Start background monitoring threads."""
        # Monitor system for anomalies
        def monitor_system():
            while self.is_active:
                try:
                    self._check_system_anomalies()
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.warning(f"System monitoring error: {e}")
                    time.sleep(300)  # Wait 5 minutes on error

        # Start monitoring thread
        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()

    def _check_system_anomalies(self):
        """Check for system anomalies that might indicate detection."""
        # Check CPU usage patterns
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:  # Suspiciously high CPU usage
            self.detection_events.append({
                "type": "high_cpu",
                "value": cpu_percent,
                "timestamp": datetime.now()
            })

        # Check memory usage
        memory = psutil.virtual_memory()
        if memory.percent > 95:  # Suspiciously high memory usage
            self.detection_events.append({
                "type": "high_memory",
                "value": memory.percent,
                "timestamp": datetime.now()
            })

        # Check for suspicious processes
        suspicious_processes = ["wireshark", "tcpdump", "ettercap", "burp"]
        for proc in psutil.process_iter(['name']):
            if any(susp_proc in proc.info['name'].lower() for susp_proc in suspicious_processes):
                self.detection_events.append({
                    "type": "suspicious_process",
                    "process": proc.info['name'],
                    "timestamp": datetime.now()
                })

    def get_detection_risk_level(self) -> str:
        """Get current detection risk level."""
        recent_events = [
            event for event in self.detection_events
            if (datetime.now() - event["timestamp"]).seconds < 3600  # Last hour
        ]

        if len(recent_events) >= 5:
            return "HIGH"
        elif len(recent_events) >= 2:
            return "MEDIUM"
        elif len(recent_events) >= 1:
            return "LOW"
        else:
            return "NONE"

    def apply_anti_detection_measures(self, action_type: str, **kwargs) -> Dict:
        """Apply appropriate anti-detection measures for an action."""

        measures = {
            "connection_delay": self.network_monitor.should_delay_connection(),
            "activity_level": self.behavior_simulator.get_current_activity_level(),
            "response_delay": self.behavior_simulator.get_realistic_response_delay(
                kwargs.get("message_urgency", 0.5)
            ),
            "risk_level": self.get_detection_risk_level()
        }

        # Adjust delays based on risk level
        risk_multiplier = {
            "NONE": 1.0,
            "LOW": 1.2,
            "MEDIUM": 1.5,
            "HIGH": 2.0
        }

        risk_mult = risk_multiplier.get(measures["risk_level"], 1.0)
        measures["connection_delay"] *= risk_mult
        measures["response_delay"] *= risk_mult

        # Log the measures being applied
        logger.info(f"Applied anti-detection measures for {action_type}: {measures}")

        return measures

    def report_activity(self, activity_type: str, details: Dict = None):
        """Report activity for monitoring."""
        activity_report = {
            "type": activity_type,
            "timestamp": datetime.now(),
            "details": details or {},
            "risk_level": self.get_detection_risk_level()
        }

        # Keep only recent activity reports
        if not hasattr(self, 'activity_reports'):
            self.activity_reports = []

        self.activity_reports.append(activity_report)

        # Limit history
        if len(self.activity_reports) > 1000:
            self.activity_reports = self.activity_reports[-500:]

        logger.debug(f"Activity reported: {activity_type}")

    def get_system_status(self) -> Dict:
        """Get comprehensive system status."""
        return {
            "anti_detection_active": self.is_active,
            "detection_risk_level": self.get_detection_risk_level(),
            "recent_detection_events": len([
                e for e in self.detection_events
                if (datetime.now() - e["timestamp"]).seconds < 3600
            ]),
            "activity_reports_count": len(getattr(self, 'activity_reports', [])),
            "current_activity_level": self.behavior_simulator.get_current_activity_level(),
            "system_masked": True  # Assuming masking was applied
        }

    def generate_device_config(self) -> Dict:
        """Generate a realistic device configuration for Pyrogram."""
        # Realistic device pool
        devices = [
            # Android
            {
                "device_model": "Samsung Galaxy S21",
                "system_version": "Android 12",
                "app_version": "8.4.1"
            },
            {
                "device_model": "Xiaomi Redmi Note 10",
                "system_version": "Android 11",
                "app_version": "8.5.0"
            },
            {
                "device_model": "Google Pixel 6",
                "system_version": "Android 13",
                "app_version": "9.0.0"
            },
            # iOS
            {
                "device_model": "iPhone 13",
                "system_version": "iOS 15.0",
                "app_version": "8.6.0"
            },
            {
                "device_model": "iPhone 12",
                "system_version": "iOS 14.5",
                "app_version": "8.3.2"
            }
        ]
        
        device = random.choice(devices)
        
        # Add language settings
        lang_codes = ["en", "ru", "es", "de", "fr", "it", "pt"]
        lang = random.choice(lang_codes)
        
        device["lang_code"] = lang
        device["system_lang_code"] = f"{lang}-{lang.upper()}"
        
        return device


class TelegramFingerprintGenerator:
    """Generate realistic Telegram client fingerprints."""
    
    # Realistic device database
    ANDROID_DEVICES = [
        {"brand": "Samsung", "model": "Galaxy S23 Ultra", "version": "Android 13", "app_version": "10.0.0"},
        {"brand": "Samsung", "model": "Galaxy S22", "version": "Android 13", "app_version": "9.7.6"},
        {"brand": "Samsung", "model": "Galaxy S21 FE", "version": "Android 12", "app_version": "9.5.0"},
        {"brand": "Samsung", "model": "Galaxy A54", "version": "Android 13", "app_version": "10.0.0"},
        {"brand": "Google", "model": "Pixel 7 Pro", "version": "Android 14", "app_version": "10.1.0"},
        {"brand": "Google", "model": "Pixel 7", "version": "Android 14", "app_version": "10.0.0"},
        {"brand": "Google", "model": "Pixel 6a", "version": "Android 13", "app_version": "9.8.0"},
        {"brand": "Xiaomi", "model": "13 Pro", "version": "Android 13", "app_version": "9.7.0"},
        {"brand": "Xiaomi", "model": "Redmi Note 12 Pro", "version": "Android 12", "app_version": "9.5.0"},
        {"brand": "OnePlus", "model": "11", "version": "Android 13", "app_version": "10.0.0"},
        {"brand": "OnePlus", "model": "Nord 3", "version": "Android 13", "app_version": "9.8.0"},
        {"brand": "OPPO", "model": "Find X6 Pro", "version": "Android 13", "app_version": "9.7.0"},
        {"brand": "Realme", "model": "GT 3", "version": "Android 13", "app_version": "9.6.0"},
        {"brand": "Motorola", "model": "Edge 40 Pro", "version": "Android 13", "app_version": "9.5.5"},
    ]
    
    IOS_DEVICES = [
        {"model": "iPhone 15 Pro Max", "version": "iOS 17.1", "app_version": "10.1.0"},
        {"model": "iPhone 15 Pro", "version": "iOS 17.1", "app_version": "10.0.0"},
        {"model": "iPhone 15", "version": "iOS 17.0", "app_version": "10.0.0"},
        {"model": "iPhone 14 Pro Max", "version": "iOS 17.0", "app_version": "9.8.0"},
        {"model": "iPhone 14 Pro", "version": "iOS 16.6", "app_version": "9.7.0"},
        {"model": "iPhone 14", "version": "iOS 16.5", "app_version": "9.6.0"},
        {"model": "iPhone 13 Pro Max", "version": "iOS 16.5", "app_version": "9.5.0"},
        {"model": "iPhone 13 Pro", "version": "iOS 16.4", "app_version": "9.4.0"},
        {"model": "iPhone 13", "version": "iOS 16.3", "app_version": "9.3.0"},
        {"model": "iPhone 12 Pro Max", "version": "iOS 16.2", "app_version": "9.2.0"},
        {"model": "iPhone SE (3rd generation)", "version": "iOS 16.1", "app_version": "9.1.0"},
    ]
    
    TDESKTOP_CONFIGS = [
        {"version": "4.10.3", "os": "Windows 10", "layer": 170},
        {"version": "4.10.2", "os": "Windows 11", "layer": 170},
        {"version": "4.9.8", "os": "macOS 14.0", "layer": 168},
        {"version": "4.9.5", "os": "Ubuntu 22.04", "layer": 167},
        {"version": "4.8.1", "os": "Windows 10", "layer": 165},
    ]
    
    LANGUAGES = [
        ("en", "en-US"), ("en", "en-GB"), ("es", "es-ES"), ("de", "de-DE"),
        ("fr", "fr-FR"), ("it", "it-IT"), ("pt", "pt-BR"), ("ru", "ru-RU"),
        ("zh", "zh-CN"), ("ja", "ja-JP"), ("ko", "ko-KR"), ("ar", "ar-SA"),
    ]
    
    TIMEZONES = {
        "en-US": [-8, -7, -6, -5, -4],  # US timezones
        "en-GB": [0, 1],
        "de-DE": [1, 2],
        "fr-FR": [1, 2],
        "es-ES": [1, 2],
        "ru-RU": [3, 4, 5, 6, 7, 8, 9, 10],
        "zh-CN": [8],
        "ja-JP": [9],
    }
    
    def __init__(self):
        self.generated_fingerprints: Dict[str, TelegramFingerprint] = {}
    
    def generate(self, client_type: TelegramClientType = None, 
                 preferred_lang: str = None) -> TelegramFingerprint:
        """Generate a new fingerprint."""
        if client_type is None:
            # Realistic distribution: 60% Android, 30% iOS, 10% Desktop
            rand = random.random()
            if rand < 0.6:
                client_type = TelegramClientType.ANDROID
            elif rand < 0.9:
                client_type = TelegramClientType.IOS
            else:
                client_type = TelegramClientType.TDESKTOP
        
        if preferred_lang:
            lang = (preferred_lang, f"{preferred_lang}-{preferred_lang.upper()}")
        else:
            lang = random.choice(self.LANGUAGES)
        
        # Get timezone for language
        tz_offset = random.choice(self.TIMEZONES.get(lang[1], [0]))
        
        if client_type == TelegramClientType.ANDROID:
            device = random.choice(self.ANDROID_DEVICES)
            fingerprint = TelegramFingerprint(
                client_type=client_type,
                device_model=f"{device['brand']} {device['model']}",
                system_version=device['version'],
                app_version=device['app_version'],
                lang_code=lang[0],
                system_lang_code=lang[1],
                layer=170,
                brand=device['brand'],
                manufacturer=device['brand'],
                screen_resolution=random.choice(["1080x2340", "1080x2400", "1440x3200", "1440x3088"]),
                timezone_offset=tz_offset
            )
        elif client_type == TelegramClientType.IOS:
            device = random.choice(self.IOS_DEVICES)
            fingerprint = TelegramFingerprint(
                client_type=client_type,
                device_model=device['model'],
                system_version=device['version'],
                app_version=device['app_version'],
                lang_code=lang[0],
                system_lang_code=lang[1],
                layer=170,
                brand="Apple",
                manufacturer="Apple",
                screen_resolution=random.choice(["1170x2532", "1284x2778", "1179x2556", "1290x2796"]),
                timezone_offset=tz_offset
            )
        else:  # TDesktop
            config = random.choice(self.TDESKTOP_CONFIGS)
            fingerprint = TelegramFingerprint(
                client_type=client_type,
                device_model="Desktop",
                system_version=config['os'],
                app_version=config['version'],
                lang_code=lang[0],
                system_lang_code=lang[1],
                layer=config['layer'],
                timezone_offset=tz_offset
            )
        
        return fingerprint
    
    def rotate_fingerprint(self, account_id: str) -> TelegramFingerprint:
        """Rotate fingerprint for an account."""
        old_fp = self.generated_fingerprints.get(account_id)
        
        # Generate new fingerprint, keeping same client type if possible
        new_fp = self.generate(
            client_type=old_fp.client_type if old_fp else None,
            preferred_lang=old_fp.lang_code if old_fp else None
        )
        
        if old_fp:
            new_fp.rotation_count = old_fp.rotation_count + 1
        
        self.generated_fingerprints[account_id] = new_fp
        return new_fp
    
    def get_fingerprint(self, account_id: str) -> Optional[TelegramFingerprint]:
        """Get fingerprint for an account."""
        return self.generated_fingerprints.get(account_id)
    
    def auto_rotate_if_needed(self, account_id: str, max_days: int = 14) -> Tuple[bool, Optional[TelegramFingerprint]]:
        """Automatically rotate fingerprint if needed.
        
        Args:
            account_id: Account ID
            max_days: Maximum days between rotations
            
        Returns:
            (was_rotated, new_fingerprint) tuple
        """
        fp = self.get_fingerprint(account_id)
        
        if fp and fp.should_rotate(max_days):
            new_fp = self.rotate_fingerprint(account_id)
            logger.info(f"Auto-rotated fingerprint for {account_id}: {new_fp.client_type.value}")
            return (True, new_fp)
        
        return (False, fp)
    
    def rotate_to_specific_type(self, account_id: str, 
                                client_type: TelegramClientType,
                                preserve_language: bool = True) -> TelegramFingerprint:
        """Rotate fingerprint to a specific client type.
        
        Args:
            account_id: Account ID
            client_type: Target client type
            preserve_language: Keep same language settings
            
        Returns:
            New fingerprint
        """
        old_fp = self.generated_fingerprints.get(account_id)
        
        new_fp = self.generate(
            client_type=client_type,
            preferred_lang=old_fp.lang_code if (old_fp and preserve_language) else None
        )
        
        if old_fp:
            new_fp.rotation_count = old_fp.rotation_count + 1
        
        self.generated_fingerprints[account_id] = new_fp
        logger.info(f"Rotated {account_id} to {client_type.value}")
        return new_fp
    
    def cycle_client_types(self, account_id: str) -> TelegramFingerprint:
        """Cycle through different client types for diversity.
        
        Args:
            account_id: Account ID
            
        Returns:
            New fingerprint with different client type
        """
        old_fp = self.generated_fingerprints.get(account_id)
        current_type = old_fp.client_type if old_fp else TelegramClientType.ANDROID
        
        # Cycle: Android -> iOS -> Desktop -> Android
        type_cycle = {
            TelegramClientType.ANDROID: TelegramClientType.IOS,
            TelegramClientType.IOS: TelegramClientType.TDESKTOP,
            TelegramClientType.TDESKTOP: TelegramClientType.ANDROID,
        }
        
        next_type = type_cycle.get(current_type, TelegramClientType.ANDROID)
        return self.rotate_to_specific_type(account_id, next_type)
    
    def smart_rotate_based_on_risk(self, account_id: str, risk_level: BanRiskLevel) -> TelegramFingerprint:
        """Smart rotation based on account risk level.
        
        Args:
            account_id: Account ID
            risk_level: Current risk level
            
        Returns:
            New fingerprint
        """
        if risk_level in [BanRiskLevel.HIGH, BanRiskLevel.CRITICAL]:
            # High risk: change to completely different type
            return self.cycle_client_types(account_id)
        elif risk_level == BanRiskLevel.MODERATE:
            # Moderate risk: rotate within same type but different device
            return self.rotate_fingerprint(account_id)
        else:
            # Low risk: no rotation needed
            return self.get_fingerprint(account_id) or self.generate()
    
    def get_rotation_strategy(self, account_id: str) -> str:
        """Get recommended rotation strategy for account.
        
        Returns:
            Strategy description
        """
        fp = self.get_fingerprint(account_id)
        
        if not fp:
            return "initialize"
        
        days_since = (datetime.now() - fp.last_rotated).days
        
        if days_since > 30:
            return "urgent_rotation"
        elif days_since > 14:
            return "recommended_rotation"
        elif fp.rotation_count == 0:
            return "first_rotation_available"
        else:
            return "no_rotation_needed"


class MessageDiversityAnalyzer:
    """Analyze message diversity to detect repetitive patterns."""
    
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.message_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.template_patterns: Dict[str, Set[str]] = defaultdict(set)
    
    def add_message(self, account_id: str, message: str):
        """Add a message to the history."""
        self.message_history[account_id].append(message)
        
        # Extract potential template
        template = self._extract_template(message)
        self.template_patterns[account_id].add(template)
        
        # Limit template set size
        if len(self.template_patterns[account_id]) > 50:
            # Keep most recent patterns
            patterns = list(self.template_patterns[account_id])
            self.template_patterns[account_id] = set(patterns[-30:])
    
    def _extract_template(self, message: str) -> str:
        """Extract template pattern from message."""
        # Replace numbers with placeholder
        template = re.sub(r'\d+', '{NUM}', message)
        # Replace names/usernames (capitalized words, @mentions)
        template = re.sub(r'@\w+', '{USER}', template)
        template = re.sub(r'\b[A-Z][a-z]+\b', '{NAME}', template)
        # Normalize whitespace
        template = ' '.join(template.split())
        return template.lower()
    
    def calculate_diversity_score(self, account_id: str) -> float:
        """Calculate message diversity score (0-1, higher is more diverse)."""
        messages = list(self.message_history[account_id])
        
        if len(messages) < 5:
            return 1.0  # Not enough data
        
        # Calculate unique message ratio
        unique_messages = len(set(messages))
        unique_ratio = unique_messages / len(messages)
        
        # Calculate unique template ratio
        templates = [self._extract_template(m) for m in messages]
        unique_templates = len(set(templates))
        template_ratio = unique_templates / len(templates)
        
        # Calculate average edit distance diversity
        similarity_scores = []
        for i in range(min(20, len(messages) - 1)):
            for j in range(i + 1, min(i + 5, len(messages))):
                similarity = self._similarity_ratio(messages[i], messages[j])
                similarity_scores.append(similarity)
        
        if similarity_scores:
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            similarity_diversity = 1.0 - avg_similarity
        else:
            similarity_diversity = 1.0
        
        # Weighted average
        score = (unique_ratio * 0.3 + template_ratio * 0.4 + similarity_diversity * 0.3)
        
        return max(0.0, min(1.0, score))
    
    def _similarity_ratio(self, s1: str, s2: str) -> float:
        """Calculate similarity ratio between two strings."""
        if not s1 or not s2:
            return 0.0
        
        # Simple Jaccard similarity on words
        words1 = set(s1.lower().split())
        words2 = set(s2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def detect_spam_pattern(self, account_id: str) -> Tuple[bool, str]:
        """Detect if account is sending spam-like patterns."""
        messages = list(self.message_history[account_id])
        
        if len(messages) < 10:
            return False, ""
        
        # Check for exact duplicates
        message_counts = defaultdict(int)
        for msg in messages:
            message_counts[msg] += 1
        
        max_count = max(message_counts.values()) if message_counts else 0
        
        if max_count >= 5:
            return True, f"Exact duplicate detected ({max_count} times)"
        
        # Check template repetition
        templates = [self._extract_template(m) for m in messages]
        template_counts = defaultdict(int)
        for tmpl in templates:
            template_counts[tmpl] += 1
        
        max_template_count = max(template_counts.values()) if template_counts else 0
        
        if max_template_count >= len(messages) * 0.7:
            return True, f"Template pattern detected ({max_template_count}/{len(messages)} messages)"
        
        return False, ""


class TimezoneAwareActivitySimulator:
    """Simulate activity based on timezone-appropriate behavior."""
    
    def __init__(self, timezone_offset: int = 0):
        self.timezone_offset = timezone_offset
        self.activity_patterns = self._generate_activity_pattern()
        self.sleep_hours = self._generate_sleep_schedule()
    
    def _generate_activity_pattern(self) -> Dict[int, float]:
        """Generate hourly activity multipliers."""
        pattern = {}
        for hour in range(24):
            if 2 <= hour < 7:  # Deep night
                pattern[hour] = random.uniform(0.02, 0.1)
            elif 7 <= hour < 9:  # Morning wake
                pattern[hour] = random.uniform(0.3, 0.6)
            elif 9 <= hour < 12:  # Morning work
                pattern[hour] = random.uniform(0.6, 0.9)
            elif 12 <= hour < 14:  # Lunch
                pattern[hour] = random.uniform(0.7, 1.0)
            elif 14 <= hour < 18:  # Afternoon work
                pattern[hour] = random.uniform(0.5, 0.8)
            elif 18 <= hour < 21:  # Evening
                pattern[hour] = random.uniform(0.8, 1.0)
            elif 21 <= hour < 24:  # Late evening
                pattern[hour] = random.uniform(0.4, 0.7)
            else:  # Early morning
                pattern[hour] = random.uniform(0.1, 0.3)
        return pattern
    
    def _generate_sleep_schedule(self) -> Tuple[int, int]:
        """Generate sleep schedule (start_hour, end_hour)."""
        # Most people sleep between 11pm-7am with some variation
        sleep_start = random.randint(22, 26) % 24  # 10pm - 2am
        sleep_end = sleep_start + random.randint(6, 9)  # 6-9 hours of sleep
        return (sleep_start, sleep_end % 24)
    
    def get_local_hour(self) -> int:
        """Get current hour in account's timezone."""
        utc_hour = datetime.utcnow().hour
        local_hour = (utc_hour + self.timezone_offset) % 24
        return local_hour
    
    def is_sleeping(self) -> bool:
        """Check if account should be sleeping."""
        local_hour = self.get_local_hour()
        sleep_start, sleep_end = self.sleep_hours
        
        if sleep_start < sleep_end:
            return sleep_start <= local_hour < sleep_end
        else:  # Wraps around midnight
            return local_hour >= sleep_start or local_hour < sleep_end
    
    def get_activity_multiplier(self) -> float:
        """Get activity multiplier for current time."""
        local_hour = self.get_local_hour()
        
        if self.is_sleeping():
            return random.uniform(0.0, 0.05)  # Very low activity during sleep
        
        base = self.activity_patterns.get(local_hour, 0.5)
        
        # Add daily variation
        day_of_week = datetime.now().weekday()
        if day_of_week >= 5:  # Weekend
            base *= random.uniform(0.7, 1.1)
        
        # Add random variation
        base *= random.uniform(0.8, 1.2)
        
        return max(0.0, min(1.0, base))
    
    def should_send_message(self) -> Tuple[bool, float]:
        """Determine if message should be sent and delay."""
        activity = self.get_activity_multiplier()
        
        if self.is_sleeping():
            return False, 0.0
        
        # Random chance based on activity
        if random.random() > activity:
            # Delay sending
            delay = random.uniform(10, 300) / activity if activity > 0 else 3600
            return True, delay
        
        return True, 0.0


class AccountQuarantineManager:
    """Manage quarantined accounts."""
    
    def __init__(self, db_path: str = "quarantine.db"):
        self.db_path = db_path
        self._init_database()
        self.quarantine_callbacks: List[Callable[[str, QuarantineReason], None]] = []
    
    def _init_database(self):
        """Initialize quarantine database."""
        with self._get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS quarantine_history (
                    id INTEGER PRIMARY KEY,
                    account_id TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    released_at TIMESTAMP,
                    duration_minutes INTEGER,
                    metrics_snapshot TEXT,
                    notes TEXT
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS active_quarantine (
                    account_id TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    quarantined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    release_at TIMESTAMP NOT NULL,
                    metrics_snapshot TEXT
                )
            ''')
            
            conn.execute('CREATE INDEX IF NOT EXISTS idx_quarantine_account ON quarantine_history(account_id)')
            conn.commit()
    
    def quarantine_account(self, account_id: str, reason: QuarantineReason, 
                          duration_minutes: int = 60, metrics: Dict = None) -> bool:
        """Quarantine an account."""
        release_at = datetime.now() + timedelta(minutes=duration_minutes)
        metrics_json = json.dumps(metrics) if metrics else None
        
        try:
            with self._get_connection() as conn:
                # Add to active quarantine
                conn.execute('''
                    INSERT OR REPLACE INTO active_quarantine 
                    (account_id, reason, quarantined_at, release_at, metrics_snapshot)
                    VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)
                ''', (account_id, reason.value, release_at, metrics_json))
                
                # Log to history
                conn.execute('''
                    INSERT INTO quarantine_history 
                    (account_id, reason, duration_minutes, metrics_snapshot)
                    VALUES (?, ?, ?, ?)
                ''', (account_id, reason.value, duration_minutes, metrics_json))
                
                conn.commit()
            
            # Notify callbacks
            for callback in self.quarantine_callbacks:
                try:
                    callback(account_id, reason)
                except Exception as e:
                    logger.error(f"Quarantine callback error: {e}")
            
            logger.warning(f"Account {account_id} quarantined for {duration_minutes} min: {reason.value}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to quarantine account {account_id}: {e}")
            return False
    
    def release_account(self, account_id: str) -> bool:
        """Release an account from quarantine."""
        try:
            with self._get_connection() as conn:
                # Update history
                conn.execute('''
                    UPDATE quarantine_history 
                    SET released_at = CURRENT_TIMESTAMP 
                    WHERE account_id = ? AND released_at IS NULL
                ''', (account_id,))
                
                # Remove from active
                conn.execute('DELETE FROM active_quarantine WHERE account_id = ?', (account_id,))
                conn.commit()
            
            logger.info(f"Account {account_id} released from quarantine")
            return True
            
        except Exception as e:
            logger.error(f"Failed to release account {account_id}: {e}")
            return False
    
    def is_quarantined(self, account_id: str) -> Tuple[bool, Optional[datetime]]:
        """Check if account is quarantined."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT release_at FROM active_quarantine 
                    WHERE account_id = ? AND release_at > CURRENT_TIMESTAMP
                ''', (account_id,))
                row = cursor.fetchone()
                
                if row:
                    return True, datetime.fromisoformat(row[0])
                return False, None
                
        except Exception as e:
            logger.error(f"Failed to check quarantine status: {e}")
            return False, None
    
    def check_and_release_expired(self) -> List[str]:
        """Check and release accounts whose quarantine has expired."""
        released = []
        
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT account_id FROM active_quarantine 
                    WHERE release_at <= CURRENT_TIMESTAMP
                ''')
                expired = [row[0] for row in cursor.fetchall()]
                
                for account_id in expired:
                    if self.release_account(account_id):
                        released.append(account_id)
                        
        except Exception as e:
            logger.error(f"Failed to release expired quarantines: {e}")
        
        return released
    
    def get_quarantine_stats(self, account_id: str) -> Dict[str, Any]:
        """Get quarantine statistics for an account."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute('''
                    SELECT COUNT(*) as total_quarantines,
                           SUM(duration_minutes) as total_minutes,
                           MAX(quarantined_at) as last_quarantine
                    FROM quarantine_history 
                    WHERE account_id = ?
                ''', (account_id,))
                row = cursor.fetchone()
                
                return {
                    'total_quarantines': row[0] or 0,
                    'total_minutes': row[1] or 0,
                    'last_quarantine': row[2]
                }
                
        except Exception as e:
            logger.error(f"Failed to get quarantine stats: {e}")
            return {'total_quarantines': 0, 'total_minutes': 0, 'last_quarantine': None}


class AccountCreationAntiDetection(AntiDetectionSystem):
    """Specialized anti-detection for account creation."""
    
    def simulate_reading_sms(self, session_id: str) -> float:
        """Simulate time taken to read SMS code."""
        # Humans take 3-10 seconds to read an SMS code
        return random.uniform(3.0, 10.0)
        
    def simulate_human_typing(self, session_id: str, text: str, field_type: str = "generic") -> List[float]:
        """Simulate typing delays for a string."""
        delays = []
        for _ in text:
            # Typing speed varies (50-200ms per key)
            delays.append(random.uniform(0.05, 0.2))
        return delays
        
    def simulate_profile_setup(self, session_id: str, step: str) -> float:
        """Simulate delays between profile setup steps."""
        if step == "name":
            return random.uniform(2.0, 5.0)
        elif step == "photo":
            return random.uniform(5.0, 15.0)
        elif step == "bio":
            return random.uniform(5.0, 10.0)
        return random.uniform(2.0, 5.0)


class EnhancedAntiDetectionSystem(AntiDetectionSystem):
    """
    Enhanced anti-detection system with Telegram-specific features.
    
    Features:
    - Telegram-specific fingerprinting
    - Session rotation
    - Message pattern analysis  
    - Real-time ban probability
    - Automatic quarantine
    - Timezone-aware simulation
    - Message diversity scoring
    """
    
    QUARANTINE_THRESHOLD = 0.6  # Ban probability threshold for auto-quarantine
    
    def __init__(self):
        super().__init__()
        
        # Enhanced components
        self.fingerprint_generator = TelegramFingerprintGenerator()
        self.diversity_analyzer = MessageDiversityAnalyzer()
        self.quarantine_manager = AccountQuarantineManager()
        
        # Per-account tracking
        self.account_metrics: Dict[str, AccountRiskMetrics] = {}
        self.activity_simulators: Dict[str, TimezoneAwareActivitySimulator] = {}
        
        # Configuration
        self.fingerprint_rotation_days = 14
        self.auto_quarantine_enabled = True
        
        # Start background tasks
        self._start_enhanced_monitoring()
    
    def _start_enhanced_monitoring(self):
        """Start enhanced background monitoring."""
        def monitor_loop():
            while self.is_active:
                try:
                    # Check for expired quarantines
                    released = self.quarantine_manager.check_and_release_expired()
                    if released:
                        logger.info(f"Released {len(released)} accounts from quarantine")
                    
                    # Update all account risk metrics
                    self._update_all_risk_metrics()
                    
                    # Check for fingerprint rotation
                    self._check_fingerprint_rotation()
                    
                    time.sleep(60)  # Every minute
                except Exception as e:
                    logger.error(f"Enhanced monitoring error: {e}")
                    time.sleep(300)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
    
    def _update_all_risk_metrics(self):
        """Update risk metrics for all accounts."""
        for account_id, metrics in self.account_metrics.items():
            metrics.calculate_ban_probability()
            
            # Check for auto-quarantine
            if (self.auto_quarantine_enabled and 
                not metrics.is_quarantined and 
                metrics.ban_probability >= self.QUARANTINE_THRESHOLD):
                
                # Determine quarantine duration based on risk
                if metrics.ban_probability >= 0.8:
                    duration = 240  # 4 hours
                elif metrics.ban_probability >= 0.7:
                    duration = 120  # 2 hours
                else:
                    duration = 60   # 1 hour
                
                self.quarantine_account(account_id, QuarantineReason.HIGH_BAN_RISK, duration)
    
    def _check_fingerprint_rotation(self):
        """Check if any fingerprints need rotation."""
        for account_id, fingerprint in self.fingerprint_generator.generated_fingerprints.items():
            if fingerprint.should_rotate(self.fingerprint_rotation_days):
                logger.info(f"Rotating fingerprint for account {account_id}")
                self.fingerprint_generator.rotate_fingerprint(account_id)
    
    def get_or_create_fingerprint(self, account_id: str, 
                                   client_type: TelegramClientType = None) -> TelegramFingerprint:
        """Get or create a fingerprint for an account."""
        existing = self.fingerprint_generator.get_fingerprint(account_id)
        if existing:
            return existing
        
        fingerprint = self.fingerprint_generator.generate(client_type)
        self.fingerprint_generator.generated_fingerprints[account_id] = fingerprint
        
        # Create activity simulator with matching timezone
        self.activity_simulators[account_id] = TimezoneAwareActivitySimulator(
            fingerprint.timezone_offset
        )
        
        return fingerprint
    
    def get_or_create_metrics(self, account_id: str) -> AccountRiskMetrics:
        """Get or create risk metrics for an account."""
        if account_id not in self.account_metrics:
            self.account_metrics[account_id] = AccountRiskMetrics(account_id=account_id)
        return self.account_metrics[account_id]
    
    def record_message_sent(self, account_id: str, message: str, recipient_id: int):
        """Record a sent message for analysis."""
        metrics = self.get_or_create_metrics(account_id)
        
        # Update counts
        metrics.messages_sent_24h += 1
        metrics.messages_sent_1h += 1
        metrics.last_activity = datetime.now()
        
        # Track unique recipients
        if not hasattr(metrics, '_recent_recipients'):
            metrics._recent_recipients = set()
        metrics._recent_recipients.add(recipient_id)
        metrics.unique_recipients_24h = len(metrics._recent_recipients)
        
        # Analyze message diversity
        self.diversity_analyzer.add_message(account_id, message)
        metrics.message_diversity_score = self.diversity_analyzer.calculate_diversity_score(account_id)
        
        # Check for spam pattern
        is_spam, spam_reason = self.diversity_analyzer.detect_spam_pattern(account_id)
        if is_spam:
            logger.warning(f"Spam pattern detected for {account_id}: {spam_reason}")
            metrics.ban_probability += 0.1
            
            if self.auto_quarantine_enabled:
                self.quarantine_account(account_id, QuarantineReason.PATTERN_DETECTED, 30)
        
        # Recalculate risk
        metrics.calculate_ban_probability()
    
    def record_error(self, account_id: str, error_type: str, error_message: str):
        """Record an error for an account."""
        metrics = self.get_or_create_metrics(account_id)
        metrics.error_count_24h += 1
        metrics.last_error = error_message
        
        # Special handling for flood wait
        if "flood" in error_type.lower() or "floodwait" in error_type.lower():
            metrics.flood_wait_count_24h += 1
            
            if metrics.flood_wait_count_24h >= 3:
                self.quarantine_account(
                    account_id, 
                    QuarantineReason.FLOOD_WAIT,
                    duration_minutes=60 * metrics.flood_wait_count_24h
                )
        
        metrics.calculate_ban_probability()
    
    def quarantine_account(self, account_id: str, reason: QuarantineReason, 
                          duration_minutes: int = 60) -> bool:
        """Quarantine an account."""
        metrics = self.get_or_create_metrics(account_id)
        
        result = self.quarantine_manager.quarantine_account(
            account_id, reason, duration_minutes,
            metrics={'ban_probability': metrics.ban_probability,
                    'messages_24h': metrics.messages_sent_24h,
                    'errors_24h': metrics.error_count_24h}
        )
        
        if result:
            metrics.is_quarantined = True
            metrics.quarantine_reason = reason
            metrics.quarantine_until = datetime.now() + timedelta(minutes=duration_minutes)
        
        return result
    
    def is_account_quarantined(self, account_id: str) -> Tuple[bool, Optional[datetime]]:
        """Check if account is quarantined."""
        return self.quarantine_manager.is_quarantined(account_id)
    
    def can_send_message(self, account_id: str) -> Tuple[bool, float, str]:
        """
        Check if account can send a message.
        
        Returns:
            Tuple of (can_send, delay_seconds, reason)
        """
        # Check quarantine
        is_quarantined, release_at = self.is_account_quarantined(account_id)
        if is_quarantined:
            wait_time = (release_at - datetime.now()).total_seconds() if release_at else 3600
            return False, wait_time, "Account is quarantined"
        
        # Check timezone-aware activity
        simulator = self.activity_simulators.get(account_id)
        if simulator:
            if simulator.is_sleeping():
                return False, 0, "Account is sleeping (timezone)"
            
            can_send, delay = simulator.should_send_message()
            if not can_send or delay > 0:
                return can_send, delay, "Activity simulation delay"
        
        # Check risk level
        metrics = self.get_or_create_metrics(account_id)
        
        if metrics.risk_level == BanRiskLevel.CRITICAL:
            return False, 600, "Critical risk level"
        elif metrics.risk_level == BanRiskLevel.HIGH:
            return True, random.uniform(30, 120), "High risk - adding delay"
        elif metrics.risk_level == BanRiskLevel.MODERATE:
            return True, random.uniform(10, 30), "Moderate risk - adding delay"
        
        return True, 0, "OK"
    
    def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """Get comprehensive status for an account."""
        metrics = self.get_or_create_metrics(account_id)
        fingerprint = self.fingerprint_generator.get_fingerprint(account_id)
        simulator = self.activity_simulators.get(account_id)
        is_quarantined, release_at = self.is_account_quarantined(account_id)
        
        return {
            'account_id': account_id,
            'ban_probability': metrics.ban_probability,
            'risk_level': metrics.risk_level.value,
            'is_quarantined': is_quarantined,
            'quarantine_release_at': release_at.isoformat() if release_at else None,
            'messages_sent_24h': metrics.messages_sent_24h,
            'message_diversity_score': metrics.message_diversity_score,
            'fingerprint': {
                'client_type': fingerprint.client_type.value if fingerprint else None,
                'device_model': fingerprint.device_model if fingerprint else None,
                'rotation_count': fingerprint.rotation_count if fingerprint else 0,
            } if fingerprint else None,
            'activity': {
                'is_sleeping': simulator.is_sleeping() if simulator else False,
                'activity_multiplier': simulator.get_activity_multiplier() if simulator else 1.0,
                'local_hour': simulator.get_local_hour() if simulator else None,
            } if simulator else None,
            'last_activity': metrics.last_activity.isoformat() if metrics.last_activity else None,
        }
    
    def reset_daily_metrics(self):
        """Reset daily metrics for all accounts."""
        for metrics in self.account_metrics.values():
            metrics.messages_sent_24h = 0
            metrics.error_count_24h = 0
            metrics.flood_wait_count_24h = 0
            metrics.unique_recipients_24h = 0
            if hasattr(metrics, '_recent_recipients'):
                metrics._recent_recipients.clear()
