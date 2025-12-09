#!/usr/bin/env python3
"""Webhook signature verification."""

import hmac
import hashlib
import logging

logger = logging.getLogger(__name__)


class WebhookVerifier:
    """Verifies webhook signatures."""

    def __init__(self, secret_key: bytes):
        self.secret_key = secret_key

    def generate_signature(self, payload: bytes) -> str:
        """Generate HMAC signature for payload."""
        signature = hmac.new(self.secret_key, payload, hashlib.sha256).hexdigest()
        return signature

    def verify_signature(self, payload: bytes, provided_signature: str) -> bool:
        """Verify webhook signature."""
        expected_signature = self.generate_signature(payload)
        return hmac.compare_digest(expected_signature, provided_signature)


def get_webhook_verifier(secret: str):
    return WebhookVerifier(secret.encode("utf-8"))
