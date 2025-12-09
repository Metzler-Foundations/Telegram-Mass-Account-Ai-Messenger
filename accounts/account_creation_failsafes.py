"""
Comprehensive fail-safes and safety mechanisms for bulk account creation.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class FailSafeLevel(Enum):
    """Levels of fail-safe protection."""

    MINIMAL = "minimal"  # Basic checks only
    STANDARD = "standard"  # Standard protection
    STRICT = "strict"  # Maximum protection
    PARANOID = "paranoid"  # Extreme protection with extensive checks


class AccountCreationFailSafe:
    """Comprehensive fail-safe system for account creation."""

    def __init__(self, level: FailSafeLevel = FailSafeLevel.STANDARD):
        self.level = level
        self.creation_history = []  # Track creation history
        self.failure_patterns = {}  # Track failure patterns
        self.rate_limits = {
            "per_hour": 10,  # Max accounts per hour
            "per_day": 50,  # Max accounts per day
            "per_ip": 5,  # Max accounts per IP per hour
        }
        self.blocked_ips = set()
        self.blocked_phone_providers = set()
        self.health_checks = []

    def register_health_check(self, check_name: str, check_func: Callable):
        """Register a health check function."""
        self.health_checks.append(
            {"name": check_name, "func": check_func, "last_run": None, "last_result": None}
        )

    async def run_health_checks(self) -> Dict[str, bool]:
        """Run all registered health checks."""
        results = {}
        for check in self.health_checks:
            try:
                result = await check["func"]()
                check["last_result"] = result
                check["last_run"] = datetime.now()
                results[check["name"]] = result
            except Exception as e:
                logger.error(f"Health check {check['name']} failed: {e}")
                results[check["name"]] = False
        return results

    def check_rate_limits(self, phone_number: str, ip_address: str) -> Tuple[bool, Optional[str]]:
        """
        Check if creation is allowed based on rate limits.

        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Check per-hour limit
        recent_creations = [
            c for c in self.creation_history if c.get("timestamp", datetime.min) > hour_ago
        ]
        if len(recent_creations) >= self.rate_limits["per_hour"]:
            return (
                False,
                f"Hourly limit exceeded: {len(recent_creations)}/{self.rate_limits['per_hour']}",
            )

        # Check per-day limit
        daily_creations = [
            c for c in self.creation_history if c.get("timestamp", datetime.min) > day_ago
        ]
        if len(daily_creations) >= self.rate_limits["per_day"]:
            return (
                False,
                f"Daily limit exceeded: {len(daily_creations)}/{self.rate_limits['per_day']}",
            )

        # Check per-IP limit
        ip_creations = [c for c in recent_creations if c.get("ip_address") == ip_address]
        if len(ip_creations) >= self.rate_limits["per_ip"]:
            return (
                False,
                f"IP limit exceeded: {len(ip_creations)}/{self.rate_limits['per_ip']} for {ip_address}",
            )

        return True, None

    def check_failure_patterns(self, config: Dict) -> Tuple[bool, Optional[str]]:
        """
        Check for suspicious failure patterns.

        Returns:
            Tuple of (is_safe, reason_if_unsafe)
        """
        # Check for rapid failures
        recent_failures = [c for c in self.creation_history[-10:] if not c.get("success", False)]
        if len(recent_failures) >= 5:
            return False, "Too many recent failures detected"

        # Check provider failures
        provider = config.get("phone_provider")
        if provider in self.blocked_phone_providers:
            return False, f"Phone provider {provider} is blocked due to failures"

        return True, None

    def record_creation_attempt(
        self,
        phone_number: str,
        ip_address: str,
        provider: str,
        success: bool,
        error: Optional[str] = None,
    ):
        """Record a creation attempt for pattern analysis."""
        record = {
            "phone_number": phone_number,
            "ip_address": ip_address,
            "provider": provider,
            "success": success,
            "error": error,
            "timestamp": datetime.now(),
        }
        self.creation_history.append(record)

        # Keep only last 1000 records
        if len(self.creation_history) > 1000:
            self.creation_history = self.creation_history[-1000:]

        # Update failure patterns
        if not success:
            self._update_failure_patterns(provider, error)

    def _update_failure_patterns(self, provider: str, error: Optional[str]):
        """Update failure pattern tracking."""
        if provider not in self.failure_patterns:
            self.failure_patterns[provider] = {
                "total_attempts": 0,
                "failures": 0,
                "recent_errors": [],
            }

        pattern = self.failure_patterns[provider]
        pattern["total_attempts"] += 1
        pattern["failures"] += 1

        if error:
            pattern["recent_errors"].append(error)
            # Keep only last 10 errors
            if len(pattern["recent_errors"]) > 10:
                pattern["recent_errors"] = pattern["recent_errors"][-10:]

        # Block provider if failure rate is too high
        if pattern["total_attempts"] >= 5:
            failure_rate = pattern["failures"] / pattern["total_attempts"]
            if failure_rate > 0.8:  # 80% failure rate
                self.blocked_phone_providers.add(provider)
                logger.warning(
                    f"Blocked phone provider {provider} due to high failure rate: {failure_rate:.1%}"
                )

    async def pre_creation_check(
        self, config: Dict, phone_number: str, ip_address: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Perform pre-creation safety checks.

        Returns:
            Tuple of (is_safe_to_proceed, reason_if_not_safe)
        """
        # Run health checks
        if self.level in [FailSafeLevel.STRICT, FailSafeLevel.PARANOID]:
            health_results = await self.run_health_checks()
            failed_checks = [name for name, result in health_results.items() if not result]
            if failed_checks:
                return False, f"Health checks failed: {', '.join(failed_checks)}"

        # Check rate limits
        is_allowed, reason = self.check_rate_limits(phone_number, ip_address)
        if not is_allowed:
            return False, reason

        # Check failure patterns
        is_safe, reason = self.check_failure_patterns(config)
        if not is_safe:
            return False, reason

        # Check IP blocking
        if ip_address in self.blocked_ips:
            return False, f"IP address {ip_address} is blocked"

        return True, None

    def block_ip(self, ip_address: str, reason: str):
        """Block an IP address from further creations."""
        self.blocked_ips.add(ip_address)
        logger.warning(f"Blocked IP {ip_address}: {reason}")

    def unblock_ip(self, ip_address: str):
        """Unblock an IP address."""
        self.blocked_ips.discard(ip_address)
        logger.info(f"Unblocked IP {ip_address}")

    def get_statistics(self) -> Dict:
        """Get fail-safe statistics."""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        recent = [c for c in self.creation_history if c.get("timestamp", datetime.min) > hour_ago]
        daily = [c for c in self.creation_history if c.get("timestamp", datetime.min) > day_ago]

        return {
            "total_attempts": len(self.creation_history),
            "recent_attempts_1h": len(recent),
            "daily_attempts": len(daily),
            "blocked_ips": len(self.blocked_ips),
            "blocked_providers": len(self.blocked_phone_providers),
            "failure_patterns": len(self.failure_patterns),
            "success_rate": (
                (
                    sum(1 for c in self.creation_history if c.get("success", False))
                    / max(len(self.creation_history), 1)
                )
                if self.creation_history
                else 0.0
            ),
        }
