#!/usr/bin/env python3
"""
Notification System - REAL desktop notifications and alerts
Uses actual system tray and desktop notification APIs
"""

import logging
from typing import Optional

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

logger = logging.getLogger(__name__)


class NotificationManager(QObject):
    """Manages REAL desktop notifications."""

    notification_clicked = pyqtSignal(str)  # notification_id

    def __init__(self, app_icon_path: Optional[str] = None):
        super().__init__()
        self.app_icon_path = app_icon_path
        self.tray_icon = None
        self.notifications_enabled = True
        self.sound_enabled = False

    def initialize_tray_icon(self, main_window):
        """Initialize REAL system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray not available on this system")
            return False

        self.tray_icon = QSystemTrayIcon(main_window)

        # Set icon (use default Qt icon if custom not available)
        if self.app_icon_path:
            self.tray_icon.setIcon(QIcon(self.app_icon_path))
        else:
            # Use application icon
            self.tray_icon.setIcon(
                main_window.style().standardIcon(main_window.style().StandardPixmap.SP_ComputerIcon)
            )

        # Create REAL context menu
        menu = QMenu()

        show_action = QAction("Show Window", main_window)
        show_action.triggered.connect(main_window.show)
        menu.addAction(show_action)

        hide_action = QAction("Hide Window", main_window)
        hide_action.triggered.connect(main_window.hide)
        menu.addAction(hide_action)

        menu.addSeparator()

        pause_action = QAction("Pause All", main_window)
        if hasattr(main_window, "pause_all_operations"):
            pause_action.triggered.connect(main_window.pause_all_operations)
        menu.addAction(pause_action)

        menu.addSeparator()

        quit_action = QAction("Quit", main_window)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(quit_action)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

        logger.info("✅ System tray icon initialized")
        return True

    def show_notification(
        self, title: str, message: str, notification_type: str = "info", duration: int = 5000
    ):
        """Show REAL desktop notification."""
        if not self.notifications_enabled:
            return

        if not self.tray_icon:
            logger.warning("Tray icon not initialized, cannot show notification")
            return

        # Map notification type to icon
        icon_map = {
            "info": QSystemTrayIcon.MessageIcon.Information,
            "warning": QSystemTrayIcon.MessageIcon.Warning,
            "error": QSystemTrayIcon.MessageIcon.Critical,
            "success": QSystemTrayIcon.MessageIcon.Information,
        }

        icon = icon_map.get(notification_type, QSystemTrayIcon.MessageIcon.Information)

        # Show ACTUAL system notification
        self.tray_icon.showMessage(title, message, icon, duration)

        logger.info(f"📢 Notification: {title} - {message[:50]}...")

    def notify_account_created(self, phone_number: str):
        """Notify account creation."""
        self.show_notification(
            "Account Created", f"✅ New account created: {phone_number}", "success"
        )

    def notify_campaign_complete(self, campaign_name: str, sent: int, failed: int):
        """Notify campaign completion."""
        success_rate = (sent / max(sent + failed, 1)) * 100
        self.show_notification(
            "Campaign Complete",
            f"✅ {campaign_name}\n"
            f"Sent: {sent}, Failed: {failed}\n"
            f"Success: {success_rate:.0f}%",
            "success",
        )

    def notify_error(self, error_message: str):
        """Notify error."""
        self.show_notification("Error Occurred", f"❌ {error_message[:100]}", "error")

    def notify_warmup_complete(self, phone_number: str):
        """Notify warmup completion."""
        self.show_notification(
            "Warmup Complete",
            f"♨️ Account {phone_number} is now warmed up and ready to use!",
            "success",
        )

    def notify_rate_limit(self, wait_seconds: int):
        """Notify rate limit."""
        self.show_notification(
            "Rate Limit",
            f"⏱️ Telegram rate limit reached. Waiting {wait_seconds} seconds...",
            "warning",
        )

    def set_notifications_enabled(self, enabled: bool):
        """Enable/disable notifications."""
        self.notifications_enabled = enabled
        logger.info(f"Notifications {'enabled' if enabled else 'disabled'}")


class KeyboardShortcuts:
    """REAL keyboard shortcuts for main window."""

    @staticmethod
    def setup_shortcuts(main_window):
        """Setup REAL keyboard shortcuts."""
        from PyQt6.QtGui import QKeySequence, QShortcut

        shortcuts = []

        # Ctrl+N - New Account
        new_account = QShortcut(QKeySequence("Ctrl+N"), main_window)
        if hasattr(main_window, "open_account_creator"):
            new_account.activated.connect(main_window.open_account_creator)
        shortcuts.append(("Ctrl+N", "New Account", new_account))

        # Ctrl+M - Scrape Members
        scrape_members = QShortcut(QKeySequence("Ctrl+M"), main_window)
        if hasattr(main_window, "open_member_scraper"):
            scrape_members.activated.connect(main_window.open_member_scraper)
        shortcuts.append(("Ctrl+M", "Scrape Members", scrape_members))

        # Ctrl+C - Create Campaign
        new_campaign = QShortcut(QKeySequence("Ctrl+Shift+C"), main_window)
        if hasattr(main_window, "create_campaign"):
            new_campaign.activated.connect(main_window.create_campaign)
        shortcuts.append(("Ctrl+Shift+C", "New Campaign", new_campaign))

        # Ctrl+S - Settings
        settings = QShortcut(QKeySequence("Ctrl+,"), main_window)
        if hasattr(main_window, "open_settings"):
            settings.activated.connect(main_window.open_settings)
        shortcuts.append(("Ctrl+,", "Settings", settings))

        # Ctrl+B - Backup
        backup = QShortcut(QKeySequence("Ctrl+B"), main_window)
        if hasattr(main_window, "create_backup"):
            backup.activated.connect(main_window.create_backup)
        shortcuts.append(("Ctrl+B", "Create Backup", backup))

        # Ctrl+E - Export Data
        export = QShortcut(QKeySequence("Ctrl+E"), main_window)
        if hasattr(main_window, "export_data"):
            export.activated.connect(main_window.export_data)
        shortcuts.append(("Ctrl+E", "Export Data", export))

        # Ctrl+R - Refresh
        refresh = QShortcut(QKeySequence("Ctrl+R"), main_window)
        if hasattr(main_window, "refresh_all"):
            refresh.activated.connect(main_window.refresh_all)
        shortcuts.append(("Ctrl+R", "Refresh", refresh))

        # Ctrl+Q - Quit
        quit_app = QShortcut(QKeySequence("Ctrl+Q"), main_window)
        quit_app.activated.connect(QApplication.quit)
        shortcuts.append(("Ctrl+Q", "Quit", quit_app))

        # F1 - Help
        help_shortcut = QShortcut(QKeySequence("F1"), main_window)
        if hasattr(main_window, "show_help"):
            help_shortcut.activated.connect(main_window.show_help)
        shortcuts.append(("F1", "Help", help_shortcut))

        # F5 - Refresh Dashboard
        refresh_dash = QShortcut(QKeySequence("F5"), main_window)
        if hasattr(main_window, "refresh_dashboard"):
            refresh_dash.activated.connect(main_window.refresh_dashboard)
        shortcuts.append(("F5", "Refresh Dashboard", refresh_dash))

        logger.info(f"✅ Configured {len(shortcuts)} REAL keyboard shortcuts")

        return shortcuts


def show_shortcuts_help(parent=None):
    """Show REAL keyboard shortcuts help."""
    from PyQt6.QtWidgets import QMessageBox

    shortcuts_text = """
<h3>⌨️ Keyboard Shortcuts</h3>
<br>
<table>
<tr><td><b>Ctrl+N</b></td><td>Create New Account</td></tr>
<tr><td><b>Ctrl+M</b></td><td>Scrape Members</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>Create Campaign</td></tr>
<tr><td><b>Ctrl+,</b></td><td>Open Settings</td></tr>
<tr><td><b>Ctrl+B</b></td><td>Create Backup</td></tr>
<tr><td><b>Ctrl+E</b></td><td>Export Data</td></tr>
<tr><td><b>Ctrl+R</b></td><td>Refresh</td></tr>
<tr><td><b>Ctrl+Q</b></td><td>Quit Application</td></tr>
<tr><td><b>F1</b></td><td>Show Help</td></tr>
<tr><td><b>F5</b></td><td>Refresh Dashboard</td></tr>
</table>
    """

    msg = QMessageBox(parent)
    msg.setWindowTitle("Keyboard Shortcuts")
    msg.setText(shortcuts_text)
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.exec()
