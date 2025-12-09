"""
Account Risk Monitor - Real-time account health and ban risk tracking.

Features:
- Continuous risk scoring based on activity patterns
- FloodWait frequency tracking
- Error rate monitoring
- Shadowban detection integration
- Automated quarantine recommendations
- Risk alert system
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Account risk levels."""

    SAFE = "safe"  # 0-20: Normal operation
    LOW = "low"  # 21-40: Minor concerns
    MEDIUM = "medium"  # 41-60: Elevated risk
    HIGH = "high"  # 61-80: High risk, reduce activity
    CRITICAL = "critical"  # 81-100: Imminent ban risk, quarantine


class RiskFactor(Enum):
    """Types of risk factors."""

    FLOODWAIT = "floodwait"
    ERROR_RATE = "error_rate"
    RAPID_ACTIVITY = "rapid_activity"
    SHADOWBAN = "shadowban"
    PROXY_FAILURE = "proxy_failure"
    REPEATED_BLOCKS = "repeated_blocks"


@dataclass
class AccountRiskScore:
    """Account risk assessment."""

    phone_number: str
    overall_score: float  # 0-100
    risk_level: RiskLevel

    # Component scores
    floodwait_score: float = 0.0
    error_rate_score: float = 0.0
    activity_score: float = 0.0
    shadowban_score: float = 0.0

    # Metrics
    total_floodwaits_24h: int = 0
    total_errors_24h: int = 0
    messages_sent_1h: int = 0
    last_floodwait: Optional[datetime] = None

    # Recommendations
    recommended_actions: List[str] = None
    should_quarantine: bool = False

    timestamp: datetime = None

    def __post_init__(self):
        if self.recommended_actions is None:
            self.recommended_actions = []
        if self.timestamp is None:
            self.timestamp = datetime.now()


