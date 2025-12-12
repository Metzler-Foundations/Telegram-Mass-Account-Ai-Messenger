#!/usr/bin/env python3
"""
UI Enhancements - Additional UI components for better user experience
Provides help dialogs, tutorials, and enhanced widgets
"""

import logging
import webbrowser
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class HelpDialog(QDialog):
    """Generic help dialog for any feature."""

    def __init__(
        self, title: str, content: str, links: Optional[Dict[str, str]] = None, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Help: {title}")
        self.resize(600, 400)

        # CRITICAL: Prevent dialog from closing parent window
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel(f"📚 {title}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)

        # Content
        content_area = QScrollArea()
        content_area.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        content_label = QLabel(content)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setOpenExternalLinks(True)
        content_layout.addWidget(content_label)

        content_layout.addStretch()
        content_area.setWidget(content_widget)
        layout.addWidget(content_area)

        # Links
        if links:
            links_layout = QHBoxLayout()
            for link_text, url in links.items():
                link_btn = QPushButton(f"🔗 {link_text}")
                link_btn.clicked.connect(lambda checked, u=url: webbrowser.open(u))
                links_layout.addWidget(link_btn)
            layout.addLayout(links_layout)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)


class QuickStartDialog(QDialog):
    """Quick start guide for new users."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Start Guide")
        self.resize(700, 500)

        # CRITICAL: Prevent dialog from closing parent window
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Quick Start Guide")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Content - with explicit colors for HTML elements
        c = ThemeManager.get_colors()
        content = QLabel(
            f"<style>"
            f"h3, h4 {{ color: {c['TEXT_BRIGHT']}; }}"
            f"ol, ul {{ color: {c['TEXT_SECONDARY']}; }}"
            f"li {{ color: {c['TEXT_SECONDARY']}; }}"
            f"b {{ color: {c['TEXT_BRIGHT']}; }}"
            f"a {{ color: #5865f2; }}"
            f"</style>"
            f"<h3>Welcome! Here's how to get started:</h3>"
            "<br>"
            "<h4>Step 1: Configure API Credentials</h4>"
            "<ol>"
            "<li>Click <b>Settings</b> (gear icon or menu)</li>"
            "<li>Go to <b>API & Auth</b> tab</li>"
            "<li>Get your <b>Telegram API credentials</b> from "
            "<a href='https://my.telegram.org/apps'>my.telegram.org/apps</a></li>"
            "<li>Get your <b>Gemini API key</b> from "
            "<a href='https://makersuite.google.com/app/apikey'>Google AI Studio</a></li>"
            "<li>Fill in all fields and click <b>Save</b></li>"
            "</ol>"
            "<br>"
            "<h4>Step 2: Create Your First Account</h4>"
            "<ol>"
            "<li>Go to <b>Settings</b> → <b>Account Creator</b> tab</li>"
            "<li>Choose a phone provider (SMS-Activate recommended for beginners)</li>"
            "<li>Get API key from your provider's website</li>"
            "<li>Click <b>Create Accounts</b> (start with 1-2 accounts)</li>"
            "<li>Wait for accounts to be created (2-5 minutes per account)</li>"
            "</ol>"
            "<br>"
            "<h4>Step 3: Let Accounts Warm Up</h4>"
            "<ol>"
            "<li>New accounts are automatically queued for warmup</li>"
            "<li>Warmup takes 3-7 days (happens automatically)</li>"
            "<li>Monitor progress in <b>Accounts</b> tab</li>"
            "</ol>"
            "<br>"
            "<h4>Step 4: Start Using Features</h4>"
            "<ul>"
            "<li><b>Dashboard:</b> Monitor all activity</li>"
            "<li><b>Members:</b> Scrape members from groups/channels</li>"
            "<li><b>Campaigns:</b> Create and run DM campaigns</li>"
            "<li><b>Messages:</b> View all messages and events</li>"
            "</ul>"
            "<br>"
            "<h4>💡 Pro Tips:</h4>"
            "<ul>"
            "<li>Start slow - 1-2 accounts first</li>"
            "<li>Keep message volumes under 30-50/hour initially</li>"
            "<li>Always provide value in messages</li>"
            "<li>Respect Telegram's Terms of Service</li>"
            "<li>Hover over any option for helpful tooltips</li>"
            "</ul>"
            "<br>"
            f"<p style='color: {c['ACCENT_WARNING']};'>"
            f"<b>Remember:</b> This is a powerful tool. "
            f"Use it responsibly and ethically!</p>"
        )
        content.setWordWrap(True)
        content.setTextFormat(Qt.TextFormat.RichText)
        content.setOpenExternalLinks(True)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        # Checkbox
        self.dont_show_again = QCheckBox("Don't show this again")
        layout.addWidget(self.dont_show_again)

        # Button
        close_btn = QPushButton("Get Started!")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        layout.addWidget(close_btn)


class ProgressDialogWithRetry(QProgressDialog):
    """Enhanced progress dialog with retry capability."""

    retry_requested = pyqtSignal()

    def __init__(self, title: str, cancel_text: str = "Cancel", parent=None):
        super().__init__(title, cancel_text, 0, 100, parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setMinimumDuration(0)

        self.error_occurred = False
        self.error_message = ""
        self.retry_btn = None

    def show_error(self, error_msg: str, allow_retry: bool = True):
        """Show error with optional retry button."""
        self.error_occurred = True
        self.error_message = error_msg

        self.setLabelText(f"Error: {error_msg}")
        self.setValue(self.maximum())

        if allow_retry and not self.retry_btn:
            # Add retry button
            self.retry_btn = QPushButton("Retry")
            self.retry_btn.clicked.connect(self._on_retry)
            self.setCancelButtonText("Close")

    def _on_retry(self):
        """Handle retry button click."""
        self.error_occurred = False
        self.error_message = ""
        self.setValue(0)
        self.retry_requested.emit()

    def update_progress(self, current: int, total: int, message: str = ""):
        """Update progress with message."""
        if total > 0:
            percentage = int((current / total) * 100)
            self.setValue(percentage)

        if message:
            self.setLabelText(message)


class StatusPanel(QFrame):
    """Status panel showing current operation status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel("Ready")
        status_font = QFont()
        status_font.setBold(True)
        self.status_label.setFont(status_font)
        layout.addWidget(self.status_label)

        # Details label
        self.details_label = QLabel("")
        self.details_label.setWordWrap(True)
        layout.addWidget(self.details_label)

        # Progress indicator (animated dots)
        self.progress_label = QLabel("")
        layout.addWidget(self.progress_label)

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self._animate_dots)
        self.dot_count = 0

    def set_status(self, status: str, details: str = "", is_working: bool = False):
        """Set status message."""
        self.status_label.setText(status)
        self.details_label.setText(details)

        if is_working:
            self.animation_timer.start(500)
        else:
            self.animation_timer.stop()
            self.progress_label.setText("")

    def _animate_dots(self):
        """Animate working dots."""
        self.dot_count = (self.dot_count + 1) % 4
        self.progress_label.setText("Working" + "." * self.dot_count)

    def set_success(self, message: str):
        """Show success status."""
        self.animation_timer.stop()
        self.status_label.setText("Success")
        self.details_label.setText(message)
        self.progress_label.setText("")

    def set_error(self, message: str):
        """Show error status."""
        self.animation_timer.stop()
        self.status_label.setText("Error")
        self.details_label.setText(message)
        self.progress_label.setText("")

    def set_warning(self, message: str):
        """Show warning status."""
        self.animation_timer.stop()
        self.status_label.setText("Warning")
        self.details_label.setText(message)
        self.progress_label.setText("")


