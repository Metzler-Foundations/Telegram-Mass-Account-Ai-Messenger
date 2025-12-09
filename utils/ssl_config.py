#!/usr/bin/env python3
"""SSL/TLS configuration and hardening."""

import ssl
import logging

logger = logging.getLogger(__name__)


class SSLConfig:
    """Secure SSL/TLS configuration."""

    @staticmethod
    def create_secure_context() -> ssl.SSLContext:
        """Create secure SSL context with hardened settings."""
        context = ssl.create_default_context()

        # Enforce TLS 1.2 minimum
        context.minimum_version = ssl.TLSVersion.TLSv1_2

        # Disable insecure protocols
        context.options |= ssl.OP_NO_SSLv2
        context.options |= ssl.OP_NO_SSLv3
        context.options |= ssl.OP_NO_TLSv1
        context.options |= ssl.OP_NO_TLSv1_1

        # Enable certificate verification
        context.check_hostname = True
        context.verify_mode = ssl.CERT_REQUIRED

        logger.info("Created secure SSL context (TLS 1.2+)")
        return context

    @staticmethod
    def get_secure_ciphers() -> str:
        """Get secure cipher suite."""
        return "ECDHE+AESGCM:" "ECDHE+CHACHA20:" "DHE+AESGCM:" "DHE+CHACHA20:" "!aNULL:!MD5:!DSS"


def get_ssl_context():
    return SSLConfig.create_secure_context()
