#!/usr/bin/env python3
"""
Welcome Wizard - First-time setup guide for new users
Provides step-by-step onboarding experience with a clean, professional UI.
"""

import asyncio
import logging
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple

from core.security_audit import audit_credential_modification
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTextEdit, QWizard, QWizardPage, QCheckBox, QMessageBox,
    QFrame, QGroupBox, QSizePolicy, QProgressDialog, QInputDialog, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QMetaObject, Q_ARG
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QCoreApplication
from PyQt6.QtGui import QFont, QPixmap
from pyrogram import Client
from pyrogram.raw.functions.help import GetNearestDc
from pyrogram.errors import SessionPasswordNeeded

from integrations.api_key_manager import APIKeyManager

from utils.user_helpers import ValidationHelper, get_tooltip
from ui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class WelcomeWizard(QWizard):
    """Welcome wizard for first-time setup."""
    
    config_completed = pyqtSignal(dict)
    skipped = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup - Telegram Automation Platform")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)
        # Ensure navigation buttons are visible
        self.setOption(QWizard.WizardOption.NoCancelButton, False)
        self.resize(900, 640)  # Elevated, comfortable size
        self.setMinimumSize(860, 600)
        
        # Theme applied globally; keep object name for targeted QSS
        self.setObjectName("welcome_wizard")
        self.setButtonText(QWizard.WizardButton.NextButton, "Next")
        self.setButtonText(QWizard.WizardButton.BackButton, "Back")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Finish Setup")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Close")
        # Add elevated shadow (QSS cannot do shadows)
        ThemeManager.apply_shadow(self, blur_radius=48, y_offset=18, opacity=0.55)
        
        # Add custom skip button
        self.setButtonText(QWizard.WizardButton.CustomButton1, "I Already Have Credentials →")
        self.setOption(QWizard.WizardOption.HaveCustomButton1, True)
        self.customButtonClicked.connect(self._handle_skip)
        
        # Add pages
        self.addPage(IntroPage())
        self.addPage(TelegramSetupPage())
        self.addPage(PhoneSetupPage())
        self.addPage(GeminiSetupPage())
        self.addPage(FeaturesPage())
        self.addPage(CompletePage())

        # Store page count for validation
        self._page_count = 6
        
        self.button(QWizard.WizardButton.FinishButton).clicked.connect(self.on_finish)

    def pageCount(self):
        """Return the number of pages in the wizard."""
        return self._page_count

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
                "phone_number": self.page(2).phone_edit.text().strip()
            },
            "sms_providers": {
                "provider": self.page(2).provider_combo.currentText(),
                "api_key": self.page(2).api_key_edit.text().strip()
            },
            "gemini": {
                "api_key": self.page(3).gemini_edit.text().strip()
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

        # Validate credentials and fetch profile info
        progress = QProgressDialog("Validating credentials…", "Cancel", 0, 3, self)
        progress.setWindowTitle("Validating Setup")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(0)
        progress.setMinimumDuration(0)

        tg_ok, tg_profile, tg_error = self._run_async_task(
            self._validate_telegram_settings(config["telegram"])
        )
        progress.setValue(1)
        if progress.wasCanceled():
            return
        if not tg_ok:
            progress.cancel()
            QMessageBox.critical(self, "Telegram Validation Failed", tg_error)
            return

        gemini_ok, gemini_error = self._run_async_task(
            self._validate_gemini_key(config["gemini"]["api_key"])
        )
        progress.setValue(2)
        if progress.wasCanceled():
            return
        if not gemini_ok:
            progress.cancel()
            QMessageBox.critical(self, "Gemini Validation Failed", gemini_error or "Gemini API key could not be validated.")
            return

        # Validate SMS provider API key if provided
        sms_config = config.get("sms_providers", {})
        if sms_config.get("api_key"):
            sms_ok, sms_error = self._run_async_task(
                self._validate_sms_provider(sms_config)
            )
            progress.setValue(3)
            if progress.wasCanceled():
                return
            if not sms_ok:
                # Don't fail the setup for SMS validation, just warn
                QMessageBox.warning(self, "SMS Provider Warning",
                    f"SMS provider API key could not be validated:\n\n{sms_error}\n\n"
                    "You can still continue with setup, but account creation may not work.")
        else:
            progress.setValue(3)

        # Stamp validation metadata
        now_ts = datetime.now().isoformat()
        config["telegram"]["validated"] = True
        config["telegram"]["validated_at"] = now_ts
        if tg_profile:
            tg_profile.setdefault("validated", True)
            tg_profile.setdefault("validated_at", now_ts)
            config["telegram"]["profile"] = tg_profile
        config["gemini"]["validated"] = True
        config["gemini"]["validated_at"] = now_ts
        
        # Save to secrets manager first (secure storage)
        try:
            from core.secrets_manager import get_secrets_manager
            secrets_manager = get_secrets_manager()

            # Save credentials to secrets manager
            secrets_manager.set_secret('telegram_api_id', config["telegram"]["api_id"])
            secrets_manager.set_secret('telegram_api_hash', config["telegram"]["api_hash"])
            secrets_manager.set_secret('gemini_api_key', config["gemini"]["api_key"])
            if config["sms_providers"]["api_key"]:
                secrets_manager.set_secret('sms_provider_api_key', config["sms_providers"]["api_key"])

            # Audit the credential setup
            audit_credential_modification('telegram_api_id', 'setup_wizard', success=True)
            audit_credential_modification('telegram_api_hash', 'setup_wizard', success=True)
            audit_credential_modification('gemini_api_key', 'setup_wizard', success=True)
            if config["sms_providers"]["api_key"]:
                audit_credential_modification('sms_provider_api_key', 'setup_wizard', success=True)

            logger.info("Credentials saved to secure secrets manager")

            # ALSO save to APIKeyManager so MainWindow can find them
            try:
                api_key_manager = APIKeyManager()
                # Telegram uses separate services for api_id and api_hash
                api_key_manager.add_api_key('telegram_api_id', config["telegram"]["api_id"])
                api_key_manager.add_api_key('telegram_api_hash', config["telegram"]["api_hash"])
                api_key_manager.add_api_key('gemini', config["gemini"]["api_key"])
                if config["sms_providers"]["api_key"]:
                    provider_name = config["sms_providers"]["provider"].lower().replace(' ', '_')
                    api_key_manager.add_api_key(provider_name, config["sms_providers"]["api_key"])
                logger.info("Credentials also saved to APIKeyManager")
            except Exception as api_mgr_error:
                logger.warning(f"Failed to save to APIKeyManager: {api_mgr_error}")

        except Exception as secrets_error:
            logger.error(f"Failed to save to secrets manager: {secrets_error}")
            QMessageBox.warning(self, "Security Warning",
                "Failed to save credentials securely. They will be stored in config file only.\n\n"
                f"Error: {secrets_error}")
            # Continue anyway - better to have working config than nothing

        # Save to config.json (ONLY non-sensitive configuration)
        import json
        import os
        try:
            config_path = os.path.join(os.getcwd(), "config.json")

            # Create clean config without credentials
            clean_config = {
                "telegram": {
                    "phone_number": config["telegram"]["phone_number"],  # Phone is needed for UI
                    "profile": config["telegram"].get("profile", {}),
                    "validated": config["telegram"]["validated"],
                    "validated_at": config["telegram"]["validated_at"]
                },
                "sms_providers": {
                    "provider": config["sms_providers"]["provider"]  # Provider name is not sensitive
                },
                "gemini": {
                    "validated": config["gemini"]["validated"],
                    "validated_at": config["gemini"]["validated_at"]
                }
            }

            # Copy over all other non-sensitive config sections
            for key, value in config.items():
                if key not in ["telegram", "sms_providers", "gemini"]:
                    clean_config[key] = value

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(clean_config, f, indent=2)

            # Mark as not first time
            setup_path = os.path.join(os.getcwd(), ".setup_complete")
            with open(setup_path, 'w') as f:
                f.write("1")

            logger.info(f"Configuration saved successfully to {config_path} (credentials in secrets manager only)")
            self.config_completed.emit(clean_config)
            
            # Accept the dialog to signal successful completion
            self.accept()
            progress.setValue(3)
            QMessageBox.information(
                self,
                "Setup Complete!",
                "🎉 Congratulations! Your Telegram automation platform is ready.\n\n"
                "✅ Telegram API credentials configured\n"
                "✅ AI (Gemini) integration ready\n"
                "✅ SMS provider configured (optional)\n\n"
                "📋 Next Steps:\n"
                "1. Click 'Create Account' to add your first Telegram account\n"
                "2. Start campaigns to automate messaging\n"
                "3. Monitor analytics in the dashboard\n\n"
                "💡 Tip: Check the Settings menu for advanced configuration options."
            )
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration: {e}")
            return

    def _run_async_task(self, coro):
        """Run an async coroutine without blocking the Qt event loop."""
        app = QApplication.instance()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._run_coro_blocking, coro)
            # Keep UI responsive while waiting
            while not future.done():
                if app:
                    app.processEvents()
                else:
                    QCoreApplication.processEvents()
            return future.result()

    @staticmethod
    def _run_coro_blocking(coro):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _validate_gemini_key(self, api_key: str) -> Tuple[bool, str]:
        """Validate Gemini API key using the APIKeyManager."""
        try:
            manager = APIKeyManager()
            is_valid, err = await manager.validate_api_key_raw("gemini", api_key)
            return is_valid, err
        except Exception as exc:
            logger.error(f"Gemini validation failed: {exc}")
            return False, str(exc)

    async def _validate_sms_provider(self, sms_config: Dict[str, str]) -> Tuple[bool, str]:
        """Validate SMS provider API key using the APIKeyManager."""
        try:
            provider = sms_config.get("provider", "")
            api_key = sms_config.get("api_key", "")

            if not provider or not api_key:
                return True, ""  # Optional, so pass if not provided

            manager = APIKeyManager()
            is_valid, err = await manager.validate_api_key_raw(provider, api_key)
            return is_valid, err
        except Exception as exc:
            logger.error(f"SMS provider validation failed: {exc}")
            return False, str(exc)

    async def _validate_telegram_settings(self, telegram_cfg: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        """
        Lightweight Telegram validation that checks connectivity and attempts to pull
        profile metadata when a valid session exists.
        """
        api_id = telegram_cfg.get("api_id")
        api_hash = telegram_cfg.get("api_hash")
        phone = telegram_cfg.get("phone_number")

        session_dir = Path(".setup_sessions")
        session_dir.mkdir(exist_ok=True)

        client = Client(
            name="setup_validation",
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone,
            workdir=str(session_dir),
            in_memory=True,
            no_updates=True
        )

        profile: Dict[str, Any] = {}

        try:
            await client.connect()
            # Connectivity and credential check (no auth required)
            await client.invoke(GetNearestDc())
        except Exception as exc:
            try:
                await client.disconnect()
            except Exception:
                pass
            logger.error(f"Telegram connectivity failed: {exc}")
            return False, profile, f"Could not reach Telegram with these credentials: {exc}"

        try:
            # Ensure account is signed in; prompt user for code/password if needed
            if not await client.is_authorized():
                sent = await client.send_code(phone)
                code, ok = self._prompt_user("Telegram Login", "Enter the login code sent to Telegram:")
                if not ok or not code.strip():
                    await client.disconnect()
                    return False, profile, "Login code was not provided."

                try:
                    await client.sign_in(
                        phone_number=phone,
                        phone_code_hash=sent.phone_code_hash,
                        phone_code=code.strip()
                    )
                except SessionPasswordNeeded:
                    password, ok_pwd = self._prompt_user("Two-Factor Password", "Enter your Telegram 2FA password:", password_mode=True)
                    if not ok_pwd or not password:
                        await client.disconnect()
                        return False, profile, "Two-factor password required to finish sign-in."
                    await client.check_password(password=password)

            me = await client.get_me()
            if me:
                display_name = f"{(me.first_name or '').strip()} {(me.last_name or '').strip()}".strip() or phone
                profile = {
                    "user_id": getattr(me, "id", None),
                    "username": getattr(me, "username", "") or "",
                    "first_name": getattr(me, "first_name", "") or "",
                    "last_name": getattr(me, "last_name", "") or "",
                    "display_name": display_name,
                    "phone_number": phone,
                    "photo_path": ""
                }

                # Download profile photo when available
                if getattr(me, "photo", None):
                    photo_dir = Path("profile_photos")
                    photo_dir.mkdir(exist_ok=True)
                    try:
                        photo_path = await client.download_media(
                            me.photo,
                            file_name=str(photo_dir / f"{me.id}.jpg")
                        )
                        if photo_path:
                            profile["photo_path"] = str(photo_path)
                    except Exception as exc:
                        logger.debug(f"Profile photo download skipped: {exc}")
            else:
                return False, profile, "Could not retrieve profile. Please ensure the account is fully signed in."
        except Exception as exc:
            # User may not be signed in yet; still treat connectivity as success
            logger.info(f"Telegram profile not available yet: {exc}")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
            # Cleanup transient session files
            try:
                if session_dir.exists():
                    for f in session_dir.glob("*"):
                        f.unlink(missing_ok=True)
            except Exception:
                logger.debug("Skipping cleanup of temporary validation session files")

        return True, profile, ""

    def _prompt_user(self, title: str, label: str, password_mode: bool = False) -> Tuple[str, bool]:
        """Prompt the user for input. Thread-safe - marshals to main thread if needed."""
        app = QApplication.instance()
        if app and QThread.currentThread() == app.thread():
            # Already on main thread, call directly
            echo = QLineEdit.EchoMode.Password if password_mode else QLineEdit.EchoMode.Normal
            text, ok = QInputDialog.getText(self, title, label, echo)
            return text, ok
        else:
            # Need to marshal to main thread
            self._prompt_result = None
            QMetaObject.invokeMethod(
                self, "_do_prompt_user", 
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_ARG(str, title), Q_ARG(str, label), Q_ARG(bool, password_mode)
            )
            return self._prompt_result if self._prompt_result else ("", False)
    
    def _do_prompt_user(self, title: str, label: str, password_mode: bool = False):
        """Helper method to run prompt on main thread."""
        echo = QLineEdit.EchoMode.Password if password_mode else QLineEdit.EchoMode.Normal
        text, ok = QInputDialog.getText(self, title, label, echo)
        self._prompt_result = (text, ok)


def create_header(title: str, subtitle: str) -> QWidget:
    """Create a clean header widget with high contrast."""
    widget = QWidget()
    widget.setStyleSheet("background-color: transparent;")
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 18)
    layout.setSpacing(8)
    
    c = ThemeManager.get_colors()
    title_label = QLabel(title)
    title_label.setStyleSheet(f"font-size: 26px; font-weight: 700; color: {c['TEXT_BRIGHT']}; letter-spacing: -0.2px; line-height: 1.25em;")
    layout.addWidget(title_label)
    
    subtitle_label = QLabel(subtitle)
    subtitle_label.setStyleSheet(f"font-size: 15px; color: {c['TEXT_SECONDARY']}; line-height: 1.5em;")
    layout.addWidget(subtitle_label)
    
    return widget


