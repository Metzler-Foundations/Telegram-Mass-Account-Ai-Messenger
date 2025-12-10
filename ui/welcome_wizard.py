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
from typing import Any, Dict, Tuple

from PyQt6.QtCore import Q_ARG, QCoreApplication, QMetaObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded
from pyrogram.raw.functions.help import GetNearestDc

from core.security_audit import audit_credential_modification
from integrations.api_key_manager import APIKeyManager
from ui.theme_manager import ThemeManager
from utils.user_helpers import ValidationHelper

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

        # Responsive sizing based on screen size
        screen = QApplication.primaryScreen().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()

        # Adaptive sizing: smaller on small screens, comfortable on large screens
        if screen_width < 1400 or screen_height < 800:
            # Small screens (laptops, small monitors)
            self.resize(800, 580)
            self.setMinimumSize(720, 520)
            self.setMaximumSize(1000, 700)
        else:
            # Large screens (desktops, large monitors)
            self.resize(900, 640)
            self.setMinimumSize(800, 580)
            self.setMaximumSize(1200, 800)

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

        # Add cleanup handler for wizard close
        self.finished.connect(self._cleanup_on_close)

    def pageCount(self):
        """Return the number of pages in the wizard."""
        return self._page_count

    def _cleanup_on_close(self):
        """Cleanup temporary session files when wizard closes."""
        try:
            session_dir = Path(".setup_sessions")
            if session_dir.exists():
                for f in session_dir.glob("*"):
                    try:
                        f.unlink(missing_ok=True)
                    except Exception:
                        pass
                logger.debug("Cleaned up temporary validation session files")
        except Exception as e:
            logger.debug(f"Error during wizard cleanup: {e}")

    def _handle_skip(self, button_id):
        """Handle skip button click."""
        if button_id == QWizard.WizardButton.CustomButton1:
            reply = QMessageBox.question(
                self,
                "Skip Setup Wizard",
                "Are you sure you want to skip the setup wizard?\n\n"
                "You can configure settings later from the Settings menu.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                # Mark setup as skipped
                setup_path = Path(".setup_complete")
                setup_path.write_text("skipped")
                self.skipped.emit()
                self.accept()

    def on_finish(self):
        """Handle wizard completion."""
        # Collect configuration from pages
        # Get phone from Telegram page (page 1) if available, otherwise from Phone page (page 2)
        telegram_page = self.page(1)
        phone_page = self.page(2)
        phone_number = ""
        if hasattr(telegram_page, "phone_edit") and telegram_page.phone_edit.text().strip():
            phone_number = telegram_page.phone_edit.text().strip()
        elif hasattr(phone_page, "phone_edit") and phone_page.phone_edit.text().strip():
            phone_number = phone_page.phone_edit.text().strip()
        
        config = {
            "telegram": {
                "api_id": telegram_page.api_id_edit.text().strip(),
                "api_hash": telegram_page.api_hash_edit.text().strip(),
                "phone_number": phone_number,
            },
            "sms_providers": {
                "provider": self.page(2).provider_combo.currentText(),
                "api_key": self.page(2).api_key_edit.text().strip(),
            },
            "gemini": {"api_key": self.page(3).gemini_edit.text().strip()},
            "brain": {
                "prompt": (
                    "You are a helpful assistant. "
                    "Respond naturally and helpfully to user messages."
                ),
                "auto_reply_enabled": True,
                "typing_delay": 2,
                "max_history": 50,
            },
            "advanced": {
                "max_reply_length": 1024,
                "enable_logging": True,
                "realistic_typing": True,
                "random_delays": True,
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
                "session_recovery": True,
            },
        }

        # Validate
        errors = ValidationHelper.validate_config(config)
        if errors:
            error_msg = "Please complete the required fields:\n\n" + "\n".join(
                f"• {err}" for err in errors
            )
            QMessageBox.warning(self, "Incomplete Setup", error_msg)
            return

        # Check if credentials were already validated on their respective pages
        telegram_page = self.page(1)
        gemini_page = self.page(3)

        tg_already_validated = hasattr(telegram_page, "_validated") and telegram_page._validated
        gemini_already_validated = hasattr(gemini_page, "_validated") and gemini_page._validated

        # Initialize variables
        tg_ok = True
        tg_profile = {}
        tg_error = ""
        gemini_ok = True
        gemini_error = ""

        # Only validate if not already done
        if not tg_already_validated or not gemini_already_validated:
            progress = QProgressDialog("Validating credentials…", "Cancel", 0, 3, self)
            progress.setWindowTitle("Validating Setup")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setValue(0)
            progress.setMinimumDuration(0)

            if not tg_already_validated:
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
            else:
                progress.setValue(1)
                logger.info("Telegram credentials already validated, skipping")

            if not gemini_already_validated:
                gemini_ok, gemini_error = self._run_async_task(
                    self._validate_gemini_key(config["gemini"]["api_key"])
                )
                progress.setValue(2)
                if progress.wasCanceled():
                    return
                if not gemini_ok:
                    progress.cancel()
                    QMessageBox.critical(
                        self,
                        "Gemini Validation Failed",
                        gemini_error or "Gemini API key could not be validated.",
                    )
                    return
            else:
                progress.setValue(2)
                logger.info("Gemini API key already validated, skipping")
        else:
            logger.info("All credentials already validated on their pages, skipping validation")
            tg_profile = {}  # Will be loaded from saved config if needed

        # Validate SMS provider API key if provided
        # Fixed: Only validate if API key is actually provided
        sms_config = config.get("sms_providers", {})
        sms_api_key = sms_config.get("api_key", "").strip()
        if sms_api_key:
            # Only update progress if we created it earlier
            if not tg_already_validated or not gemini_already_validated:
                sms_ok, sms_error = self._run_async_task(self._validate_sms_provider(sms_config))
                progress.setValue(3)
                if progress.wasCanceled():
                    return
                if not sms_ok:
                    # Don't fail the setup for SMS validation, just warn
                    QMessageBox.warning(
                        self,
                        "SMS Provider Warning",
                        f"SMS provider API key could not be validated:\n\n{sms_error}\n\n"
                        "You can still continue with setup, but account creation may not work.",
                    )
            else:
                # Both credentials already validated, validate SMS without progress dialog
                sms_ok, sms_error = self._run_async_task(self._validate_sms_provider(sms_config))
                if not sms_ok:
                    # Don't fail the setup for SMS validation, just warn
                    QMessageBox.warning(
                        self,
                        "SMS Provider Warning",
                        f"SMS provider API key could not be validated:\n\n{sms_error}\n\n"
                        "You can still continue with setup, but account creation may not work.",
                    )
        # SMS provider is optional, so no validation needed if not provided

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
        # Note: Credentials may already be saved if validated on their pages
        try:
            from core.secrets_manager import get_secrets_manager

            secrets_manager = get_secrets_manager()

            # Check if credentials are already saved (from page validation)
            api_id_exists = secrets_manager.get_secret("telegram_api_id", required=False)
            api_hash_exists = secrets_manager.get_secret("telegram_api_hash", required=False)
            gemini_exists = secrets_manager.get_secret("gemini_api_key", required=False)

            # Only save if not already saved
            if not api_id_exists:
                secrets_manager.set_secret("telegram_api_id", config["telegram"]["api_id"])
            if not api_hash_exists:
                secrets_manager.set_secret("telegram_api_hash", config["telegram"]["api_hash"])
            if not gemini_exists:
                secrets_manager.set_secret("gemini_api_key", config["gemini"]["api_key"])

            # Fixed: Use .get() to safely access optional SMS provider API key
            sms_api_key = config.get("sms_providers", {}).get("api_key")
            if sms_api_key:
                secrets_manager.set_secret("sms_provider_api_key", sms_api_key)

            # Audit the credential setup (only if newly saved)
            if not api_id_exists:
                audit_credential_modification("telegram_api_id", "setup_wizard", success=True)
            if not api_hash_exists:
                audit_credential_modification("telegram_api_hash", "setup_wizard", success=True)
            if not gemini_exists:
                audit_credential_modification("gemini_api_key", "setup_wizard", success=True)
            # Fixed: Use .get() to safely access optional SMS provider API key
            if sms_api_key:
                audit_credential_modification("sms_provider_api_key", "setup_wizard", success=True)

            logger.info("Credentials saved to secure secrets manager")

            # ALSO save to APIKeyManager so MainWindow can find them
            try:
                api_key_manager = APIKeyManager()
                # Only add if not already present
                if not api_key_manager.get_api_key("telegram_api_id"):
                    api_key_manager.add_api_key("telegram_api_id", config["telegram"]["api_id"])
                if not api_key_manager.get_api_key("telegram_api_hash"):
                    api_key_manager.add_api_key("telegram_api_hash", config["telegram"]["api_hash"])
                if not api_key_manager.get_api_key("gemini"):
                    api_key_manager.add_api_key("gemini", config["gemini"]["api_key"])
                # Fixed: Use .get() to safely access optional SMS provider settings
                sms_config = config.get("sms_providers", {})
                sms_api_key = sms_config.get("api_key")
                if sms_api_key:
                    provider_name = sms_config.get("provider", "unknown").lower().replace(" ", "_")
                    if not api_key_manager.get_api_key(provider_name):
                        api_key_manager.add_api_key(provider_name, sms_api_key)
                logger.info("Credentials also saved to APIKeyManager")
            except Exception as api_mgr_error:
                logger.warning(f"Failed to save to APIKeyManager: {api_mgr_error}")

        except Exception as secrets_error:
            logger.error(f"Failed to save to secrets manager: {secrets_error}")
            # Fixed: Ask user if they want to continue without secure storage
            reply = QMessageBox.warning(
                self,
                "Security Warning",
                "Failed to save credentials securely to secrets manager.\n\n"
                f"Error: {secrets_error}\n\n"
                "Credentials will NOT be saved securely. Continue anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return  # User chose not to continue
            # Continue anyway - better to have working config than nothing

        # Save to config.json (ONLY non-sensitive configuration)
        import json

        try:
            config_path = Path("config.json")

            # Create clean config without credentials
            clean_config = {
                "telegram": {
                    "phone_number": config["telegram"]["phone_number"],  # Phone is needed for UI
                    "profile": config["telegram"].get("profile", {}),
                    "validated": config["telegram"]["validated"],
                    "validated_at": config["telegram"]["validated_at"],
                },
                "sms_providers": {
                    # Fixed: Use .get() to safely access optional SMS provider
                    "provider": config.get("sms_providers", {}).get("provider", "daisysms")
                },
                "gemini": {
                    "validated": config["gemini"]["validated"],
                    "validated_at": config["gemini"]["validated_at"],
                },
            }

            # Copy over all other non-sensitive config sections
            for key, value in config.items():
                if key not in ["telegram", "sms_providers", "gemini"]:
                    clean_config[key] = value

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(clean_config, f, indent=2)

            # Mark as not first time
            setup_path = Path(".setup_complete")
            setup_path.write_text("1")

            logger.info(
                f"Configuration saved successfully to {config_path} "
                f"(credentials in secrets manager only)"
            )
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
                "💡 Tip: Check the Settings menu for advanced configuration options.",
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
            # Fixed: Always cancel pending tasks and reset event loop to prevent leaks
            try:
                # Cancel any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                # Wait for cancellation (with timeout)
                if pending:
                    loop.run_until_complete(asyncio.wait(pending, timeout=1.0))
            except Exception:
                pass  # Ignore errors during cleanup
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

    async def _validate_telegram_settings(
        self, telegram_cfg: Dict[str, Any]
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Lightweight Telegram validation that checks connectivity and attempts to pull
        profile metadata when a valid session exists.
        """
        api_id = telegram_cfg.get("api_id")
        api_hash = telegram_cfg.get("api_hash")
        phone = telegram_cfg.get("phone_number")

        session_dir = Path(".setup_sessions")
        session_dir.mkdir(exist_ok=True)

        # Convert api_id to int (Pyrogram requires int)
        try:
            api_id_int = int(api_id)
        except (ValueError, TypeError):
            return False, {}, f"API ID must be a number, got: {api_id}"

        client = Client(
            name="setup_validation",
            api_id=api_id_int,
            api_hash=api_hash,
            phone_number=phone,
            workdir=str(session_dir),
            in_memory=True,
            no_updates=True,
        )

        profile: Dict[str, Any] = {}

        # Retry logic for connectivity with exponential backoff
        import asyncio

        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                await client.connect()
                # Connectivity and credential check (no auth required)
                await client.invoke(GetNearestDc())
                break  # Success
            except Exception as exc:
                try:
                    await client.disconnect()
                except Exception:
                    pass

                # Don't retry on authentication/credential errors
                error_str = str(exc).lower()
                if any(
                    keyword in error_str
                    for keyword in ["api_id", "api_hash", "invalid", "unauthorized", "wrong"]
                ):
                    logger.error(f"Telegram credential error: {exc}")
                    return False, profile, f"Invalid credentials: {exc}"

                # Retry on network errors
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt)
                    logger.debug(
                        f"Telegram connectivity attempt {attempt + 1} "
                        f"failed, retrying in {delay}s: {exc}"
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(
                        f"Telegram connectivity failed after {max_retries} " f"attempts: {exc}"
                    )
                    return (
                        False,
                        profile,
                        f"Could not reach Telegram after {max_retries} " f"attempts: {exc}",
                    )

        try:
            # Ensure account is signed in; prompt user for code/password if needed
            if not await client.is_authorized():
                sent = await client.send_code(phone)
                code, ok = self._prompt_user(
                    "Telegram Login", "Enter the login code sent to Telegram:"
                )
                if not ok or not code.strip():
                    await client.disconnect()
                    return False, profile, "Login code was not provided."

                try:
                    await client.sign_in(
                        phone_number=phone,
                        phone_code_hash=sent.phone_code_hash,
                        phone_code=code.strip(),
                    )
                except SessionPasswordNeeded:
                    password, ok_pwd = self._prompt_user(
                        "Two-Factor Password",
                        "Enter your Telegram 2FA password:",
                        password_mode=True,
                    )
                    if not ok_pwd or not password:
                        await client.disconnect()
                        return False, profile, "Two-factor password required to finish sign-in."
                    await client.check_password(password=password)

            me = await client.get_me()
            if me:
                display_name = (
                    f"{(me.first_name or '').strip()} {(me.last_name or '').strip()}".strip()
                    or phone
                )
                profile = {
                    "user_id": getattr(me, "id", None),
                    "username": getattr(me, "username", "") or "",
                    "first_name": getattr(me, "first_name", "") or "",
                    "last_name": getattr(me, "last_name", "") or "",
                    "display_name": display_name,
                    "phone_number": phone,
                    "photo_path": "",
                }

                # Download profile photo when available
                if getattr(me, "photo", None):
                    photo_dir = Path("profile_photos")
                    photo_dir.mkdir(exist_ok=True)
                    try:
                        photo_path = await client.download_media(
                            me.photo, file_name=str(photo_dir / f"{me.id}.jpg")
                        )
                        if photo_path:
                            profile["photo_path"] = str(photo_path)
                    except Exception as exc:
                        logger.debug(f"Profile photo download skipped: {exc}")
            else:
                return (
                    False,
                    profile,
                    "Could not retrieve profile. Please ensure the account is fully signed in.",
                )
        except Exception as exc:
            # User may not be signed in yet; still treat connectivity as success
            logger.info(f"Telegram profile not available yet: {exc}")
        finally:
            # Always cleanup client connection
            try:
                await client.disconnect()
            except Exception:
                pass

            # Always cleanup transient session files
            try:
                if session_dir.exists():
                    for f in session_dir.glob("setup_validation*"):
                        try:
                            f.unlink(missing_ok=True)
                        except Exception:
                            pass
            except Exception as cleanup_exc:
                logger.debug(
                    f"Skipping cleanup of temporary validation session " f"files: {cleanup_exc}"
                )

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
                self,
                "_do_prompt_user",
                Qt.ConnectionType.BlockingQueuedConnection,
                Q_ARG(str, title),
                Q_ARG(str, label),
                Q_ARG(bool, password_mode),
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
    title_label.setStyleSheet(
        f"font-size: 26px; font-weight: 700; color: {c['TEXT_BRIGHT']}; "
        f"letter-spacing: -0.2px; line-height: 1.25em;"
    )
    layout.addWidget(title_label)

    subtitle_label = QLabel(subtitle)
    subtitle_label.setStyleSheet(
        f"font-size: 15px; color: {c['TEXT_SECONDARY']}; line-height: 1.5em;"
    )
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
    label.setStyleSheet(
        f"color: {c['TEXT_SECONDARY']}; font-size: 14px; line-height: 1.55; border: none;"
    )
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

        layout.addWidget(
            create_header(
                "Telegram Automation Platform", "Professional Multi-Account Management System"
            )
        )

        # Core Capabilities Grid
        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.addWidget(
            create_info_card(
                "Intelligent Automation",
                "AI-powered response system using Google Gemini for "
                "natural, context-aware communication.",
            )
        )
        left_col.addWidget(
            create_info_card(
                "Safety & Protection",
                "Sophisticated anti-detection algorithms with human "
                "behavior simulation and rate limiting.",
            )
        )
        grid_layout.addLayout(left_col)

        right_col = QVBoxLayout()
        right_col.addWidget(
            create_info_card(
                "Targeted Outreach",
                "Advanced member extraction and filtering to build "
                "precise audiences from communities.",
            )
        )
        right_col.addWidget(
            create_info_card(
                "Analytics & Insights",
                (
                    "Real-time dashboard with campaign performance metrics "
                    "and system health monitoring."
                ),
            )
        )
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
    """Telegram API setup page with improved UI and full login validation."""

    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")
        self._validated = False
        self._validation_in_progress = False
        self._validated_profile = {}  # Store profile info after validation

        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)
        layout.setSpacing(28)

        # Header with better styling
        header_widget = create_header("Telegram Configuration", "Step 1 of 3: Connect to Telegram API")
        layout.addWidget(header_widget)

        # Instructions card with improved design
        info_group = QGroupBox("📋 How to obtain credentials")
        info_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 2px solid {c['BORDER_DEFAULT']};
                border-radius: 16px;
                margin-top: 8px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 10px;
                color: {c['TEXT_BRIGHT']};
                font-weight: 600;
                font-size: 15px;
            }}
            """
        )
        info_layout = QVBoxLayout(info_group)
        info_layout.setContentsMargins(20, 28, 20, 20)
        info_layout.setSpacing(12)

        steps = QLabel(
            "<ol style='line-height: 2.0; margin-top: 8px; margin-bottom: 8px; padding-left: 20px;'>"
            "<li style='margin-bottom: 8px;'>Visit <b style='color: #5865f2;'>my.telegram.org/apps</b></li>"
            "<li style='margin-bottom: 8px;'>Log in with your phone number</li>"
            "<li style='margin-bottom: 8px;'>Go to <b>API Development Tools</b></li>"
            "<li style='margin-bottom: 8px;'>Create a new application</li>"
            "<li style='margin-bottom: 8px;'>Copy the <b>API ID</b> and <b>API Hash</b></li>"
            "</ol>"
        )
        steps.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 14px; line-height: 1.8;")
        info_layout.addWidget(steps)

        open_btn = QPushButton("🌐 Open Telegram Portal")
        open_btn.setObjectName("primary")
        open_btn.setFixedHeight(40)
        open_btn.setFixedWidth(220)
        open_btn.setStyleSheet(
            f"""
            QPushButton {{
                font-weight: 600;
                font-size: 14px;
                border-radius: 8px;
            }}
            """
        )
        open_btn.clicked.connect(lambda: webbrowser.open("https://my.telegram.org/apps"))
        info_layout.addWidget(open_btn)

        layout.addWidget(info_group)

        # Credentials form with better styling
        form_group = QGroupBox("🔐 Enter Your Credentials")
        form_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 2px solid {c['BORDER_DEFAULT']};
                border-radius: 16px;
                margin-top: 8px;
                padding-top: 16px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 10px;
                color: {c['TEXT_BRIGHT']};
                font-weight: 600;
                font-size: 15px;
            }}
            """
        )
        form_layout = QVBoxLayout(form_group)
        form_layout.setContentsMargins(20, 28, 20, 20)
        form_layout.setSpacing(20)

        # API ID with improved styling
        id_layout = QVBoxLayout()
        id_layout.setSpacing(8)
        id_label = QLabel("API ID")
        id_label.setStyleSheet(
            f"font-weight: 600; font-size: 14px; color: {c['TEXT_BRIGHT']}; padding-bottom: 4px;"
        )
        self.api_id_edit = QLineEdit()
        self.api_id_edit.setPlaceholderText("Enter your API ID (e.g. 12345678)")
        self.api_id_edit.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 12px;
                border: 2px solid {c['BORDER_DEFAULT']};
                border-radius: 8px;
                background-color: {c['BG_PRIMARY']};
                color: {c['TEXT_BRIGHT']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid #5865f2;
            }}
            """
        )
        self.api_id_edit.textChanged.connect(self._on_credentials_changed)
        id_layout.addWidget(id_label)
        id_layout.addWidget(self.api_id_edit)
        form_layout.addLayout(id_layout)

        # API Hash with improved styling
        hash_layout = QVBoxLayout()
        hash_layout.setSpacing(8)
        hash_label = QLabel("API Hash")
        hash_label.setStyleSheet(
            f"font-weight: 600; font-size: 14px; color: {c['TEXT_BRIGHT']}; padding-bottom: 4px;"
        )
        self.api_hash_edit = QLineEdit()
        self.api_hash_edit.setPlaceholderText("Enter your API Hash (e.g. 0123456789abcdef0123456789abcdef)")
        self.api_hash_edit.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 12px;
                border: 2px solid {c['BORDER_DEFAULT']};
                border-radius: 8px;
                background-color: {c['BG_PRIMARY']};
                color: {c['TEXT_BRIGHT']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid #5865f2;
            }}
            """
        )
        self.api_hash_edit.textChanged.connect(self._on_credentials_changed)
        hash_layout.addWidget(hash_label)
        hash_layout.addWidget(self.api_hash_edit)
        form_layout.addLayout(hash_layout)

        # Phone number input for full login
        phone_layout = QVBoxLayout()
        phone_layout.setSpacing(8)
        phone_label = QLabel("Phone Number (for login)")
        phone_label.setStyleSheet(
            f"font-weight: 600; font-size: 14px; color: {c['TEXT_BRIGHT']}; padding-bottom: 4px;"
        )
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Enter phone number with country code (e.g. +1234567890)")
        self.phone_edit.setStyleSheet(
            f"""
            QLineEdit {{
                padding: 12px;
                border: 2px solid {c['BORDER_DEFAULT']};
                border-radius: 8px;
                background-color: {c['BG_PRIMARY']};
                color: {c['TEXT_BRIGHT']};
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border: 2px solid #5865f2;
            }}
            """
        )
        self.phone_edit.textChanged.connect(self._on_credentials_changed)
        phone_layout.addWidget(phone_label)
        phone_layout.addWidget(self.phone_edit)
        form_layout.addLayout(phone_layout)

        # Validation status with prominent display
        self.validation_status = QLabel("")
        self.validation_status.setWordWrap(True)
        self.validation_status.setStyleSheet(
            f"""
            color: {c['TEXT_SECONDARY']};
            font-size: 14px;
            padding: 12px;
            background-color: transparent;
            border-radius: 8px;
            min-height: 50px;
            """
        )
        form_layout.addWidget(self.validation_status)

        # Success display for validated account
        self.success_display = QWidget()
        self.success_display.setVisible(False)
        success_layout = QVBoxLayout(self.success_display)
        success_layout.setContentsMargins(12, 12, 12, 12)
        success_layout.setSpacing(8)
        self.success_display.setStyleSheet(
            f"""
            QWidget {{
                background-color: rgba(35, 165, 90, 0.15);
                border: 2px solid #23a55a;
                border-radius: 12px;
            }}
            """
        )
        self.success_label = QLabel("")
        self.success_label.setStyleSheet(
            f"color: #23a55a; font-size: 15px; font-weight: 600; padding: 4px;"
        )
        self.username_label = QLabel("")
        self.username_label.setStyleSheet(
            f"color: {c['TEXT_BRIGHT']}; font-size: 14px; padding: 4px;"
        )
        success_layout.addWidget(self.success_label)
        success_layout.addWidget(self.username_label)
        form_layout.addWidget(self.success_display)

        # Button layout with better styling
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        self.validate_btn = QPushButton("🔐 Validate & Login")
        self.validate_btn.setObjectName("primary")
        self.validate_btn.setEnabled(False)
        self.validate_btn.setFixedHeight(48)
        self.validate_btn.setStyleSheet(
            f"""
            QPushButton {{
                font-weight: 600;
                font-size: 15px;
                border-radius: 10px;
                padding: 12px 24px;
            }}
            QPushButton:disabled {{
                opacity: 0.5;
            }}
            """
        )
        self.validate_btn.clicked.connect(self._validate_credentials)
        button_layout.addWidget(self.validate_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.setEnabled(False)
        self.clear_btn.setFixedHeight(48)
        self.clear_btn.setVisible(False)
        self.clear_btn.clicked.connect(self._clear_credentials)
        button_layout.addWidget(self.clear_btn)

        form_layout.addLayout(button_layout)
        layout.addWidget(form_group)

        layout.addStretch()

        # Register fields
        self.registerField("api_id*", self.api_id_edit)
        self.registerField("api_hash*", self.api_hash_edit)
        self.registerField("phone*", self.phone_edit)

    def _on_credentials_changed(self):
        """Enable validate button when all fields have content."""
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()
        has_all = bool(api_id and api_hash and phone)
        self.validate_btn.setEnabled(has_all and not self._validation_in_progress)
        
        if not has_all:
            self.validation_status.setText("")
            self._validated = False
            self.success_display.setVisible(False)
            # Update wizard to disable Next button
            self.completeChanged.emit()
        else:
            # Reset validation state if credentials changed
            # This ensures re-validation if user edits after validation
            if self._validated:
                # Check if values actually changed by comparing with saved values
                try:
                    from core.secrets_manager import get_secrets_manager

                    secrets = get_secrets_manager()
                    saved_api_id = secrets.get_secret("telegram_api_id", required=False)
                    saved_api_hash = secrets.get_secret("telegram_api_hash", required=False)
                    if saved_api_id != api_id or saved_api_hash != api_hash:
                        self._validated = False
                        self.success_display.setVisible(False)
                        self.validation_status.setText(
                            "⚠️ Credentials changed - please re-validate"
                        )
                        self.validation_status.setStyleSheet(
                            f"color: #faa61a; font-size: 14px; padding: 12px; background-color: rgba(250, 166, 26, 0.1); border-radius: 8px;"
                        )
                        self.completeChanged.emit()
                except Exception:
                    pass  # If we can't check, assume unchanged

    def _validate_credentials(self):
        """Validate Telegram credentials with actual login test."""
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()

        # Basic format validation first
        errors = []
        valid, msg = ValidationHelper.validate_api_id(api_id)
        if not valid:
            errors.append(msg)
        valid, msg = ValidationHelper.validate_api_hash(api_hash)
        if not valid:
            errors.append(msg)
        valid, msg = ValidationHelper.validate_phone_number(phone)
        if not valid:
            errors.append(msg)

        if errors:
            self.validation_status.setText(
                f"❌ Format error: {errors[0]}\n💡 Please correct the format and try again"
            )
            c = ThemeManager.get_colors()
            self.validation_status.setStyleSheet(
                f"color: #ed4245; font-size: 14px; padding: 12px; background-color: rgba(237, 66, 69, 0.1); border-radius: 8px;"
            )
            self.clear_btn.setVisible(True)
            self.clear_btn.setEnabled(True)
            self.success_display.setVisible(False)
            return

        # Perform full validation with login (always requires phone)
        self._perform_validation(api_id, api_hash, phone)


    def _perform_validation(self, api_id: str, api_hash: str, phone: str):
        """Perform full validation with actual login - NO FAKE STUFF."""
        self._validation_in_progress = True
        self.validate_btn.setEnabled(False)
        self.success_display.setVisible(False)
        self.validation_status.setText("🔄 Connecting to Telegram...")
        self.validation_status.setStyleSheet(
            "color: #5865f2; font-size: 14px; padding: 12px; background-color: rgba(88, 101, 242, 0.1); border-radius: 8px;"
        )

        # Run async validation - this performs REAL login
        wizard = self.wizard()
        if wizard:
            tg_ok, tg_profile, tg_error = wizard._run_async_task(
                wizard._validate_telegram_settings(
                    {"api_id": api_id, "api_hash": api_hash, "phone_number": phone}
                )
            )

            self._validation_in_progress = False
            self._on_credentials_changed()

            if tg_ok and tg_profile:
                # Store profile for display
                self._validated_profile = tg_profile
                
                # Get username or display name
                username = tg_profile.get("username", "")
                display_name = tg_profile.get("display_name", phone)
                user_id = tg_profile.get("user_id", "")
                
                # Build success message with username prominently displayed
                if username:
                    success_text = f"✅ Successfully logged in!"
                    username_text = f"👤 Username: @{username}\n📱 Account: {display_name}\n🆔 ID: {user_id}"
                else:
                    success_text = f"✅ Successfully logged in!"
                    username_text = f"👤 Account: {display_name}\n🆔 ID: {user_id}\n⚠️ No username set"
                
                # Show success display
                self.success_label.setText(success_text)
                self.username_label.setText(username_text)
                self.success_display.setVisible(True)
                
                # Update status
                self.validation_status.setText("")
                self.validation_status.setStyleSheet("")
                
                self._validated = True
                # Save credentials immediately
                self._save_credentials(api_id, api_hash)
                self.clear_btn.setVisible(False)
                
                # Emit signal to enable Next button
                self.completeChanged.emit()
            else:
                self.validation_status.setText(
                    f"❌ Login failed: {tg_error}\n💡 Please check your credentials and phone number, then try again"
                )
                self.validation_status.setStyleSheet(
                    "color: #ed4245; font-size: 14px; padding: 12px; background-color: rgba(237, 66, 69, 0.1); border-radius: 8px;"
                )
                self._validated = False
                self.success_display.setVisible(False)
                self.clear_btn.setVisible(True)
                self.clear_btn.setEnabled(True)
                self.completeChanged.emit()

    def _clear_credentials(self):
        """Clear credentials and reset validation state."""
        self.api_id_edit.clear()
        self.api_hash_edit.clear()
        self.phone_edit.clear()
        self.validation_status.setText("")
        self._validated = False
        self._validated_profile = {}
        self.success_display.setVisible(False)
        self.clear_btn.setVisible(False)
        self.clear_btn.setEnabled(False)
        self._on_credentials_changed()
        self.completeChanged.emit()

    def _save_credentials(self, api_id: str, api_hash: str):
        """Save validated credentials immediately."""
        try:
            from core.secrets_manager import get_secrets_manager
            from integrations.api_key_manager import APIKeyManager
            from core.security_audit import audit_credential_modification

            secrets_manager = get_secrets_manager()
            secrets_manager.set_secret("telegram_api_id", api_id)
            secrets_manager.set_secret("telegram_api_hash", api_hash)

            api_key_manager = APIKeyManager()
            api_key_manager.add_api_key("telegram_api_id", api_id)
            api_key_manager.add_api_key("telegram_api_hash", api_hash)

            audit_credential_modification("telegram_api_id", "wizard_validation", success=True)
            audit_credential_modification("telegram_api_hash", "wizard_validation", success=True)

            logger.info("Telegram credentials validated and saved immediately")
        except Exception as e:
            logger.error(f"Failed to save validated credentials: {e}")

    def isComplete(self):
        """Check if page is complete - requires validation."""
        return self._validated

    def validatePage(self):
        """Validate inputs - MUST have validated credentials to proceed."""
        if not self._validated:
            QMessageBox.warning(
                self,
                "Validation Required",
                "⚠️ You must validate and login before proceeding.\n\n"
                "Please click 'Validate & Login' to test your credentials and complete the login process.\n\n"
                "This ensures your credentials are correct and you're successfully logged in.",
            )
            return False

        # Double-check that we have all required fields
        api_id = self.api_id_edit.text().strip()
        api_hash = self.api_hash_edit.text().strip()
        phone = self.phone_edit.text().strip()

        if not api_id or not api_hash or not phone:
            QMessageBox.warning(
                self,
                "Incomplete Information",
                "Please fill in all fields (API ID, API Hash, and Phone Number) and validate.",
            )
            return False

        return True


class PhoneSetupPage(QWizardPage):
    """Phone number and SMS provider setup page for account creation."""

    def __init__(self):
        super().__init__()
        self.setTitle("")
        self.setSubTitle("")

        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        layout.addWidget(
            create_header("Account Creation Setup", "Step 2 of 4: Configure Phone & SMS")
        )

        # Phone number section - auto-filled from page 1 if available
        phone_group = QGroupBox("Primary Phone Number (for account creation)")
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
            "This phone number will be used for creating your first Telegram account. "
            "It has been auto-filled from the validated login on the previous page. "
            "You can change it if needed. Additional accounts will use SMS provider numbers."
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
        self.phone_edit.setPlaceholderText("e.g. +1234567890 (auto-filled from previous page)")
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
        self.provider_combo.addItems(
            ["daisysms", "sms-activate", "sms-hub", "5sim", "smspool", "textverified"]
        )
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

        # Register fields - phone is optional here since it's already validated on page 1
        self.registerField("phone", self.phone_edit)  # Not required (*) since it's from page 1
        self.registerField("sms_provider", self.provider_combo)
        self.registerField("sms_api_key", self.api_key_edit)

    def initializePage(self):
        """Auto-fill phone number from page 1 if available."""
        wizard = self.wizard()
        if wizard and wizard.page(1):
            telegram_page = wizard.page(1)
            if hasattr(telegram_page, "phone_edit") and hasattr(telegram_page, "_validated"):
                # If Telegram page has validated phone, use it
                if telegram_page._validated:
                    phone = telegram_page.phone_edit.text().strip()
                    if phone:
                        self.phone_edit.setText(phone)
                        logger.info(f"Auto-filled phone number from Telegram page: {phone}")

    def validatePage(self):
        """Validate inputs - phone is optional since it's already validated on page 1."""
        phone = self.phone_edit.text().strip()
        api_key = self.api_key_edit.text().strip()

        errors = []

        # Phone validation (optional - if provided, validate format)
        if phone:
            valid, msg = ValidationHelper.validate_phone_number(phone)
            if not valid:
                errors.append(msg)
        else:
            # Try to get phone from page 1
            wizard = self.wizard()
            if wizard and wizard.page(1):
                telegram_page = wizard.page(1)
                if hasattr(telegram_page, "phone_edit"):
                    phone_from_page1 = telegram_page.phone_edit.text().strip()
                    if not phone_from_page1:
                        errors.append("Phone number is required. Please enter it on the previous page or here.")

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
        self._validated = False
        self._validation_in_progress = False

        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        layout.addWidget(
            create_header("AI Engine Configuration", "Step 3 of 4: Connect Intelligence Layer")
        )

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
        open_btn.clicked.connect(
            lambda: webbrowser.open("https://makersuite.google.com/app/apikey")
        )
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
        self.gemini_edit.textChanged.connect(self._on_key_changed)

        show_check = QCheckBox("Show API Key")
        show_check.toggled.connect(
            lambda checked: self.gemini_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )

        key_layout.addWidget(key_label)
        key_layout.addWidget(self.gemini_edit)
        key_layout.addWidget(show_check)

        # Validation status and button
        validation_layout = QVBoxLayout()
        validation_layout.setSpacing(8)

        self.validation_status = QLabel("")
        self.validation_status.setStyleSheet(
            f"color: {c['TEXT_SECONDARY']}; font-size: 13px; padding: 8px 0;"
        )
        validation_layout.addWidget(self.validation_status)

        # Button layout
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)

        self.validate_btn = QPushButton("Validate API Key")
        self.validate_btn.setObjectName("primary")
        self.validate_btn.setEnabled(False)
        self.validate_btn.clicked.connect(self._validate_api_key)
        button_layout.addWidget(self.validate_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("secondary")
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self._clear_api_key)
        self.clear_btn.setVisible(False)
        button_layout.addWidget(self.clear_btn)

        validation_layout.addLayout(button_layout)
        key_layout.addLayout(validation_layout)

        layout.addLayout(key_layout)
        layout.addStretch()

        self.registerField("gemini*", self.gemini_edit)

    def _on_key_changed(self):
        """Enable validate button when key has content."""
        api_key = self.gemini_edit.text().strip()
        has_key = bool(api_key)
        self.validate_btn.setEnabled(has_key and not self._validation_in_progress)
        if not has_key:
            self.validation_status.setText("")
            self._validated = False

    def _validate_api_key(self):
        """Validate Gemini API key with actual API test."""
        api_key = self.gemini_edit.text().strip()

        # Basic format validation first
        valid, msg = ValidationHelper.validate_gemini_api_key(api_key)
        if not valid:
            self.validation_status.setText(f"❌ {msg}\n💡 Please check the format and try again")
            self.validation_status.setStyleSheet("color: #ed4245; font-size: 13px; padding: 8px 0;")
            self.clear_btn.setVisible(True)
            self.clear_btn.setEnabled(True)
            return

        # Perform actual API validation
        self._validation_in_progress = True
        self.validate_btn.setEnabled(False)
        self.validation_status.setText("🔄 Validating API key...")
        self.validation_status.setStyleSheet("color: #5865f2; font-size: 13px; padding: 8px 0;")

        # Run async validation
        wizard = self.wizard()
        if wizard:
            gemini_ok, gemini_error = wizard._run_async_task(wizard._validate_gemini_key(api_key))

            self._validation_in_progress = False
            self._on_key_changed()

            if gemini_ok:
                self.validation_status.setText("✅ API key validated and working")
                self.validation_status.setStyleSheet(
                    "color: #23a55a; font-size: 13px; padding: 8px 0;"
                )
                self._validated = True
                # Save credentials immediately
                self._save_credentials(api_key)
                self.clear_btn.setVisible(False)
            else:
                self.validation_status.setText(
                    f"❌ {gemini_error or 'API key validation failed'}\n"
                    f"💡 Check your API key and try again"
                )
                self.validation_status.setStyleSheet(
                    "color: #ed4245; font-size: 13px; padding: 8px 0;"
                )
                self._validated = False
                self.clear_btn.setVisible(True)
                self.clear_btn.setEnabled(True)

    def _clear_api_key(self):
        """Clear API key and reset validation state."""
        self.gemini_edit.clear()
        self.validation_status.setText("")
        self._validated = False
        self.clear_btn.setVisible(False)
        self.clear_btn.setEnabled(False)
        self._on_key_changed()

    def _save_credentials(self, api_key: str):
        """Save validated credentials immediately."""
        try:
            from core.secrets_manager import get_secrets_manager
            from integrations.api_key_manager import APIKeyManager
            from core.security_audit import audit_credential_modification

            secrets_manager = get_secrets_manager()
            secrets_manager.set_secret("gemini_api_key", api_key)

            api_key_manager = APIKeyManager()
            api_key_manager.add_api_key("gemini", api_key)

            audit_credential_modification("gemini_api_key", "wizard_validation", success=True)

            logger.info("Gemini API key validated and saved immediately")
        except Exception as e:
            logger.error(f"Failed to save validated Gemini credentials: {e}")

    def validatePage(self):
        """Validate API key - check if already validated."""
        if self._validated:
            return True

        api_key = self.gemini_edit.text().strip()
        valid, msg = ValidationHelper.validate_gemini_api_key(api_key)
        if not valid:
            QMessageBox.warning(self, "Validation Error", msg)
            return False

        # If not validated yet, prompt user
        if not self._validated:
            reply = QMessageBox.question(
                self,
                "Validate API Key",
                "Would you like to validate the API key now?\n\n"
                "This will test your key and save it if valid.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._validate_api_key()
                return self._validated

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
        col1.addWidget(
            create_info_card(
                "Command Center",
                "Unified operations dashboard for monitoring all accounts and campaigns.",
            )
        )
        col1.addWidget(
            create_info_card(
                "Analytics", "Detailed metrics for engagement, growth, and system performance."
            )
        )
        grid.addLayout(col1)

        col2 = QVBoxLayout()
        col2.addWidget(
            create_info_card(
                "Campaign Engine", "Automated direct messaging with scheduling and templates."
            )
        )
        col2.addWidget(
            create_info_card(
                "Member Scraper", "Extract targeted user lists from groups for outreach."
            )
        )
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
        practices_label.setStyleSheet(
            f"color: {c['TEXT_SECONDARY']}; font-size: 13px; line-height: 1.6;"
        )
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
        steps_label.setStyleSheet(
            f"color: {c['TEXT_SECONDARY']}; font-size: 14px; line-height: 1.8;"
        )
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

        api_id = secrets.get_secret("telegram_api_id", required=False)
        api_hash = secrets.get_secret("telegram_api_hash", required=False)

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

    from PyQt6.QtWidgets import QApplication  # noqa: F811

    try:
        from ui.theme_manager import ThemeManager  # noqa: F811
    except Exception:
        ThemeManager = None

    app = QApplication(sys.argv)
    if ThemeManager:
        ThemeManager.apply_to_application(app)
    wizard = WelcomeWizard()
    wizard.show()
    sys.exit(app.exec())
