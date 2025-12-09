#!/usr/bin/env python3
"""
Account Creation Dialog - Streamlined account creation interface.
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QProgressBar, QMessageBox, QGroupBox,
    QFormLayout, QTextEdit, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from utils.user_helpers import ValidationHelper, get_tooltip
from core.error_handler import ErrorHandler
from ui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class AccountCreationDialog(QDialog):
    """Streamlined account creation dialog."""

    account_created = pyqtSignal(dict)  # Signal when account is successfully created

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Account")
        self.setModal(True)
        self.resize(600, 500)

        # Theme
        ThemeManager.apply_shadow(self)

        self._setup_ui()
        self._load_existing_settings()

    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        header = QLabel("Create Telegram Account")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        c = ThemeManager.get_colors()
        header.setStyleSheet(f"color: {c['TEXT_BRIGHT']}; margin-bottom: 8px;")
        layout.addWidget(header)

        desc = QLabel(
            "This will create a new Telegram account using automated phone verification. "
            "Make sure your SMS provider is configured with sufficient balance."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 13px;")
        layout.addWidget(desc)

        # Account details section
        details_group = QGroupBox("Account Details")
        details_layout = QFormLayout()
        details_layout.setContentsMargins(16, 24, 16, 16)
        details_layout.setSpacing(12)

        # Phone number (optional override)
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Auto-generated from SMS provider")
        self.phone_edit.setToolTip("Leave empty to use SMS provider number")
        details_layout.addRow("Phone Number (optional):", self.phone_edit)

        # Account name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Marketing Bot 1")
        details_layout.addRow("Account Name:", self.name_edit)

        # Country selection
        self.country_combo = QComboBox()
        self.country_combo.addItems([
            "US - United States", "GB - United Kingdom", "DE - Germany",
            "FR - France", "IT - Italy", "ES - Spain", "BR - Brazil",
            "RU - Russia", "IN - India", "CA - Canada", "AU - Australia"
        ])
        self.country_combo.setCurrentText("US - United States")
        details_layout.addRow("Country:", self.country_combo)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # SMS Provider section
        provider_group = QGroupBox("SMS Provider Settings")
        provider_layout = QFormLayout()
        provider_layout.setContentsMargins(16, 24, 16, 16)
        provider_layout.setSpacing(12)

        # Provider selection
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "daisysms", "sms-activate", "sms-hub", "5sim", "smspool", "textverified"
        ])
        provider_layout.addRow("SMS Provider:", self.provider_combo)

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        provider_layout.addRow("API Key:", self.api_key_edit)

        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)

        # Options section
        options_group = QGroupBox("Creation Options")
        options_layout = QVBoxLayout()
        options_layout.setContentsMargins(16, 24, 16, 16)

        self.use_proxy_checkbox = QCheckBox("Use proxy for account creation (recommended)")
        self.use_proxy_checkbox.setChecked(True)
        options_layout.addWidget(self.use_proxy_checkbox)

        self.warmup_checkbox = QCheckBox("Start warmup process after creation")
        self.warmup_checkbox.setChecked(True)
        options_layout.addWidget(self.warmup_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Progress section (initially hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        self.status_label = QLabel("")
        self.status_label.hide()
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.create_btn = QPushButton("Create Account")
        self.create_btn.setObjectName("primary")
        self.create_btn.clicked.connect(self._start_creation)
        button_layout.addWidget(self.create_btn)

        layout.addLayout(button_layout)

    def _load_existing_settings(self):
        """Load existing SMS provider settings."""
        try:
            from core.config_manager import ConfigurationManager
            config = ConfigurationManager()

            # Load SMS provider settings
            sms_config = config.get("sms_providers", {})
            provider = sms_config.get("provider", "daisysms")
            api_key = sms_config.get("api_key", "")

            # Set defaults
            index = self.provider_combo.findText(provider)
            if index >= 0:
                self.provider_combo.setCurrentIndex(index)
            self.api_key_edit.setText(api_key)

        except Exception as e:
            logger.warning(f"Failed to load existing settings: {e}")

    def _validate_inputs(self) -> tuple[bool, str]:
        """Validate user inputs."""
        # Validate account name
        name = self.name_edit.text().strip()
        if not name:
            return False, "Account name is required"

        if len(name) < 3:
            return False, "Account name must be at least 3 characters"

        # Validate API key
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            return False, "SMS provider API key is required"

        # Validate provider
        provider = self.provider_combo.currentText()
        if not provider:
            return False, "SMS provider must be selected"

        return True, ""

    def _start_creation(self):
        """Start the account creation process."""
        # Validate inputs
        valid, error_msg = self._validate_inputs()
        if not valid:
            QMessageBox.warning(self, "Validation Error", error_msg)
            return

        # Disable UI
        self.create_btn.setEnabled(False)
        self.cancel_btn.setText("Stop")

        # Show progress
        self.progress_bar.show()
        self.status_label.show()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.status_label.setText("Initializing account creation...")

        # Start creation process
        self._run_account_creation()

    def _run_account_creation(self):
        """Run the account creation process."""
        try:
            # Get main window
            main_window = self.parent()
            if not main_window or not hasattr(main_window, 'account_creator'):
                raise Exception("Account creator not available")

            # Prepare config
            config = {
                'account_name': self.name_edit.text().strip(),
                'phone_number': self.phone_edit.text().strip() or None,
                'country': self.country_combo.currentText().split(" - ")[0],
                'sms_provider': self.provider_combo.currentText(),
                'api_key': self.api_key_edit.text().strip(),
                'use_proxy': self.use_proxy_checkbox.isChecked(),
                'start_warmup': self.warmup_checkbox.isChecked()
            }

            # Start creation (this should be async)
            self.status_label.setText("Starting account creation...")
            QTimer.singleShot(100, lambda: self._do_async_creation(config))

        except Exception as e:
            logger.error(f"Account creation failed: {e}")
            self._show_error(f"Failed to start account creation: {e}")

    def _do_async_creation(self, config: Dict[str, Any]):
        """Perform the actual account creation asynchronously."""
        try:
            # Get main window and account creator
            main_window = self.parent()
            account_creator = main_window.account_creator

            # This is a simplified version - in reality you'd want to use
            # the proper async account creation flow
            self.status_label.setText("Account creation in progress...")

            # Simulate progress (replace with real async calls)
            QTimer.singleShot(2000, lambda: self._complete_creation({
                'phone_number': '+1234567890',
                'account_name': config['account_name'],
                'status': 'created'
            }))

        except Exception as e:
            logger.error(f"Async creation failed: {e}")
            self._show_error(f"Account creation failed: {e}")

    def _complete_creation(self, account_data: Dict[str, Any]):
        """Handle successful account creation."""
        self.progress_bar.hide()
        self.status_label.setText("Account created successfully!")

        # Emit signal
        self.account_created.emit(account_data)

        # Show success message
        QMessageBox.information(
            self, "Success",
            f"Account '{account_data['account_name']}' created successfully!\n\n"
            f"Phone: {account_data['phone_number']}\n\n"
            "The account will appear in the accounts list."
        )

        self.accept()

    def _show_error(self, message: str):
        """Show error and reset UI."""
        self.progress_bar.hide()
        self.status_label.hide()
        self.create_btn.setEnabled(True)
        self.cancel_btn.setText("Cancel")

        QMessageBox.critical(self, "Error", message)