#!/usr/bin/env python3
"""Backup file encryption."""

import logging
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class BackupEncryption:
    """Encrypts backup files containing sensitive data."""

    @staticmethod
    def encrypt_backup(backup_path: str, key: bytes = None) -> bool:
        """Encrypt backup file."""
        try:
            if key is None:
                from core.secrets_manager import get_secrets_manager

                secrets = get_secrets_manager()
                key = secrets.get_secret("backup_encryption_key", required=False)

                if not key:
                    # Generate new key
                    key = Fernet.generate_key()
                    secrets.set_secret("backup_encryption_key", key.decode())
                else:
                    key = key.encode()

            fernet = Fernet(key)

            # Read backup file
            with open(backup_path, "rb") as f:
                data = f.read()

            # Encrypt
            encrypted = fernet.encrypt(data)

            # Write encrypted backup
            encrypted_path = f"{backup_path}.enc"
            with open(encrypted_path, "wb") as f:
                f.write(encrypted)

            # Remove unencrypted backup
            Path(backup_path).unlink()

            logger.info(f"Encrypted backup: {encrypted_path}")
            return True

        except Exception as e:
            logger.error(f"Backup encryption failed: {e}")
            return False

    @staticmethod
    def decrypt_backup(encrypted_path: str, output_path: str, key: bytes) -> bool:
        """Decrypt backup file."""
        try:
            fernet = Fernet(key)

            with open(encrypted_path, "rb") as f:
                encrypted = f.read()

            decrypted = fernet.decrypt(encrypted)

            with open(output_path, "wb") as f:
                f.write(decrypted)

            logger.info(f"Decrypted backup to: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Backup decryption failed: {e}")
            return False


def encrypt_backup_file(backup_path: str) -> bool:
    """Encrypt backup file."""
    return BackupEncryption.encrypt_backup(backup_path)
