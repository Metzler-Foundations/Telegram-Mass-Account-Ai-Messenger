#!/usr/bin/env python3
"""
Welcome Wizard - First-time setup guide for new users
Provides step-by-step onboarding experience with a clean, professional UI.
"""

import logging
import webbrowser
from pathlib import Path
from typing import Dict, Any

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QWizard, QWizardPage, QCheckBox, QMessageBox,
    QFrame, QGroupBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPixmap

from user_helpers import ValidationHelper, get_tooltip

logger = logging.getLogger(__name__)


class WelcomeWizard(QWizard):
    """Welcome wizard for first-time setup."""
    
    config_completed = pyqtSignal(dict)
    skipped = pyqtSignal()  # Signal emitted when user skips wizard
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup - Telegram Automation Platform")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        # Ensure navigation buttons are visible
        self.setOption(QWizard.WizardOption.NoCancelButton, False)
        self.resize(800, 600)  # More compact default size
        
        # Apply theme
        try:
            from ui_redesign import DISCORD_THEME
            self.setStyleSheet(DISCORD_THEME)
        except ImportError:
            pass
        
        # Add custom skip button
        self.setButtonText(QWizard.WizardButton.CustomButton1, "I Already Have Credentials →")
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        self.customButtonClicked.connect(self._handle_skip)
        
        # Add pages
        self.addPage(IntroPage())
        self.addPage(TelegramSetupPage())
        self.addPage(GeminiSetupPage())
        self.addPage(FeaturesPage())
        self.addPage(CompletePage())
        
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self.on_finish)
    
    def _handle_skip(self, button_id):
        """Handle skip button click."""
        if button_id == QWizard.WizardButton.CustomButton1:
            reply = QMessageBox.question(
                self,
                "Skip Setup Wizard",
                "Are you sure you want to skip the setup wizard?\n\n"
                "You can configure settings later from the Settings menu.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Mark setup as skipped
                import os
                setup_path = os.path.join(os.getcwd(), ".setup_complete")
                with open(setup_path, 'w') as f:
                    f.write("skipped")
                self.skipped.emit()
                self.accept()
    
    def on_finish(self):
        """Handle wizard completion."""
        # Collect configuration from pages
        config = {
            "telegram": {
                "api_id": self.page(1).api_id_edit.text().strip(),
                "api_hash": self.page(1).api_hash_edit.text().strip(),
                "phone_number": self.page(1).phone_edit.text().strip()
            },
            "gemini": {
                "api_key": self.page(2).gemini_edit.text().strip()
            },
            "brain": {
                "prompt": "You are a helpful assistant. Respond naturally and helpfully to user messages.",
                "auto_reply_enabled": True,
                "typing_delay": 2,
                "max_history": 50
            },
            "advanced": {
                "max_reply_length": 1024,
                "enable_logging": True,
                "realistic_typing": True,
                "random_delays": True
            },
            "anti_detection": {
                "min_delay": 2,
                "max_delay": 30,
                "messages_per_hour": 50,
                "burst_limit": 3,
                "online_simulation": True,
                "random_skip": True,
                "time_based_delays": True,
                "error_backoff": True,
                "session_recovery": True
            }
        }
        
        # Validate
        errors = ValidationHelper.validate_config(config)
        if errors:
            error_msg = "Please complete the required fields:\n\n" + "\n".join(f"• {err}" for err in errors)
            QMessageBox.warning(self, "Incomplete Setup", error_msg)
            return
        
        # Save to config.json
        import json
        import os
        try:
            config_path = os.path.join(os.getcwd(), "config.json")
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)

            # Mark as not first time
            setup_path = os.path.join(os.getcwd(), ".setup_complete")
            with open(setup_path, 'w') as f:
                f.write("1")

            logger.info(f"Configuration saved successfully to {config_path}")
            self.config_completed.emit(config)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")


