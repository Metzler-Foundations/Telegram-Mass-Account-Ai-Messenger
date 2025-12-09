#!/usr/bin/env python3
"""Prometheus metrics collection."""

import logging

from prometheus_client import Counter, Gauge, Histogram, start_http_server

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects application metrics for Prometheus."""

    def __init__(self):
        # Counters
        self.accounts_created = Counter("accounts_created_total", "Total accounts created")
        self.messages_sent = Counter("messages_sent_total", "Total messages sent")
        self.errors = Counter("errors_total", "Total errors", ["error_type"])

        # Histograms
        self.message_send_duration = Histogram(
            "message_send_duration_seconds", "Message send duration"
        )
        self.api_call_duration = Histogram(
            "api_call_duration_seconds", "API call duration", ["endpoint"]
        )

        # Gauges
        self.active_accounts = Gauge("active_accounts", "Number of active accounts")
        self.proxy_pool_size = Gauge("proxy_pool_size", "Proxy pool size")
        self.db_size_mb = Gauge("database_size_mb", "Database size in MB")

        logger.info("Metrics collector initialized")

    def start_server(self, port: int = 9090):
        """Start Prometheus metrics server."""
        try:
            start_http_server(port)
            logger.info(f"Prometheus metrics server started on port {port}")
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")


_metrics = None


def get_metrics():
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
