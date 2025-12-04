#!/usr/bin/env python3
"""Confirmation dialogs for destructive operations."""

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt


class ConfirmationDialog:
    """Confirmation dialogs for critical actions."""
    
    @staticmethod
    def confirm_delete(parent, item_name: str) -> bool:
        """Confirm deletion."""
        reply = QMessageBox.question(
            parent,
            'Confirm Deletion',
            f'Are you sure you want to delete "{item_name}"?\n\nThis action cannot be undone.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    @staticmethod
    def confirm_campaign_start(parent, account_count: int, message_count: int) -> bool:
        """Confirm campaign start."""
        reply = QMessageBox.question(
            parent,
            'Start Campaign',
            f'Start campaign with {account_count} accounts sending {message_count} messages?\n\n'
            f'This will consume API quota and may incur costs.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes
    
    @staticmethod
    def confirm_account_deletion(parent, account_count: int) -> bool:
        """Confirm account deletion."""
        reply = QMessageBox.warning(
            parent,
            'Delete Accounts',
            f'Delete {account_count} account(s)?\n\n'
            f'Session files and data will be permanently removed.',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