class AccountRiskMonitor:
    """
    Monitor account health and ban risk in real-time.
    """

    def __init__(self, db_path: str = "account_risk.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except Exception:
            pass
        self._init_database()

    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return self._get_connection()

        # Risk scoring weights
        self.weights = {
            "floodwait": 0.35,  # FloodWait is strongest ban signal
            "error_rate": 0.25,  # High error rate indicates problems
            "activity": 0.20,  # Rapid activity patterns
            "shadowban": 0.15,  # Shadowban detection
            "proxy": 0.05,  # Proxy issues (minor)
        }

    def _init_database(self):
        """Initialize risk monitoring database."""
        with self._get_connection() as conn:
            # Account risk scores table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS account_risk_scores (
                    phone_number TEXT PRIMARY KEY,
                    overall_score REAL NOT NULL,
                    risk_level TEXT NOT NULL,

                    floodwait_score REAL DEFAULT 0,
                    error_rate_score REAL DEFAULT 0,
                    activity_score REAL DEFAULT 0,
                    shadowban_score REAL DEFAULT 0,

                    total_floodwaits_24h INTEGER DEFAULT 0,
                    total_errors_24h INTEGER DEFAULT 0,
                    messages_sent_1h INTEGER DEFAULT 0,
                    last_floodwait TIMESTAMP,

                    recommended_actions TEXT,
                    should_quarantine INTEGER DEFAULT 0,

                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Risk events log
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone_number TEXT NOT NULL,
                    risk_factor TEXT NOT NULL,
                    severity REAL NOT NULL,
                    description TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY(phone_number) REFERENCES account_risk_scores(phone_number)
                )
            """
            )

            # Indexes
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_risk_level
                ON account_risk_scores(risk_level, overall_score DESC)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_risk_quarantine
                ON account_risk_scores(should_quarantine, updated_at DESC)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_risk_events_phone
                ON risk_events(phone_number, timestamp DESC)
            """
            )

            conn.commit()

    def calculate_risk_score(
        self,
        phone_number: str,
        floodwaits_24h: int = 0,
        errors_24h: int = 0,
        messages_1h: int = 0,
        has_shadowban: bool = False,
        proxy_failures: int = 0,
    ) -> AccountRiskScore:
        """
        Calculate comprehensive risk score for an account.

        Args:
            phone_number: Phone number
            floodwaits_24h: FloodWait count in last 24 hours
            errors_24h: Error count in last 24 hours
            messages_1h: Messages sent in last hour
            has_shadowban: Whether account is shadowbanned
            proxy_failures: Proxy failure count

        Returns:
            AccountRiskScore object
        """
        # Calculate component scores (0-100 scale)

        # FloodWait score (0-100)
        floodwait_score = min(100, floodwaits_24h * 25)  # 1 = 25, 2 = 50, 3 = 75, 4+ = 100

        # Error rate score (0-100)
        error_rate_score = min(100, errors_24h * 2)  # 50 errors = 100

        # Activity score based on message velocity (0-100)
        if messages_1h == 0:
            activity_score = 0
        elif messages_1h <= 10:
            activity_score = 10  # Normal
        elif messages_1h <= 20:
            activity_score = 30  # Elevated
        elif messages_1h <= 40:
            activity_score = 60  # High
        else:
            activity_score = 100  # Critical

        # Shadowban score (binary: 0 or 80)
        shadowban_score = 80 if has_shadowban else 0

        # Proxy score
        proxy_score = min(50, proxy_failures * 10)

        # Calculate weighted overall score
        overall_score = (
            self.weights["floodwait"] * floodwait_score
            + self.weights["error_rate"] * error_rate_score
            + self.weights["activity"] * activity_score
            + self.weights["shadowban"] * shadowban_score
            + self.weights["proxy"] * proxy_score
        )

        # Determine risk level
        if overall_score <= 20:
            risk_level = RiskLevel.SAFE
        elif overall_score <= 40:
            risk_level = RiskLevel.LOW
        elif overall_score <= 60:
            risk_level = RiskLevel.MEDIUM
        elif overall_score <= 80:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        # Generate recommendations
        recommendations = []
        should_quarantine = False

        if floodwait_score >= 75:
            recommendations.append(
                "🚨 Multiple FloodWaits detected - pause all campaigns on this account"
            )
            should_quarantine = True
        elif floodwait_score >= 50:
            recommendations.append(
                "⚠️ FloodWait activity elevated - reduce message frequency by 50%"
            )

        if error_rate_score >= 50:
            recommendations.append("📉 High error rate - check proxy and connection quality")

        if activity_score >= 60:
            recommendations.append("⚡ Activity too rapid - increase delays between messages")

        if shadowban_score > 0:
            recommendations.append("👻 Shadowban detected - stop all activity and investigate")
            should_quarantine = True

        if proxy_score >= 30:
            recommendations.append("🌐 Proxy instability - consider rotating proxy")

        if overall_score >= 80:
            recommendations.append("🛑 CRITICAL RISK - Immediately quarantine account")
            should_quarantine = True
        elif overall_score >= 60:
            recommendations.append("⚠️ HIGH RISK - Reduce activity and monitor closely")

        return AccountRiskScore(
            phone_number=phone_number,
            overall_score=round(overall_score, 2),
            risk_level=risk_level,
            floodwait_score=round(floodwait_score, 2),
            error_rate_score=round(error_rate_score, 2),
            activity_score=round(activity_score, 2),
            shadowban_score=round(shadowban_score, 2),
            total_floodwaits_24h=floodwaits_24h,
            total_errors_24h=errors_24h,
            messages_sent_1h=messages_1h,
            recommended_actions=recommendations,
            should_quarantine=should_quarantine,
        )

    def save_risk_score(self, score: AccountRiskScore) -> bool:
        """Save risk score to database."""
        try:
            with self._get_connection() as conn:
                import json

                conn.execute(
                    """
                    INSERT INTO account_risk_scores
                    (phone_number, overall_score, risk_level,
                     floodwait_score, error_rate_score, activity_score, shadowban_score,
                     total_floodwaits_24h, total_errors_24h, messages_sent_1h,
                     recommended_actions, should_quarantine, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(phone_number) DO UPDATE SET
                        overall_score = excluded.overall_score,
                        risk_level = excluded.risk_level,
                        floodwait_score = excluded.floodwait_score,
                        error_rate_score = excluded.error_rate_score,
                        activity_score = excluded.activity_score,
                        shadowban_score = excluded.shadowban_score,
                        total_floodwaits_24h = excluded.total_floodwaits_24h,
                        total_errors_24h = excluded.total_errors_24h,
                        messages_sent_1h = excluded.messages_sent_1h,
                        recommended_actions = excluded.recommended_actions,
                        should_quarantine = excluded.should_quarantine,
                        updated_at = excluded.updated_at
                """,
                    (
                        score.phone_number,
                        score.overall_score,
                        score.risk_level.value,
                        score.floodwait_score,
                        score.error_rate_score,
                        score.activity_score,
                        score.shadowban_score,
                        score.total_floodwaits_24h,
                        score.total_errors_24h,
                        score.messages_sent_1h,
                        json.dumps(score.recommended_actions),
                        1 if score.should_quarantine else 0,
                        datetime.now(),
                    ),
                )
                conn.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to save risk score: {e}")
            return False

    def log_risk_event(
        self, phone_number: str, risk_factor: RiskFactor, severity: float, description: str
    ) -> bool:
        """Log a risk event."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO risk_events
                    (phone_number, risk_factor, severity, description)
                    VALUES (?, ?, ?, ?)
                """,
                    (phone_number, risk_factor.value, severity, description),
                )
                conn.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to log risk event: {e}")
            return False

    def get_account_risk(self, phone_number: str) -> Optional[AccountRiskScore]:
        """Get current risk score for an account."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM account_risk_scores
                    WHERE phone_number = ?
                """,
                    (phone_number,),
                )

                row = cursor.fetchone()
                if not row:
                    return None

                import json

                return AccountRiskScore(
                    phone_number=row["phone_number"],
                    overall_score=row["overall_score"],
                    risk_level=RiskLevel(row["risk_level"]),
                    floodwait_score=row["floodwait_score"],
                    error_rate_score=row["error_rate_score"],
                    activity_score=row["activity_score"],
                    shadowban_score=row["shadowban_score"],
                    total_floodwaits_24h=row["total_floodwaits_24h"],
                    total_errors_24h=row["total_errors_24h"],
                    messages_sent_1h=row["messages_sent_1h"],
                    recommended_actions=(
                        json.loads(row["recommended_actions"]) if row["recommended_actions"] else []
                    ),
                    should_quarantine=bool(row["should_quarantine"]),
                    timestamp=datetime.fromisoformat(row["updated_at"]),
                )

        except Exception as e:
            logger.error(f"Failed to get account risk: {e}")
            return None

    def get_high_risk_accounts(
        self, min_risk_level: RiskLevel = RiskLevel.HIGH
    ) -> List[AccountRiskScore]:
        """Get all accounts at or above specified risk level."""
        risk_threshold = {
            RiskLevel.SAFE: 0,
            RiskLevel.LOW: 21,
            RiskLevel.MEDIUM: 41,
            RiskLevel.HIGH: 61,
            RiskLevel.CRITICAL: 81,
        }

        threshold = risk_threshold.get(min_risk_level, 61)
        accounts = []

        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM account_risk_scores
                    WHERE overall_score >= ?
                    ORDER BY overall_score DESC
                """,
                    (threshold,),
                )

                import json

                for row in cursor:
                    accounts.append(
                        AccountRiskScore(
                            phone_number=row["phone_number"],
                            overall_score=row["overall_score"],
                            risk_level=RiskLevel(row["risk_level"]),
                            floodwait_score=row["floodwait_score"],
                            error_rate_score=row["error_rate_score"],
                            activity_score=row["activity_score"],
                            shadowban_score=row["shadowban_score"],
                            total_floodwaits_24h=row["total_floodwaits_24h"],
                            total_errors_24h=row["total_errors_24h"],
                            messages_sent_1h=row["messages_sent_1h"],
                            recommended_actions=(
                                json.loads(row["recommended_actions"])
                                if row["recommended_actions"]
                                else []
                            ),
                            should_quarantine=bool(row["should_quarantine"]),
                            timestamp=datetime.fromisoformat(row["updated_at"]),
                        )
                    )

        except Exception as e:
            logger.error(f"Failed to get high risk accounts: {e}")

        return accounts

    def get_quarantine_candidates(self) -> List[AccountRiskScore]:
        """Get accounts that should be quarantined."""
        try:
            accounts = []

            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM account_risk_scores
                    WHERE should_quarantine = 1
                    ORDER BY overall_score DESC
                """
                )

                import json

                for row in cursor:
                    accounts.append(
                        AccountRiskScore(
                            phone_number=row["phone_number"],
                            overall_score=row["overall_score"],
                            risk_level=RiskLevel(row["risk_level"]),
                            recommended_actions=(
                                json.loads(row["recommended_actions"])
                                if row["recommended_actions"]
                                else []
                            ),
                            should_quarantine=True,
                            timestamp=datetime.fromisoformat(row["updated_at"]),
                        )
                    )

            return accounts

        except Exception as e:
            logger.error(f"Failed to get quarantine candidates: {e}")
            return []

    def get_risk_summary(self) -> Dict[str, Any]:
        """Get summary of risk across all accounts."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row

                # Count by risk level
                cursor = conn.execute(
                    """
                    SELECT risk_level, COUNT(*) as count
                    FROM account_risk_scores
                    GROUP BY risk_level
                """
                )

                by_level = {row["risk_level"]: row["count"] for row in cursor}

                # Total accounts
                cursor = conn.execute("SELECT COUNT(*) as total FROM account_risk_scores")
                total = cursor.fetchone()["total"]

                # Quarantine candidates
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM account_risk_scores WHERE should_quarantine = 1"
                )
                quarantine_count = cursor.fetchone()["count"]

                # Average score
                cursor = conn.execute("SELECT AVG(overall_score) as avg FROM account_risk_scores")
                avg_score = cursor.fetchone()["avg"] or 0

                return {
                    "total_accounts": total,
                    "safe": by_level.get("safe", 0),
                    "low": by_level.get("low", 0),
                    "medium": by_level.get("medium", 0),
                    "high": by_level.get("high", 0),
                    "critical": by_level.get("critical", 0),
                    "quarantine_candidates": quarantine_count,
                    "avg_risk_score": round(avg_score, 2),
                }

        except Exception as e:
            logger.error(f"Failed to get risk summary: {e}")
            return {
                "total_accounts": 0,
                "safe": 0,
                "low": 0,
                "medium": 0,
                "high": 0,
                "critical": 0,
                "quarantine_candidates": 0,
                "avg_risk_score": 0.0,
            }


# Singleton instance
_risk_monitor: Optional[AccountRiskMonitor] = None


def get_risk_monitor() -> AccountRiskMonitor:
    """Get singleton risk monitor."""
    global _risk_monitor
    if _risk_monitor is None:
        _risk_monitor = AccountRiskMonitor()
    return _risk_monitor