def create_header(title: str, subtitle: str) -> QWidget:
    """Create a clean header widget."""
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 20)
    layout.setSpacing(8)
    
    title_label = QLabel(title)
    title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #ffffff;")
    layout.addWidget(title_label)
    
    subtitle_label = QLabel(subtitle)
    subtitle_label.setStyleSheet("font-size: 14px; color: #a1a1aa;")
    layout.addWidget(subtitle_label)
    
    return widget


def create_info_card(title: str, text: str) -> QGroupBox:
    """Create a clean info card using QGroupBox."""
    group = QGroupBox(title)
    # Ensure group box title is visible
    group.setStyleSheet("QGroupBox { font-weight: bold; color: #ffffff; border: 1px solid #3f3f46; border-radius: 6px; margin-top: 12px; } QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }")
    
    layout = QVBoxLayout(group)
    layout.setContentsMargins(12, 24, 12, 12)
    
    label = QLabel(text)
    label.setWordWrap(True)
    # Force bright text color and line height
    label.setStyleSheet("color: #e4e4e7; font-size: 13px; line-height: 1.4; border: none;")
    label.setMinimumWidth(200)
    label.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding)
    layout.addWidget(label)
    
    return group


class IntroPage(QWizardPage):
    """Introduction page."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        layout.addWidget(create_header("Telegram Automation Platform", "Professional Multi-Account Management System"))
        
        # Core Capabilities Grid
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(16)
        
        left_col = QVBoxLayout()
        left_col.addWidget(create_info_card("⚡ Intelligent Automation", 
            "AI-powered response system using Google Gemini for natural, context-aware communication."))
        left_col.addWidget(create_info_card("🛡️ Safety & Protection", 
            "Sophisticated anti-detection algorithms with human behavior simulation and rate limiting."))
        grid_layout.addLayout(left_col)
        
        right_col = QVBoxLayout()
        right_col.addWidget(create_info_card("🎯 Targeted Outreach", 
            "Advanced member extraction and filtering to build precise audiences from communities."))
        right_col.addWidget(create_info_card("📊 Analytics & Insights", 
            "Real-time dashboard with campaign performance metrics and system health monitoring."))
        grid_layout.addLayout(right_col)
        
        layout.addLayout(grid_layout)
        
        # Prerequisites
        prereq_group = QGroupBox("Prerequisites")
        prereq_layout = QVBoxLayout(prereq_group)
        prereq_layout.setContentsMargins(16, 24, 16, 16)
        
        prereq_label = QLabel(
            "<ul style='line-height: 1.6; margin-top: 5px;'>"
            "<li><b>Telegram API Credentials</b> (my.telegram.org)</li>"
            "<li><b>Google Gemini API Key</b> (Google AI Studio)</li>"
            "<li>Approx. 3-5 minutes for configuration</li>"
            "</ul>"
        )
        prereq_label.setStyleSheet("color: #d4d4d8; font-size: 13px;")
        prereq_layout.addWidget(prereq_label)
        layout.addWidget(prereq_group)
        
        layout.addStretch()


class TelegramSetupPage(QWizardPage):
    """Telegram API setup page."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        layout.addWidget(create_header("Telegram Configuration", "Step 1 of 3: Connect to Telegram API"))
        
        # Instructions
        info_group = QGroupBox("How to obtain credentials")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(16, 24, 16, 16)
        
        steps = QLabel(
            "<ol style='line-height: 1.8; margin-top: 10px; margin-bottom: 10px;'>"
            "<li>Visit <b>my.telegram.org/apps</b></li>"
            "<li>Log in with your phone number</li>"
            "<li>Go to <b>API Development Tools</b></li>"
            "<li>Create a new application</li>"
            "<li>Copy the <b>API ID</b> and <b>API Hash</b></li>"
            "</ol>"
        )
        steps.setStyleSheet("color: #d4d4d8; font-size: 13px;")
        info_layout.addWidget(steps)
        
        open_btn = QPushButton("Open Telegram Portal")
        open_btn.setObjectName("primary")
        open_btn.setFixedWidth(200)
        open_btn.clicked.connect(lambda: webbrowser.open("https://my.telegram.org/apps"))
        info_layout.addWidget(open_btn)
        
        layout.addWidget(info_group)
        
        # Form
        form_layout = QVBoxLayout()
        form_layout.setSpacing(16)
        
        # API ID
        id_layout = QVBoxLayout()
        id_layout.setSpacing(6)
        id_label = QLabel("API ID")
        id_label.setStyleSheet("font-weight: 600; color: #e4e4e7;")
        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("e.g. 12345678")
        id_layout.addWidget(id_label)
        id_layout.addWidget(self.api_id_edit)
        form_layout.addLayout(id_layout)
        
        # API Hash
        hash_layout = QVBoxLayout()
        hash_layout.setSpacing(6)
        hash_label = QLabel("API Hash")
        hash_label.setStyleSheet("font-weight: 600; color: #e4e4e7;")
        self.api_hash_edit = QLineEdit()
        self.api_hash_edit.setPlaceholderText("e.g. 0123456789abcdef...")
        hash_layout.addWidget(hash_label)
        hash_layout.addWidget(self.api_hash_edit)
        form_layout.addLayout(hash_layout)
        
        # Phone
        phone_layout = QVBoxLayout()
        phone_layout.setSpacing(6)
        phone_label = QLabel("Phone Number")
        phone_label.setStyleSheet("font-weight: 600; color: #e4e4e7;")
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("e.g. +1234567890")
        phone_layout.addWidget(phone_label)
        phone_layout.addWidget(self.phone_edit)
        form_layout.addLayout(phone_layout)
        
        layout.addLayout(form_layout)
        layout.addStretch()
        
        # Register fields
        self.registerField("api_id*", self.api_id_edit)
        self.registerField("api_hash*", self.api_hash_edit)
        self.registerField("phone*", self.phone_edit)
    
    def validatePage(self):
        """Validate inputs."""
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()
        
        errors = []
        valid, msg = ValidationHelper.validate_api_id(api_id)
        if not valid: errors.append(msg)
        
        valid, msg = ValidationHelper.validate_api_hash(api_hash)
        if not valid: errors.append(msg)
        
        valid, msg = ValidationHelper.validate_phone_number(phone)
        if not valid: errors.append(msg)
        
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return False
        return True