class ConfirmationDialog(QDialog):
    """Enhanced confirmation dialog with details."""

    def __init__(
        self,
        title: str,
        message: str,
        details: Optional[List[str]] = None,
        warning: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)

        # Apply dialog styling
        self.setStyleSheet(ThemeManager.get_dialog_style())

        # CRITICAL: Prevent dialog from closing parent window
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Main message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_font = QFont()
        msg_font.setPointSize(11)
        msg_label.setFont(msg_font)
        msg_label.setStyleSheet(f"color: {c['TEXT_PRIMARY']};")
        layout.addWidget(msg_label)

        # Details
        if details:
            details_html = f"<ul style='color: {c['TEXT_SECONDARY']};'>" + "".join(f"<li style='color: {c['TEXT_SECONDARY']};'>{d}</li>" for d in details) + "</ul>"
            details_label = QLabel(details_html)
            details_label.setWordWrap(True)
            details_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
            layout.addWidget(details_label)

        # Warning
        if warning:
            warning_frame = QFrame()
            warn_hex = c["ACCENT_WARNING"].lstrip("#")
            warn_r = int(warn_hex[0:2], 16)
            warn_g = int(warn_hex[2:4], 16)
            warn_b = int(warn_hex[4:6], 16)
            warning_frame.setStyleSheet(
                f"background-color: rgba({warn_r}, {warn_g}, {warn_b}, 0.15); "
                f"border: 2px solid {c['ACCENT_WARNING']}; "
                f"border-radius: 4px; padding: 12px;"
            )
            warning_layout = QVBoxLayout(warning_frame)
            warning_label = QLabel(f"{warning}")
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet(f"color: {c['ACCENT_WARNING']};")
            warning_layout.addWidget(warning_label)
            layout.addWidget(warning_frame)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet(ThemeManager.get_button_style("default"))
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.confirm_btn = QPushButton("Confirm")
        self.confirm_btn.setStyleSheet(ThemeManager.get_button_style("primary"))
        self.confirm_btn.clicked.connect(self.accept)
        self.confirm_btn.setDefault(True)
        button_layout.addWidget(self.confirm_btn)

        layout.addLayout(button_layout)


