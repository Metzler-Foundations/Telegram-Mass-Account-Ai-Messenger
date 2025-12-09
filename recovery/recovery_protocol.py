"""
Recovery Protocol - Automated recovery from restrictions and bans.

Features:
- Automatic cooldown periods
- Activity reduction protocols
- Account rehabilitation strategies
- Progressive recovery steps
"""

import asyncio
import logging
import sqlite3
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class RecoveryStage(Enum):
    """Recovery stages."""

    INITIAL_COOLDOWN = "initial_cooldown"
    REDUCED_ACTIVITY = "reduced_activity"
    GRADUAL_INCREASE = "gradual_increase"
    MONITORING = "monitoring"
    RECOVERED = "recovered"


@dataclass
class RecoveryPlan:
    """Recovery plan for an account."""

    account_id: str
    stage: RecoveryStage
    cooldown_until: datetime
    activity_limit: int  # Messages per day
    started_at: datetime
    estimated_recovery: datetime


class RecoveryProtocol:
    """Automated account recovery system."""

    def __init__(self, db_path: str = "recovery_plans.db"):
        """Initialize."""
        self.db_path = db_path
        self._connection_pool = None
        try:
            from database.connection_pool import get_pool

            self._connection_pool = get_pool(self.db_path)
        except:
            pass
        self._init_database()

    def _get_connection(self):
        if self._connection_pool:
            return self._connection_pool.get_connection()
        return self._get_connection()

    def _init_database(self):
        """Initialize recovery database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_plans (
                account_id TEXT PRIMARY KEY,
                stage TEXT,
                cooldown_until TIMESTAMP,
                activity_limit INTEGER,
                started_at TIMESTAMP,
                estimated_recovery TIMESTAMP,
                last_updated TIMESTAMP
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS recovery_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                action TEXT,
                stage TEXT,
                timestamp TIMESTAMP,
                notes TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def initiate_recovery(self, account_id: str, severity: str = "moderate") -> RecoveryPlan:
        """Initiate recovery protocol for an account.

        Args:
            account_id: Account ID
            severity: Severity level (mild, moderate, severe)

        Returns:
            RecoveryPlan
        """
        now = datetime.now()

        # Set cooldown and limits based on severity
        if severity == "severe":
            cooldown_hours = 72
            activity_limit = 5
            recovery_days = 14
        elif severity == "moderate":
            cooldown_hours = 48
            activity_limit = 10
            recovery_days = 7
        else:  # mild
            cooldown_hours = 24
            activity_limit = 20
            recovery_days = 3

        plan = RecoveryPlan(
            account_id=account_id,
            stage=RecoveryStage.INITIAL_COOLDOWN,
            cooldown_until=now + timedelta(hours=cooldown_hours),
            activity_limit=activity_limit,
            started_at=now,
            estimated_recovery=now + timedelta(days=recovery_days),
        )

        self._save_plan(plan)
        self._log_action(account_id, "recovery_initiated", plan.stage, f"Severity: {severity}")

        logger.info(f"Recovery protocol initiated for {account_id}: {severity} severity")
        return plan

    def _save_plan(self, plan: RecoveryPlan):
        """Save recovery plan to database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO recovery_plans
            (account_id, stage, cooldown_until, activity_limit, started_at,
             estimated_recovery, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                plan.account_id,
                plan.stage.value,
                plan.cooldown_until,
                plan.activity_limit,
                plan.started_at,
                plan.estimated_recovery,
                datetime.now(),
            ),
        )
        conn.commit()
        conn.close()

    def _log_action(self, account_id: str, action: str, stage: RecoveryStage, notes: str = ""):
        """Log recovery action."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO recovery_log (account_id, action, stage, timestamp, notes)
            VALUES (?, ?, ?, ?, ?)
        """,
            (account_id, action, stage.value, datetime.now(), notes),
        )
        conn.commit()
        conn.close()

    def check_and_advance(self, account_id: str) -> Optional[RecoveryPlan]:
        """Check and advance recovery stage if appropriate.

        Args:
            account_id: Account ID

        Returns:
            Updated RecoveryPlan or None
        """
        plan = self.get_plan(account_id)
        if not plan:
            return None

        now = datetime.now()

        # Check if can advance stage
        if plan.stage == RecoveryStage.INITIAL_COOLDOWN:
            if now >= plan.cooldown_until:
                plan.stage = RecoveryStage.REDUCED_ACTIVITY
                plan.activity_limit = int(plan.activity_limit * 1.5)
                self._save_plan(plan)
                self._log_action(account_id, "stage_advanced", plan.stage)
                logger.info(f"{account_id} advanced to REDUCED_ACTIVITY")

        elif plan.stage == RecoveryStage.REDUCED_ACTIVITY:
            # Check time passed (e.g., 3 days)
            if (now - plan.started_at).days >= 3:
                plan.stage = RecoveryStage.GRADUAL_INCREASE
                plan.activity_limit = int(plan.activity_limit * 2)
                self._save_plan(plan)
                self._log_action(account_id, "stage_advanced", plan.stage)
                logger.info(f"{account_id} advanced to GRADUAL_INCREASE")

        elif plan.stage == RecoveryStage.GRADUAL_INCREASE:
            if (now - plan.started_at).days >= 7:
                plan.stage = RecoveryStage.MONITORING
                plan.activity_limit = int(plan.activity_limit * 1.5)
                self._save_plan(plan)
                self._log_action(account_id, "stage_advanced", plan.stage)
                logger.info(f"{account_id} advanced to MONITORING")

        elif plan.stage == RecoveryStage.MONITORING:
            if now >= plan.estimated_recovery:
                plan.stage = RecoveryStage.RECOVERED
                self._save_plan(plan)
                self._log_action(account_id, "recovery_complete", plan.stage)
                logger.info(f"{account_id} recovery COMPLETE")

        return plan

    def get_plan(self, account_id: str) -> Optional[RecoveryPlan]:
        """Get recovery plan for account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM recovery_plans WHERE account_id = ?
        """,
            (account_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return RecoveryPlan(
            account_id=row[0],
            stage=RecoveryStage(row[1]),
            cooldown_until=datetime.fromisoformat(row[2]),
            activity_limit=row[3],
            started_at=datetime.fromisoformat(row[4]),
            estimated_recovery=datetime.fromisoformat(row[5]),
        )

    def can_send_message(self, account_id: str) -> Tuple[bool, str]:
        """Check if account can send a message.

        Returns:
            (can_send, reason) tuple
        """
        plan = self.get_plan(account_id)

        if not plan:
            return True, "No recovery plan"

        if plan.stage == RecoveryStage.RECOVERED:
            return True, "Recovered"

        if plan.stage == RecoveryStage.INITIAL_COOLDOWN:
            if datetime.now() < plan.cooldown_until:
                remaining = (plan.cooldown_until - datetime.now()).total_seconds() / 3600
                return False, f"In cooldown ({remaining:.1f}h remaining)"

        # Check activity limit (simplified - would need actual tracking)
        return True, f"Activity limit: {plan.activity_limit}/day"

    def get_accounts_in_recovery(self) -> Dict[str, RecoveryPlan]:
        """Get all accounts currently in recovery."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM recovery_plans WHERE stage != 'recovered'
        """
        )

        plans = {}
        for row in cursor.fetchall():
            plan = RecoveryPlan(
                account_id=row[0],
                stage=RecoveryStage(row[1]),
                cooldown_until=datetime.fromisoformat(row[2]),
                activity_limit=row[3],
                started_at=datetime.fromisoformat(row[4]),
                estimated_recovery=datetime.fromisoformat(row[5]),
            )
            plans[plan.account_id] = plan

        conn.close()
        return plans
