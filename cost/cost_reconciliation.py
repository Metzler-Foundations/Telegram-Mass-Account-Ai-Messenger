#!/usr/bin/env python3
"""Cost tracking reconciliation with actual charges."""

import logging
from datetime import datetime
from typing import Dict

logger = logging.getLogger(__name__)


class CostReconciliation:
    """Reconciles tracked costs with actual provider charges."""

    def __init__(self, db_path: str = "database.db"):
        self.db_path = db_path

    def get_tracked_costs(self, provider: str, start_date: str, end_date: str) -> float:
        """Get costs tracked in database."""
        try:
            from database.connection_pool import get_pool

            pool = get_pool(self.db_path)
            with pool.get_connection() as conn:
                result = conn.execute(
                    """
                    SELECT SUM(cost) as total
                    FROM account_costs
                    WHERE provider = ?
                    AND created_at BETWEEN ? AND ?
                """,
                    (provider, start_date, end_date),
                ).fetchone()

                return result["total"] if result["total"] else 0.0
        except Exception as e:
            logger.error(f"Failed to get tracked costs: {e}")
            return 0.0

    def reconcile(
        self, provider: str, actual_charge: float, start_date: str, end_date: str
    ) -> Dict:
        """Reconcile tracked costs with actual charges."""
        tracked = self.get_tracked_costs(provider, start_date, end_date)
        difference = actual_charge - tracked
        variance_pct = (difference / actual_charge * 100) if actual_charge > 0 else 0.0

        reconciliation = {
            "provider": provider,
            "period": f"{start_date} to {end_date}",
            "tracked_cost": round(tracked, 2),
            "actual_charge": round(actual_charge, 2),
            "difference": round(difference, 2),
            "variance_percentage": round(variance_pct, 2),
            "status": "MATCH" if abs(variance_pct) < 5 else "MISMATCH",
            "reconciled_at": datetime.now().isoformat(),
        }

        if abs(variance_pct) >= 5:
            logger.warning(f"Cost mismatch for {provider}: {variance_pct:.1f}% variance")
        else:
            logger.info(f"Costs reconciled for {provider}: {variance_pct:.1f}% variance")

        # Store reconciliation record
        self._store_reconciliation(reconciliation)

        return reconciliation

    def _store_reconciliation(self, record: Dict):
        """Store reconciliation record."""
        try:
            from database.connection_pool import get_pool

            pool = get_pool(self.db_path)
            with pool.get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO cost_reconciliations
                    (provider, period, tracked_cost, actual_charge, difference,
                     variance_percentage, status, reconciled_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        record["provider"],
                        record["period"],
                        record["tracked_cost"],
                        record["actual_charge"],
                        record["difference"],
                        record["variance_percentage"],
                        record["status"],
                        record["reconciled_at"],
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to store reconciliation: {e}")


def reconcile_provider_costs(
    provider: str, actual_charge: float, start_date: str, end_date: str
) -> Dict:
    """Reconcile costs for provider."""
    reconciler = CostReconciliation()
    return reconciler.reconcile(provider, actual_charge, start_date, end_date)
