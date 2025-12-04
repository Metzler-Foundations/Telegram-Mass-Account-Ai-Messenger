"""
Cost Alert System - Monitor costs and send alerts when thresholds exceeded.

Features:
- Real-time cost tracking from audit logs
- Configurable cost thresholds
- Daily/weekly/monthly budget alerts
- Per-provider cost monitoring
- Alert notifications to operators
- Cost trend analysis
"""

import logging
import sqlite3
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class CostPeriod(Enum):
    """Cost tracking periods."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ALL_TIME = "all_time"


@dataclass
class CostAlert:
    """Cost alert data."""
    alert_id: Optional[int]
    alert_level: AlertLevel
    period: CostPeriod
    threshold: float
    current_cost: float
    provider: Optional[str]
    message: str
    timestamp: datetime
    acknowledged: bool = False


class CostAlertSystem:
    """
    Monitor costs from audit logs and alert when thresholds exceeded.
    """
    
    def __init__(self, audit_db_path: str = "accounts_audit.db"):
        """Initialize cost alert system."""
        self.audit_db_path = audit_db_path
        self.alerts_db_path = "cost_alerts.db"
        self._init_database()
        
        # Alert thresholds (USD)
        self.thresholds = {
            CostPeriod.DAILY: {
                'warning': 50.0,
                'critical': 100.0
            },
            CostPeriod.WEEKLY: {
                'warning': 200.0,
                'critical': 500.0
            },
            CostPeriod.MONTHLY: {
                'warning': 500.0,
                'critical': 1000.0
            }
        }
        
        # Per-provider limits
        self.provider_thresholds = {
            'smspool': 100.0,
            'textverified': 100.0,
            'sms-activate': 100.0,
            'sms-hub': 75.0,
            '5sim': 100.0,
            'daisysms': 75.0
        }
        
        # Notification callbacks
        self.notification_callbacks: List[Callable] = []
        
        # Alert cooldown (don't repeat same alert within this period)
        self.alert_cooldown = timedelta(hours=1)
        self._recent_alerts: Dict[str, datetime] = {}
    
    def _init_database(self):
        """Initialize alerts database."""
        with sqlite3.connect(self.alerts_db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cost_alerts (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_level TEXT NOT NULL,
                    period TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    current_cost REAL NOT NULL,
                    provider TEXT,
                    message TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    acknowledged INTEGER DEFAULT 0
                )
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_level 
                ON cost_alerts(alert_level, timestamp DESC)
            ''')
            
            conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_alerts_acknowledged 
                ON cost_alerts(acknowledged, timestamp DESC)
            ''')
            
            conn.commit()
    
    def add_notification_callback(self, callback: Callable):
        """Add callback for alert notifications."""
        self.notification_callbacks.append(callback)
    
    def check_costs(self) -> List[CostAlert]:
        """
        Check costs against thresholds and generate alerts.
        
        Returns:
            List of new alerts
        """
        alerts = []
        
        try:
            # Check overall costs by period
            for period in [CostPeriod.DAILY, CostPeriod.WEEKLY, CostPeriod.MONTHLY]:
                current_cost = self._get_period_cost(period)
                thresholds = self.thresholds.get(period, {})
                
                # Check warning threshold
                if current_cost >= thresholds.get('warning', float('inf')):
                    level = AlertLevel.WARNING
                    threshold = thresholds['warning']
                    
                    # Upgrade to critical if exceeded
                    if current_cost >= thresholds.get('critical', float('inf')):
                        level = AlertLevel.CRITICAL
                        threshold = thresholds['critical']
                    
                    # Check cooldown
                    alert_key = f"{period.value}_{level.value}"
                    if alert_key in self._recent_alerts:
                        last_alert = self._recent_alerts[alert_key]
                        if datetime.now() - last_alert < self.alert_cooldown:
                            continue  # Skip due to cooldown
                    
                    # Create alert
                    alert = CostAlert(
                        alert_id=None,
                        alert_level=level,
                        period=period,
                        threshold=threshold,
                        current_cost=current_cost,
                        provider=None,
                        message=f"{period.value.title()} cost ${current_cost:.2f} exceeded {level.value} threshold ${threshold:.2f}",
                        timestamp=datetime.now()
                    )
                    
                    alerts.append(alert)
                    self._recent_alerts[alert_key] = datetime.now()
            
            # Check per-provider costs
            provider_costs = self._get_provider_costs()
            
            for provider, cost in provider_costs.items():
                threshold = self.provider_thresholds.get(provider, 100.0)
                
                if cost >= threshold:
                    alert_key = f"provider_{provider}_critical"
                    if alert_key in self._recent_alerts:
                        last_alert = self._recent_alerts[alert_key]
                        if datetime.now() - last_alert < self.alert_cooldown:
                            continue
                    
                    alert = CostAlert(
                        alert_id=None,
                        alert_level=AlertLevel.CRITICAL,
                        period=CostPeriod.ALL_TIME,
                        threshold=threshold,
                        current_cost=cost,
                        provider=provider,
                        message=f"Provider {provider} total cost ${cost:.2f} exceeded limit ${threshold:.2f}",
                        timestamp=datetime.now()
                    )
                    
                    alerts.append(alert)
                    self._recent_alerts[alert_key] = datetime.now()
            
            # Save and notify
            for alert in alerts:
                self._save_alert(alert)
                self._notify_operators(alert)
            
            return alerts
            
        except Exception as e:
            logger.error(f"Failed to check costs: {e}")
            return []
    
    def _get_period_cost(self, period: CostPeriod) -> float:
        """Get total cost for a period."""
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                if period == CostPeriod.DAILY:
                    cutoff = datetime.now() - timedelta(days=1)
                elif period == CostPeriod.WEEKLY:
                    cutoff = datetime.now() - timedelta(days=7)
                elif period == CostPeriod.MONTHLY:
                    cutoff = datetime.now() - timedelta(days=30)
                else:
                    cutoff = datetime(2000, 1, 1)
                
                cursor = conn.execute('''
                    SELECT SUM(sms_cost) as total
                    FROM audit_events
                    WHERE sms_cost IS NOT NULL AND timestamp >= ?
                ''', (cutoff,))
                
                row = cursor.fetchone()
                return row[0] or 0.0
                
        except Exception as e:
            logger.error(f"Failed to get period cost: {e}")
            return 0.0
    
    def _get_provider_costs(self) -> Dict[str, float]:
        """Get costs grouped by provider."""
        try:
            with sqlite3.connect(self.audit_db_path) as conn:
                cursor = conn.execute('''
                    SELECT sms_provider, SUM(sms_cost) as total
                    FROM audit_events
                    WHERE sms_cost IS NOT NULL
                    GROUP BY sms_provider
                ''')
                
                return {row[0]: row[1] for row in cursor if row[0]}
                
        except Exception as e:
            logger.error(f"Failed to get provider costs: {e}")
            return {}
    
    def _save_alert(self, alert: CostAlert):
        """Save alert to database."""
        try:
            with sqlite3.connect(self.alerts_db_path) as conn:
                conn.execute('''
                    INSERT INTO cost_alerts
                    (alert_level, period, threshold, current_cost, provider, message)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    alert.alert_level.value,
                    alert.period.value,
                    alert.threshold,
                    alert.current_cost,
                    alert.provider,
                    alert.message
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save alert: {e}")
    
    def _notify_operators(self, alert: CostAlert):
        """Send alert to operators."""
        logger.warning(f"💰 COST ALERT ({alert.alert_level.value.upper()}): {alert.message}")
        
        for callback in self.notification_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.warning(f"Alert callback failed: {e}")
    
    def get_unacknowledged_alerts(self) -> List[CostAlert]:
        """Get all unacknowledged alerts."""
        alerts = []
        
        try:
            with sqlite3.connect(self.alerts_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT * FROM cost_alerts
                    WHERE acknowledged = 0
                    ORDER BY timestamp DESC
                ''')
                
                for row in cursor:
                    alerts.append(CostAlert(
                        alert_id=row['alert_id'],
                        alert_level=AlertLevel(row['alert_level']),
                        period=CostPeriod(row['period']),
                        threshold=row['threshold'],
                        current_cost=row['current_cost'],
                        provider=row['provider'],
                        message=row['message'],
                        timestamp=datetime.fromisoformat(row['timestamp']),
                        acknowledged=False
                    ))
                    
        except Exception as e:
            logger.error(f"Failed to get unacknowledged alerts: {e}")
        
        return alerts
    
    def acknowledge_alert(self, alert_id: int) -> bool:
        """Mark alert as acknowledged."""
        try:
            with sqlite3.connect(self.alerts_db_path) as conn:
                conn.execute('''
                    UPDATE cost_alerts
                    SET acknowledged = 1
                    WHERE alert_id = ?
                ''', (alert_id,))
                conn.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to acknowledge alert: {e}")
            return False


# Singleton
_cost_alert_system: Optional[CostAlertSystem] = None


def get_cost_alert_system() -> CostAlertSystem:
    """Get singleton cost alert system."""
    global _cost_alert_system
    if _cost_alert_system is None:
        _cost_alert_system = CostAlertSystem()
    return _cost_alert_system



