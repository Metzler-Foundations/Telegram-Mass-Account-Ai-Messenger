"""Comprehensive tests for secrets manager."""

import pytest
import os
import tempfile
from pathlib import Path
from core.secrets_manager import SecretsManager, get_secrets_manager


class TestSecretsManager:
    """Test secrets manager functionality."""

    def setup_method(self):
        """Setup for each test."""
        # Use temporary file for secrets
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".encrypted")
        self.temp_file.close()

    def teardown_method(self):
        """Cleanup after each test."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)

    def test_secret_storage_and_retrieval(self):
        """Test storing and retrieving secrets."""
        manager = SecretsManager(self.temp_file.name)

        # Store secret
        manager.set_secret("test_key", "test_value")

        # Retrieve secret
        value = manager.get_secret("test_key")
        assert value == "test_value"

    def test_secret_encryption(self):
        """Test secrets are encrypted on disk."""
        manager = SecretsManager(self.temp_file.name)

        manager.set_secret("password", "super_secret_123")

        # Read raw file content
        with open(self.temp_file.name, "rb") as f:
            encrypted_data = f.read()

        # Should not contain plaintext
        assert b"super_secret_123" not in encrypted_data
        assert len(encrypted_data) > 0

    def test_environment_variable_priority(self):
        """Test environment variables take priority."""
        manager = SecretsManager(self.temp_file.name)

        # Set environment variable FIRST
        os.environ["SECRET_API_KEY"] = "env_value"

        try:
            # Store in encrypted file
            manager.set_secret("api_key", "file_value")

            # Create NEW manager instance to bypass cache
            manager2 = SecretsManager(self.temp_file.name)

            # Should return env value (bypasses file)
            value = manager2.get_secret("api_key")
            assert value == "env_value"
        finally:
            del os.environ["SECRET_API_KEY"]

    def test_required_secret_missing(self):
        """Test required secret raises error if not found."""
        manager = SecretsManager(self.temp_file.name)

        with pytest.raises(ValueError, match="Required secret"):
            manager.get_secret("missing_key", required=True)

    def test_secret_deletion(self):
        """Test secret deletion."""
        manager = SecretsManager(self.temp_file.name)

        manager.set_secret("temp_key", "temp_value")
        assert manager.get_secret("temp_key") == "temp_value"

        deleted = manager.delete_secret("temp_key")
        assert deleted is True
        assert manager.get_secret("temp_key") is None

    def test_access_logging(self):
        """Test secret access is logged."""
        manager = SecretsManager(self.temp_file.name)

        manager.set_secret("logged_key", "value")
        manager.get_secret("logged_key")

        log = manager.get_access_log()
        assert len(log) > 0
        assert any(entry["key"] == "logged_key" for entry in log)

    def test_validate_secrets(self):
        """Test secret validation."""
        manager = SecretsManager(self.temp_file.name)

        # Set some required secrets
        manager.set_secret("telegram_api_id", "12345")
        manager.set_secret("telegram_api_hash", "abc123")

        status = manager.validate_secrets()
        assert status["telegram_api_id"] is True
        assert status["telegram_api_hash"] is True
        assert status["gemini_api_key"] is False  # Not set