class TutorialOverlay(QWidget):
    """Tutorial overlay that highlights UI elements."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)

        layout = QVBoxLayout(self)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        c = ThemeManager.get_colors()
        self.message_label.setStyleSheet(
            f"background-color: {c['ACCENT_PRIMARY']}; color: {c['TEXT_BRIGHT']}; padding: 15px; "
            "border-radius: 8px; font-size: 14px;"
        )
        layout.addWidget(self.message_label)

        button_layout = QHBoxLayout()

        self.skip_btn = QPushButton("Skip Tutorial")
        self.skip_btn.clicked.connect(self.close)
        button_layout.addWidget(self.skip_btn)

        self.next_btn = QPushButton("Next →")
        self.next_btn.clicked.connect(self._next_step)
        button_layout.addWidget(self.next_btn)

        layout.addLayout(button_layout)

        self.steps = []
        self.current_step = 0

    def set_steps(self, steps: List[str]):
        """Set tutorial steps."""
        self.steps = steps
        self.current_step = 0
        if steps:
            self._show_step(0)

    def _show_step(self, step_index: int):
        """Show a tutorial step."""
        if 0 <= step_index < len(self.steps):
            self.message_label.setText(
                f"📚 Step {step_index + 1}/{len(self.steps)}\n\n{self.steps[step_index]}"
            )

            if step_index == len(self.steps) - 1:
                self.next_btn.setText("Finish")
            else:
                self.next_btn.setText("Next →")

    def _next_step(self):
        """Show next step."""
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.close()
        else:
            self._show_step(self.current_step)


class FeatureCard(QFrame):
    """Card widget for displaying a feature with icon and description."""

    clicked = pyqtSignal()

    def __init__(self, icon: str, title: str, description: str, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        c = ThemeManager.get_colors()
        self.setStyleSheet(
            f"FeatureCard {{ background-color: {c['BG_TERTIARY']}; "
            f"border-radius: 8px; padding: 15px; }} "
            f"FeatureCard:hover {{ background-color: {c['BG_SECONDARY']}; }}"
        )

        layout = QVBoxLayout(self)

        # Icon and title
        header_layout = QHBoxLayout()
        icon_label = QLabel(icon)
        icon_font = QFont()
        icon_font.setPointSize(24)
        icon_label.setFont(icon_font)
        header_layout.addWidget(icon_label)

        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        c = ThemeManager.get_colors()
        desc_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
        layout.addWidget(desc_label)

    def mousePressEvent(self, event):
        """Handle click."""
        self.clicked.emit()
        super().mousePressEvent(event)


class SettingsValidator(QWidget):
    """Widget that shows validation status in real-time."""

    validation_changed = pyqtSignal(bool)  # True if valid

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel("Validating...")
        layout.addWidget(self.status_label)

        self.issues_label = QLabel("")
        self.issues_label.setWordWrap(True)
        c = ThemeManager.get_colors()
        self.issues_label.setStyleSheet(f"color: {c['ACCENT_DANGER']};")
        layout.addWidget(self.issues_label)

        self.is_valid = False

    def set_validation_result(self, is_valid: bool, errors: List[str]):
        """Set validation result."""
        self.is_valid = is_valid

        if is_valid:
            self.status_label.setText("Configuration Valid")
            self.issues_label.setText("")
        else:
            self.status_label.setText(f"{len(errors)} Issue(s) Found")
            self.issues_label.setText("\n".join(f"• {err}" for err in errors[:5]))  # Show first 5

            if len(errors) > 5:
                self.issues_label.setText(
                    self.issues_label.text() + f"\n• ... and {len(errors) - 5} more"
                )

        self.validation_changed.emit(is_valid)


def show_help(title: str, content: str, links: Optional[Dict[str, str]] = None, parent=None):
    """Show a help dialog."""
    dialog = HelpDialog(title, content, links, parent)
    dialog.exec()


def show_quick_start(parent=None) -> bool:
    """Show quick start guide. Returns True if user wants to see it again."""
    dialog = QuickStartDialog(parent)
    dialog.exec()
    return not dialog.dont_show_again.isChecked()


def confirm_action(
    title: str,
    message: str,
    details: Optional[List[str]] = None,
    warning: Optional[str] = None,
    parent=None,
) -> bool:
    """Show confirmation dialog. Returns True if confirmed."""
    dialog = ConfirmationDialog(title, message, details, warning, parent)
    return dialog.exec() == QDialog.DialogCode.Accepted