def create_info_card(title: str, text: str) -> QGroupBox:
    """Create a clean info card using QGroupBox."""
    c = ThemeManager.get_colors()
    group = QGroupBox(title)
    group.setStyleSheet(
        f"""
        QGroupBox {{
            font-weight: 700;
            color: {c['TEXT_BRIGHT']};
            background-color: {c['BG_SECONDARY']};
            border: 1px solid {c['BORDER_DEFAULT']};
            border-radius: 12px;
            margin-top: 12px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 14px;
            padding: 0 8px;
        }}
        """
    )
    
    layout = QVBoxLayout(group)
    layout.setContentsMargins(16, 22, 16, 16)
    
    label = QLabel(text)
    label.setWordWrap(True)
    # Force bright text color and line height
    label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 14px; line-height: 1.55; border: none;")
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
        left_col.addWidget(create_info_card("Intelligent Automation", 
            "AI-powered response system using Google Gemini for natural, context-aware communication."))
        left_col.addWidget(create_info_card("Safety & Protection", 
            "Sophisticated anti-detection algorithms with human behavior simulation and rate limiting."))
        grid_layout.addLayout(left_col)
        
        right_col = QVBoxLayout()
        right_col.addWidget(create_info_card("Targeted Outreach", 
            "Advanced member extraction and filtering to build precise audiences from communities."))
        right_col.addWidget(create_info_card("Analytics & Insights", 
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
        c = ThemeManager.get_colors()
        prereq_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 13px;")
        prereq_layout.addWidget(prereq_label)
        layout.addWidget(prereq_group)
        
        layout.addStretch()


class TelegramSetupPage(QWizardPage):
    """Telegram API setup page."""
    
    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")
        
        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        layout.addWidget(create_header("Telegram Configuration", "Step 1 of 3: Connect to Telegram API"))
        
        # Instructions
        info_group = QGroupBox("How to obtain credentials")
        info_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 1px solid {c['BORDER_DEFAULT']};
                border-radius: 12px;
                margin-top: 6px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['TEXT_SECONDARY']};
            }}
            """
        )
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
        c = ThemeManager.get_colors()
        steps.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 14px; line-height: 1.6;")
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
        c = ThemeManager.get_colors()
        id_label = QLabel("API ID")
        id_label.setStyleSheet(f"font-weight: 600; color: {c['TEXT_BRIGHT']};")
        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("e.g. 12345678")
        id_layout.addWidget(id_label)
        id_layout.addWidget(self.api_id_edit)
        form_layout.addLayout(id_layout)
        
        # API Hash
        hash_layout = QVBoxLayout()
        hash_layout.setSpacing(6)
        c = ThemeManager.get_colors()
        hash_label = QLabel("API Hash")
        hash_label.setStyleSheet(f"font-weight: 600; color: {c['TEXT_BRIGHT']};")
        self.api_hash_edit = QLineEdit()
        self.api_hash_edit.setPlaceholderText("e.g. 0123456789abcdef...")
        hash_layout.addWidget(hash_label)
        hash_layout.addWidget(self.api_hash_edit)
        form_layout.addLayout(hash_layout)
        
        # Phone
        phone_layout = QVBoxLayout()
        phone_layout.setSpacing(6)
        c = ThemeManager.get_colors()
        phone_label = QLabel("Phone Number")
        phone_label.setStyleSheet(f"font-weight: 600; color: {c['TEXT_BRIGHT']};")
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
        self.registerField("telegram_phone", self.phone_edit)
    
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


class PhoneSetupPage(QWizardPage):
    """Phone number and SMS provider setup page."""

    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")

        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        layout.addWidget(create_header("Account Creation Setup", "Step 2 of 4: Configure Phone & SMS"))

        # Phone number section
        phone_group = QGroupBox("Primary Phone Number")
        phone_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 1px solid {c['BORDER_DEFAULT']};
                border-radius: 12px;
                margin-top: 6px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['TEXT_SECONDARY']};
            }}
            """
        )
        phone_layout = QVBoxLayout(phone_group)
        phone_layout.setContentsMargins(16, 24, 16, 16)

        phone_info = QLabel(
            "Your primary phone number will be used for the first Telegram account. "
            "Additional accounts will use SMS provider numbers."
        )
        phone_info.setWordWrap(True)
        phone_info.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 13px;")
        phone_layout.addWidget(phone_info)

        # Phone input
        phone_input_layout = QVBoxLayout()
        phone_input_layout.setSpacing(6)
        c = ThemeManager.get_colors()
        phone_label = QLabel("Phone Number")
        phone_label.setStyleSheet(f"font-weight: 600; color: {c['TEXT_BRIGHT']};")
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("e.g. +1234567890")
        phone_input_layout.addWidget(phone_label)
        phone_input_layout.addWidget(self.phone_edit)
        phone_layout.addLayout(phone_input_layout)

        layout.addWidget(phone_group)

        # SMS Provider section
        sms_group = QGroupBox("SMS Provider (for bulk account creation)")
        sms_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 1px solid {c['BORDER_DEFAULT']};
                border-radius: 12px;
                margin-top: 6px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['TEXT_SECONDARY']};
            }}
            """
        )
        sms_layout = QVBoxLayout(sms_group)
        sms_layout.setContentsMargins(16, 24, 16, 16)

        sms_info = QLabel(
            "Choose an SMS provider for automated phone number rental and OTP verification. "
            "This enables bulk account creation."
        )
        sms_info.setWordWrap(True)
        sms_info.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 13px;")
        sms_layout.addWidget(sms_info)

        # Provider selection
        provider_layout = QVBoxLayout()
        provider_layout.setSpacing(6)
        c = ThemeManager.get_colors()
        provider_label = QLabel("SMS Provider")
        provider_label.setStyleSheet(f"font-weight: 600; color: {c['TEXT_BRIGHT']};")
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "daisysms", "sms-activate", "sms-hub", "5sim", "smspool", "textverified"
        ])
        provider_layout.addWidget(provider_label)
        provider_layout.addWidget(self.provider_combo)
        sms_layout.addLayout(provider_layout)

        # API Key input
        api_layout = QVBoxLayout()
        api_layout.setSpacing(6)
        c = ThemeManager.get_colors()
        api_label = QLabel("Provider API Key")
        api_label.setStyleSheet(f"font-weight: 600; color: {c['TEXT_BRIGHT']};")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Your SMS provider API key")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addWidget(api_label)
        api_layout.addWidget(self.api_key_edit)
        sms_layout.addLayout(api_layout)

        layout.addWidget(sms_group)

        # Register fields
        self.registerField("phone*", self.phone_edit)
        self.registerField("sms_provider", self.provider_combo)
        self.registerField("sms_api_key", self.api_key_edit)

    def validatePage(self):
        """Validate inputs."""
        phone = self.phone_edit.text().strip()
        api_key = self.api_key_edit.text().strip()

        errors = []

        # Phone validation (required)
        valid, msg = ValidationHelper.validate_phone_number(phone)
        if not valid:
            errors.append(msg)

        # API key validation (optional but recommended)
        if api_key and len(api_key) < 10:
            errors.append("SMS provider API key seems too short (should be 10+ characters)")

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
        
        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        layout.addWidget(create_header("AI Engine Configuration", "Step 3 of 4: Connect Intelligence Layer"))
        
        # Info
        info_group = QGroupBox("Google Gemini API")
        info_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 1px solid {c['BORDER_DEFAULT']};
                border-radius: 12px;
                margin-top: 6px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['TEXT_SECONDARY']};
            }}
            """
        )
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(16, 24, 16, 16)
        
        info_text = QLabel(
            "Gemini provides the neural processing for intelligent conversations.\n"
            "The free tier includes 60 requests/minute and 1,500 requests/day."
        )
        c = ThemeManager.get_colors()
        info_text.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 14px; line-height: 1.6;")
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
        c = ThemeManager.get_colors()
        key_label = QLabel("Gemini API Key")
        key_label.setStyleSheet(f"font-weight: 600; color: {c['TEXT_BRIGHT']};")
        
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
        
        layout.addWidget(create_header("System Capabilities", "Step 4 of 4: Overview"))
        
        # Feature Cards
        grid = QHBoxLayout()
        grid.setSpacing(16)
        
        col1 = QVBoxLayout()
        col1.addWidget(create_info_card("Command Center", 
            "Unified operations dashboard for monitoring all accounts and campaigns."))
        col1.addWidget(create_info_card("Analytics", 
            "Detailed metrics for engagement, growth, and system performance."))
        grid.addLayout(col1)
        
        col2 = QVBoxLayout()
        col2.addWidget(create_info_card("Campaign Engine", 
            "Automated direct messaging with scheduling and templates."))
        col2.addWidget(create_info_card("Member Scraper", 
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
        c = ThemeManager.get_colors()
        practices_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 13px; line-height: 1.6;")
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
        
        c = ThemeManager.get_colors()
        title = QLabel("System Initialized")
        title.setStyleSheet(f"font-size: 28px; font-weight: 700; color: {c['TEXT_BRIGHT']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        subtitle = QLabel("Configuration complete. Platform ready for deployment.")
        subtitle.setStyleSheet(f"font-size: 16px; color: {c['TEXT_SECONDARY']};")
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
        c = ThemeManager.get_colors()
        steps_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 14px; line-height: 1.8;")
        steps_layout.addWidget(steps_label)
        layout.addWidget(steps_group)
        
        # Launch Button Note
        note = QLabel("Click Finish to launch the platform dashboard.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c = ThemeManager.get_colors()
        note.setStyleSheet(f"color: {c['TEXT_DISABLED']}; margin-top: 20px;")
        layout.addWidget(note)
        
        layout.addStretch()


def should_show_wizard() -> bool:
    """Check if welcome wizard should be shown (first time use)."""
    setup_file = Path(".setup_complete")
    
    # If setup file doesn't exist, show wizard
    if not setup_file.exists():
        return True
    
    # Check if credentials exist in secrets_manager (where wizard saves them)
    try:
        from core.secrets_manager import get_secrets_manager
        secrets = get_secrets_manager()
        
        api_id = secrets.get_secret('telegram_api_id', required=False)
        api_hash = secrets.get_secret('telegram_api_hash', required=False)
        
        # If either is missing, show wizard
        if not api_id or not api_hash:
            return True
        
        return False
    except Exception as e:
        logger.warning(f"Error checking wizard status: {e}")
        # On error, show wizard to be safe
        return True


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    try:
        from ui.theme_manager import ThemeManager
    except Exception:
        ThemeManager = None
    
    app = QApplication(sys.argv)
    if ThemeManager:
        ThemeManager.apply_to_application(app)
    wizard = WelcomeWizard()
    wizard.show()
    sys.exit(app.exec())
