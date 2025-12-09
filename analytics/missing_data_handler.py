#!/usr/bin/env python3
"""Handle missing data gracefully in analytics dashboard."""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class MissingDataHandler:
    """Handles missing or incomplete data in analytics with comprehensive strategies."""

    @staticmethod
    def fill_missing_dates(
        data: List[Dict], date_key: str = "date", value_key: str = "count", fill_value: Any = 0
    ) -> List[Dict]:
        """Fill missing dates in time series data with validation."""
        if not data:
            logger.debug("No data to fill")
            return []

        if not isinstance(data, list):
            logger.error(f"Expected list, got {type(data)}")
            return []

        # Sort by date safely
        try:
            sorted_data = sorted(data, key=lambda x: x.get(date_key, ""))
        except Exception as e:
            logger.error(f"Error sorting data: {e}")
            return data

        if len(sorted_data) < 2:
            return sorted_data

        # Fill gaps with error handling
        filled = []
        try:
            from utils.datetime_validator import DateTimeValidator

            start = DateTimeValidator.safe_parse(sorted_data[0].get(date_key))
            end = DateTimeValidator.safe_parse(sorted_data[-1].get(date_key))

            if not start or not end:
                logger.warning("Could not parse start/end dates")
                return sorted_data

            current = start
            data_idx = 0

            while current <= end:
                date_str = current.isoformat()

                if data_idx < len(sorted_data) and sorted_data[data_idx].get(date_key) == date_str:
                    filled.append(sorted_data[data_idx])
                    data_idx += 1
                else:
                    filled.append({date_key: date_str, value_key: fill_value})

                current += timedelta(days=1)

            logger.debug(f"Filled {len(filled) - len(sorted_data)} missing dates")
            return filled

        except Exception as e:
            logger.error(f"Error filling missing dates: {e}")
            return sorted_data

    @staticmethod
    def get_with_default(data: Dict, key: str, default: Any = None) -> Any:
        """Get value with default fallback."""
        value = data.get(key, default)
        if value is None or value == "":
            return default
        return value

    @staticmethod
    def compute_missing_metrics(campaign_data: Dict) -> Dict:
        """Compute missing metrics from available data with validation."""
        if not isinstance(campaign_data, dict):
            logger.error(f"Expected dict, got {type(campaign_data)}")
            return {}

        metrics = campaign_data.copy()

        try:
            # Compute delivery rate if missing
            if "delivery_rate" not in metrics:
                sent = int(metrics.get("messages_sent", 0))
                delivered = int(metrics.get("messages_delivered", 0))
                if sent > 0:
                    metrics["delivery_rate"] = round((delivered / sent) * 100, 2)
                else:
                    metrics["delivery_rate"] = 0.0

            # Compute response rate if missing
            if "response_rate" not in metrics:
                delivered = int(metrics.get("messages_delivered", 0))
                responses = int(metrics.get("responses_received", 0))
                if delivered > 0:
                    metrics["response_rate"] = round((responses / delivered) * 100, 2)
                else:
                    metrics["response_rate"] = 0.0

            # Compute read rate if missing
            if "read_rate" not in metrics:
                delivered = int(metrics.get("messages_delivered", 0))
                read = int(metrics.get("messages_read", 0))
                if delivered > 0:
                    metrics["read_rate"] = round((read / delivered) * 100, 2)
                else:
                    metrics["read_rate"] = 0.0

            # Compute error rate if missing
            if "error_rate" not in metrics:
                sent = int(metrics.get("messages_sent", 0))
                failed = int(metrics.get("messages_failed", 0))
                if sent > 0:
                    metrics["error_rate"] = round((failed / sent) * 100, 2)
                else:
                    metrics["error_rate"] = 0.0

            # Add timestamps if missing
            if "last_updated" not in metrics:
                metrics["last_updated"] = datetime.now().isoformat()

            # Ensure numeric values are valid
            for key in ["delivery_rate", "response_rate", "read_rate", "error_rate"]:
                if key in metrics:
                    try:
                        metrics[key] = float(metrics[key])
                        # Cap at 100%
                        if metrics[key] > 100.0:
                            logger.warning(f"{key} > 100%, capping at 100")
                            metrics[key] = 100.0
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid {key} value: {metrics[key]}, setting to 0")
                        metrics[key] = 0.0

        except Exception as e:
            logger.error(f"Error computing missing metrics: {e}")

        return metrics

    @staticmethod
    def interpolate_missing_values(data: List[Dict], key: str) -> List[Dict]:
        """Interpolate missing values in time series."""
        if not data or len(data) < 2:
            return data

        result = []
        for i, item in enumerate(data):
            if key not in item or item[key] is None:
                # Try to interpolate
                prev_val = None
                next_val = None

                # Find previous valid value
                for j in range(i - 1, -1, -1):
                    if key in data[j] and data[j][key] is not None:
                        prev_val = data[j][key]
                        break

                # Find next valid value
                for j in range(i + 1, len(data)):
                    if key in data[j] and data[j][key] is not None:
                        next_val = data[j][key]
                        break

                # Interpolate
                if prev_val is not None and next_val is not None:
                    item[key] = (prev_val + next_val) / 2
                elif prev_val is not None:
                    item[key] = prev_val
                elif next_val is not None:
                    item[key] = next_val
                else:
                    item[key] = 0

            result.append(item)

        return result


def handle_missing_data(data: Any, default: Any = None) -> Any:
    """General purpose missing data handler."""
    return data if data is not None else default