class GeminiSetupPage(QWizardPage):
    """Gemini API setup page."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        layout.addWidget(create_header("AI Engine Configuration", "Step 2 of 3: Connect Intelligence Layer"))
        
        # Info
        info_group = QGroupBox("Google Gemini API")
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(16, 24, 16, 16)
        
        info_text = QLabel(
            "Gemini provides the neural processing for intelligent conversations.\n"
            "The free tier includes 60 requests/minute and 1,500 requests/day."
        )
        info_text.setStyleSheet("color: #d4d4d8; font-size: 13px; line-height: 1.4;")
        info_layout.addWidget(info_text)
        
        open_btn = QPushButton("Get API Key from Google")
        open_btn.setObjectName("primary")
        open_btn.setFixedWidth(200)
        open_btn.clicked.connect(lambda: webbrowser.open("https://makersuite.google.com/app/apikey"))
        info_layout.addWidget(open_btn)
        
        layout.addWidget(info_group)
        
        # Input
        key_layout = QVBoxLayout()
        key_layout.setSpacing(6)
        key_label = QLabel("Gemini API Key")
        key_label.setStyleSheet("font-weight: 600; color: #e4e4e7;")
        
        self.gemini_edit = QLineEdit()
        self.gemini_edit.setPlaceholderText("Starts with AIza...")
        self.gemini_edit.setEchoMode(QLineEdit.EchoMode.Password)
        
        show_check = QCheckBox("Show API Key")
        show_check.toggled.connect(lambda checked: self.gemini_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        
        key_layout.addWidget(key_label)
        key_layout.addWidget(self.gemini_edit)
        key_layout.addWidget(show_check)
        
        layout.addLayout(key_layout)
        layout.addStretch()
        
        self.registerField("gemini*", self.gemini_edit)
    
    def validatePage(self):
        """Validate API key."""
        api_key = self.gemini_edit.text().strip()
        valid, msg = ValidationHelper.validate_gemini_api_key(api_key)
        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return False
        return True


class FeaturesPage(QWizardPage):
    """Features overview page."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        layout.addWidget(create_header("System Capabilities", "Step 3 of 3: Overview"))
        
        # Feature Cards
        grid = QHBoxLayout()
        grid.setSpacing(16)
        
        col1 = QVBoxLayout()
        col1.addWidget(create_info_card("⚡ Command Center", 
            "Unified operations dashboard for monitoring all accounts and campaigns."))
        col1.addWidget(create_info_card("📊 Analytics", 
            "Detailed metrics for engagement, growth, and system performance."))
        grid.addLayout(col1)
        
        col2 = QVBoxLayout()
        col2.addWidget(create_info_card("📧 Campaign Engine", 
            "Automated direct messaging with scheduling and templates."))
        col2.addWidget(create_info_card("👥 Member Scraper", 
            "Extract targeted user lists from groups for outreach."))
        grid.addLayout(col2)
        
        layout.addLayout(grid)
        
        # Best Practices
        practices_group = QGroupBox("Operational Best Practices")
        practices_layout = QVBoxLayout(practices_group)
        practices_layout.setContentsMargins(16, 24, 16, 16)
        
        practices_label = QLabel(
            "• Start with 1-2 accounts to test your configuration\n"
            "• Allow 3-7 days for new account warming\n"
            "• Keep message rates below 50/hour initially\n"
            "• Ensure high-quality, relevant content in messages"
        )
        practices_label.setStyleSheet("color: #d4d4d8; font-size: 13px; line-height: 1.6;")
        practices_layout.addWidget(practices_label)
        
        layout.addWidget(practices_group)
        layout.addStretch()


