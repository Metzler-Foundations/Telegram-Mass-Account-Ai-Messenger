#!/usr/bin/env python3
"""
UX Helpers - Enhanced user experience utilities
Provides better feedback, empty states, help dialogs, and user guidance.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.theme_manager import ThemeManager
from ui.toast_notifications import show_toast


def show_success_toast(parent, message: str, duration: int = 3000):
    """Show success toast notification."""
    return show_toast(parent, f"✅ {message}", duration, "success")


def show_error_toast(parent, message: str, duration: int = 4000):
    """Show error toast notification."""
    return show_toast(parent, f"❌ {message}", duration, "error")


def show_info_toast(parent, message: str, duration: int = 3000):
    """Show info toast notification."""
    return show_toast(parent, f"ℹ️ {message}", duration, "info")


def show_warning_toast(parent, message: str, duration: int = 3500):
    """Show warning toast notification."""
    return show_toast(parent, f"⚠️ {message}", duration, "warning")


def create_empty_state(
    parent,
    icon: str = "📭",
    title: str = "No Data",
    message: str = "There's nothing here yet.",
    action_text: str = None,
    action_callback=None,
) -> QWidget:
    """Create a helpful empty state widget."""
    widget = QWidget(parent)
    widget.setObjectName("empty_state")
    layout = QVBoxLayout(widget)
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.setSpacing(16)
    layout.setContentsMargins(40, 60, 40, 60)

    c = ThemeManager.get_colors()

    # Icon
    icon_label = QLabel(icon)
    icon_label.setObjectName("empty_state_icon")
    icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    icon_label.setStyleSheet(
        f"""
        font-size: 64px;
        color: {c['TEXT_DISABLED']};
        background-color: transparent;
        padding: 20px;
    """
    )
    layout.addWidget(icon_label)

    # Title
    title_label = QLabel(title)
    title_label.setObjectName("empty_state_title")
    title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    title_label.setStyleSheet(
        f"""
        font-size: 20px;
        font-weight: 700;
        color: {c['TEXT_SECONDARY']};
        letter-spacing: -0.3px;
        background-color: transparent;
        margin-top: 10px;
    """
    )
    layout.addWidget(title_label)

    # Message
    message_label = QLabel(message)
    message_label.setObjectName("empty_state_message")
    message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    message_label.setWordWrap(True)
    message_label.setStyleSheet(
        f"""
        font-size: 15px;
        color: {c['TEXT_DISABLED']};
        letter-spacing: -0.08px;
        line-height: 1.5em;
        background-color: transparent;
        margin-top: 8px;
        max-width: 400px;
    """
    )
    layout.addWidget(message_label)

    # Action button (optional)
    if action_text and action_callback:
        action_btn = QPushButton(action_text)
        action_btn.setObjectName("primary_button")
        action_btn.clicked.connect(action_callback)
        action_btn.setStyleSheet(
            """
            margin-top: 20px;
            min-width: 160px;
        """
        )
        layout.addWidget(action_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    return widget


def show_keyboard_shortcuts_help(parent):
    """Show keyboard shortcuts help dialog."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Keyboard Shortcuts")
    dialog.setMinimumSize(600, 500)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)

    # Title
    title = QLabel("⌨️ Keyboard Shortcuts")
    title_font = QFont()
    title_font.setPointSize(20)
    title_font.setBold(True)
    title.setFont(title_font)
    layout.addWidget(title)

    # Scrollable content
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("border: none; background: transparent;")

    content = QWidget()
    content_layout = QVBoxLayout(content)
    content_layout.setSpacing(12)

    shortcuts = [
        (
            "Navigation",
            [
                ("Ctrl+1", "Dashboard"),
                ("Ctrl+2", "Scraper"),
                ("Ctrl+3", "Campaigns"),
                ("Ctrl+4", "Auto Reply"),
                ("Ctrl+5", "Accounts"),
                ("Ctrl+6", "Analytics"),
                ("Ctrl+7", "Proxy Pool"),
                ("Ctrl+8", "Health"),
                ("Ctrl+9", "Logs"),
            ],
        ),
        (
            "Actions",
            [
                ("Ctrl+N", "Create New Account"),
                ("Ctrl+M", "Scrape Members"),
                ("Ctrl+Shift+C", "Create Campaign"),
                ("Ctrl+F", "Search"),
                ("Ctrl+Space", "Start/Stop Bot"),
            ],
        ),
        (
            "General",
            [
                ("Ctrl+,", "Open Settings"),
                ("Ctrl+R / F5", "Refresh Current View"),
                ("Ctrl+Q", "Quit Application"),
                ("F1", "Show This Help"),
            ],
        ),
    ]

    c = ThemeManager.get_colors()

    for category, items in shortcuts:
        # Category header
        cat_label = QLabel(category)
        cat_label.setStyleSheet(
            f"""
            font-size: 14px;
            font-weight: 600;
            color: {c['TEXT_SECONDARY']};
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 16px;
            margin-bottom: 8px;
        """
        )
        content_layout.addWidget(cat_label)

        # Shortcuts in this category
        for key, desc in items:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(16)

            key_label = QLabel(f"<b>{key}</b>")
            key_label.setStyleSheet(
                f"""
                font-size: 13px;
                color: {c['ACCENT_PRIMARY']};
                font-family: 'Courier New', monospace;
                min-width: 120px;
            """
            )
            row_layout.addWidget(key_label)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet(
                f"""
                font-size: 14px;
                color: {c['TEXT_PRIMARY']};
            """
            )
            row_layout.addWidget(desc_label)
            row_layout.addStretch()

            content_layout.addWidget(row)

    content_layout.addStretch()
    scroll.setWidget(content)
    layout.addWidget(scroll)

    # Close button
    close_btn = QPushButton("Close")
    close_btn.setObjectName("primary_button")
    close_btn.clicked.connect(dialog.accept)
    layout.addWidget(close_btn)

    dialog.exec()


def show_user_friendly_error(parent, title: str, error: str, suggestion: str = None):
    """Show user-friendly error dialog with actionable guidance."""
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setWindowTitle(title)

    error_text = f"<b>{error}</b>"
    if suggestion:
        error_text += f"<br><br><b>💡 Suggestion:</b><br>{suggestion}"

    msg.setText(error_text)
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.exec()


def show_confirmation(
    parent,
    title: str,
    message: str,
    detailed_text: str = None,
    confirm_text: str = "Yes",
    cancel_text: str = "Cancel",
) -> bool:
    """Show improved confirmation dialog."""
    msg = QMessageBox(parent)
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setWindowTitle(title)
    msg.setText(f"<b>{message}</b>")
    msg.setTextFormat(Qt.TextFormat.RichText)

    if detailed_text:
        msg.setInformativeText(detailed_text)

    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.button(QMessageBox.StandardButton.Yes).setText(confirm_text)
    msg.button(QMessageBox.StandardButton.No).setText(cancel_text)

    return msg.exec() == QMessageBox.StandardButton.Yes


def add_help_tooltip(widget: QWidget, text: str):
    """Add helpful tooltip to a widget."""
    widget.setToolTip(text)
    widget.setWhatsThis(text)  # For accessibility


def show_loading_overlay_message(parent, message: str):
    """Show loading message overlay."""
    from ui.ui_components import LoadingOverlay

    overlay = LoadingOverlay(parent, message)
    overlay.show()
    return overlay
