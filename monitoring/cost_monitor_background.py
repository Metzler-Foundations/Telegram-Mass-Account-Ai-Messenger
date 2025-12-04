"""
Cost Monitor Background Service - Continuously monitor costs and trigger alerts.

Features:
- Background task that runs cost checks periodically
- Integrates with audit logs
- Triggers cost alert system
- Can be started with main application
"""

import logging
import asyncio
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CostMonitorBackgroundService:
    """Background service for continuous cost monitoring."""
    
    def __init__(self, check_interval_hours: int = 1):
        """
        Initialize cost monitor background service.
        
        Args:
            check_interval_hours: Hours between cost checks (default: 1 hour)
        """
        self.check_interval_hours = check_interval_hours
        self.is_running = False
        self._monitor_task: Optional[asyncio.Task] = None
        self._cost_alert_system = None
    
    async def start(self):
        """Start the background monitoring service."""
        if self.is_running:
            logger.warning("Cost monitor already running")
            return
        
        # Initialize cost alert system
        try:
            from monitoring.cost_alert_system import get_cost_alert_system
            self._cost_alert_system = get_cost_alert_system()
            logger.info("✓ Cost alert system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize cost alert system: {e}")
            return
        
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info(f"🚀 Started cost monitoring (checking every {self.check_interval_hours}h)")
    
    async def stop(self):
        """Stop the monitoring service."""
        self.is_running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Stopped cost monitoring")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.is_running:
            try:
                # Run cost check
                alerts = self._cost_alert_system.check_costs()
                
                if alerts:
                    logger.warning(f"💰 Generated {len(alerts)} cost alert(s)")
                    for alert in alerts:
                        logger.warning(
                            f"  {alert.alert_level.value.upper()}: {alert.message}"
                        )
                else:
                    logger.debug(f"✓ Cost check passed at {datetime.now()}")
                
                # Wait for next check
                await asyncio.sleep(self.check_interval_hours * 3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cost monitoring error: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error


# Singleton
_monitor_service: Optional[CostMonitorBackgroundService] = None


def get_cost_monitor_service(check_interval_hours: int = 1) -> CostMonitorBackgroundService:
    """Get singleton cost monitor service."""
    global _monitor_service
    if _monitor_service is None:
        _monitor_service = CostMonitorBackgroundService(check_interval_hours)
    return _monitor_service


async def start_cost_monitoring(check_interval_hours: int = 1):
    """Start cost monitoring service."""
    service = get_cost_monitor_service(check_interval_hours)
    await service.start()
    return service