class CompletePage(QWizardPage):
    """Completion page."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        # Success Icon/Header
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        title = QLabel("System Initialized")
        title.setStyleSheet("font-size: 28px; font-weight: 700; color: #ffffff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle = QLabel("Configuration complete. Platform ready for deployment.")
        subtitle.setStyleSheet("font-size: 16px; color: #a1a1aa;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        layout.addWidget(header_widget)
        
        # Next Steps
        steps_group = QGroupBox("Deployment Sequence")
        steps_layout = QVBoxLayout(steps_group)
        steps_layout.setContentsMargins(16, 24, 16, 16)
        
        steps_label = QLabel(
            "1. Account Provisioning: Add your first account in Settings\n"
            "2. Warming Protocol: Allow automated warming cycle\n"
            "3. Audience Building: Extract members from target groups\n"
            "4. Campaign Launch: Create and schedule your first campaign"
        )
        steps_label.setStyleSheet("color: #d4d4d8; font-size: 14px; line-height: 1.8;")
        steps_layout.addWidget(steps_label)
        layout.addWidget(steps_group)
        
        # Launch Button Note
        note = QLabel("Click Finish to launch the platform dashboard.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet("color: #71717a; margin-top: 20px;")
        layout.addWidget(note)
        
        layout.addStretch()


def should_show_wizard() -> bool:
    """Check if welcome wizard should be shown (first time use)."""
    setup_file = Path(".setup_complete")
    config_file = Path("config.json")
    
    if not setup_file.exists():
        return True
    
    if not config_file.exists():
        return True
    
    try:
        import json
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        if not config.get("telegram", {}).get("api_id"):
            return True
        if not config.get("telegram", {}).get("api_hash"):
            return True
        
        return False
    except Exception:
        return True


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    wizard = WelcomeWizard()
    wizard.show()
    sys.exit(app.exec())
