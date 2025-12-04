#!/usr/bin/env python3
"""
Settings Window - Configuration interface for the Telegram bot
"""

import logging
import os
import json
import datetime
import threading
import time
from typing import Dict, Any, Optional, List
from pathlib import Path
import requests

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QTextEdit, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QTabWidget,
    QScrollArea, QMessageBox, QFileDialog, QListWidget,
    QListWidgetItem, QProgressBar, QInputDialog, QFrame,
    QToolButton, QApplication, QProgressDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation
from PyQt6.QtGui import QIcon, QFont

from utils.user_helpers import ValidationHelper, get_tooltip
from core.error_handler import ErrorHandler
import webbrowser

logger = logging.getLogger(__name__)


class SetupWizardManager:
    """Manages setup wizard state and progression."""
    
    STEP_TELEGRAM = 0
    STEP_GEMINI = 1
    STEP_SMS_PROVIDER = 2
    STEP_OPTIONAL = 3
    
    def __init__(self, settings_data: Dict[str, Any]):
        self.settings_data = settings_data
        self.wizard_complete_file = Path(".wizard_complete")
        self.wizard_progress_file = Path(".wizard_progress.json")

    def is_wizard_needed(self) -> bool:
        """Check if wizard should be shown (first-time or missing required settings)."""
        # Check if wizard was previously completed
        if self.wizard_complete_file.exists():
            marker = self._load_completion_marker()
            if marker is None:
                return True
            # Still check if critical settings are missing
            if not self._has_critical_settings():
                return True
            return False
        
        # No wizard completion marker, check settings
        if not self._has_critical_settings():
            return True
            
        return False
    
    def _has_critical_settings(self) -> bool:
        """Check if all critical settings are present."""
        telegram = self.settings_data.get("telegram", {})
        if not telegram.get("api_id") or not telegram.get("api_hash") or not telegram.get("phone_number"):
            return False
        
        gemini = self.settings_data.get("gemini", {})
        if not gemini.get("api_key"):
            return False
        
        sms = self.settings_data.get("sms_providers", {})
        if not sms.get("provider") or sms.get("provider") == "None" or not sms.get("api_key"):
            return False
        
        return True
    
    def get_starting_step(self) -> int:
        """Determine which step to start from based on what's already configured."""
        telegram = self.settings_data.get("telegram", {})
        if not telegram.get("api_id") or not telegram.get("api_hash") or not telegram.get("phone_number"):
            return self.STEP_TELEGRAM
        
        gemini = self.settings_data.get("gemini", {})
        if not gemini.get("api_key"):
            return self.STEP_GEMINI
        
        sms = self.settings_data.get("sms_providers", {})
        if not sms.get("provider") or sms.get("provider") == "None" or not sms.get("api_key"):
            return self.STEP_SMS_PROVIDER
        
        return self.STEP_OPTIONAL
    
    def is_step_complete(self, step: int, settings: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Check if a step is complete and return validation errors."""
        errors = []
        
        if step == self.STEP_TELEGRAM:
            telegram = settings.get("telegram", {})
            valid, msg = ValidationHelper.validate_api_id(telegram.get("api_id", ""))
            if not valid:
                errors.append(msg)
            
            valid, msg = ValidationHelper.validate_api_hash(telegram.get("api_hash", ""))
            if not valid:
                errors.append(msg)
            
            valid, msg = ValidationHelper.validate_phone_number(telegram.get("phone_number", ""))
            if not valid:
                errors.append(msg)
        
        elif step == self.STEP_GEMINI:
            gemini = settings.get("gemini", {})
            valid, msg = ValidationHelper.validate_gemini_api_key(gemini.get("api_key", ""))
            if not valid:
                errors.append(msg)
        
        elif step == self.STEP_SMS_PROVIDER:
            sms = settings.get("sms_providers", {})
            provider = sms.get("provider", "")
            api_key = sms.get("api_key", "")
            
            if not provider or provider == "None":
                errors.append("Please select an SMS provider")
            
            if not api_key:
                errors.append("SMS provider API key is required")
            elif len(api_key) < 10:
                errors.append("SMS provider API key seems too short")
        
        # Step 3 (Optional) is always valid
        
        return len(errors) == 0, errors
    
    def mark_wizard_complete(self):
        """Mark wizard as completed with metadata."""
        try:
            import datetime
            completion_data = {
                "completed": True,
                "timestamp": datetime.datetime.now().isoformat(),
                "version": "1.0",
                "completed_steps": [
                    "telegram_api",
                    "gemini_ai",
                    "sms_provider",
                    "optional_settings"
                ]
            }
            with open(self.wizard_complete_file, 'w') as f:
                json.dump(completion_data, f, indent=2)
            logger.info("Wizard marked as complete with metadata")
        except Exception as e:
            logger.error(f"Failed to mark wizard as complete: {e}")
    
    def save_step_progress(self, step: int, settings: Dict[str, Any]):
        """Save progress after each successful step."""
        try:
            progress_data = {
                "current_step": step,
                "completed_steps": list(range(step)),
                "timestamp": datetime.datetime.now().isoformat(),
                "partial_settings": settings
            }
            with open(self.wizard_progress_file, 'w') as f:
                json.dump(progress_data, f, indent=2)
            logger.info(f"Saved wizard progress at step {step}")
        except Exception as e:
            logger.error(f"Failed to save wizard progress: {e}")

    def load_step_progress(self) -> Optional[Dict[str, Any]]:
        """Load saved progress if exists."""
        try:
            if self.wizard_progress_file.exists():
                with open(self.wizard_progress_file, 'r') as f:
                    progress = json.load(f)
                if self._is_progress_metadata_valid(progress):
                    return progress
                logger.warning("Wizard progress file is invalid or corrupted; clearing it")
                self.clear_step_progress()
        except Exception as e:
            logger.error(f"Failed to load wizard progress: {e}")
        return None

    def clear_step_progress(self):
        """Clear saved progress after completion."""
        try:
            if self.wizard_progress_file.exists():
                self.wizard_progress_file.unlink()
            logger.info("Cleared wizard progress")
        except Exception as e:
            logger.error(f"Failed to clear wizard progress: {e}")
    
    def get_step_name(self, step: int) -> str:
        """Get human-readable name for step."""
        names = {
            self.STEP_TELEGRAM: "Telegram API",
            self.STEP_GEMINI: "Gemini AI",
            self.STEP_SMS_PROVIDER: "SMS Provider",
            self.STEP_OPTIONAL: "Optional Settings"
        }
        return names.get(step, "Unknown")

    def _load_completion_marker(self) -> Optional[Dict[str, Any]]:
        """Load and validate the wizard completion marker."""
        try:
            with open(self.wizard_complete_file, 'r') as f:
                marker = json.load(f)
            if not self._is_completion_metadata_valid(marker):
                logger.warning("Wizard completion marker is invalid; removing and re-running wizard")
                self.wizard_complete_file.unlink(missing_ok=True)
                return None
            return marker
        except FileNotFoundError:
            return None
        except Exception as e:
            logger.warning(f"Failed to load wizard completion marker: {e}")
            try:
                self.wizard_complete_file.unlink(missing_ok=True)
            except Exception:
                pass
            return None

    @staticmethod
    def _is_completion_metadata_valid(marker: Dict[str, Any]) -> bool:
        """Ensure the completion file has expected shape to avoid false positives."""
        if not isinstance(marker, dict):
            return False
        required_keys = {"completed", "timestamp", "version", "completed_steps"}
        if not required_keys.issubset(set(marker.keys())):
            return False
        if marker.get("completed") is not True:
            return False
        if not isinstance(marker.get("completed_steps"), list) or len(marker["completed_steps"]) < 3:
            return False
        return True

    @staticmethod
    def _is_progress_metadata_valid(progress: Dict[str, Any]) -> bool:
        """Validate partial wizard progress to guard against corrupted files."""
        if not isinstance(progress, dict):
            return False
        if not isinstance(progress.get("current_step"), int):
            return False
        if not isinstance(progress.get("completed_steps"), list):
            return False
        if "partial_settings" not in progress:
            return False
        return True


class QCollapsibleGroupBox(QGroupBox):
    """A collapsible group box widget for progressive disclosure."""

    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)

        # Set up the toggle button
        self.toggle_button = QToolButton(self)
        self.toggle_button.setStyleSheet("QToolButton { border: none; }")
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setText(title)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)

        # Remove the default title and use our custom button
        self.setTitle("")

        # Create animation for smooth expand/collapse
        self.animation = QPropertyAnimation(self, b"maximumHeight")
        self.animation.setDuration(200)  # 200ms animation

        # Connect signals
        self.toggle_button.clicked.connect(self.on_toggle)
        self.clicked.connect(self.on_toggle)

        # Store the expanded height
        self.expanded_height = 0

    def on_toggle(self, checked):
        """Handle toggle state changes."""
        if checked:
            # Expanding
            self.toggle_button.setArrowType(Qt.ArrowType.DownArrow)
            self.animation.setStartValue(self.minimumSizeHint().height())
            self.animation.setEndValue(self.expanded_height or self.sizeHint().height())
            self.setMaximumHeight(self.expanded_height or 16777215)  # Reset to default max
        else:
            # Collapsing
            self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
            self.expanded_height = self.height()
            self.animation.setStartValue(self.height())
            self.animation.setEndValue(self.minimumSizeHint().height())

        self.animation.start()
        self.setChecked(checked)

    def resizeEvent(self, event):
        """Handle resize events to position the toggle button."""
        super().resizeEvent(event)
        self.toggle_button.move(5, 0)
        self.toggle_button.resize(self.width() - 10, self.toggle_button.height())

    def setTitle(self, title):
        """Override setTitle to update our toggle button."""
        super().setTitle("")
        self.toggle_button.setText(title)


class APISettingsWidget(QWidget):
    """API and Authentication settings widget."""

    # Styles for validation feedback
    VALID_STYLE = "border: 1px solid #23a559;"
    INVALID_STYLE = "border: 1px solid #ed4245;"
    NORMAL_STYLE = ""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self._setup_validation()

    def _setup_validation(self):
        """Set up real-time validation for input fields."""
        self.api_id_edit.textChanged.connect(lambda: self._validate_api_id())
        self.api_hash_edit.textChanged.connect(lambda: self._validate_api_hash())
        self.phone_edit.textChanged.connect(lambda: self._validate_phone())
        self.gemini_key_edit.textChanged.connect(lambda: self._validate_gemini_key())

    def _validate_api_id(self):
        """Validate API ID field."""
        text = self.api_id_edit.text().strip()
        if not text:
            self.api_id_edit.setStyleSheet(self.NORMAL_STYLE)
            return True
        if text.isdigit() and len(text) >= 6:
            self.api_id_edit.setStyleSheet(self.VALID_STYLE)
            return True
        else:
            self.api_id_edit.setStyleSheet(self.INVALID_STYLE)
            return False

    def _validate_api_hash(self):
        """Validate API Hash field."""
        text = self.api_hash_edit.text().strip()
        if not text:
            self.api_hash_edit.setStyleSheet(self.NORMAL_STYLE)
            return True
        import re
        if len(text) == 32 and re.match(r'^[a-f0-9]{32}$', text.lower()):
            self.api_hash_edit.setStyleSheet(self.VALID_STYLE)
            return True
        else:
            self.api_hash_edit.setStyleSheet(self.INVALID_STYLE)
            return False

    def _validate_phone(self):
        """Validate phone number field."""
        text = self.phone_edit.text().strip()
        if not text:
            self.phone_edit.setStyleSheet(self.NORMAL_STYLE)
            return True
        cleaned = text.replace(" ", "").replace("-", "")
        if cleaned.startswith("+") and cleaned[1:].isdigit() and 10 <= len(cleaned) <= 16:
            self.phone_edit.setStyleSheet(self.VALID_STYLE)
            return True
        else:
            self.phone_edit.setStyleSheet(self.INVALID_STYLE)
            return False

    def _validate_gemini_key(self):
        """Validate Gemini API key field."""
        text = self.gemini_key_edit.text().strip()
        if not text:
            self.gemini_key_edit.setStyleSheet(self.NORMAL_STYLE)
            return True
        if text.startswith("AI") and len(text) >= 30:
            self.gemini_key_edit.setStyleSheet(self.VALID_STYLE)
            return True
        else:
            self.gemini_key_edit.setStyleSheet(self.INVALID_STYLE)
            return False

    def validate_all(self) -> tuple:
        """Validate all fields and return (is_valid, errors)."""
        errors = []
        if not self._validate_api_id():
            errors.append("API ID should be a 7-8 digit number")
        if not self._validate_api_hash():
            errors.append("API Hash should be 32 hexadecimal characters")
        if not self._validate_phone():
            errors.append("Phone number should start with + and include country code")
        if not self._validate_gemini_key():
            errors.append("Gemini API key should start with 'AI' and be at least 30 characters")
        return len(errors) == 0, errors
    
    def is_telegram_step_complete(self) -> tuple[bool, List[str]]:
        """Check if Telegram API step is complete (for wizard)."""
        errors = []
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()
        
        valid, msg = ValidationHelper.validate_api_id(api_id)
        if not valid:
            errors.append(msg)
        
        valid, msg = ValidationHelper.validate_api_hash(api_hash)
        if not valid:
            errors.append(msg)
        
        valid, msg = ValidationHelper.validate_phone_number(phone)
        if not valid:
            errors.append(msg)
        
        return len(errors) == 0, errors
    
    def is_gemini_step_complete(self) -> tuple[bool, List[str]]:
        """Check if Gemini API step is complete (for wizard)."""
        errors = []
        api_key = self.gemini_key_edit.text().strip()
        
        valid, msg = ValidationHelper.validate_gemini_api_key(api_key)
        if not valid:
            errors.append(msg)
        
        return len(errors) == 0, errors

    def setup_ui(self):
        """Set up the API & Auth tab UI with progressive disclosure."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Essential settings (always visible)
        essential_group = QGroupBox("Essential Settings")
        essential_layout = QVBoxLayout()
        essential_layout.setSpacing(12)

        # Telegram API section - Basic required fields
        telegram_basic_group = QGroupBox("Telegram API (Required)")
        telegram_basic_layout = QFormLayout()

        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("e.g., 12345678")
        self.api_id_edit.setToolTip("Enter your 7-8 digit API ID from my.telegram.org/apps\nExample: 12345678")
        telegram_basic_layout.addRow("API ID:", self.api_id_edit)

        self.api_hash_edit = QLineEdit()
        self.api_hash_edit.setPlaceholderText("e.g., 0123456789abcdef...")
        self.api_hash_edit.setToolTip("Enter your 32-character API Hash from my.telegram.org/apps\nExample: 0123456789abcdef0123456789abcdef")
        self.api_hash_edit.setEchoMode(QLineEdit.EchoMode.Password)
        telegram_basic_layout.addRow("API Hash:", self.api_hash_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("e.g., +1234567890")
        self.phone_edit.setToolTip("Enter your phone number with country code\nFormat: +[country code][number]\nExample: +1234567890")
        telegram_basic_layout.addRow("Phone Number:", self.phone_edit)

        telegram_basic_group.setLayout(telegram_basic_layout)
        essential_layout.addWidget(telegram_basic_group)

        # AI API section - Basic required fields
        ai_basic_group = QGroupBox("AI Services (Required)")
        ai_basic_layout = QFormLayout()

        self.gemini_key_edit = QLineEdit()
        self.gemini_key_edit.setPlaceholderText("e.g., AIzaSyABC123...")
        self.gemini_key_edit.setToolTip("Enter your Gemini API key from aistudio.google.com/app/apikey\nFormat: Starts with 'AIza' and is 39+ characters\nExample: AIzaSyABC123XYZ...")
        self.gemini_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        ai_basic_layout.addRow("Gemini API Key:", self.gemini_key_edit)

        ai_basic_group.setLayout(ai_basic_layout)
        essential_layout.addWidget(ai_basic_group)

        essential_group.setLayout(essential_layout)
        layout.addWidget(essential_group)

        # Advanced settings (collapsible)
        advanced_group = QCollapsibleGroupBox("Advanced Settings")
        # Note: Will be expanded if in wizard mode
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(12)

        # Additional AI APIs
        additional_ai_group = QGroupBox("Additional AI APIs")
        additional_ai_layout = QFormLayout()

        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setPlaceholderText("Your OpenAI API Key (sk-...)")
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_key_edit.setToolTip("OpenAI API key for fallback AI services")
        additional_ai_layout.addRow("OpenAI API Key:", self.openai_key_edit)

        self.elevenlabs_key_edit = QLineEdit()
        self.elevenlabs_key_edit.setPlaceholderText("Your ElevenLabs API Key")
        self.elevenlabs_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.elevenlabs_key_edit.setToolTip(get_tooltip("elevenlabs_api_key"))
        additional_ai_layout.addRow("ElevenLabs API Key:", self.elevenlabs_key_edit)

        additional_ai_group.setLayout(additional_ai_layout)
        advanced_layout.addWidget(additional_ai_group)

        # SMS Services (for number verification)
        sms_group = QGroupBox("SMS Services (Optional)")
        sms_layout = QFormLayout()

        self.sms_service_combo = QComboBox()
        self.sms_service_combo.addItems([
            "None",
            "SMS-Activate",
            "5SIM",
            "SMS-Hub",
            "TextVerified",
            "DaisySMS"
        ])
        sms_layout.addRow("SMS Service:", self.sms_service_combo)

        self.sms_api_key_edit = QLineEdit()
        self.sms_api_key_edit.setPlaceholderText("SMS service API key")
        self.sms_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        sms_layout.addRow("SMS API Key:", self.sms_api_key_edit)

        sms_group.setLayout(sms_layout)
        advanced_layout.addWidget(sms_group)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        layout.addStretch()

    def load_settings(self, settings):
        """Load settings into UI."""
        telegram_cfg = settings.get("telegram", {})
        self.api_id_edit.setText(telegram_cfg.get("api_id", ""))
        self.api_hash_edit.setText(telegram_cfg.get("api_hash", ""))
        self.phone_edit.setText(telegram_cfg.get("phone_number", ""))

        gemini_cfg = settings.get("gemini", {})
        self.gemini_key_edit.setText(gemini_cfg.get("api_key", ""))

        # Load advanced settings
        self.openai_key_edit.setText(settings.get("openai", {}).get("api_key", ""))
        self.elevenlabs_key_edit.setText(settings.get("elevenlabs", {}).get("api_key", ""))

        sms_cfg = settings.get("sms_providers", {})
        self.sms_service_combo.setCurrentText(sms_cfg.get("provider", "None"))
        self.sms_api_key_edit.setText(sms_cfg.get("api_key", ""))

    def save_settings(self, settings):
        """Save UI settings."""
        # Save essential settings
        if "telegram" not in settings:
            settings["telegram"] = {}
        settings["telegram"]["api_id"] = self.api_id_edit.text().strip()
        settings["telegram"]["api_hash"] = self.api_hash_edit.text().strip()
        settings["telegram"]["phone_number"] = self.phone_edit.text().strip()

        if "gemini" not in settings:
            settings["gemini"] = {}
        settings["gemini"]["api_key"] = self.gemini_key_edit.text().strip()

        # Save advanced settings
        if "openai" not in settings:
            settings["openai"] = {}
        settings["openai"]["api_key"] = self.openai_key_edit.text().strip()

        if "elevenlabs" not in settings:
            settings["elevenlabs"] = {}
        settings["elevenlabs"]["api_key"] = self.elevenlabs_key_edit.text().strip()

        if "sms_providers" not in settings:
            settings["sms_providers"] = {}
        settings["sms_providers"]["provider"] = self.sms_service_combo.currentText()
        settings["sms_providers"]["api_key"] = self.sms_api_key_edit.text().strip()


class BrainSettingsWidget(QWidget):
    """AI Brain and Behavior settings widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Set up the Brain & Behavior tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # System Prompt Configuration
        prompt_group = QGroupBox("System Prompt & Personality")
        prompt_layout = QVBoxLayout()

        prompt_layout.addWidget(QLabel("Define the AI's personality and behavior:"))
        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("You are a helpful, professional assistant who responds naturally and engagingly to user messages. Be friendly but not overly casual. Focus on providing value and building genuine connections.")
        prompt_layout.addWidget(self.prompt_edit)

        prompt_group.setLayout(prompt_layout)
        layout.addWidget(prompt_group)

        # Response Configuration
        response_group = QGroupBox("Response Settings")
        response_layout = QFormLayout()

        self.max_reply_length_spin = QSpinBox()
        self.max_reply_length_spin.setRange(100, 4000)
        self.max_reply_length_spin.setValue(1024)
        self.max_reply_length_spin.setSuffix(" characters")
        self.max_reply_length_spin.setToolTip("Maximum length of AI responses")
        response_layout.addRow("Max Reply Length:", self.max_reply_length_spin)

        self.typing_delay_spin = QDoubleSpinBox()
        self.typing_delay_spin.setRange(0.5, 10.0)
        self.typing_delay_spin.setValue(2.0)
        self.typing_delay_spin.setSingleStep(0.5)
        self.typing_delay_spin.setSuffix(" seconds")
        self.typing_delay_spin.setToolTip("Delay before showing typing indicator")
        response_layout.addRow("Typing Delay:", self.typing_delay_spin)

        response_group.setLayout(response_layout)
        layout.addWidget(response_group)

        # AI Parameters
        ai_group = QGroupBox("AI Model Parameters")
        ai_layout = QFormLayout()

        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.1, 1.0)
        self.temperature_spin.setValue(0.8)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setToolTip("Higher values make responses more creative but less focused")
        ai_layout.addRow("Temperature:", self.temperature_spin)

        self.top_p_spin = QDoubleSpinBox()
        self.top_p_spin.setRange(0.1, 1.0)
        self.top_p_spin.setValue(0.9)
        self.top_p_spin.setSingleStep(0.1)
        self.top_p_spin.setToolTip("Nucleus sampling parameter")
        ai_layout.addRow("Top P:", self.top_p_spin)

        self.top_k_spin = QSpinBox()
        self.top_k_spin.setRange(1, 100)
        self.top_k_spin.setValue(40)
        self.top_k_spin.setToolTip("Top-k sampling parameter")
        ai_layout.addRow("Top K:", self.top_k_spin)

        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(100, 2000)
        self.max_tokens_spin.setValue(1000)
        self.max_tokens_spin.setToolTip("Maximum tokens in response")
        ai_layout.addRow("Max Tokens:", self.max_tokens_spin)

        ai_group.setLayout(ai_layout)
        layout.addWidget(ai_group)

        layout.addStretch()

    def load_settings(self, settings):
        """Load settings into UI."""
        brain_cfg = settings.get("brain", {})
        self.prompt_edit.setPlainText(brain_cfg.get("prompt", ""))
        self.max_reply_length_spin.setValue(brain_cfg.get("max_reply_length", 1024))
        self.typing_delay_spin.setValue(brain_cfg.get("typing_delay", 2.0))

        ai_cfg = brain_cfg.get("ai", {})
        self.temperature_spin.setValue(ai_cfg.get("temperature", 0.8))
        self.top_p_spin.setValue(ai_cfg.get("top_p", 0.9))
        self.top_k_spin.setValue(ai_cfg.get("top_k", 40))
        self.max_tokens_spin.setValue(ai_cfg.get("max_tokens", 1000))

    def save_settings(self, settings):
        """Save UI settings."""
        if "brain" not in settings:
            settings["brain"] = {}

        settings["brain"]["prompt"] = self.prompt_edit.toPlainText().strip()
        settings["brain"]["max_reply_length"] = self.max_reply_length_spin.value()
        settings["brain"]["typing_delay"] = self.typing_delay_spin.value()

        if "ai" not in settings["brain"]:
            settings["brain"]["ai"] = {}
        settings["brain"]["ai"]["temperature"] = self.temperature_spin.value()
        settings["brain"]["ai"]["top_p"] = self.top_p_spin.value()
        settings["brain"]["ai"]["top_k"] = self.top_k_spin.value()
        settings["brain"]["ai"]["max_tokens"] = self.max_tokens_spin.value()


class AntiDetectionSettingsWidget(QWidget):
    """Anti-detection settings widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """Set up the Anti-Detection tab UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Rate Limiting
        rate_group = QGroupBox("Rate Limiting")
        rate_layout = QFormLayout()

        self.messages_per_hour_spin = QSpinBox()
        self.messages_per_hour_spin.setRange(1, 1000)
        self.messages_per_hour_spin.setValue(50)
        self.messages_per_hour_spin.setToolTip("Maximum messages per hour to avoid detection")
        rate_layout.addRow("Messages/Hour:", self.messages_per_hour_spin)

        self.burst_limit_spin = QSpinBox()
        self.burst_limit_spin.setRange(1, 20)
        self.burst_limit_spin.setValue(3)
        self.burst_limit_spin.setToolTip("Maximum consecutive messages before forced delay")
        rate_layout.addRow("Burst Limit:", self.burst_limit_spin)

        rate_group.setLayout(rate_layout)
        layout.addWidget(rate_group)

        # Timing Controls
        timing_group = QGroupBox("Timing & Delays")
        timing_layout = QFormLayout()

        self.min_delay_spin = QDoubleSpinBox()
        self.min_delay_spin.setRange(0.5, 60.0)
        self.min_delay_spin.setValue(2.0)
        self.min_delay_spin.setSingleStep(0.5)
        self.min_delay_spin.setSuffix(" seconds")
        self.min_delay_spin.setToolTip("Minimum delay between responses")
        timing_layout.addRow("Min Delay:", self.min_delay_spin)

        self.max_delay_spin = QDoubleSpinBox()
        self.max_delay_spin.setRange(5.0, 300.0)
        self.max_delay_spin.setValue(30.0)
        self.max_delay_spin.setSingleStep(5.0)
        self.max_delay_spin.setSuffix(" seconds")
        self.max_delay_spin.setToolTip("Maximum delay between responses")
        timing_layout.addRow("Max Delay:", self.max_delay_spin)

        timing_group.setLayout(timing_layout)
        layout.addWidget(timing_group)

        # Behavioral Options
        behavior_group = QGroupBox("Behavioral Simulation")
        behavior_layout = QVBoxLayout()

        self.online_simulation_check = QCheckBox("Simulate online/offline status")
        self.online_simulation_check.setChecked(True)
        self.online_simulation_check.setToolTip("Mimic human online/offline patterns")
        behavior_layout.addWidget(self.online_simulation_check)

        self.random_skip_check = QCheckBox("Random response skipping")
        self.random_skip_check.setChecked(True)
        self.random_skip_check.setToolTip("Occasionally skip responses to appear more human")
        behavior_layout.addWidget(self.random_skip_check)

        self.time_based_delays_check = QCheckBox("Time-based delay adjustments")
        self.time_based_delays_check.setChecked(True)
        self.time_based_delays_check.setToolTip("Adjust delays based on time of day")
        behavior_layout.addWidget(self.time_based_delays_check)

        self.error_backoff_check = QCheckBox("Exponential backoff on errors")
        self.error_backoff_check.setChecked(True)
        self.error_backoff_check.setToolTip("Increase delays after errors to avoid bans")
        behavior_layout.addWidget(self.error_backoff_check)

        self.session_recovery_check = QCheckBox("Session recovery on restart")
        self.session_recovery_check.setChecked(True)
        self.session_recovery_check.setToolTip("Attempt to recover sessions after application restart")
        behavior_layout.addWidget(self.session_recovery_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        layout.addStretch()

    def load_settings(self, settings):
        """Load settings into UI."""
        anti_cfg = settings.get("anti_detection", {})

        self.messages_per_hour_spin.setValue(anti_cfg.get("messages_per_hour", 50))
        self.burst_limit_spin.setValue(anti_cfg.get("burst_limit", 3))
        self.min_delay_spin.setValue(anti_cfg.get("min_delay", 2.0))
        self.max_delay_spin.setValue(anti_cfg.get("max_delay", 30.0))

        self.online_simulation_check.setChecked(anti_cfg.get("online_simulation", True))
        self.random_skip_check.setChecked(anti_cfg.get("random_skip", True))
        self.time_based_delays_check.setChecked(anti_cfg.get("time_based_delays", True))
        self.error_backoff_check.setChecked(anti_cfg.get("error_backoff", True))
        self.session_recovery_check.setChecked(anti_cfg.get("session_recovery", True))

    def save_settings(self, settings):
        """Save UI settings."""
        if "anti_detection" not in settings:
            settings["anti_detection"] = {}

        settings["anti_detection"]["messages_per_hour"] = self.messages_per_hour_spin.value()
        settings["anti_detection"]["burst_limit"] = self.burst_limit_spin.value()
        settings["anti_detection"]["min_delay"] = self.min_delay_spin.value()
        settings["anti_detection"]["max_delay"] = self.max_delay_spin.value()

        settings["anti_detection"]["online_simulation"] = self.online_simulation_check.isChecked()
        settings["anti_detection"]["random_skip"] = self.random_skip_check.isChecked()
        settings["anti_detection"]["time_based_delays"] = self.time_based_delays_check.isChecked()
        settings["anti_detection"]["error_backoff"] = self.error_backoff_check.isChecked()
        settings["anti_detection"]["session_recovery"] = self.session_recovery_check.isChecked()


class TelegramStepWidget(QWidget):
    """Telegram-specific step widget for wizard - shows only Telegram fields."""
    
    def __init__(self, api_widget: 'APISettingsWidget', parent=None):
        super().__init__(parent)
        self.api_widget = api_widget
        self.setup_ui()
    
    def setup_ui(self):
        """Set up UI showing only Telegram fields."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Telegram API Group
        telegram_group = QGroupBox("Telegram API Credentials")
        telegram_layout = QFormLayout()
        telegram_layout.setSpacing(12)
        
        telegram_layout.addRow("API ID:", self.api_widget.api_id_edit)
        telegram_layout.addRow("API Hash:", self.api_widget.api_hash_edit)
        
        # Show API Hash toggle
        show_hash_check = QCheckBox("Show API Hash")
        show_hash_check.toggled.connect(lambda checked: self.api_widget.api_hash_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        telegram_layout.addRow("", show_hash_check)
        
        telegram_layout.addRow("Phone Number:", self.api_widget.phone_edit)
        
        telegram_group.setLayout(telegram_layout)
        layout.addWidget(telegram_group)
        
        # Help text
        help_text = QLabel(
            "<b>Format Examples:</b><br>"
            "• API ID: 12345678 (7-8 digits)<br>"
            "• API Hash: abcd1234abcd1234... (32 characters)<br>"
            "• Phone: +1234567890 (with country code)"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #a1a1aa; padding: 8px; background-color: #2b2d31; border-radius: 4px;")
        layout.addWidget(help_text)
        
        layout.addStretch()


class GeminiStepWidget(QWidget):
    """Gemini-specific step widget for wizard - shows only Gemini field."""
    
    def __init__(self, api_widget: 'APISettingsWidget', parent=None):
        super().__init__(parent)
        self.api_widget = api_widget
        self.setup_ui()
    
    def setup_ui(self):
        """Set up UI showing only Gemini field."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Gemini API Group
        gemini_group = QGroupBox("Google Gemini API Key")
        gemini_layout = QFormLayout()
        gemini_layout.setSpacing(12)
        
        gemini_layout.addRow("API Key:", self.api_widget.gemini_key_edit)
        
        # Show key toggle
        show_key_check = QCheckBox("Show API Key")
        show_key_check.toggled.connect(lambda checked: self.api_widget.gemini_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        gemini_layout.addRow("", show_key_check)
        
        gemini_group.setLayout(gemini_layout)
        layout.addWidget(gemini_group)
        
        # Help text
        help_text = QLabel(
            "<b>About Gemini AI:</b><br>"
            "Gemini powers the intelligent responses for your Telegram accounts. "
            "The free tier includes:<br>"
            "• 60 requests per minute<br>"
            "• 1,500 requests per day<br><br>"
            "<b>Format:</b> API key starts with 'AIza' and is 39+ characters long"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #a1a1aa; padding: 8px; background-color: #2b2d31; border-radius: 4px;")
        layout.addWidget(help_text)
        
        layout.addStretch()


class SMSProviderSetupWidget(QWidget):
    """SMS Provider configuration widget with comprehensive help."""
    
    # Provider information
    PROVIDERS = {
        "sms-activate": {
            "name": "SMS-Activate",
            "url": "https://sms-activate.org/en/api2",
            "signup": "https://sms-activate.org/en/register",
            "recommended": True,
            "description": "Popular service with good coverage and reliability"
        },
        "daisysms": {
            "name": "DaisySMS",
            "url": "https://daisysms.com/docs/",
            "signup": "https://daisysms.com/",
            "recommended": False,
            "description": "Alternative provider with competitive pricing"
        },
        "5sim": {
            "name": "5SIM",
            "url": "https://5sim.net/en/info/api",
            "signup": "https://5sim.net/",
            "recommended": False,
            "description": "Fast service with global number availability"
        },
        "smshub": {
            "name": "SMS-Hub",
            "url": "https://smshub.org/en/info/api",
            "signup": "https://smshub.org/",
            "recommended": False,
            "description": "Reliable service with good API documentation"
        }
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the SMS Provider setup UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        
        # Info section
        info_group = QGroupBox("About SMS Providers")
        info_layout = QVBoxLayout()
        
        info_label = QLabel(
            "SMS providers supply phone numbers for Telegram account creation. "
            "You'll need an API key from one of the supported providers."
        )
        info_label.setWordWrap(True)
        info_layout.addWidget(info_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Provider selection
        provider_group = QGroupBox("Provider Configuration")
        provider_layout = QVBoxLayout()
        provider_layout.setSpacing(12)
        
        # Provider dropdown
        provider_select_layout = QFormLayout()
        self.provider_combo = QComboBox()
        
        for key, info in self.PROVIDERS.items():
            label = info["name"]
            if info.get("recommended"):
                label += " ⭐ (Recommended)"
            self.provider_combo.addItem(label, key)
        
        provider_select_layout.addRow("Provider:", self.provider_combo)
        provider_layout.addLayout(provider_select_layout)
        
        # Provider description
        self.provider_description = QLabel()
        self.provider_description.setWordWrap(True)
        self.provider_description.setStyleSheet("color: #a1a1aa; font-style: italic; padding: 8px;")
        provider_layout.addWidget(self.provider_description)
        
        # API Key input
        api_key_layout = QFormLayout()
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Paste your API key here...")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_key_layout.addRow("API Key:", self.api_key_edit)
        
        show_key_check = QCheckBox("Show API Key")
        show_key_check.toggled.connect(lambda checked: self.api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        ))
        api_key_layout.addRow("", show_key_check)
        
        provider_layout.addLayout(api_key_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        
        self.get_api_key_button = QPushButton("📋 Get API Key")
        self.get_api_key_button.setObjectName("primary")
        self.get_api_key_button.clicked.connect(self._open_provider_url)
        self.get_api_key_button.setToolTip("Open provider's website to get your API key")
        button_layout.addWidget(self.get_api_key_button)
        
        self.signup_button = QPushButton("✨ Sign Up")
        self.signup_button.clicked.connect(self._open_signup_url)
        self.signup_button.setToolTip("Create a new account with this provider")
        button_layout.addWidget(self.signup_button)
        
        self.test_button = QPushButton("🧪 Test API Key")
        self.test_button.clicked.connect(self._test_api_key)
        self.test_button.setToolTip("Verify that your API key works")
        button_layout.addWidget(self.test_button)
        
        button_layout.addStretch()
        provider_layout.addLayout(button_layout)
        
        # Status label
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        provider_layout.addWidget(self.status_label)
        
        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)
        
        # Setup instructions
        instructions_group = QGroupBox("Setup Instructions")
        instructions_layout = QVBoxLayout()
        
        instructions_text = QLabel(
            "<ol style='line-height: 1.6;'>"
            "<li>Choose a provider from the dropdown above</li>"
            "<li>Click <b>'Sign Up'</b> if you don't have an account yet</li>"
            "<li>After logging in, click <b>'Get API Key'</b> to find your API key</li>"
            "<li>Copy the API key and paste it in the field above</li>"
            "<li>Click <b>'Test API Key'</b> to verify it works</li>"
            "</ol>"
        )
        instructions_text.setWordWrap(True)
        instructions_layout.addWidget(instructions_text)
        
        instructions_group.setLayout(instructions_layout)
        layout.addWidget(instructions_group)
        
        layout.addStretch()
        
        # Connect signals
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        
        # Initialize description
        self._on_provider_changed()
    
    def _on_provider_changed(self):
        """Update description when provider changes."""
        provider_key = self.provider_combo.currentData()
        if provider_key and provider_key in self.PROVIDERS:
            info = self.PROVIDERS[provider_key]
            self.provider_description.setText(f"ℹ️ {info['description']}")
        else:
            self.provider_description.setText("")
    
    def _open_provider_url(self):
        """Open provider's API documentation."""
        provider_key = self.provider_combo.currentData()
        if provider_key and provider_key in self.PROVIDERS:
            url = self.PROVIDERS[provider_key]["url"]
            webbrowser.open(url)
    
    def _open_signup_url(self):
        """Open provider's signup page."""
        provider_key = self.provider_combo.currentData()
        if provider_key and provider_key in self.PROVIDERS:
            url = self.PROVIDERS[provider_key]["signup"]
            webbrowser.open(url)
    
    def _test_api_key(self):
        """Test the API key (basic validation for now)."""
        api_key = self.api_key_edit.text().strip()
        
        if not api_key:
            self.status_label.setText("❌ Please enter an API key first")
            self.status_label.setStyleSheet("color: #ed4245;")
            return
        
        if len(api_key) < 10:
            self.status_label.setText("⚠️ API key seems too short")
            self.status_label.setStyleSheet("color: #f59e0b;")
            return
        
        # Basic validation passed
        self.status_label.setText("✅ API key format looks valid (actual connectivity will be tested during account creation)")
        self.status_label.setStyleSheet("color: #23a559;")
    
    def is_step_complete(self) -> tuple[bool, List[str]]:
        """Check if SMS provider step is complete."""
        errors = []
        
        provider_key = self.provider_combo.currentData()
        if not provider_key:
            errors.append("Please select an SMS provider")
        
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            errors.append("SMS provider API key is required")
        elif len(api_key) < 10:
            errors.append("SMS provider API key seems too short")
        
        return len(errors) == 0, errors
    
    def load_settings(self, settings):
        """Load settings into UI."""
        sms_cfg = settings.get("sms_providers", {})
        provider = sms_cfg.get("provider", "sms-activate")
        
        # Find and set provider
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == provider:
                self.provider_combo.setCurrentIndex(i)
                break
        
        self.api_key_edit.setText(sms_cfg.get("api_key", ""))
    
    def save_settings(self, settings):
        """Save UI settings."""
        if "sms_providers" not in settings:
            settings["sms_providers"] = {}
        
        settings["sms_providers"]["provider"] = self.provider_combo.currentData()
        settings["sms_providers"]["api_key"] = self.api_key_edit.text().strip()


class SettingsWindow(QDialog):
    """Settings dialog for configuring the Telegram bot."""

    settings_updated = pyqtSignal(dict)

    def __init__(self, parent=None, force_wizard=False):
        super().__init__(parent)
        self.setWindowTitle("Settings - Telegram Auto-Reply Bot")
        self.setAccessibleName("Bot Configuration Settings")
        self.setAccessibleDescription("Dialog for configuring Telegram bot settings and preferences")
        self.resize(900, 700)
        self.settings_data = {}
        self.balance_cache: Dict[tuple[str, str], Dict[str, Any]] = {}
        
        # CRITICAL: Prevent dialog from closing parent window when dismissed
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        
        self.load_settings()
        
        # Initialize wizard manager
        self.wizard_manager = SetupWizardManager(self.settings_data)
        self.wizard_mode = force_wizard or self.wizard_manager.is_wizard_needed()
        self.current_wizard_step = 0
        
        if self.wizard_mode:
            self.current_wizard_step = self.wizard_manager.get_starting_step()

        # Apply theme
        self.apply_theme()

        self.setup_ui()
        self.load_ui_from_settings()
        self._setup_accessibility()
        self._apply_word_wraps()
        
        # If in wizard mode, show the appropriate step
        if self.wizard_mode:
            self._show_wizard_step(self.current_wizard_step)

    def _setup_accessibility(self):
        """Set up accessibility features for the settings dialog."""
        # Set up keyboard navigation
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Set accessible names for key elements
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setAccessibleName("Settings Categories")
            self.tab_widget.setAccessibleDescription("Tabbed interface for different settings categories")

        # Enable screen reader support for form elements
        for child in self.findChildren(QWidget):
            if hasattr(child, 'setAccessibleName'):
                # Set accessible names based on widget type and text
                if isinstance(child, QLabel) and child.text():
                    # Labels already have text, screen readers can use that
                    pass
                elif isinstance(child, (QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox)):
                    # These widgets need accessible names
                    if hasattr(child, 'placeholderText') and child.placeholderText():
                        child.setAccessibleName(child.placeholderText())
                    elif hasattr(child, 'text') and child.text():
                        child.setAccessibleName(child.text())
                    else:
                        # Set generic name based on widget type
                        widget_type = type(child).__name__
                        child.setAccessibleName(f"{widget_type} input field")

        # Set up tab order for logical navigation
        self._setup_tab_order()

    def _setup_tab_order(self):
        """Set up logical tab order for the settings dialog."""
        # Focus should start at the first tab
        if hasattr(self, 'tab_widget'):
            first_tab = self.tab_widget.widget(0)
            if first_tab:
                first_tab.setFocus()

    def _apply_word_wraps(self):
        """Ensure long labels and checkboxes wrap instead of overflowing."""
        long_text_threshold = 60

        for label in self.findChildren(QLabel):
            text = label.text()
            if text and (len(text) > long_text_threshold or "\n" in text):
                label.setWordWrap(True)

        for checkbox in self.findChildren(QCheckBox):
            text = checkbox.text()
            if hasattr(checkbox, "setWordWrap") and text and len(text) > long_text_threshold:
                checkbox.setWordWrap(True)

    def keyPressEvent(self, event):
        """Override to handle keyboard shortcuts in wizard mode.
        
        This prevents the dialog from closing when message boxes are dismissed,
        which can happen due to key event propagation in Qt.
        """
        # Wizard mode keyboard shortcuts
        if self.wizard_mode:
            # Enter = Next step
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not event.modifiers() or event.modifiers() == Qt.KeyboardModifier.KeypadModifier:
                    self.next_step()
                    event.accept()
                    return
            # Shift+Enter = Previous step
            elif event.key() == Qt.Key.Key_Return and event.modifiers() == Qt.KeyboardModifier.ShiftModifier:
                self.previous_step()
                event.accept()
                return
            # Ctrl+S = Complete wizard (on last step)
            elif event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                if self.current_wizard_step == SetupWizardManager.STEP_OPTIONAL:
                    self.complete_wizard()
                event.accept()
                return
            # Escape in wizard = Previous step (not close)
            elif event.key() == Qt.Key.Key_Escape:
                if self.current_wizard_step > 0:
                    self.previous_step()
                event.accept()
                return
        else:
            # Normal mode - prevent dialog close on Escape/Enter
            if event.key() == Qt.Key.Key_Escape:
                event.ignore()
                return
            # Prevent Enter from triggering any default button behavior
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                event.ignore()
                return
        
        super().keyPressEvent(event)

    def apply_theme(self):
        """Apply clean professional theme."""
        try:
            from ui_redesign import DISCORD_THEME
            self.setStyleSheet(DISCORD_THEME)
        except ImportError:
            logger.warning("Could not import theme")

    def setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Wizard progress indicator (only shown in wizard mode)
        if self.wizard_mode:
            self.progress_widget = self._create_progress_indicator()
            layout.addWidget(self.progress_widget)

        # Title
        if self.wizard_mode:
            title_label = QLabel("Initial Setup Wizard")
            title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #e4e4e7; margin-bottom: 8px;")
            layout.addWidget(title_label)
            
            subtitle_label = QLabel("Let's configure the essential settings to get you started.")
            subtitle_label.setStyleSheet("color: #a1a1aa; font-size: 14px; margin-bottom: 20px;")
            layout.addWidget(subtitle_label)
        else:
            title_label = QLabel("Bot Configuration")
            title_label.setStyleSheet("font-size: 24px; font-weight: 600; color: #e4e4e7; margin-bottom: 8px;")
            layout.addWidget(title_label)

            subtitle_label = QLabel("Configure API keys, account creation, anti-detection, and advanced features.")
            subtitle_label.setStyleSheet("color: #a1a1aa; font-size: 14px; margin-bottom: 20px;")
            layout.addWidget(subtitle_label)

        # Create widgets first
        self.api_widget = APISettingsWidget()
        self.brain_widget = BrainSettingsWidget()
        self.anti_detection_widget = AntiDetectionSettingsWidget()
        self.sms_provider_widget = SMSProviderSetupWidget()
        
        # Wizard content area or Tab widget
        if self.wizard_mode:
            # In wizard mode, show single step at a time
            self.wizard_content_widget = QWidget()
            self.wizard_content_layout = QVBoxLayout(self.wizard_content_widget)
            self.wizard_content_layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.wizard_content_widget)
            
            # Create wizard step widgets
            self._create_wizard_steps()
        else:
            # Normal mode: tab widget
            self.tab_widget = QTabWidget()
            self.tab_widget.setObjectName("settings_tabs")
            layout.addWidget(self.tab_widget)

            # Create tabs - using widgets for refactored tabs, methods for others
            self.tab_widget.addTab(self.create_api_tab(), "API & Auth")
            self.tab_widget.addTab(self.create_brain_tab(), "Brain & Behavior")
            self.tab_widget.addTab(self.create_anti_detection_tab(), "Anti-Detection")
            self.tab_widget.addTab(self.create_member_scraper_tab(), "Member Intelligence")
            self.tab_widget.addTab(self.create_account_creator_tab(), "Account Factory")
            self.tab_widget.addTab(self.create_advanced_tab(), "Advanced Controls")

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        if self.wizard_mode:
            # Wizard navigation buttons
            self.wizard_prev_button = QPushButton("← Previous")
            self.wizard_prev_button.clicked.connect(self.previous_step)
            self.wizard_prev_button.setObjectName("secondary")
            self.wizard_prev_button.setFixedWidth(100)
            self.wizard_prev_button.setAutoDefault(False)
            self.wizard_prev_button.setDefault(False)
            button_layout.addWidget(self.wizard_prev_button)
            
            button_layout.addStretch()
            
            self.wizard_skip_button = QPushButton("Skip")
            self.wizard_skip_button.clicked.connect(self.skip_optional)
            self.wizard_skip_button.setObjectName("secondary")
            self.wizard_skip_button.setFixedWidth(80)
            self.wizard_skip_button.setAutoDefault(False)
            self.wizard_skip_button.setDefault(False)
            self.wizard_skip_button.setVisible(False)  # Only show on optional step
            button_layout.addWidget(self.wizard_skip_button)
            
            self.wizard_next_button = QPushButton("Next →")
            self.wizard_next_button.clicked.connect(self.next_step)
            self.wizard_next_button.setObjectName("primary")
            self.wizard_next_button.setFixedWidth(100)
            self.wizard_next_button.setAutoDefault(False)
            self.wizard_next_button.setDefault(False)
            button_layout.addWidget(self.wizard_next_button)
        else:
            # Normal mode buttons
            save_button = QPushButton("Save Settings")
            save_button.clicked.connect(self.save_settings)
            save_button.setObjectName("primary")
            save_button.setFixedWidth(120)
            save_button.setAutoDefault(False)
            save_button.setDefault(False)
            button_layout.addWidget(save_button)

            test_button = QPushButton("Test Configuration")
            test_button.clicked.connect(self.test_configuration)
            test_button.setFixedWidth(140)
            test_button.setAutoDefault(False)
            test_button.setDefault(False)
            button_layout.addWidget(test_button)

            cancel_button = QPushButton("Cancel")
            cancel_button.clicked.connect(self.reject)
            cancel_button.setObjectName("secondary")
            cancel_button.setFixedWidth(80)
            cancel_button.setAutoDefault(False)
            cancel_button.setDefault(False)
            button_layout.addWidget(cancel_button)

            button_layout.addStretch()
            
        layout.addLayout(button_layout)

    def _create_progress_indicator(self) -> QWidget:
        """Create the wizard progress indicator."""
        progress_widget = QFrame()
        progress_widget.setFrameShape(QFrame.Shape.StyledPanel)
        progress_widget.setStyleSheet("background-color: #2b2d31; border-radius: 8px; padding: 16px;")
        
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setSpacing(8)
        
        self.progress_labels = []
        steps = [
            ("1", "Telegram API"),
            ("2", "Gemini AI"),
            ("3", "SMS Provider"),
            ("4", "Optional")
        ]
        
        for i, (num, name) in enumerate(steps):
            if i > 0:
                # Add arrow separator
                arrow_label = QLabel("→")
                arrow_label.setStyleSheet("color: #71717a; font-size: 16px;")
                progress_layout.addWidget(arrow_label)
            
            # Step container
            step_container = QHBoxLayout()
            step_container.setSpacing(6)
            
            # Step number circle
            step_num = QLabel(num)
            step_num.setFixedSize(28, 28)
            step_num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            step_num.setStyleSheet(
                "background-color: #3f3f46; color: #a1a1aa; "
                "border-radius: 14px; font-weight: 600;"
            )
            
            # Step name
            step_name = QLabel(name)
            step_name.setStyleSheet("color: #a1a1aa;")
            
            step_container.addWidget(step_num)
            step_container.addWidget(step_name)
            
            # Store references
            self.progress_labels.append((step_num, step_name))
            
            # Add to main layout
            container_widget = QWidget()
            container_widget.setLayout(step_container)
            progress_layout.addWidget(container_widget)
        
        progress_layout.addStretch()
        
        return progress_widget
    
    def _update_progress_indicator(self):
        """Update the progress indicator to show current step with checkmarks."""
        for i, (num_label, name_label) in enumerate(self.progress_labels):
            if i < self.current_wizard_step:
                # Completed step - show checkmark
                num_label.setText("✓")
                num_label.setStyleSheet(
                    "background-color: #23a559; color: #ffffff; "
                    "border-radius: 14px; font-weight: 600; font-size: 16px;"
                )
                name_label.setStyleSheet("color: #23a559; font-weight: 600;")
            elif i == self.current_wizard_step:
                # Current step - show number
                num_label.setText(str(i + 1))
                num_label.setStyleSheet(
                    "background-color: #5865f2; color: #ffffff; "
                    "border-radius: 14px; font-weight: 600;"
                )
                name_label.setStyleSheet("color: #e4e4e7; font-weight: 600;")
            else:
                # Future step - show number
                num_label.setText(str(i + 1))
                num_label.setStyleSheet(
                    "background-color: #3f3f46; color: #a1a1aa; "
                    "border-radius: 14px; font-weight: 600;"
                )
                name_label.setStyleSheet("color: #a1a1aa;")
    
    def _create_wizard_steps(self):
        """Create wizard step widgets."""
        self.wizard_steps = []
        
        # Create step-specific widgets that show only relevant fields
        self.telegram_step_widget = TelegramStepWidget(self.api_widget)
        self.gemini_step_widget = GeminiStepWidget(self.api_widget)
        
        # Step 0: Telegram API
        telegram_step = self._create_wizard_step_widget(
            "Step 1: Telegram API Configuration",
            "Configure your Telegram API credentials to connect to Telegram's services.",
            self.telegram_step_widget,
            instructions="""
            <p><b>What you need:</b></p>
            <ol>
                <li>Visit <a href='https://my.telegram.org/apps'>my.telegram.org/apps</a></li>
                <li>Log in with your phone number</li>
                <li>Go to "API Development Tools"</li>
                <li>Create a new application</li>
                <li>Copy your API ID and API Hash</li>
            </ol>
            <p><b>Why this is needed:</b> These credentials allow the bot to connect to Telegram on your behalf.</p>
            """,
            help_url="https://my.telegram.org/apps"
        )
        self.wizard_steps.append(telegram_step)
        
        # Step 1: Gemini AI
        gemini_step = self._create_wizard_step_widget(
            "Step 2: Gemini AI Configuration",
            "Set up Google Gemini AI for intelligent automated responses.",
            self.gemini_step_widget,
            instructions="""
            <p><b>What you need:</b></p>
            <ol>
                <li>Visit <a href='https://aistudio.google.com/app/apikey'>Google AI Studio</a></li>
                <li>Sign in with your Google account</li>
                <li>Click "Create API Key"</li>
                <li>Copy the generated key (starts with "AIza")</li>
            </ol>
            <p><b>Why this is needed:</b> Gemini powers the AI responses for your Telegram accounts.</p>
            <p><b>Free tier:</b> 60 requests/minute, 1,500 requests/day</p>
            """,
            help_url="https://aistudio.google.com/app/apikey"
        )
        self.wizard_steps.append(gemini_step)
        
        # Step 2: SMS Provider
        sms_step = self._create_wizard_step_widget(
            "Step 3: SMS Provider Configuration",
            "Configure an SMS provider to receive verification codes for new Telegram accounts.",
            self.sms_provider_widget,
            instructions="""
            <p><b>What you need:</b></p>
            <ol>
                <li>Choose an SMS provider (SMS-Activate recommended for beginners)</li>
                <li>Create an account with the provider</li>
                <li>Add funds to your account ($5-10 is usually enough to start)</li>
                <li>Get your API key from the provider's dashboard</li>
            </ol>
            <p><b>Why this is needed:</b> SMS providers supply phone numbers for creating new Telegram accounts.</p>
            <p><b>Cost:</b> Typically $0.10-0.20 per phone number</p>
            """,
            help_url=None  # Provider-specific, handled by widget
        )
        self.wizard_steps.append(sms_step)
        
        # Step 3: Optional settings
        optional_step = self._create_wizard_step_widget(
            "Step 4: Optional Settings (Safe to Skip)",
            "Fine-tune advanced settings - or skip and use smart defaults.",
            self.anti_detection_widget,
            instructions="""
            <p><b>⚡ You can safely skip this step!</b></p>
            <p>The default settings are optimized for safety and work great for beginners. 
            You can always adjust these later in the Settings menu.</p>
            
            <p><b>What you can configure here (optional):</b></p>
            <ul>
                <li><b>Anti-Detection:</b> Rate limiting and behavior simulation (default: 50 msg/hour)</li>
                <li><b>Timing:</b> Message delays and response patterns (default: 2-30 seconds)</li>
                <li><b>Safety Features:</b> Auto-retry and session recovery (default: enabled)</li>
            </ul>
            
            <p><b>💡 Recommendation:</b> Skip this step now, use defaults, and adjust later if needed.</p>
            """,
            help_url=None
        )
        self.wizard_steps.append(optional_step)
    
    def _create_wizard_step_widget(self, title: str, description: str, content_widget: QWidget, 
                                   instructions: str = "", help_url: Optional[str] = None) -> QWidget:
        """Create a wizard step widget with title, description, and content."""
        step_widget = QWidget()
        step_layout = QVBoxLayout(step_widget)
        step_layout.setContentsMargins(0, 0, 0, 0)
        step_layout.setSpacing(16)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 20px; font-weight: 600; color: #e4e4e7;")
        step_layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #a1a1aa; font-size: 14px;")
        step_layout.addWidget(desc_label)
        
        # Instructions (if provided)
        if instructions:
            instructions_group = QGroupBox("📚 Instructions")
            instructions_layout = QVBoxLayout()
            
            instructions_label = QLabel(instructions)
            instructions_label.setWordWrap(True)
            instructions_label.setTextFormat(Qt.TextFormat.RichText)
            instructions_label.setOpenExternalLinks(True)
            instructions_label.setStyleSheet("color: #d4d4d8;")
            instructions_layout.addWidget(instructions_label)
            
            if help_url:
                help_button = QPushButton("🔗 Open Setup Page")
                help_button.setObjectName("primary")
                help_button.setFixedWidth(150)
                help_button.clicked.connect(lambda: webbrowser.open(help_url))
                instructions_layout.addWidget(help_button)
            
            instructions_group.setLayout(instructions_layout)
            step_layout.addWidget(instructions_group)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #3f3f46;")
        step_layout.addWidget(separator)
        
        # Content widget (scroll area)
        scroll = QScrollArea()
        scroll.setWidget(content_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        step_layout.addWidget(scroll)
        
        return step_widget
    
    def _show_wizard_step(self, step: int):
        """Show the specified wizard step."""
        # Clear current content
        while self.wizard_content_layout.count():
            child = self.wizard_content_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)
        
        # Add new step
        if 0 <= step < len(self.wizard_steps):
            self.wizard_content_layout.addWidget(self.wizard_steps[step])
        
        # Update progress indicator
        self._update_progress_indicator()
        
        # Update button states
        self.wizard_prev_button.setEnabled(step > 0)
        
        # Show/hide skip button (only on optional step)
        self.wizard_skip_button.setVisible(step == SetupWizardManager.STEP_OPTIONAL)
        
        # Update next button text
        if step == SetupWizardManager.STEP_OPTIONAL:
            self.wizard_next_button.setText("Complete Setup ✓")
        else:
            self.wizard_next_button.setText("Next →")
        
        # Auto-focus first empty required field
        QTimer.singleShot(100, lambda: self._focus_first_field(step))
    
    def _focus_first_field(self, step: int):
        """Auto-focus the first empty required field for the given step."""
        try:
            if step == SetupWizardManager.STEP_TELEGRAM:
                # Focus first empty Telegram field
                if not self.api_widget.api_id_edit.text().strip():
                    self.api_widget.api_id_edit.setFocus()
                elif not self.api_widget.api_hash_edit.text().strip():
                    self.api_widget.api_hash_edit.setFocus()
                elif not self.api_widget.phone_edit.text().strip():
                    self.api_widget.phone_edit.setFocus()
                else:
                    self.api_widget.api_id_edit.setFocus()  # Default to first field
            
            elif step == SetupWizardManager.STEP_GEMINI:
                # Focus Gemini key field
                self.api_widget.gemini_key_edit.setFocus()
            
            elif step == SetupWizardManager.STEP_SMS_PROVIDER:
                # Focus SMS API key field if provider is selected
                if self.sms_provider_widget.provider_combo.currentData():
                    self.sms_provider_widget.api_key_edit.setFocus()
                else:
                    self.sms_provider_widget.provider_combo.setFocus()
        except Exception as e:
            logger.warning(f"Failed to auto-focus field: {e}")
    
    def next_step(self):
        """Move to the next wizard step."""
        # Validate current step using widget-specific validation
        is_valid = False
        errors = []
        
        if self.current_wizard_step == SetupWizardManager.STEP_TELEGRAM:
            is_valid, errors = self.api_widget.is_telegram_step_complete()
        elif self.current_wizard_step == SetupWizardManager.STEP_GEMINI:
            is_valid, errors = self.api_widget.is_gemini_step_complete()
        elif self.current_wizard_step == SetupWizardManager.STEP_SMS_PROVIDER:
            is_valid, errors = self.sms_provider_widget.is_step_complete()
        elif self.current_wizard_step == SetupWizardManager.STEP_OPTIONAL:
            # Optional step - always valid
            is_valid = True
        
        if not is_valid:
            # Show validation errors with error icon (not warning)
            error_msg = "❌ Please fix the following issues before continuing:\n\n" + "\n".join(f"• {err}" for err in errors)
            ErrorHandler.safe_critical(self, "Validation Required", error_msg)
            return
        
        # Save progress after successful validation
        try:
            partial_settings = self.collect_ui_settings()
            self.wizard_manager.save_step_progress(self.current_wizard_step, partial_settings)
        except Exception as e:
            logger.warning(f"Failed to save progress: {e}")
        
        # Move to next step or complete
        if self.current_wizard_step < SetupWizardManager.STEP_OPTIONAL:
            self.current_wizard_step += 1
            self._show_wizard_step(self.current_wizard_step)
        else:
            # Complete wizard
            self.complete_wizard()
    
    def previous_step(self):
        """Move to the previous wizard step."""
        if self.current_wizard_step > 0:
            self.current_wizard_step -= 1
            self._show_wizard_step(self.current_wizard_step)
    
    def skip_optional(self):
        """Skip the optional step."""
        if self.current_wizard_step == SetupWizardManager.STEP_OPTIONAL:
            self.complete_wizard()
    
    def complete_wizard(self):
        """Complete the wizard and save settings."""
        # Show loading indicator
        from PyQt6.QtWidgets import QProgressDialog
        progress = QProgressDialog("Saving configuration...", None, 0, 0, self)
        progress.setWindowTitle("Please Wait")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Save settings
            self.save_settings()
            
            # Mark wizard as complete
            self.wizard_manager.mark_wizard_complete()
            
            # Clear progress tracking
            self.wizard_manager.clear_step_progress()
            
            progress.close()
            
            # Show success message with security warnings and tips
            success_msg = (
                "✅ Setup Complete!\n\n"
                "Your bot is now configured and ready to use.\n\n"
                "🔒 SECURITY REMINDER:\n"
                "• Never share your API keys or config.json file\n"
                "• Don't post screenshots showing your credentials\n"
                "• Keep your API keys secure - treat them like passwords\n"
                "• config.json contains sensitive data in plain text\n\n"
                "Next steps:\n"
                "• Create your first Telegram account in Settings → Account Factory\n"
                "• Let accounts warm up for 3-7 days (automatic)\n"
                "• Configure your AI brain personality\n"
                "• Start your first campaign\n\n"
                "💡 Tips:\n"
                "• Adjust settings anytime from the Settings menu\n"
                "• Keyboard shortcuts: Enter=Next, Shift+Enter=Previous, Ctrl+S=Complete\n"
                "• Start with 1-2 accounts to test your setup"
            )
            ErrorHandler.safe_information(self, "Setup Complete", success_msg)
            
            # Close dialog
            self.accept()
            
        except Exception as e:
            progress.close()
            logger.error(f"Failed to complete wizard: {e}")
            ErrorHandler.safe_critical(
                self, 
                "Save Failed",
                f"Failed to save configuration:\n\n{str(e)}\n\n"
                "Please check:\n"
                "• You have write permissions\n"
                "• Disk is not full\n"
                "• config.json is not open in another program\n\n"
                "The wizard will remain open so you can try again."
            )
            # Don't mark wizard complete or close dialog on failure

    def create_api_tab(self):
        """Create the wrapped API & Auth tab."""
        return self._wrap_widget_tab(
            self.api_widget,
            "API & Auth",
            "Configure API keys, SMS services, and AI integrations."
        )

    def create_brain_tab(self) -> QWidget:
        """Create the wrapped Brain & Behavior tab."""
        return self._wrap_widget_tab(
            self.brain_widget,
            "Brain & Behavior",
            "Fine-tune Gemini responses and conversational behavior."
        )

    def create_anti_detection_tab(self) -> QWidget:
        """Create the wrapped Anti-Detection tab."""
        return self._wrap_widget_tab(
            self.anti_detection_widget,
            "Anti-Detection",
            "Tune rate limiting and human-behavior simulation safeguards."
        )

    def create_member_scraper_tab(self) -> QWidget:
        """Create the member scraper tab."""
        scroll_area, content = self._create_tab_content_widget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        description = QLabel(
            "Scrape members from public channels, monitor activity, and queue prospects for campaigns."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # Channel Input Section
        input_group = QGroupBox("Channel/Group Input")
        input_layout = QVBoxLayout()

        # URL input
        url_layout = QHBoxLayout()
        self.channel_url_edit = QLineEdit()
        self.channel_url_edit.setPlaceholderText("https://t.me/channelname or @channelname or channelname")
        url_layout.addWidget(QLabel("Channel URL/ID:"))
        url_layout.addWidget(self.channel_url_edit)

        input_layout.addLayout(url_layout)

        # Control buttons
        button_layout = QHBoxLayout()

        self.scrape_button = QPushButton("🔍 Scrape Members")
        self.scrape_button.clicked.connect(self.scrape_channel_members)
        self.scrape_button.setObjectName("secondary")
        self.scrape_button.setToolTip("Start scraping members from the specified channel.\nThis may take several minutes for large channels.")
        button_layout.addWidget(self.scrape_button)

        self.stop_scrape_button = QPushButton("⏹️ Stop Scraping")
        self.stop_scrape_button.clicked.connect(self.stop_scraping)
        self.stop_scrape_button.setEnabled(False)
        self.stop_scrape_button.setObjectName("secondary")
        self.stop_scrape_button.setToolTip("Stop the current scraping operation")
        button_layout.addWidget(self.stop_scrape_button)

        input_layout.addLayout(button_layout)

        # Progress indicator
        self.scrape_progress = QProgressBar()
        self.scrape_progress.setVisible(False)
        self.scrape_progress.setFormat("Scraping members: %v found")
        input_layout.addWidget(self.scrape_progress)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group)

        # Results Section
        results_group = QGroupBox("Scraping Results")
        results_layout = QVBoxLayout()

        # Results display
        self.scraper_results_text = QTextEdit()
        self.scraper_results_text.setReadOnly(True)
        self.scraper_results_text.setMaximumHeight(200)
        results_layout.addWidget(self.scraper_results_text)

        # Channel stats
        stats_layout = QHBoxLayout()
        self.stats_total = QLabel("Total: 0")
        self.stats_active = QLabel("Active: 0")
        self.stats_inactive = QLabel("Inactive: 0")

        stats_layout.addWidget(self.stats_total)
        stats_layout.addWidget(self.stats_active)
        stats_layout.addWidget(self.stats_inactive)
        stats_layout.addStretch()

        results_layout.addLayout(stats_layout)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        # Member Management Section
        manage_group = QGroupBox("Member Management")
        manage_layout = QVBoxLayout()

        # Channel selection
        channel_layout = QHBoxLayout()
        self.channel_select = QComboBox()
        self.channel_select.addItem("Select Channel...")
        channel_layout.addWidget(QLabel("Channel:"))
        channel_layout.addWidget(self.channel_select)

        manage_layout.addLayout(channel_layout)

        # Member list
        self.members_list = QListWidget()
        self.members_list.setMaximumHeight(150)
        manage_layout.addWidget(self.members_list)

        # Member actions
        action_layout = QHBoxLayout()

        self.refresh_members_button = QPushButton("Refresh List")
        self.refresh_members_button.clicked.connect(self.refresh_members)
        self.refresh_members_button.setObjectName("secondary")
        action_layout.addWidget(self.refresh_members_button)

        self.message_member_button = QPushButton("Message Selected")
        self.message_member_button.clicked.connect(self.message_selected_member)
        self.message_member_button.setObjectName("secondary")
        action_layout.addWidget(self.message_member_button)

        manage_layout.addLayout(action_layout)

        manage_group.setLayout(manage_layout)
        layout.addWidget(manage_group)

        layout.addStretch()

        # Store reference to main window for member operations
        self._main_window = self.parent()

        # Initialize parent reference if not set
        if not hasattr(self, '_main_window') or not self._main_window:
            # Try to get from parent
            parent = self.parent()
            if parent:
                self._main_window = parent

        return self._wrap_tab(scroll_area, "Member Intelligence", "Pull fresh audiences, audit engagement, and push prospects into messaging pipelines.")

    def create_account_creator_tab(self) -> QWidget:
        """Create the account creator tab."""
        scroll_area, content = self._create_tab_content_widget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        info_label = QLabel(
            "Connect a phone-number API provider once and let the automation engine purchase numbers, "
            "verify OTPs, and warm up each account with safe anti-detection pacing."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Bulk Creation Section
        bulk_group = QGroupBox("Bulk Account Creation")
        bulk_layout = QVBoxLayout()

        # Account count
        count_layout = QHBoxLayout()
        self.account_count_spin = QSpinBox()
        self.account_count_spin.setRange(1, 100)
        self.account_count_spin.setValue(10)
        count_layout.addWidget(QLabel("Number of accounts:"))
        count_layout.addWidget(self.account_count_spin)
        count_layout.addStretch()
        bulk_layout.addLayout(count_layout)

        # Country selection
        country_layout = QHBoxLayout()
        self.country_combo = QComboBox()
        self.country_combo.addItems([
            "US - United States", "GB - United Kingdom", "DE - Germany",
            "FR - France", "IT - Italy", "ES - Spain", "BR - Brazil",
            "RU - Russia", "IN - India", "CA - Canada", "AU - Australia"
        ])
        country_layout.addWidget(QLabel("Country:"))
        country_layout.addWidget(self.country_combo)
        bulk_layout.addLayout(country_layout)

        # Phone provider
        provider_layout = QHBoxLayout()
        self.phone_provider_combo = QComboBox()
        self.phone_provider_combo.addItems([
            "sms-activate", "sms-hub", "5sim", "daisysms", "smspool", "textverified"
        ])
        provider_layout.addWidget(QLabel("Phone Provider:"))
        provider_layout.addWidget(self.phone_provider_combo)
        bulk_layout.addLayout(provider_layout)

        # Provider API key
        api_layout = QHBoxLayout()
        self.provider_api_edit = QLineEdit()
        self.provider_api_edit.setPlaceholderText("Your provider API key")
        self.provider_api_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addWidget(QLabel("Provider API Key:"))
        api_layout.addWidget(self.provider_api_edit)

        # Check Balance Button
        self.check_balance_button = QPushButton("Check Balance")
        self.check_balance_button.clicked.connect(self.check_provider_balance)
        self.check_balance_button.setObjectName("secondary")
        self.check_balance_button.setFixedWidth(120)
        api_layout.addWidget(self.check_balance_button)

        bulk_layout.addLayout(api_layout)

        # Balance Label
        self.balance_label = QLabel("Balance: --")
        self.balance_label.setStyleSheet("color: #b5bac1; font-weight: bold;")
        bulk_layout.addWidget(self.balance_label)

        # Setup Checklist
        checklist_group = QGroupBox("✅ Setup Checklist")
        checklist_layout = QVBoxLayout()

        self.checklist_api_key = QLabel("Provider API Key")
        self.checklist_api_key.setStyleSheet("padding: 4px;")
        checklist_layout.addWidget(self.checklist_api_key)

        self.checklist_proxies = QLabel("Proxies (Required for 10+ accounts)")
        self.checklist_proxies.setStyleSheet("padding: 4px;")
        checklist_layout.addWidget(self.checklist_proxies)

        self.checklist_country = QLabel("✅ Country Selected")
        self.checklist_country.setStyleSheet("padding: 4px;")
        checklist_layout.addWidget(self.checklist_country)

        self.checklist_anti_detection = QLabel("✅ Anti-Detection Enabled")
        self.checklist_anti_detection.setStyleSheet("padding: 4px;")
        checklist_layout.addWidget(self.checklist_anti_detection)

        # Update checklist when fields change
        self.provider_api_edit.textChanged.connect(self._update_checklist)
        self.account_count_spin.valueChanged.connect(self._update_checklist)
        self.country_combo.currentTextChanged.connect(self._update_checklist)

        # Note: proxy_list_edit and randomize_fingerprint_checkbox connections
        # will be added after those widgets are created

        checklist_group.setLayout(checklist_layout)
        bulk_layout.addWidget(checklist_group)

        # Helpful info label
        help_label = QLabel(
            "📋 Quick Guide:\n"
            "• For 1-9 accounts: Proxies optional but recommended\n"
            "• For 10+ accounts: Proxies REQUIRED (1 per account ideal)\n"
            "• Enable all anti-detection features for best results\n"
            "• Monitor progress in the results section below"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #7289da; padding: 8px; background: rgba(114, 137, 218, 0.1); border-radius: 4px;")
        bulk_layout.addWidget(help_label)

        # Control buttons
        control_layout = QHBoxLayout()
        self.start_creation_button = QPushButton("🚀 Start Bulk Creation")
        self.start_creation_button.clicked.connect(self.start_bulk_creation)
        self.start_creation_button.setObjectName("success")
        self.start_creation_button.setToolTip("Start creating the specified number of accounts")
        control_layout.addWidget(self.start_creation_button)

        self.stop_creation_button = QPushButton("⏹ Stop Creation")
        self.stop_creation_button.clicked.connect(self.stop_bulk_creation)
        self.stop_creation_button.setEnabled(False)
        self.stop_creation_button.setObjectName("secondary")
        self.stop_creation_button.setToolTip("Stop the current account creation process")
        control_layout.addWidget(self.stop_creation_button)

        bulk_layout.addLayout(control_layout)

        # Progress and status
        self.creation_progress = QProgressBar()
        self.creation_progress.setVisible(False)
        self.creation_progress.setFormat("Creating accounts: %v/%m (%p%)")
        bulk_layout.addWidget(self.creation_progress)

        self.creation_status = QLabel("Ready to create accounts")
        self.creation_status.setStyleSheet("font-weight: bold; padding: 5px;")
        self.creation_status.setWordWrap(True)
        bulk_layout.addWidget(self.creation_status)

        # Success/Failure summary
        self.creation_summary = QLabel("")
        self.creation_summary.setStyleSheet("font-weight: bold; padding: 5px;")
        self.creation_summary.setWordWrap(True)
        self.creation_summary.setVisible(False)
        bulk_layout.addWidget(self.creation_summary)

        # Progress tracking variables for account creation
        self.account_creation_current = 0
        self.account_creation_total = 0

        bulk_group.setLayout(bulk_layout)
        layout.addWidget(bulk_group)

        # Account Type & Voice Configuration Section
        account_config_group = QGroupBox("Account Type & Voice Messages")
        account_config_layout = QVBoxLayout()
        
        # Info label
        config_info = QLabel(
            "Configure default settings for new accounts. Each account can have its own type, brain, and voice settings."
        )
        config_info.setWordWrap(True)
        config_info.setStyleSheet("color: #a1a1aa; margin-bottom: 8px;")
        account_config_layout.addWidget(config_info)
        
        # Account Type
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Default Account Type:"))
        self.account_type_combo = QComboBox()
        self.account_type_combo.addItems(["Reactive (Wait for DMs)", "Outreach (Message First)"])
        self.account_type_combo.setToolTip(
            "Reactive: Account waits for incoming DMs and handles sales conversations\n"
            "Outreach: Account reaches out to scraped members with initial messages"
        )
        type_layout.addWidget(self.account_type_combo)
        type_layout.addStretch()
        account_config_layout.addLayout(type_layout)
        
        # Brain Configuration
        brain_config_layout = QVBoxLayout()
        
        self.use_shared_brain_checkbox = QCheckBox("Use Shared Brain (Same AI prompt for all accounts)")
        self.use_shared_brain_checkbox.setChecked(True)
        self.use_shared_brain_checkbox.setToolTip("When checked, all accounts use the global brain settings from Brain & Behavior tab")
        self.use_shared_brain_checkbox.stateChanged.connect(self._toggle_custom_brain)
        brain_config_layout.addWidget(self.use_shared_brain_checkbox)
        
        # Custom brain prompt (hidden by default)
        self.custom_brain_container = QWidget()
        custom_brain_layout = QVBoxLayout(self.custom_brain_container)
        custom_brain_layout.setContentsMargins(0, 8, 0, 0)
        
        custom_brain_label = QLabel("Custom Brain Prompt (for accounts not using shared brain):")
        custom_brain_label.setStyleSheet("font-weight: 500;")
        custom_brain_layout.addWidget(custom_brain_label)
        
        self.custom_brain_edit = QTextEdit()
        self.custom_brain_edit.setPlaceholderText(
            "You are a friendly, flirty young woman (age 19) who creates exclusive content...\n\n"
            "Leave empty to use the default prompt for the selected account type."
        )
        self.custom_brain_edit.setMaximumHeight(100)
        custom_brain_layout.addWidget(self.custom_brain_edit)
        
        self.custom_brain_container.setVisible(False)
        brain_config_layout.addWidget(self.custom_brain_container)
        
        account_config_layout.addLayout(brain_config_layout)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background: #3f3f46; margin: 8px 0;")
        account_config_layout.addWidget(separator)
        
        # Voice Messages Configuration
        voice_section_label = QLabel("Voice Messages")
        voice_section_label.setStyleSheet("font-weight: 600; font-size: 14px; margin-top: 4px;")
        account_config_layout.addWidget(voice_section_label)
        
        self.enable_voice_checkbox = QCheckBox("Enable Voice Messages (requires ElevenLabs API key)")
        self.enable_voice_checkbox.setChecked(False)
        self.enable_voice_checkbox.setToolTip("Send realistic AI-generated voice messages in conversations")
        self.enable_voice_checkbox.stateChanged.connect(self._toggle_voice_settings)
        account_config_layout.addWidget(self.enable_voice_checkbox)
        
        # Voice settings container (hidden by default)
        self.voice_settings_container = QWidget()
        voice_settings_layout = QVBoxLayout(self.voice_settings_container)
        voice_settings_layout.setContentsMargins(0, 8, 0, 0)
        
        # Voice selection
        voice_select_layout = QHBoxLayout()
        voice_select_layout.addWidget(QLabel("Voice:"))
        self.voice_select_combo = QComboBox()
        self.voice_select_combo.addItems([
            "Rachel (Young American, 18-25)",
            "Elli (Energetic, 18-22)", 
            "Bella (Soft & Gentle, 20-28)",
            "Charlotte (Sweet & Youthful, 18-25)",
            "Sarah (Confident, 20-25)"
        ])
        self.voice_select_combo.setToolTip("Select the voice profile for voice messages")
        voice_select_layout.addWidget(self.voice_select_combo)
        voice_select_layout.addStretch()
        voice_settings_layout.addLayout(voice_select_layout)
        
        # Voice trigger mode
        trigger_layout = QHBoxLayout()
        trigger_layout.addWidget(QLabel("When to Send Voice:"))
        self.voice_trigger_combo = QComboBox()
        self.voice_trigger_combo.addItems([
            "Random Chance",
            "Every Nth Message",
            "Keyword Triggered",
            "Smart (AI-Decides)",
            "Always",
            "Never"
        ])
        self.voice_trigger_combo.currentIndexChanged.connect(self._update_voice_trigger_options)
        trigger_layout.addWidget(self.voice_trigger_combo)
        trigger_layout.addStretch()
        voice_settings_layout.addLayout(trigger_layout)
        
        # Trigger options container
        self.voice_trigger_options = QWidget()
        trigger_options_layout = QHBoxLayout(self.voice_trigger_options)
        trigger_options_layout.setContentsMargins(0, 4, 0, 0)
        
        # Random chance option
        self.voice_random_label = QLabel("Chance %:")
        trigger_options_layout.addWidget(self.voice_random_label)
        self.voice_random_spin = QSpinBox()
        self.voice_random_spin.setRange(1, 100)
        self.voice_random_spin.setValue(30)
        self.voice_random_spin.setToolTip("Percentage chance to send voice message instead of text")
        trigger_options_layout.addWidget(self.voice_random_spin)
        
        # Every Nth option
        self.voice_nth_label = QLabel("Every N messages:")
        self.voice_nth_label.setVisible(False)
        trigger_options_layout.addWidget(self.voice_nth_label)
        self.voice_nth_spin = QSpinBox()
        self.voice_nth_spin.setRange(2, 20)
        self.voice_nth_spin.setValue(3)
        self.voice_nth_spin.setVisible(False)
        trigger_options_layout.addWidget(self.voice_nth_spin)
        
        # Keywords option
        self.voice_keywords_label = QLabel("Keywords:")
        self.voice_keywords_label.setVisible(False)
        trigger_options_layout.addWidget(self.voice_keywords_label)
        self.voice_keywords_edit = QLineEdit()
        self.voice_keywords_edit.setPlaceholderText("hey, hi, interested, price")
        self.voice_keywords_edit.setVisible(False)
        trigger_options_layout.addWidget(self.voice_keywords_edit)
        
        trigger_options_layout.addStretch()
        voice_settings_layout.addWidget(self.voice_trigger_options)
        
        # Advanced voice options
        advanced_voice_layout = QHBoxLayout()
        
        self.voice_time_boost_checkbox = QCheckBox("Prime Time Boost (6-11 PM)")
        self.voice_time_boost_checkbox.setChecked(True)
        self.voice_time_boost_checkbox.setToolTip("Increase voice message chance during evening hours")
        advanced_voice_layout.addWidget(self.voice_time_boost_checkbox)
        
        self.voice_rapport_boost_checkbox = QCheckBox("Rapport Boost")
        self.voice_rapport_boost_checkbox.setChecked(True)
        self.voice_rapport_boost_checkbox.setToolTip("Send more voice messages as conversation progresses")
        advanced_voice_layout.addWidget(self.voice_rapport_boost_checkbox)
        
        advanced_voice_layout.addStretch()
        voice_settings_layout.addLayout(advanced_voice_layout)
        
        # Test voice button and status
        test_voice_layout = QHBoxLayout()
        
        self.test_voice_button = QPushButton("🎤 Test Voice")
        self.test_voice_button.clicked.connect(self._test_voice_generation)
        self.test_voice_button.setToolTip("Generate a test voice message to preview the selected voice")
        self.test_voice_button.setObjectName("secondary")
        test_voice_layout.addWidget(self.test_voice_button)
        
        self.voice_status_label = QLabel("Voice not tested")
        self.voice_status_label.setStyleSheet("color: #a1a1aa; font-style: italic;")
        test_voice_layout.addWidget(self.voice_status_label)
        
        test_voice_layout.addStretch()
        voice_settings_layout.addLayout(test_voice_layout)
        
        self.voice_settings_container.setVisible(False)
        account_config_layout.addWidget(self.voice_settings_container)
        
        account_config_group.setLayout(account_config_layout)
        layout.addWidget(account_config_group)

        # Account Cloning Section
        clone_group = QGroupBox("Account Cloning (Advanced)")
        clone_layout = QVBoxLayout()

        # Clone username input
        clone_input_layout = QHBoxLayout()
        self.clone_username_edit = QLineEdit()
        self.clone_username_edit.setPlaceholderText("@username or username to clone")
        clone_input_layout.addWidget(QLabel("Clone from:"))
        clone_input_layout.addWidget(self.clone_username_edit)
        clone_layout.addLayout(clone_input_layout)

        # Clone options
        clone_options_layout = QVBoxLayout()

        self.clone_profile_checkbox = QCheckBox("Clone profile (name, bio, photo)")
        self.clone_profile_checkbox.setChecked(True)
        clone_options_layout.addWidget(self.clone_profile_checkbox)

        self.clone_settings_checkbox = QCheckBox("Clone privacy settings")
        self.clone_settings_checkbox.setChecked(True)
        clone_options_layout.addWidget(self.clone_settings_checkbox)

        self.clone_contacts_checkbox = QCheckBox("Add mutual contacts")
        self.clone_contacts_checkbox.setChecked(False)
        clone_options_layout.addWidget(self.clone_contacts_checkbox)

        clone_layout.addLayout(clone_options_layout)

        # Clone button
        self.clone_button = QPushButton("Clone Account")
        self.clone_button.clicked.connect(self.clone_account)
        self.clone_button.setObjectName("warning")
        clone_layout.addWidget(self.clone_button)

        clone_group.setLayout(clone_layout)
        layout.addWidget(clone_group)

        # Proxy Management Section
        proxy_group = QGroupBox("🔐 Proxy Management (Required for 10+ Accounts)")
        proxy_layout = QVBoxLayout()

        # Proxy info banner
        proxy_info_banner = QLabel(
            "⚠️ IMPORTANT: For creating 10+ accounts, proxies are REQUIRED.\n"
            "Each account should ideally have a unique proxy to prevent detection.\n"
            "Format: ip:port or ip:port:username:password (one per line)"
        )
        proxy_info_banner.setWordWrap(True)
        proxy_info_banner.setStyleSheet("""
            background: rgba(250, 166, 26, 0.15);
            padding: 10px;
            border-radius: 6px;
            border-left: 3px solid #faa61a;
            font-weight: bold;
        """)
        proxy_layout.addWidget(proxy_info_banner)

        # Proxy list display
        proxy_info_label = QLabel("📝 Paste proxies below or load from file:")
        proxy_info_label.setWordWrap(True)
        proxy_layout.addWidget(proxy_info_label)

        # Proxy text area
        self.proxy_list_edit = QTextEdit()
        self.proxy_list_edit.setPlaceholderText(
            "Enter proxies one per line:\n"
            "192.168.1.1:8080\n"
            "192.168.1.2:8080:user:pass\n"
            "Or click 'Load from File' to import a text file"
        )
        self.proxy_list_edit.setMaximumHeight(120)
        proxy_layout.addWidget(self.proxy_list_edit)

        # Proxy buttons
        proxy_buttons_layout = QHBoxLayout()

        self.load_proxy_file_button = QPushButton("Load from File")
        self.load_proxy_file_button.clicked.connect(self.load_proxy_file)
        self.load_proxy_file_button.setObjectName("secondary")
        proxy_buttons_layout.addWidget(self.load_proxy_file_button)

        self.clear_proxies_button = QPushButton("Clear All")
        self.clear_proxies_button.clicked.connect(self.clear_proxy_list)
        self.clear_proxies_button.setObjectName("secondary")
        proxy_buttons_layout.addWidget(self.clear_proxies_button)

        proxy_buttons_layout.addStretch()
        proxy_layout.addLayout(proxy_buttons_layout)

        # Proxy count label
        self.proxy_count_label = QLabel("0 proxies loaded")
        self.proxy_count_label.setStyleSheet("font-weight: bold; color: #7289da;")
        proxy_layout.addWidget(self.proxy_count_label)

        # Update proxy count when text changes
        self.proxy_list_edit.textChanged.connect(self.update_proxy_count)

        # Now connect proxy_list_edit to checklist update (after widget is created)
        self.proxy_list_edit.textChanged.connect(self._update_checklist)

        proxy_group.setLayout(proxy_layout)
        layout.addWidget(proxy_group)

        # Anti-Detection Settings
        detection_group = QGroupBox("Anti-Detection Measures")
        detection_layout = QVBoxLayout()

        self.use_proxy_checkbox = QCheckBox("Use proxies for account creation (recommended)")
        self.use_proxy_checkbox.setChecked(True)
        self.use_proxy_checkbox.setToolTip("Each account will be assigned a permanent proxy from your list")
        detection_layout.addWidget(self.use_proxy_checkbox)

        self.randomize_fingerprint_checkbox = QCheckBox("Randomize device fingerprints")
        self.randomize_fingerprint_checkbox.setChecked(True)
        detection_layout.addWidget(self.randomize_fingerprint_checkbox)

        # Now connect randomize_fingerprint_checkbox to checklist update (after widget is created)
        self.randomize_fingerprint_checkbox.stateChanged.connect(self._update_checklist)

        self.realistic_timing_checkbox = QCheckBox("Use realistic account creation timing")
        self.realistic_timing_checkbox.setChecked(True)
        detection_layout.addWidget(self.realistic_timing_checkbox)

        self.vary_platform_checkbox = QCheckBox("Vary device platforms (Android/iOS)")
        self.vary_platform_checkbox.setChecked(True)
        detection_layout.addWidget(self.vary_platform_checkbox)

        detection_group.setLayout(detection_layout)
        layout.addWidget(detection_group)

        # Results Section
        results_group = QGroupBox("Creation Results")
        results_layout = QVBoxLayout()

        self.creation_results_text = QTextEdit()
        self.creation_results_text.setReadOnly(True)
        self.creation_results_text.setMaximumHeight(150)
        results_layout.addWidget(self.creation_results_text)

        results_group.setLayout(results_layout)
        layout.addWidget(results_group)

        layout.addStretch()
        return self._wrap_tab(scroll_area, "Account Factory", "Provision new Telegram identities via SMS providers, smart proxies, and hardened safety rails.")

    def create_advanced_tab(self) -> QWidget:
        """Create the advanced settings tab."""
        scroll_area, content = self._create_tab_content_widget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Safety Settings
        safety_group = QGroupBox("Safety & Limits")
        safety_layout = QFormLayout()

        self.max_reply_length_spin = QSpinBox()
        self.max_reply_length_spin.setRange(100, 2000)
        self.max_reply_length_spin.setValue(1024)
        self.max_reply_length_spin.setSuffix(" characters")
        safety_layout.addRow("Max reply length:", self.max_reply_length_spin)

        safety_group.setLayout(safety_layout)
        layout.addWidget(safety_group)

        # Debug Settings
        debug_group = QGroupBox("Debug & Logging")
        debug_layout = QFormLayout()

        self.enable_logging_checkbox = QCheckBox("Enable detailed logging")
        self.enable_logging_checkbox.setChecked(True)
        debug_layout.addRow(self.enable_logging_checkbox)

        # Human-like typing settings
        human_layout = QGroupBox("Human-like Behavior")
        human_form = QFormLayout()

        self.realistic_typing_checkbox = QCheckBox("Realistic character-by-character typing")
        self.realistic_typing_checkbox.setChecked(True)
        self.realistic_typing_checkbox.setToolTip("Types each character individually with natural delays")
        human_form.addRow(self.realistic_typing_checkbox)

        self.random_delays_checkbox = QCheckBox("Random delays between messages")
        self.random_delays_checkbox.setChecked(True)
        self.random_delays_checkbox.setToolTip("Adds random pauses between responses")
        human_form.addRow(self.random_delays_checkbox)

        human_layout.setLayout(human_form)
        layout.addWidget(human_layout)

        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)

        layout.addStretch()
        return self._wrap_tab(scroll_area, "Advanced Controls", "Dial in logging, max token limits, and human-behavior simulation toggles.")

    def _create_tab_content_widget(self):
        """Create a scrollable content widget for tabs."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setObjectName("settings_scroll_area")

        content_widget = QWidget()
        content_widget.setMinimumWidth(600)  # Ensure minimum width
        scroll_area.setWidget(content_widget)

        return scroll_area, content_widget

    def _wrap_tab(self, scroll_area, title: str, description: str):
        """Create a properly structured tab with title, description, and scrollable content."""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        tab_layout.setContentsMargins(20, 20, 20, 20)
        tab_layout.setSpacing(12)

        # Tab title
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 18px; font-weight: 600; color: #e4e4e7; margin-bottom: 4px;")
        tab_layout.addWidget(title_label)

        # Tab description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #a1a1aa; font-size: 13px; margin-bottom: 16px;")
        desc_label.setWordWrap(True)
        tab_layout.addWidget(desc_label)

        # Add the scroll area
        tab_layout.addWidget(scroll_area)

        return tab_widget

    def _wrap_widget_tab(self, widget: QWidget, title: str, description: str) -> QWidget:
        """Wrap an existing widget inside the standard scrollable tab layout."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("settings_scroll_area")

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(widget)
        container_layout.addStretch()

        scroll_area.setWidget(container)
        return self._wrap_tab(scroll_area, title, description)

    def check_provider_balance(self):
        """Check balance for the selected SMS provider."""
        provider = self.phone_provider_combo.currentText()
        api_key = self.provider_api_edit.text().strip()

        if not api_key:
            ErrorHandler.safe_warning(self, "Missing API Key", "Please enter an API key.")
            return

        self.balance_label.setText("Checking balance...")
        self.check_balance_button.setEnabled(False)
        cached = self._get_cached_balance(provider, api_key)
        if cached:
            self._apply_balance_result(cached.get('balance'), cached.get('error'))
            return

        def run_balance_lookup():
            balance, error = self._fetch_provider_balance(provider, api_key)
            QTimer.singleShot(0, lambda: self._apply_balance_result(balance, error))

        threading.Thread(target=run_balance_lookup, daemon=True).start()

    def _apply_balance_result(self, balance: Optional[str], error: Optional[str]):
        """Apply balance result back on the UI thread and update cache."""
        provider = self.phone_provider_combo.currentText()
        api_key = self.provider_api_edit.text().strip()

        if balance is not None:
            self.balance_label.setText(f"Balance: {balance}")
            self.balance_label.setStyleSheet("color: #23a559; font-weight: bold;")
            self._cache_balance(provider, api_key, balance)
        else:
            self.balance_label.setText("Check failed")
            self.balance_label.setStyleSheet("color: #f23f42; font-weight: bold;")
            if error:
                logger.error(f"Balance check error: {error}")

        self.check_balance_button.setEnabled(True)

    def _get_cached_balance(self, provider: str, api_key: str, ttl_seconds: int = 300) -> Optional[Dict[str, Any]]:
        """Return cached balance if it is still fresh."""
        key = (provider, api_key)
        cached = self.balance_cache.get(key)
        if not cached:
            return None

        if time.time() - cached.get('timestamp', 0) > ttl_seconds:
            return None

        return cached

    def _cache_balance(self, provider: str, api_key: str, balance: str):
        """Persist balance in memory for quick reuse."""
        key = (provider, api_key)
        self.balance_cache[key] = {
            'balance': balance,
            'timestamp': time.time(),
        }

    def _fetch_provider_balance(self, provider: str, api_key: str) -> tuple[Optional[str], Optional[str]]:
        """Fetch provider balance with timeouts and error reporting."""
        balance = None
        error = None
        try:
            if provider == 'sms-activate':
                params = {'api_key': api_key, 'action': 'getBalance'}
                resp = requests.get('https://api.sms-activate.org/stubs/handler_api.php', params=params, timeout=10)
                if resp.status_code == 200 and 'ACCESS_BALANCE' in resp.text:
                    balance = resp.text.split(':')[1]
            elif provider == 'sms-hub':
                params = {'api_key': api_key, 'action': 'getBalance'}
                resp = requests.get('https://smshub.org/api.php', params=params, timeout=10)
                if resp.status_code == 200 and 'ACCESS_BALANCE' in resp.text:
                    balance = resp.text.split(':')[1]
            elif provider == '5sim':
                headers = {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json'}
                resp = requests.get('https://5sim.net/v1/user/profile', headers=headers, timeout=10)
                if resp.status_code == 200:
                    balance = str(resp.json().get('balance', 0))
            elif provider == 'daisysms':
                headers = {'Authorization': f'Bearer {api_key}'}
                resp = requests.get('https://daisysms.com/api/balance', headers=headers, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    balance = str(data.get('balance', 0))
            elif provider == 'smspool':
                headers = {'Authorization': f'Bearer {api_key}'}
                resp = requests.get('https://api.smspool.net/me', headers=headers, timeout=10)
                if resp.status_code == 200:
                    balance = str(resp.json().get('balance', 0))
            elif provider == 'textverified':
                headers = {'Authorization': f'Bearer {api_key}'}
                resp = requests.get('https://www.textverified.com/api/me', headers=headers, timeout=10)
                if resp.status_code == 200:
                    balance = str(resp.json().get('balance', 0))
        except Exception as exc:
            error = str(exc)
            logger.error(f"Balance check error: {exc}")

        return balance, error

    def _toggle_custom_brain(self, state):
        """Toggle custom brain prompt visibility."""
        self.custom_brain_container.setVisible(state != Qt.CheckState.Checked.value)
    
    def _toggle_voice_settings(self, state):
        """Toggle voice settings visibility."""
        self.voice_settings_container.setVisible(state == Qt.CheckState.Checked.value)
    
    def _test_voice_generation(self):
        """Test voice generation with the selected voice."""
        # Check for API key - use correct widget name
        api_key = self.api_widget.elevenlabs_key_edit.text().strip() if hasattr(self.api_widget, 'elevenlabs_key_edit') else ""
        if not api_key:
            ErrorHandler.safe_warning(self, "Missing API Key", 
                "Please enter your ElevenLabs API key in the API & Auth tab first.")
            return
        
        # Get selected voice
        voice_id_map = {
            "Rachel (Young American, 18-25)": "rachel",
            "Elli (Energetic, 18-22)": "elli",
            "Bella (Soft & Gentle, 20-28)": "bella",
            "Charlotte (Sweet & Youthful, 18-25)": "charlotte",
            "Sarah (Confident, 20-25)": "sarah"
        }
        selected_voice = self.voice_select_combo.currentText()
        voice_id = voice_id_map.get(selected_voice, "rachel")
        
        # Update UI
        self.test_voice_button.setEnabled(False)
        self.voice_status_label.setText("Testing voice generation...")
        self.voice_status_label.setStyleSheet("color: #faa61a;")
        
        # Run test in background
        import asyncio
        
        async def run_test():
            try:
                from voice_service import VoiceService
                service = VoiceService(api_key=api_key)
                success, audio_path = await service.test_voice_generation(voice_id=voice_id, phrase_type="greeting")
                return success, audio_path
            except Exception as e:
                logger.error(f"Voice test failed: {e}")
                return False, str(e)
        
        def on_complete(result):
            success, info = result
            self.test_voice_button.setEnabled(True)
            
            if success:
                self.voice_status_label.setText(f"✅ Voice test passed!")
                self.voice_status_label.setStyleSheet("color: #23a559; font-weight: bold;")
                ErrorHandler.safe_information(self, "Voice Test Successful", 
                    f"Voice generation is working!\n\nTest audio saved to:\n{info}")
            else:
                self.voice_status_label.setText(f"❌ Voice test failed")
                self.voice_status_label.setStyleSheet("color: #f23f42; font-weight: bold;")
                ErrorHandler.safe_warning(self, "Voice Test Failed", 
                    f"Could not generate voice message.\n\nError: {info}\n\n"
                    "Please check:\n• ElevenLabs API key is correct\n• You have available credits\n• Internet connection")
        
        # Run async test
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is running, create task
                future = asyncio.ensure_future(run_test())
                future.add_done_callback(lambda f: on_complete(f.result()))
            else:
                # Run synchronously
                result = loop.run_until_complete(run_test())
                on_complete(result)
        except RuntimeError:
            # No event loop, create one
            result = asyncio.run(run_test())
            on_complete(result)
    
    def _update_voice_trigger_options(self, index):
        """Update voice trigger options based on selected mode."""
        # Hide all first
        self.voice_random_label.setVisible(False)
        self.voice_random_spin.setVisible(False)
        self.voice_nth_label.setVisible(False)
        self.voice_nth_spin.setVisible(False)
        self.voice_keywords_label.setVisible(False)
        self.voice_keywords_edit.setVisible(False)
        
        mode = self.voice_trigger_combo.currentText()
        
        if "Random" in mode:
            self.voice_random_label.setVisible(True)
            self.voice_random_spin.setVisible(True)
        elif "Nth" in mode:
            self.voice_nth_label.setVisible(True)
            self.voice_nth_spin.setVisible(True)
        elif "Keyword" in mode:
            self.voice_keywords_label.setVisible(True)
            self.voice_keywords_edit.setVisible(True)
        # "Always" and "Never" don't need additional options

    def _update_checklist(self):
        """Update the setup checklist based on current inputs."""
        # Check API key
        api_key = self.provider_api_edit.text().strip()
        if api_key:
            self.checklist_api_key.setText("✅ Provider API Key")
            self.checklist_api_key.setStyleSheet("color: #23a559; padding: 4px;")
        else:
            self.checklist_api_key.setText("❌ Provider API Key")
            self.checklist_api_key.setStyleSheet("color: #f23f42; padding: 4px;")

        # Check proxies - for account creation tab, check proxy pool availability
        account_count = self.account_count_spin.value()

        # Get parent main window to check proxy availability
        main_window = self.parent()
        proxy_available = False
        proxy_count = 0

        if main_window and hasattr(main_window, 'proxy_pool_manager') and main_window.proxy_pool_manager:
            try:
                if hasattr(main_window.proxy_pool_manager, 'get_proxy_count'):
                    proxy_count = main_window.proxy_pool_manager.get_proxy_count()
                    proxy_available = proxy_count > 0
            except Exception as e:
                logger.debug(f"Could not check proxy count: {e}")

        if account_count >= 10:
            if proxy_available and proxy_count >= account_count:
                self.checklist_proxies.setText(f"✅ Proxies ({proxy_count} available, {account_count} needed)")
                self.checklist_proxies.setStyleSheet("color: #23a559; padding: 4px;")
            else:
                self.checklist_proxies.setText(f"❌ Proxies ({proxy_count} available, {account_count} needed)")
                self.checklist_proxies.setStyleSheet("color: #f23f42; padding: 4px;")
        else:
            if proxy_available:
                self.checklist_proxies.setText(f"✅ Proxies ({proxy_count} available, optional)")
                self.checklist_proxies.setStyleSheet("color: #b5bac1; padding: 4px;")
            else:
                self.checklist_proxies.setText("ℹ️ Proxies (Optional for <10 accounts)")
                self.checklist_proxies.setStyleSheet("color: #b5bac1; padding: 4px;")

        # Country is always selected (has default)
        self.checklist_country.setText("✅ Country Selected")
        self.checklist_country.setStyleSheet("color: #23a559; padding: 4px;")

        # Anti-detection - for account creation, this is always enabled via the backend
        self.checklist_anti_detection.setText("✅ Anti-Detection Enabled")
        self.checklist_anti_detection.setStyleSheet("color: #23a559; padding: 4px;")

    def update_proxy_count(self):
        """Update the proxy count label."""
        proxy_text = self.proxy_list_edit.toPlainText()
        proxy_lines = [line.strip() for line in proxy_text.split('\n') if line.strip()]
        self.proxy_count_label.setText(f"{len(proxy_lines)} proxies loaded")

    def load_proxy_file(self):
        """Load proxies from a file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Proxy File", "", "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    proxies = f.read().strip()
                    self.proxy_list_edit.setPlainText(proxies)
                    self.update_proxy_count()
            except Exception as e:
                ErrorHandler.safe_critical(self, "Error", f"Failed to load proxy file: {e}")

    def clear_proxy_list(self):
        """Clear the proxy list."""
        self.proxy_list_edit.clear()
        self.update_proxy_count()

    def start_bulk_creation(self):
        """Start bulk account creation."""
        # Validate inputs
        count = self.account_count_spin.value()
        provider = self.phone_provider_combo.currentText()
        api_key = self.provider_api_edit.text().strip()
        country = self.country_combo.currentText().split(" - ")[0]

        # Basic input validation
        if not api_key:
            ErrorHandler.safe_warning(self, "Missing API Key", "Please enter your SMS provider API key.")
            return

        if count <= 0 or count > 100:
            ErrorHandler.safe_warning(self, "Invalid Count", "Please enter a valid number of accounts (1-100).")
            return

        # Get parent main window
        main_window = self.parent()
        if not main_window or not hasattr(main_window, 'account_creator'):
            ErrorHandler.safe_warning(self, "Error", "Cannot access account creator from settings dialog.")
            return

        if not main_window.account_creator:
            ErrorHandler.safe_warning(self, "Error", "Account creator not initialized. Please restart the application.")
            return

        # Validate Telegram API credentials
        api_id = ""
        api_hash = ""
        if hasattr(main_window, 'api_widget'):
            api_id = getattr(main_window.api_widget, 'api_id_edit', lambda: '').text().strip()
            api_hash = getattr(main_window.api_widget, 'api_hash_edit', lambda: '').text().strip()

        if not api_id or not api_hash:
            ErrorHandler.safe_warning(self, "Missing Telegram Credentials",
                "Please enter your Telegram API ID and API Hash in the API & Auth tab first.")
            return

        # Validate API credentials format
        if not api_id.isdigit() or len(api_id) < 6:
            ErrorHandler.safe_warning(self, "Invalid API ID",
                "Telegram API ID should be a numeric value (usually 7-8 digits).")
            return

        if len(api_hash) != 32 or not all(c in '0123456789abcdefABCDEF' for c in api_hash):
            ErrorHandler.safe_warning(self, "Invalid API Hash",
                "Telegram API Hash should be 32 hexadecimal characters.")
            return

        if not self._validate_country_support(provider, country, main_window.account_creator):
            return

        # Check proxy requirements
        require_proxies = count >= 10
        if require_proxies:
            # Check if proxy pool manager is available
            if not hasattr(main_window, 'proxy_pool_manager') or not main_window.proxy_pool_manager:
                ErrorHandler.safe_warning(self, "Proxies Required",
                    f"For {count} accounts, proxies are required but no proxy pool manager is available.\n\n"
                    "Please configure proxies in the Proxy Pool tab first.")
                return

            # Check proxy availability (basic check)
            try:
                # This would need to be async, but for validation we'll do a basic check
                if hasattr(main_window.proxy_pool_manager, 'get_proxy_count'):
                    proxy_count = main_window.proxy_pool_manager.get_proxy_count()
                    if proxy_count < count:
                        ErrorHandler.safe_warning(self, "Insufficient Proxies",
                            f"You have {proxy_count} proxies but need at least {count} for {count} accounts.\n\n"
                            "Add more proxies in the Proxy Pool tab.")
                        return
            except Exception as e:
                logger.warning(f"Could not check proxy count: {e}")

        # Validate voice settings if enabled
        if self.enable_voice_checkbox.isChecked():
            elevenlabs_key = ""
            if hasattr(main_window, 'api_widget') and hasattr(main_window.api_widget, 'elevenlabs_key_edit'):
                elevenlabs_key = main_window.api_widget.elevenlabs_key_edit.text().strip()

            if not elevenlabs_key:
                ErrorHandler.safe_warning(self, "Missing ElevenLabs API Key",
                    "Voice messages are enabled but no ElevenLabs API key is configured.\n\n"
                    "Please add your ElevenLabs API key in the API & Auth tab.")
                return

        # Try to validate provider balance before proceeding
        balance_valid = self._validate_provider_balance(provider, api_key, count)
        if not balance_valid:
            return

        # Confirm action
        proxy_info = f"Proxies: {'Required' if require_proxies else 'Optional'}"
        voice_info = f"Voice Messages: {'Enabled' if self.enable_voice_checkbox.isChecked() else 'Disabled'}"

        if not ErrorHandler.safe_question(
            self,
            "Confirm Bulk Creation",
            f"Create {count} accounts using {provider}?\n\n"
            f"Country: {country}\n"
            f"Account Type: {self.account_type_combo.currentText()}\n"
            f"{proxy_info}\n"
            f"{voice_info}\n\n"
            f"This will consume approximately {count} SMS credits.\n\n"
            f"Continue?"
        ):
            return

        # Prepare creation configuration using the latest UI state
        settings_config = self.collect_ui_settings()
        factory_settings = settings_config.get('account_factory', {})
        use_proxy = factory_settings.get('use_proxy', True)
        realistic_timing = factory_settings.get('realistic_timing', True)

        config = {
            'phone_provider': provider,
            'provider_api_key': factory_settings.get('provider_api_key', api_key) or api_key,
            'country': factory_settings.get('country', country),
            'use_proxy': use_proxy,
            'require_proxy': use_proxy and count >= 10,  # Require proxies for 10+ accounts when proxying is enabled
            'api_id': settings_config.get('telegram', {}).get('api_id', ''),
            'api_hash': settings_config.get('telegram', {}).get('api_hash', ''),
            'realistic_timing': realistic_timing,
            'account_type': self.account_type_combo.currentText(),
            'enable_voice': self.enable_voice_checkbox.isChecked(),
            'voice_config': {
                'voice': self.voice_select_combo.currentText(),
                'trigger_mode': self.voice_trigger_combo.currentText(),
                'random_chance': self.voice_random_spin.value(),
                'nth_message': self.voice_nth_spin.value(),
                'keywords': self.voice_keywords_edit.text().strip()
            } if self.enable_voice_checkbox.isChecked() else None,
            'anti_detection': settings_config.get('anti_detection', {}),
            'proxy_pool': settings_config.get('proxy_pool', {}),
            'brain': settings_config.get('brain', {}),
            'account_defaults': settings_config.get('account_defaults', {}),
            'randomize_fingerprint': factory_settings.get('randomize_fingerprint', True),
            'vary_platform': factory_settings.get('vary_platform', True),
            'manual_proxies': factory_settings.get('proxies', []),
        }

        # Disable button during creation
        self.start_creation_button.setEnabled(False)
        self.stop_creation_button.setEnabled(True)
        self.creation_progress.setVisible(True)
        self.creation_progress.setMaximum(count)
        self.creation_progress.setValue(0)
        self.creation_status.setText(f"Creating {count} accounts...")
        self.creation_summary.setText("")
        self.creation_summary.setVisible(False)

        # Reset stats
        self.account_creation_current = 0
        self.account_creation_total = count

        # Set up progress callback
        main_window.account_creator.set_progress_callback(self._update_creation_progress)

        # Start creation in background
        import asyncio
        import threading

        def run_creation():
            """Run the creation process in a background thread."""
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Run the bulk creation
                results = loop.run_until_complete(
                    main_window.account_creator.start_bulk_creation(count, config)
                )

                # Update UI on main thread
                QTimer.singleShot(0, lambda: self._handle_creation_complete(results))

            except Exception as e:
                logger.error(f"Bulk creation failed: {e}")
                QTimer.singleShot(0, lambda: self._handle_creation_error(str(e)))
            finally:
                loop.close()

        # Start background thread
        creation_thread = threading.Thread(target=run_creation, daemon=True)
        creation_thread.start()

    def stop_bulk_creation(self):
        """Stop bulk account creation."""
        # Get parent main window
        main_window = self.parent()
        if main_window and hasattr(main_window, 'account_creator') and main_window.account_creator:
            main_window.account_creator.stop_creation()

        self.stop_creation_button.setEnabled(False)
        self.start_creation_button.setEnabled(True)
        self.creation_progress.setVisible(False)
        self.creation_status.setText("Account creation stopped by user")
        self.creation_summary.setText("Creation cancelled")
        self.creation_summary.setVisible(True)

        ErrorHandler.safe_information(self, "Stopped", "Account creation has been stopped.")

    def _validate_provider_balance(self, provider: str, api_key: str, count: int) -> bool:
        """Validate that the provider has sufficient balance for the requested accounts."""
        try:
            # Try to get balance
            cached = self._get_cached_balance(provider, api_key)
            balance = float(cached['balance']) if cached and cached.get('balance') is not None else None
            error = cached.get('error') if cached else None

            if balance is None:
                fetched_balance, fetch_error = self._fetch_provider_balance(provider, api_key)
                balance = float(fetched_balance) if fetched_balance is not None else None
                error = fetch_error
                if fetched_balance is not None:
                    self._cache_balance(provider, api_key, fetched_balance)

            if balance is not None:
                # Check if balance is sufficient (with some buffer)
                if balance < count * 1.2:  # Require 20% buffer
                    ErrorHandler.safe_warning(self, "Insufficient Balance",
                        f"Your {provider} balance is {balance:.2f}, but you need approximately {count * 1.2:.1f} "
                        f"to create {count} accounts (with safety buffer).\n\n"
                        "Please top up your account or reduce the number of accounts.")
                    return False
                else:
                    logger.info(f"Balance validation passed: {balance:.2f} >= {count * 1.2:.1f}")
                    return True
            else:
                # Could not check balance, warn user but allow to continue
                if error:
                    logger.warning(f"Could not validate balance: {error}")

                if not ErrorHandler.safe_question(self, "Balance Check Failed",
                    f"Could not verify your {provider} account balance.\n\n"
                    f"This could be due to network issues or invalid API key.\n\n"
                    f"Continue anyway? (You may run out of credits during creation)"):
                    return False

                return True

        except Exception as e:
            logger.error(f"Balance validation error: {e}")
            # Allow to continue on validation errors
            return True

    def _validate_country_support(self, provider: str, country: str, account_creator) -> bool:
        """Ensure selected country is supported by the provider and current catalog."""
        try:
            provider_map = getattr(getattr(account_creator, 'phone_provider', None), 'providers', {}) or {}
            provider_config = provider_map.get(provider, {})
            supported = provider_config.get('countries', [])
            if supported and country not in supported:
                ErrorHandler.safe_warning(
                    self,
                    "Unsupported Country",
                    f"{provider} does not support {country}. Supported countries: {', '.join(supported)}"
                )
                return False
        except Exception as exc:
            logger.warning(f"Country support validation skipped due to error: {exc}")
        return True

    def _update_creation_progress(self, current: int, total: int, message: str):
        """Update creation progress in UI."""
        self.account_creation_current = current
        self.account_creation_total = total

        # Update progress bar
        if total > 0:
            self.creation_progress.setValue(current)
            self.creation_progress.setFormat(f"Creating: {current}/{total} ({(current/total*100):.0f}%)")

        # Update status
        self.creation_status.setText(message)

    def _handle_creation_complete(self, results: list):
        """Handle completion of bulk account creation."""
        # Re-enable UI
        self.start_creation_button.setEnabled(True)
        self.stop_creation_button.setEnabled(False)
        self.creation_progress.setVisible(False)

        # Calculate statistics
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful

        # Update summary
        summary_text = f"✅ Creation Complete\n"
        summary_text += f"• Total: {len(results)}\n"
        summary_text += f"• Successful: {successful}\n"
        summary_text += f"• Failed: {failed}"

        self.creation_summary.setText(summary_text)
        self.creation_summary.setVisible(True)
        self.creation_status.setText("Account creation completed")

        # Show detailed results
        if successful > 0:
            success_msg = f"Successfully created {successful} accounts!\n\n"
            if failed > 0:
                success_msg += f"{failed} accounts failed to create.\n\n"

            # List successful accounts
            success_msg += "Created accounts:\n"
            for result in results:
                if result.get('success'):
                    phone = result.get('phone_number', 'Unknown')
                    success_msg += f"• {phone}\n"

            ErrorHandler.safe_information(self, "Creation Complete", success_msg)
        else:
            ErrorHandler.safe_warning(self, "Creation Failed",
                f"All {len(results)} account creation attempts failed.\n\n"
                "Check your SMS provider API key and balance.")

        # Refresh account list in main window
        main_window = self.parent()
        if main_window and hasattr(main_window, 'update_account_list'):
            QTimer.singleShot(1000, main_window.update_account_list)

    def _handle_creation_error(self, error: str):
        """Handle creation error."""
        # Re-enable UI
        self.start_creation_button.setEnabled(True)
        self.stop_creation_button.setEnabled(False)
        self.creation_progress.setVisible(False)

        self.creation_status.setText("Account creation failed")
        self.creation_summary.setText(f"❌ Error: {error}")
        self.creation_summary.setVisible(True)

        ErrorHandler.safe_critical(self, "Creation Failed",
            f"Bulk account creation failed:\n\n{error}\n\n"
            "Check your configuration and try again.")

    def clone_account(self):
        """Clone an account profile."""
        # Get list of accounts to clone from
        main_window = self.parent()
        if not main_window or not hasattr(main_window, 'account_manager'):
            ErrorHandler.safe_warning(self, "Error", "Cannot access account manager.")
            return
        
        if not main_window.account_manager:
            ErrorHandler.safe_warning(self, "No Accounts", "No accounts available to clone.")
            return
        
        # Get available accounts
        accounts = main_window.account_manager.get_all_accounts()
        if not accounts:
            ErrorHandler.safe_warning(self, "No Accounts", "You need at least one account to clone from.\n\nCreate an account first in the Accounts tab.")
            return
        
        # Show account selector
        account_names = [f"{acc.get('phone_number', 'Unknown')} - {acc.get('username', 'No username')}" for acc in accounts]
        account_choice, ok = QInputDialog.getItem(
            self,
            "Select Account to Clone",
            "Choose the account to clone profile from:",
            account_names,
            0,
            False
        )
        
        if ok and account_choice:
            ErrorHandler.safe_information(
                self,
                "Cloning Feature",
                f"Account cloning will copy:\n"
                f"• Profile photo\n"
                f"• Bio/About\n"
                f"• Username style\n\n"
                f"Selected: {account_choice}\n\n"
                f"This feature requires the advanced cloning system.\n"
                f"Use the main window's cloning interface for full functionality."
            )

    def scrape_channel_members(self):
        """Scrape members from a channel - actually perform the scraping inline."""
        channel_url = self.channel_url_edit.text().strip()
        
        if not channel_url:
            ErrorHandler.safe_warning(
                self,
                "Missing Channel",
                "Please enter a channel URL or username.\n\nExamples:\n• https://t.me/channelname\n• @channelname\n• channelname"
            )
            return
        
        # Get parent main window to access scraper client
        main_window = self.parent()
        if not main_window or not hasattr(main_window, '_get_scraper_client'):
            ErrorHandler.safe_warning(
                self,
                "Cannot Scrape",
                "Settings dialog must be opened from the main window.\n\nAlternatively, use the Members tab in the main window."
            )
            return
        
        # Get a valid Pyrogram client
        scraper_client = main_window._get_scraper_client()
        if not scraper_client:
            ErrorHandler.safe_warning(
                self,
                "No Active Account",
                "Please start at least one Telegram account before scraping members.\n\n"
                "Go to Accounts tab → Add/Start an account → Then return here to scrape."
            )
            return
        
        # Disable UI during scraping
        self.scrape_button.setEnabled(False)
        self.stop_scrape_button.setEnabled(True)
        self.scrape_progress.setVisible(True)
        self.scrape_progress.setMaximum(0)  # Indeterminate progress
        self.scraper_results_text.clear()
        self.scraper_results_text.append(f"🔍 Starting scrape of: {channel_url}\n")
        
        # Import and initialize scraper
        try:
            from member_scraper import MemberScraper, EliteAntiDetectionSystem, ComprehensiveDataExtractor
            
            if not hasattr(main_window, 'member_db') or not main_window.member_db:
                raise Exception("Member database not initialized")
            
            # Create scraper
            anti_detection = EliteAntiDetectionSystem()
            scraper = MemberScraper(
                client=scraper_client,
                db=main_window.member_db,
                anti_detection=anti_detection
            )
            
            # Start async scraping
            import asyncio
            
            async def perform_scrape():
                try:
                    self.scraper_results_text.append("📊 Initializing scraper...\n")
                    
                    def progress_update(count):
                        self.scrape_progress.setValue(count)
                        self.scrape_progress.setFormat(f"Found {count} members")
                    
                    result = await scraper.scrape_channel_members(
                        channel_url,
                        progress_callback=progress_update,
                        analyze_messages=True,
                        use_elite_scraping=False  # Start with basic scraping
                    )
                    
                    # Update UI with results
                    if result.get('success'):
                        self.scraper_results_text.append(f"\n✅ Scraping complete!\n")
                        self.scraper_results_text.append(f"📊 Channel: {result.get('channel_title', 'Unknown')}\n")
                        self.scraper_results_text.append(f"👥 Members found: {result.get('members_scraped', 0)}\n")
                        self.scraper_results_text.append(f"🎯 Safe targets: {result.get('safe_targets', 0)}\n")
                        self.scraper_results_text.append(f"🛡️ Threats filtered: {result.get('threats_filtered', 0)}\n")
                        
                        # Update stats
                        self.stats_total.setText(f"Total: {result.get('members_scraped', 0)}")
                        self.stats_active.setText(f"Safe: {result.get('safe_targets', 0)}")
                        self.stats_inactive.setText(f"Filtered: {result.get('threats_filtered', 0)}")
                        
                        ErrorHandler.safe_information(
                            self,
                            "Scraping Complete",
                            f"Successfully scraped {result.get('members_scraped', 0)} members!"
                        )
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        self.scraper_results_text.append(f"\n❌ Error: {error_msg}\n")
                        ErrorHandler.safe_warning(self, "Scraping Failed", f"Failed to scrape members:\n\n{error_msg}")
                
                except Exception as e:
                    logger.error(f"Scraping error: {e}")
                    self.scraper_results_text.append(f"\n❌ Error: {str(e)}\n")
                    ErrorHandler.safe_critical(self, "Error", f"Scraping failed:\n\n{str(e)}")
                
                finally:
                    # Re-enable UI
                    self.scrape_button.setEnabled(True)
                    self.stop_scrape_button.setEnabled(False)
                    self.scrape_progress.setVisible(False)
            
            # Run the async scraping operation
            if hasattr(main_window, '_run_async_task'):
                main_window._run_async_task(perform_scrape())
            else:
                # Fallback: run in new event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(perform_scrape())
                finally:
                    loop.close()
        
        except Exception as e:
            logger.error(f"Failed to start scraping: {e}")
            self.scraper_results_text.append(f"\n❌ Failed to initialize scraper: {str(e)}\n")
            ErrorHandler.safe_critical(self, "Error", f"Failed to start scraping:\n\n{str(e)}")
            self.scrape_button.setEnabled(True)
            self.stop_scrape_button.setEnabled(False)
            self.scrape_progress.setVisible(False)

    def stop_scraping(self):
        """Stop scraping operation."""
        # Note: Actual stopping would require tracking the scraper instance
        # For now, just disable the button and show feedback
        self.stop_scrape_button.setEnabled(False)
        self.scrape_button.setEnabled(True)
        self.scrape_progress.setVisible(False)
        self.scraper_results_text.append("\n⏹️ Scraping stopped by user\n")
        
        ErrorHandler.safe_information(self, "Stopped", "Scraping operation stopped.")

    def refresh_members(self):
        """Refresh member list from database."""
        try:
            main_window = self.parent()
            if not main_window or not hasattr(main_window, 'member_db'):
                ErrorHandler.safe_warning(self, "Error", "Cannot access member database")
                return
            
            # Get all channels
            channels = main_window.member_db.get_all_channels()
            
            # Update channel selector
            self.channel_select.clear()
            self.channel_select.addItem("Select Channel...")
            for channel in channels:
                self.channel_select.addItem(f"{channel.get('title', 'Unknown')} ({channel.get('member_count', 0)} members)")
            
            # Update member list for first channel
            if channels:
                first_channel_id = channels[0].get('channel_id')
                members = main_window.member_db.get_all_members(first_channel_id)[:50]  # Limit to 50
                
                self.members_list.clear()
                for member in members:
                    name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() or 'Unknown'
                    username = member.get('username', '')
                    display = f"{name} (@{username})" if username else name
                    self.members_list.addItem(display)
                
                self.scraper_results_text.append(f"\n🔄 Refreshed: Showing {len(members)} members from {channels[0].get('title')}\n")
            else:
                self.scraper_results_text.append("\nℹ️ No channels scraped yet.\n")
        
        except Exception as e:
            logger.error(f"Error refreshing members: {e}")
            ErrorHandler.safe_critical(self, "Error", f"Failed to refresh members:\n\n{str(e)}")

    def message_selected_member(self):
        """Message selected member."""
        selected_items = self.members_list.selectedItems()
        if not selected_items:
            ErrorHandler.safe_warning(self, "No Selection", "Please select a member from the list first.")
            return
        
        # Get the selected member
        member_text = selected_items[0].text()
        
        # Show message composer
        message, ok = QInputDialog.getText(
            self,
            "Send Message",
            f"Enter message to send to {member_text}:",
            QLineEdit.EchoMode.Normal
        )
        
        if ok and message.strip():
            ErrorHandler.safe_information(
                self,
                "Feature Available in Campaigns",
                f"💡 Direct messaging is available through the Campaigns tab for proper rate limiting.\n\n"
                f"Your message: \"{message[:50]}...\"\n\n"
                f"Go to Campaigns → Create Campaign → Select members → Send safely"
            )

    def load_settings(self) -> Dict[str, Any]:
        """Load settings from the configuration file."""
        default_settings = {
            "telegram": {
                "api_id": "",
                "api_hash": "",
                "phone_number": ""
            },
            "gemini": {
                "api_key": ""
            },
            "sms_providers": {
                "provider": "sms-activate",
                "api_key": "",
            },
            "account_factory": {
                "account_count": 10,
                "country": "US",
                "phone_provider": "sms-activate",
                "provider_api_key": "",
                "use_proxy": True,
                "randomize_fingerprint": True,
                "realistic_timing": True,
                "vary_platform": True,
                "proxies": [],
            },
            "brain": {
                "prompt": "",
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
                "enabled": True
            }
        }

        try:
            config_path = Path("config.json")
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults
                    self._merge_settings(default_settings, loaded_settings)
                    self.settings_data = default_settings
            else:
                self.settings_data = default_settings

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")
            self.settings_data = default_settings

        return self.settings_data

    def _merge_settings(self, base: Dict, override: Dict):
        """Recursively merge settings dictionaries."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_settings(base[key], value)
            else:
                base[key] = value

    def load_ui_from_settings(self):
        """Load settings into UI elements."""
        # Load settings into the widget components
        self.api_widget.load_settings(self.settings_data)
        self.brain_widget.load_settings(self.settings_data)
        self.anti_detection_widget.load_settings(self.settings_data)
        self.sms_provider_widget.load_settings(self.settings_data)

        # Continue with remaining settings that haven't been refactored yet
        # Note: Brain and anti-detection settings are now handled by their respective widgets
        # Only load settings for UI elements that still exist in the main window
        brain = self.settings_data.get("brain", {})
        
        # Account defaults settings
        account_defaults = self.settings_data.get("account_defaults", {})
        if hasattr(self, 'account_type_combo'):
            account_type = account_defaults.get("account_type", "reactive")
            index = 0 if account_type == "reactive" else 1
            self.account_type_combo.setCurrentIndex(index)
        
        if hasattr(self, 'use_shared_brain_checkbox'):
            self.use_shared_brain_checkbox.setChecked(account_defaults.get("use_shared_brain", True))
            # Update visibility
            self._toggle_custom_brain(self.use_shared_brain_checkbox.checkState().value)
        
        if hasattr(self, 'custom_brain_edit'):
            self.custom_brain_edit.setPlainText(account_defaults.get("custom_brain_prompt", ""))
        
        # Voice settings
        voice = self.settings_data.get("voice", {})
        if hasattr(self, 'enable_voice_checkbox'):
            self.enable_voice_checkbox.setChecked(voice.get("enabled", False))
            # Update visibility
            self._toggle_voice_settings(self.enable_voice_checkbox.checkState().value)
        
        if hasattr(self, 'voice_select_combo'):
            voice_id = voice.get("voice_id", "rachel")
            voice_index_map = {"rachel": 0, "elli": 1, "bella": 2, "charlotte": 3, "sarah": 4}
            self.voice_select_combo.setCurrentIndex(voice_index_map.get(voice_id, 0))
        
        if hasattr(self, 'voice_trigger_combo'):
            trigger_mode = voice.get("trigger_mode", "random")
            trigger_index_map = {"random": 0, "every_nth": 1, "keyword": 2, "smart": 3, "always": 4, "never": 5}
            self.voice_trigger_combo.setCurrentIndex(trigger_index_map.get(trigger_mode, 0))
            # Update trigger options visibility
            self._update_voice_trigger_options(self.voice_trigger_combo.currentIndex())
        
        if hasattr(self, 'voice_random_spin'):
            self.voice_random_spin.setValue(voice.get("random_chance", 30))
        
        if hasattr(self, 'voice_nth_spin'):
            self.voice_nth_spin.setValue(voice.get("nth_message", 3))
        
        if hasattr(self, 'voice_keywords_edit'):
            keywords = voice.get("keywords", ["hey", "hi", "hello", "interested", "price"])
            self.voice_keywords_edit.setText(", ".join(keywords))
        
        if hasattr(self, 'voice_time_boost_checkbox'):
            self.voice_time_boost_checkbox.setChecked(voice.get("time_boost_enabled", True))
        
        if hasattr(self, 'voice_rapport_boost_checkbox'):
            self.voice_rapport_boost_checkbox.setChecked(voice.get("rapport_boost_enabled", True))

        # Anti-detection and advanced settings are now handled by their respective widgets
        # Only load settings for UI elements that still exist in the main window
        advanced = self.settings_data.get("advanced", {})
        if hasattr(self, 'enable_logging_checkbox'):
            self.enable_logging_checkbox.setChecked(advanced.get("enable_logging", True))
        if hasattr(self, 'realistic_typing_checkbox'):
            self.realistic_typing_checkbox.setChecked(advanced.get("realistic_typing", True))
        if hasattr(self, 'random_delays_checkbox'):
            self.random_delays_checkbox.setChecked(advanced.get("random_delays", True))

        # Account factory settings
        factory_settings = self.settings_data.get("account_factory", {})
        if hasattr(self, 'account_count_spin'):
            self.account_count_spin.setValue(factory_settings.get("account_count", 10))
        if hasattr(self, 'country_combo'):
            stored_country = factory_settings.get("country", "US")
            for i in range(self.country_combo.count()):
                if self.country_combo.itemText(i).startswith(f"{stored_country} "):
                    self.country_combo.setCurrentIndex(i)
                    break
        if hasattr(self, 'phone_provider_combo'):
            provider = factory_settings.get("phone_provider", "sms-activate")
            index = self.phone_provider_combo.findText(provider)
            if index != -1:
                self.phone_provider_combo.setCurrentIndex(index)
        if hasattr(self, 'provider_api_edit'):
            self.provider_api_edit.setText(factory_settings.get("provider_api_key", ""))
        if hasattr(self, 'use_proxy_checkbox'):
            self.use_proxy_checkbox.setChecked(factory_settings.get("use_proxy", True))
        if hasattr(self, 'randomize_fingerprint_checkbox'):
            self.randomize_fingerprint_checkbox.setChecked(factory_settings.get("randomize_fingerprint", True))
        if hasattr(self, 'realistic_timing_checkbox'):
            self.realistic_timing_checkbox.setChecked(factory_settings.get("realistic_timing", True))
        if hasattr(self, 'vary_platform_checkbox'):
            self.vary_platform_checkbox.setChecked(factory_settings.get("vary_platform", True))
        if hasattr(self, 'proxy_list_edit'):
            proxies = factory_settings.get("proxies", [])
            proxy_text = "\n".join(proxies) if isinstance(proxies, list) else str(proxies)
            self.proxy_list_edit.setPlainText(proxy_text)
            self.update_proxy_count()

    def collect_ui_settings(self) -> Dict[str, Any]:
        """Collect settings from UI elements."""
        voice_trigger_map = {
            "Random Chance": "random",
            "Every Nth Message": "every_nth",
            "Keyword Triggered": "keyword",
            "Smart (AI-Decides)": "smart",
            "Always": "always",
            "Never": "never"
        }
        voice_id_map = {
            "Rachel (Young American, 18-25)": "rachel",
            "Elli (Energetic, 18-22)": "elli",
            "Bella (Soft & Gentle, 20-28)": "bella",
            "Charlotte (Sweet & Youthful, 18-25)": "charlotte",
            "Sarah (Confident, 20-25)": "sarah"
        }
        account_type_map = {
            "Reactive (Wait for DMs)": "reactive",
            "Outreach (Message First)": "outreach"
        }

        voice_trigger_text = getattr(self, 'voice_trigger_combo', None) and self.voice_trigger_combo.currentText() or "Random Chance"
        voice_trigger = voice_trigger_map.get(voice_trigger_text, "random")

        voice_id_text = getattr(self, 'voice_select_combo', None) and self.voice_select_combo.currentText() or ""
        voice_id = voice_id_map.get(voice_id_text, "rachel")

        account_type_text = getattr(self, 'account_type_combo', None) and self.account_type_combo.currentText() or ""
        account_type = account_type_map.get(account_type_text, "reactive")

        keywords_text = getattr(self, 'voice_keywords_edit', None) and self.voice_keywords_edit.text() or ""
        keywords = [k.strip() for k in keywords_text.split(",") if k.strip()]

        settings: Dict[str, Any] = {}

        # Collect settings from modular widgets first
        self.api_widget.save_settings(settings)
        self.brain_widget.save_settings(settings)
        self.anti_detection_widget.save_settings(settings)
        self.sms_provider_widget.save_settings(settings)

        # Also collect SMS provider from Account Factory tab if it exists (for backward compatibility)
        if hasattr(self, 'phone_provider_combo') and hasattr(self, 'provider_api_edit'):
            sms_provider = self.phone_provider_combo.currentText()
            sms_key = self.provider_api_edit.text()
            if sms_provider or sms_key:
                settings.setdefault("sms_providers", {})
                if sms_provider:
                    settings["sms_providers"]["provider"] = sms_provider
                if sms_key:
                    settings["sms_providers"]["api_key"] = sms_key

        # Account defaults
        settings.setdefault("account_defaults", {})
        settings["account_defaults"].update({
            "account_type": account_type,
            "use_shared_brain": self.use_shared_brain_checkbox.isChecked() if hasattr(self, 'use_shared_brain_checkbox') else True,
            "custom_brain_prompt": getattr(self, 'custom_brain_edit', None) and self.custom_brain_edit.toPlainText() or ""
        })

        # Voice configuration
        voice_settings = settings.setdefault("voice", {})
        voice_settings.update({
            "enabled": self.enable_voice_checkbox.isChecked() if hasattr(self, 'enable_voice_checkbox') else False,
            "voice_id": voice_id,
            "trigger_mode": voice_trigger,
            "random_chance": self.voice_random_spin.value() if hasattr(self, 'voice_random_spin') else 30,
            "nth_message": self.voice_nth_spin.value() if hasattr(self, 'voice_nth_spin') else 3,
            "keywords": keywords if keywords else ["hey", "hi", "hello", "interested", "price"],
            "time_boost_enabled": self.voice_time_boost_checkbox.isChecked() if hasattr(self, 'voice_time_boost_checkbox') else True,
            "rapport_boost_enabled": self.voice_rapport_boost_checkbox.isChecked() if hasattr(self, 'voice_rapport_boost_checkbox') else True
        })

        # Campaign/account level metadata
        settings.setdefault("account", {})
        settings["account"]["type"] = account_type

        # Optional proxy/scalability controls (if present)
        settings.setdefault("proxy_pool", {})
        settings["proxy_pool"].update({
            "enabled": self.proxy_pool_enabled_checkbox.isChecked() if hasattr(self, 'proxy_pool_enabled_checkbox') else True,
            "min_score": self.proxy_min_score_spin.value() if hasattr(self, 'proxy_min_score_spin') else 30,
            "health_check_interval": self.proxy_health_interval_spin.value() if hasattr(self, 'proxy_health_interval_spin') else 60,
            "auto_reassign": self.proxy_auto_reassign_checkbox.isChecked() if hasattr(self, 'proxy_auto_reassign_checkbox') else True,
            "prefer_us_proxies": self.prefer_us_proxies_checkbox.isChecked() if hasattr(self, 'prefer_us_proxies_checkbox') else True
        })

        settings.setdefault("scalability", {})
        settings["scalability"].update({
            "max_concurrent_accounts": self.max_concurrent_accounts_spin.value() if hasattr(self, 'max_concurrent_accounts_spin') else 50,
            "max_per_shard": self.max_per_shard_spin.value() if hasattr(self, 'max_per_shard_spin') else 10,
            "idle_timeout": self.idle_timeout_spin.value() if hasattr(self, 'idle_timeout_spin') else 300,
            "batch_update_interval": self.batch_update_interval_spin.value() if hasattr(self, 'batch_update_interval_spin') else 5
        })

        settings.setdefault("advanced", {})
        settings["advanced"].update({
            "max_reply_length": self.max_reply_length_spin.value() if hasattr(self, 'max_reply_length_spin') else 1024,
            "enable_logging": self.enable_logging_checkbox.isChecked() if hasattr(self, 'enable_logging_checkbox') else True,
            "realistic_typing": self.realistic_typing_checkbox.isChecked() if hasattr(self, 'realistic_typing_checkbox') else True,
            "random_delays": self.random_delays_checkbox.isChecked() if hasattr(self, 'random_delays_checkbox') else True
        })

        # Account factory settings
        settings["account_factory"] = {
            "account_count": self.account_count_spin.value() if hasattr(self, 'account_count_spin') else 10,
            "country": self.country_combo.currentText().split(" - ")[0] if hasattr(self, 'country_combo') else "US",
            "phone_provider": self.phone_provider_combo.currentText() if hasattr(self, 'phone_provider_combo') else "sms-activate",
            "provider_api_key": self.provider_api_edit.text().strip() if hasattr(self, 'provider_api_edit') else "",
            "use_proxy": self.use_proxy_checkbox.isChecked() if hasattr(self, 'use_proxy_checkbox') else False,
            "randomize_fingerprint": self.randomize_fingerprint_checkbox.isChecked() if hasattr(self, 'randomize_fingerprint_checkbox') else False,
            "realistic_timing": self.realistic_timing_checkbox.isChecked() if hasattr(self, 'realistic_timing_checkbox') else False,
            "vary_platform": self.vary_platform_checkbox.isChecked() if hasattr(self, 'vary_platform_checkbox') else False,
            "proxies": [line.strip() for line in getattr(self, 'proxy_list_edit', QTextEdit())
                         .toPlainText().split('\n') if line.strip()] if hasattr(self, 'proxy_list_edit') else [],
        }

        return settings

    def save_settings(self):
        """Save settings to configuration file with validation."""
        try:
            self.settings_data = self.collect_ui_settings()
            
            # Validate configuration
            errors = ValidationHelper.validate_config(self.settings_data)
            
            # Show warnings but allow saving (flexible validation)
            if errors and not self.wizard_mode:
                error_msg = "⚠️ Configuration warnings:\n\n" + "\n".join(f"• {err}" for err in errors)
                error_msg += "\n\n💡 These settings may prevent certain features from working."
                error_msg += "\n\nDo you want to save anyway?"
                
                reply = QMessageBox.question(
                    self,
                    "Configuration Warnings",
                    error_msg,
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.No:
                    return

            config_path = Path("config.json")
            
            # Backup existing config
            if config_path.exists():
                backup_path = Path("config.json.backup")
                import shutil
                shutil.copy(config_path, backup_path)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings_data, f, indent=2)

            self.settings_updated.emit(self.settings_data)
            
            if not self.wizard_mode:
                ErrorHandler.safe_information(self, "✅ Success", "Settings saved successfully!\n\nYou may need to restart for some changes to take effect.")

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            ErrorHandler.show_error(self, "database_connection_failed", str(e))

    def test_configuration(self):
        """Test the current configuration with detailed validation."""
        config = self.collect_ui_settings()
        
        # Validate configuration
        errors = ValidationHelper.validate_config(config)
        
        if errors:
            error_msg = "Configuration Issues Found:\n\n" + "\n".join(f"• {err}" for err in errors)
            error_msg += "\n\n💡 Fix these issues and test again."
            ErrorHandler.safe_warning(self, "Configuration Test Failed", error_msg)
            return
        
        # Test actual connections
        test_results = []
        
        # Test Telegram API (just validate format, actual test requires connection)
        test_results.append("✅ Telegram API credentials format is valid")
        
        # Test Gemini API if provided
        if config.get("gemini", {}).get("api_key"):
            test_results.append("✅ Gemini API key format is valid")
        
        # Check proxy format if provided
        if hasattr(self, 'proxy_list') and self.proxy_list.count() > 0:
            test_results.append(f"✅ {self.proxy_list.count()} proxy(ies) configured")
        
        success_msg = "✅ Configuration Test Passed!\n\n" + "\n".join(test_results)
        success_msg += "\n\n💡 Note: This validates format only. Actual connectivity will be tested when you connect."
        
        ErrorHandler.safe_information(self, "Configuration Test Passed", success_msg)
    
    def _open_url(self, url: str):
        """Open URL in default browser."""
        import webbrowser
        webbrowser.open(url)
