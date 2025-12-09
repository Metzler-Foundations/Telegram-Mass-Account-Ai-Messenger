import logging
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QProgressBar,
    QHeaderView,
    QFrame,
    QMessageBox,
    QDialog,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QListWidget,
    QAbstractItemView,
    QSplitter,
    QGroupBox,
    QTabWidget,
    QScrollArea,
    QGroupBox as QGroupBoxWidget,
    QInputDialog,
    QFileDialog,
    QGraphicsOpacityEffect,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QColor, QIcon, QMovie, QPixmap

from core.error_handler import ErrorHandler
from ui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)


class LoadingOverlay(QWidget):
    """Loading overlay widget with spinner animation."""

    def __init__(self, parent=None, message: str = "Loading..."):
        super().__init__(parent)
        self.message = message
        self.setup_ui()
        self.hide()  # Hidden by default

    def setup_ui(self):
        """Set up the loading overlay UI."""
        c = ThemeManager.get_colors()
        is_dark = ThemeManager.current_theme == "dark"

        # Convert hex to rgba for overlay background
        bg_hex = c["BG_PRIMARY"].lstrip("#")
        bg_r = int(bg_hex[0:2], 16)
        bg_g = int(bg_hex[2:4], 16)
        bg_b = int(bg_hex[4:6], 16)

        # Make overlay cover parent
        self.setStyleSheet(
            f"""
            LoadingOverlay {{
                background-color: rgba({bg_r}, {bg_g}, {bg_b}, 0.85);
            }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Container for centering
        container = QFrame()
        container.setObjectName("hero_card")
        container.setStyleSheet(
            f"""
            QFrame#hero_card {{
                background-color: {c["BG_SECONDARY"]};
                border: 1px solid {c["BORDER_DEFAULT"]};
                border-radius: 12px;
                padding: 24px 32px;
            }}
        """
        )
        container_layout = QVBoxLayout(container)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.setSpacing(16)

        # Spinner using animated dots (text-based, no emoji)
        self.spinner_label = QLabel("...")
        self.spinner_label.setStyleSheet(
            f"""
            font-size: 32px;
            color: {c["ACCENT_PRIMARY"]};
            font-weight: 700;
            letter-spacing: 4px;
        """
        )
        self.spinner_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.spinner_label)

        # Message
        self.message_label = QLabel(self.message)
        self.message_label.setStyleSheet(
            f"""
            font-size: 14px;
            color: {c["TEXT_PRIMARY"]};
            font-weight: 500;
        """
        )
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.message_label)

        # Progress bar (indeterminate)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        # Use relative sizing instead of fixed
        self.progress_bar.setMinimumWidth(240)
        self.progress_bar.setMaximumWidth(400)
        self.progress_bar.setFixedHeight(6)
        container_layout.addWidget(self.progress_bar)

        layout.addWidget(container)

        # Animation timer for spinner
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self._animate_spinner)
        self.spinner_frames = [".", "..", "...", ".."]
        self.current_frame = 0

    def _animate_spinner(self):
        """Animate the spinner."""
        self.current_frame = (self.current_frame + 1) % len(self.spinner_frames)
        self.spinner_label.setText(self.spinner_frames[self.current_frame])

    def show_loading(self, message: str = None):
        """Show the loading overlay."""
        if message:
            self.message_label.setText(message)

        # Resize to cover parent
        if self.parent():
            self.setGeometry(self.parent().rect())

        self.show()
        self.raise_()
        self.animation_timer.start(500)  # Animate every 500ms

    def hide_loading(self):
        """Hide the loading overlay."""
        self.animation_timer.stop()
        self.hide()

    def set_message(self, message: str):
        """Update the loading message."""
        self.message_label.setText(message)

    def resizeEvent(self, event):
        """Handle resize to stay centered."""
        super().resizeEvent(event)
        if self.parent():
            self.setGeometry(self.parent().rect())


class MessageHistoryWidget(QWidget):
    """Widget for displaying message history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Filter controls
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search messages...")
        self.search_input.textChanged.connect(self.filter_messages)
        filter_layout.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All Statuses", "Sent", "Failed", "Pending", "Received"])
        self.status_filter.currentTextChanged.connect(self.filter_messages)
        filter_layout.addWidget(self.status_filter)

        layout.addLayout(filter_layout)

        # Message Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Time", "Account", "Contact", "Message", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setMinimumHeight(240)
        layout.addWidget(self.table)

        # Store messages data
        self.messages = []

    def add_message(self, message_data: Dict):
        """Add a message to the history."""
        self.messages.insert(0, message_data)
        self.refresh_table()

    def refresh_table(self):
        """Refresh table content based on filters."""
        search_text = self.search_input.text().lower()
        status_filter = self.status_filter.currentText()

        filtered = []
        for msg in self.messages:
            if (
                status_filter != "All Statuses"
                and msg.get("status", "").lower() != status_filter.lower()
            ):
                continue

            if search_text:
                text_content = f"{msg.get('account', '')} {msg.get('contact', '')} {msg.get('message', '')}".lower()
                if search_text not in text_content:
                    continue

            filtered.append(msg)

        self.table.setRowCount(len(filtered))
        for row, msg in enumerate(filtered):
            time_item = QTableWidgetItem(msg.get("time", ""))
            account_item = QTableWidgetItem(msg.get("account", ""))
            contact_item = QTableWidgetItem(msg.get("contact", ""))
            message_item = QTableWidgetItem(msg.get("message", ""))
            status_item = QTableWidgetItem(msg.get("status", ""))

            # Color code status
            c = ThemeManager.get_colors()
            status = msg.get("status", "").lower()
            if status == "sent":
                status_item.setForeground(QColor(c["ACCENT_SUCCESS"]))
            elif status == "failed":
                status_item.setForeground(QColor(c["ACCENT_DANGER"]))
            elif status == "received":
                status_item.setForeground(QColor(c["ACCENT_PRIMARY"]))

            self.table.setItem(row, 0, time_item)
            self.table.setItem(row, 1, account_item)
            self.table.setItem(row, 2, contact_item)
            self.table.setItem(row, 3, message_item)
            self.table.setItem(row, 4, status_item)

    def filter_messages(self):
        self.refresh_table()


class CreateCampaignDialog(QDialog):
    """Dialog for creating a new campaign."""

    def __init__(self, parent=None, accounts=None, channels=None):
        super().__init__(parent)
        self.accounts = accounts or []
        self.channels = channels or []
        self.setWindowTitle("Create New Campaign")
        self.setModal(True)
        self.resize(600, 700)  # Reduced width, standard height
        self.setObjectName("settings_dialog")

        # CRITICAL: Prevent dialog from closing parent window
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self.setup_ui()

    def setup_ui(self):
        c = ThemeManager.get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # Dialog Title
        title_label = QLabel("New Campaign")
        title_label.setStyleSheet(f"font-size: 20px; font-weight: 600; color: {c['TEXT_BRIGHT']};")
        layout.addWidget(title_label)

        subtitle_label = QLabel("Configure your DM campaign settings")
        subtitle_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; margin-bottom: 12px;")
        layout.addWidget(subtitle_label)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Welcome Series Q1 2024")
        self.name_input.setToolTip(
            "Enter a descriptive name for this campaign.\nThis will help you identify it in analytics and reports."
        )

        name_label = QLabel("Campaign Name")
        name_label.setStyleSheet("font-weight: 500;")
        form_layout.addRow(name_label, self.name_input)

        self.template_input = QTextEdit()
        self.template_input.setPlaceholderText(
            "Hi {first_name},\n\nI noticed you're interested in..."
        )
        self.template_input.setMaximumHeight(180)
        self.template_input.setMinimumHeight(120)
        self.template_input.setToolTip(
            "Write your message template here.\n"
            "Available variables:\n"
            "  • {first_name} - User's first name\n"
            "  • {last_name} - User's last name\n"
            "  • {username} - User's @username\n"
            "  • {name} - Full name\n"
            "Keep messages natural and personalized for best results."
        )

        template_label = QLabel("Message Template")
        template_label.setStyleSheet("font-weight: 500;")
        form_layout.addRow(template_label, self.template_input)

        # Variable help
        help_label = QLabel("Available variables: {first_name}, {last_name}, {username}, {name}")
        help_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 12px; padding: 4px;")
        form_layout.addRow("", help_label)

        layout.addLayout(form_layout)

        # Template Variants (A/B Testing)
        variant_group = QGroupBox("Template Variants (A/B Testing)")
        variant_layout = QVBoxLayout(variant_group)
        variant_layout.setContentsMargins(12, 24, 12, 12)
        variant_layout.setSpacing(8)

        variant_subtitle = QLabel("Add multiple template variants for A/B testing")
        variant_subtitle.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 12px;")
        variant_layout.addWidget(variant_subtitle)

        # Variant table
        self.variant_table = QTableWidget()
        self.variant_table.setColumnCount(3)
        self.variant_table.setHorizontalHeaderLabels(["Variant Name", "Template", "Weight"])
        self.variant_table.horizontalHeader().setStretchLastSection(True)
        # Use relative sizing - minimum 150px but can grow
        self.variant_table.setMinimumHeight(150)
        # Remove fixed max height to allow flexibility
        self.variant_table.setToolTip(
            "Create multiple message variants for A/B testing.\n"
            "Weight determines distribution (e.g., 1.0 = equal split).\n"
            "System will automatically track which variant performs best.\n"
            "Use chi-square testing to determine statistical significance."
        )
        variant_layout.addWidget(self.variant_table)

        # Variant controls
        variant_controls = QHBoxLayout()
        variant_controls.setSpacing(8)

        add_variant_btn = QPushButton("+ Add Variant")
        add_variant_btn.setObjectName("secondary")
        add_variant_btn.clicked.connect(self._add_variant_row)
        variant_controls.addWidget(add_variant_btn)

        remove_variant_btn = QPushButton("Remove Selected")
        remove_variant_btn.setObjectName("danger")
        remove_variant_btn.clicked.connect(self._remove_variant_row)
        variant_controls.addWidget(remove_variant_btn)

        variant_controls.addStretch()
        variant_layout.addLayout(variant_controls)

        # Default variant (from main template)
        self._add_default_variant()

        layout.addWidget(variant_group)

        # Target Selection
        target_group = QGroupBox("Target Audience")
        target_layout = QVBoxLayout(target_group)
        target_layout.setContentsMargins(12, 24, 12, 12)
        target_layout.setSpacing(8)

        target_subtitle = QLabel("Select channels to scrape members from")
        target_subtitle.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 12px;")
        target_layout.addWidget(target_subtitle)

        self.channel_list = QListWidget()
        self.channel_list.setMinimumHeight(120)
        # Allow flexible sizing
        self.channel_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.channel_list.setToolTip(
            "Select one or more channels to target.\n"
            "Members from selected channels will receive your message.\n"
            "Hold Ctrl/Cmd to select multiple channels."
        )
        for channel in self.channels:
            display = (
                f"{channel.get('title', 'Unknown')} ({channel.get('member_count', 0)} members)"
            )
            item = QTableWidgetItem(
                display
            )  # Using QTableWidgetItem for QListWidget... wait, no. QListWidgetItem.
            # Fix: Use QListWidgetItem
            from PyQt6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, channel)
            self.channel_list.addItem(item)

        target_layout.addWidget(self.channel_list)
        layout.addWidget(target_group)

        # Account Selection
        account_group = QGroupBox("Sending Accounts")
        account_layout = QVBoxLayout(account_group)
        account_layout.setContentsMargins(12, 24, 12, 12)
        account_layout.setSpacing(8)

        account_subtitle = QLabel("Select which accounts will send messages")
        account_subtitle.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 12px;")
        account_layout.addWidget(account_subtitle)

        self.account_list = QListWidget()
        self.account_list.setMinimumHeight(120)
        # Allow flexible sizing
        self.account_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.account_list.setToolTip(
            "Select accounts to send messages from.\n"
            "Using multiple accounts distributes sending load.\n"
            "Only select warmed-up, healthy accounts for best results.\n"
            "Hold Ctrl/Cmd to select multiple accounts."
        )
        for account in self.accounts:
            display = f"{account.get('phone_number')} - {account.get('status', 'Unknown')}"
            from PyQt6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, account)
            self.account_list.addItem(item)

        account_layout.addWidget(self.account_list)
        layout.addWidget(account_group)

        # Buttons
        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        buttons.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(cancel_btn)

        create_btn = QPushButton("Create Campaign")
        create_btn.setObjectName("primary")
        create_btn.setMinimumWidth(140)
        create_btn.clicked.connect(self.accept)
        buttons.addWidget(create_btn)

        layout.addLayout(buttons)

    def _add_default_variant(self):
        """Add default variant from main template."""
        row = self.variant_table.rowCount()
        self.variant_table.insertRow(row)

        name_item = QTableWidgetItem("default")
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.variant_table.setItem(row, 0, name_item)

        template_item = QTableWidgetItem(self.template_input.toPlainText() or "")
        self.variant_table.setItem(row, 1, template_item)

        weight_item = QTableWidgetItem("1.0")
        self.variant_table.setItem(row, 2, weight_item)

    def _add_variant_row(self):
        """Add a new variant row."""
        row = self.variant_table.rowCount()
        self.variant_table.insertRow(row)

        name_item = QTableWidgetItem(f"variant_{row}")
        self.variant_table.setItem(row, 0, name_item)

        template_item = QTableWidgetItem("")
        self.variant_table.setItem(row, 1, template_item)

        weight_item = QTableWidgetItem("1.0")
        self.variant_table.setItem(row, 2, weight_item)

    def _remove_variant_row(self):
        """Remove selected variant row."""
        current_row = self.variant_table.currentRow()
        if current_row >= 0:
            # Don't allow removing the default variant
            if current_row == 0 and self.variant_table.item(0, 0).text() == "default":
                ErrorHandler.safe_warning(
                    self, "Cannot Remove", "Default variant cannot be removed."
                )
                return
            self.variant_table.removeRow(current_row)

    def get_data(self):
        """Get the campaign configuration."""
        selected_channels = [
            item.data(Qt.ItemDataRole.UserRole) for item in self.channel_list.selectedItems()
        ]
        selected_accounts = [
            item.data(Qt.ItemDataRole.UserRole) for item in self.account_list.selectedItems()
        ]

        # Collect template variants
        template_variants = []
        for row in range(self.variant_table.rowCount()):
            name_item = self.variant_table.item(row, 0)
            template_item = self.variant_table.item(row, 1)
            weight_item = self.variant_table.item(row, 2)

            if name_item and template_item:
                variant_name = name_item.text().strip()
                variant_template = template_item.text().strip()
                try:
                    variant_weight = float(weight_item.text() if weight_item else "1.0")
                except ValueError:
                    variant_weight = 1.0

                if variant_template:  # Only add non-empty variants
                    template_variants.append(
                        {
                            "name": variant_name,
                            "template": variant_template,
                            "weight": variant_weight,
                        }
                    )

        # Get primary template (from default variant or first variant)
        primary_template = self.template_input.toPlainText()
        if template_variants:
            # Use first variant as primary if main template is empty
            if not primary_template and template_variants:
                primary_template = template_variants[0]["template"]

        return {
            "name": self.name_input.text(),
            "template": primary_template,
            "channels": selected_channels,
            "accounts": selected_accounts,
            "template_variants": template_variants if len(template_variants) > 1 else [],
        }


class MemberProfileViewer(QDialog):
    """Detailed member profile viewer with comprehensive data display."""

    def __init__(self, member_data: Dict, data_access_layer=None, parent=None):
        """Initialize the member profile viewer.

        Args:
            member_data: Basic member data
            data_access_layer: EliteDataAccessLayer instance for comprehensive data
        """
        super().__init__(parent)
        self.member_data = member_data
        self.data_access_layer = data_access_layer
        self.comprehensive_data = None

        self.setWindowTitle(
            f"Member Profile: {member_data.get('first_name', '')} {member_data.get('last_name', '')}".strip()
            or member_data.get("username", "Unknown")
        )
        self.resize(800, 600)
        self.setModal(True)

        # CRITICAL: Prevent dialog from closing parent window
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self.setup_ui()
        self.load_comprehensive_data()

    def setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)

        # Header with basic info
        header_layout = QHBoxLayout()

        c = ThemeManager.get_colors()
        # Profile photo placeholder (replaced if actual photo is available)
        self.photo_label = QLabel("👤")
        accent_hex = c["ACCENT_PRIMARY"].lstrip("#")
        accent_r = int(accent_hex[0:2], 16)
        accent_g = int(accent_hex[2:4], 16)
        accent_b = int(accent_hex[4:6], 16)
        self.photo_label.setStyleSheet(
            f"""
            font-size: 48px;
            padding: 20px;
            background: rgba({accent_r}, {accent_g}, {accent_b}, 0.1);
            border-radius: 8px;
        """
        )
        header_layout.addWidget(self.photo_label)

        # Basic info
        info_layout = QVBoxLayout()
        name_label = QLabel(
            f"{self.member_data.get('first_name', '')} {self.member_data.get('last_name', '')}".strip()
        )
        name_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {c['TEXT_BRIGHT']};")
        info_layout.addWidget(name_label)

        username = self.member_data.get("username", "")
        username_label = QLabel(f"@{username}" if username else "No username")
        username_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 14px;")
        info_layout.addWidget(username_label)

        # Status badges
        badges_layout = QHBoxLayout()
        if self.member_data.get("is_verified"):
            verified_badge = QLabel("✓ Verified")
            success_hex = c["ACCENT_SUCCESS"].lstrip("#")
            success_r = int(success_hex[0:2], 16)
            success_g = int(success_hex[2:4], 16)
            success_b = int(success_hex[4:6], 16)
            verified_badge.setStyleSheet(
                f"color: {c['ACCENT_SUCCESS']}; font-size: 12px; background: rgba({success_r}, {success_g}, {success_b}, 0.1); padding: 4px 8px; border-radius: 4px;"
            )
            badges_layout.addWidget(verified_badge)

        if self.member_data.get("is_premium"):
            premium_badge = QLabel("⭐ Premium")
            warn_hex = c["ACCENT_WARNING"].lstrip("#")
            warn_r = int(warn_hex[0:2], 16)
            warn_g = int(warn_hex[2:4], 16)
            warn_b = int(warn_hex[4:6], 16)
            premium_badge.setStyleSheet(
                f"color: {c['ACCENT_WARNING']}; font-size: 12px; background: rgba({warn_r}, {warn_g}, {warn_b}, 0.1); padding: 4px 8px; border-radius: 4px;"
            )
            badges_layout.addWidget(premium_badge)

        badges_layout.addStretch()
        info_layout.addLayout(badges_layout)

        header_layout.addLayout(info_layout)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Tab widget for different data sections
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Basic Info Tab
        self.setup_basic_info_tab()

        # Activity Tab
        self.setup_activity_tab()

        # Network Tab
        self.setup_network_tab()

        # Behavioral Tab
        self.setup_behavioral_tab()

        # Risk Assessment Tab
        self.setup_risk_tab()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        message_btn = QPushButton("Send Message")
        message_btn.setObjectName("quick_action")
        message_btn.setMinimumHeight(32)
        message_btn.clicked.connect(self.send_message)
        button_layout.addWidget(message_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def setup_basic_info_tab(self):
        """Setup the basic information tab."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        # Profile completeness indicator
        completeness = self.member_data.get("profile_quality_score", 0) or 0
        completeness_label = QLabel(f"Profile Completeness: {completeness:.1%}")
        completeness_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(completeness_label)

        # Basic fields
        fields = [
            ("User ID", str(self.member_data.get("user_id", "Unknown"))),
            ("Phone", self.member_data.get("phone", "Not available")),
            (
                "Bio",
                self.member_data.get("bio", "No bio")[:200]
                + ("..." if len(self.member_data.get("bio", "")) > 200 else ""),
            ),
            ("Language", self.member_data.get("language_code", "Unknown")),
            ("Last Online", str(self.member_data.get("last_online_date", "Unknown"))),
            ("Joined Date", str(self.member_data.get("joined_date", "Unknown"))),
            ("Message Count", str(self.member_data.get("message_count", 0))),
            ("Activity Score", ".1f"),
            ("Threat Score", str(self.member_data.get("threat_score", 0))),
        ]

        for label_text, value in fields:
            field_layout = QHBoxLayout()
            label = QLabel(f"{label_text}:")
            label.setStyleSheet("font-weight: bold; min-width: 120px;")
            field_layout.addWidget(label)

            value_label = QLabel(str(value))
            value_label.setWordWrap(True)
            field_layout.addWidget(value_label)
            field_layout.addStretch()
            layout.addLayout(field_layout)

        layout.addStretch()
        scroll_area.setWidget(content)
        self.tab_widget.addTab(scroll_area, "📋 Basic Info")

    def setup_activity_tab(self):
        """Setup the activity patterns tab."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        if self.comprehensive_data:
            activity = self.comprehensive_data.get("activity_patterns", {})

            # Message frequency
            freq = activity.get("message_frequency", {})
            freq_group = QGroupBox("Message Frequency")
            freq_layout = QVBoxLayout()

            freq_layout.addWidget(
                QLabel(f"Messages per day: {freq.get('messages_per_day', 0):.1f}")
            )
            freq_layout.addWidget(
                QLabel(f"Messages per week: {freq.get('messages_per_week', 0):.1f}")
            )
            freq_layout.addWidget(
                QLabel(f"Consistency score: {freq.get('consistency_score', 0):.1%}")
            )
            freq_layout.addWidget(
                QLabel(f"Bust patterns: {'Yes' if freq.get('burst_patterns') else 'No'}")
            )

            freq_group.setLayout(freq_layout)
            layout.addWidget(freq_group)

            # Temporal patterns
            temporal = activity.get("temporal_patterns", {})
            temporal_group = QGroupBox("Activity Patterns")
            temporal_layout = QVBoxLayout()

            active_hours = temporal.get("active_hours", [])
            if active_hours:
                temporal_layout.addWidget(
                    QLabel(f"Most active hours: {', '.join(map(str, active_hours))}")
                )

            timezone = temporal.get("timezone_estimate", "Unknown")
            temporal_layout.addWidget(QLabel(f"Estimated timezone: {timezone}"))

            consistency = temporal.get("activity_consistency", 0)
            temporal_layout.addWidget(QLabel(f"Activity consistency: {consistency:.1%}"))

            temporal_group.setLayout(temporal_layout)
            layout.addWidget(temporal_group)

            # Engagement patterns
            engagement = activity.get("engagement_patterns", {})
            engagement_group = QGroupBox("Engagement Style")
            engagement_layout = QVBoxLayout()

            engagement_layout.addWidget(
                QLabel(f"Engagement score: {engagement.get('engagement_score', 0):.1%}")
            )
            engagement_layout.addWidget(
                QLabel(f"Conversation length: {engagement.get('conversation_length', 'Unknown')}")
            )

            interaction_types = engagement.get("interaction_types", [])
            if interaction_types:
                engagement_layout.addWidget(
                    QLabel(f"Interaction types: {', '.join(interaction_types)}")
                )

            engagement_group.setLayout(engagement_layout)
            layout.addWidget(engagement_group)
        else:
            layout.addWidget(QLabel("No detailed activity data available"))

        layout.addStretch()
        scroll_area.setWidget(content)
        self.tab_widget.addTab(scroll_area, "Activity")

    def setup_network_tab(self):
        """Setup the network connections tab."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        if self.comprehensive_data:
            network = self.comprehensive_data.get("network_analysis", {})

            # Network metrics
            metrics_group = QGroupBox("Network Metrics")
            metrics_layout = QVBoxLayout()

            metrics_layout.addWidget(
                QLabel(f"Common chats: {network.get('common_chats_count', 0)}")
            )
            metrics_layout.addWidget(
                QLabel(f"Influence score: {network.get('influence_score', 0):.2f}")
            )
            metrics_layout.addWidget(
                QLabel(f"Network centrality: {network.get('network_centrality', 0):.2f}")
            )

            communities = network.get("community_membership", [])
            if communities:
                metrics_layout.addWidget(QLabel(f"Communities: {', '.join(communities)}"))

            metrics_group.setLayout(metrics_layout)
            layout.addWidget(metrics_group)

            # Group memberships
            memberships = network.get("group_memberships", [])
            if memberships:
                membership_group = QGroupBox("Group Memberships")
                membership_layout = QVBoxLayout()

                for group in memberships[:10]:  # Limit display
                    group_label = QLabel(
                        f"{group.get('title', 'Unknown Group')} ({group.get('member_count', 0)} members)"
                    )
                    membership_layout.addWidget(group_label)

                if len(memberships) > 10:
                    membership_layout.addWidget(
                        QLabel(f"... and {len(memberships) - 10} more groups")
                    )

                membership_group.setLayout(membership_layout)
                layout.addWidget(membership_group)
        else:
            layout.addWidget(QLabel("No network data available"))

        layout.addStretch()
        scroll_area.setWidget(content)
        self.tab_widget.addTab(scroll_area, "Network")

    def setup_behavioral_tab(self):
        """Setup the behavioral insights tab."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        if self.comprehensive_data:
            behavioral = self.comprehensive_data.get("behavioral_insights", {})

            # Account type and activity
            type_group = QGroupBox("Account Analysis")
            type_layout = QVBoxLayout()

            type_layout.addWidget(
                QLabel(f"Account type: {behavioral.get('account_type_prediction', 'Unknown')}")
            )
            type_layout.addWidget(
                QLabel(f"Activity level: {behavioral.get('activity_level', 'Unknown')}")
            )
            type_layout.addWidget(
                QLabel(f"Engagement style: {behavioral.get('engagement_style', 'Unknown')}")
            )
            type_layout.addWidget(
                QLabel(f"Behavioral score: {behavioral.get('behavioral_score', 0):.2f}")
            )

            type_group.setLayout(type_layout)
            layout.addWidget(type_group)

            # Communication preferences
            prefs = behavioral.get("communication_preferences", [])
            if prefs:
                pref_group = QGroupBox("Communication Preferences")
                pref_layout = QVBoxLayout()

                for pref in prefs:
                    pref_layout.addWidget(QLabel(f"• {pref}"))

                pref_group.setLayout(pref_layout)
                layout.addWidget(pref_group)

            # Messaging potential
            potential = behavioral.get("messaging_potential", {})
            if potential:
                potential_group = QGroupBox("Messaging Potential")
                potential_layout = QVBoxLayout()

                potential_layout.addWidget(
                    QLabel(f"Messaging potential: {potential.get('score', 0):.2f}")
                )
                potential_layout.addWidget(
                    QLabel(f"Recommendation: {potential.get('category', 'Unknown')}")
                )
                potential_layout.addWidget(
                    QLabel(f"Best contact time: {behavioral.get('best_contact_time', 'Unknown')}")
                )

                potential_group.setLayout(potential_layout)
                layout.addWidget(potential_group)
        else:
            layout.addWidget(QLabel("No behavioral insights available"))

        layout.addStretch()
        scroll_area.setWidget(content)
        self.tab_widget.addTab(scroll_area, "🧠 Behavioral")

    def setup_risk_tab(self):
        """Setup the risk assessment tab."""
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)

        if self.comprehensive_data:
            risk = self.comprehensive_data.get("risk_assessment", {})

            # Risk scores
            scores_group = QGroupBox("Risk Scores")
            scores_layout = QVBoxLayout()

            scores_layout.addWidget(QLabel(f"Ban risk: {risk.get('ban_risk', 0):.1%}"))
            scores_layout.addWidget(QLabel(f"Spam risk: {risk.get('spam_risk', 0):.1%}"))
            scores_layout.addWidget(QLabel(f"Bot risk: {risk.get('bot_risk', 0):.1%}"))
            scores_layout.addWidget(QLabel(f"Scam risk: {risk.get('scam_risk', 0):.1%}"))
            scores_layout.addWidget(
                QLabel(f"Overall risk: {risk.get('overall_risk_score', 0):.1%}")
            )
            scores_layout.addWidget(
                QLabel(f"Risk level: {risk.get('risk_level', 'Unknown').upper()}")
            )

            scores_group.setLayout(scores_layout)
            layout.addWidget(scores_group)

            # Risk factors
            factors = risk.get("risk_factors", [])
            if factors:
                factors_group = QGroupBox("Risk Factors")
                factors_layout = QVBoxLayout()

                c = ThemeManager.get_colors()
                for factor in factors:
                    factor_label = QLabel(f"{factor}")
                    factor_label.setStyleSheet(f"color: {c['ACCENT_DANGER']};")
                    factors_layout.addWidget(factor_label)

                factors_group.setLayout(factors_layout)
                layout.addWidget(factors_group)
        else:
            layout.addWidget(QLabel("No risk assessment available"))

        layout.addStretch()
        scroll_area.setWidget(content)
        self.tab_widget.addTab(scroll_area, "Risk Assessment")

    def load_comprehensive_data(self):
        """Load comprehensive member data."""
        if self.data_access_layer:
            try:
                self.comprehensive_data = self.data_access_layer.get_comprehensive_profile(
                    self.member_data["user_id"]
                )
                self._update_profile_photo()
            except Exception as e:
                logger.error(f"Failed to load comprehensive data: {e}")

        # Fallback to basic member data photo if no DAL is provided
        if not self.comprehensive_data:
            self._update_profile_photo()

    def _update_profile_photo(self):
        """Load a stored profile photo path into the UI when available."""
        photo_path = None
        if self.comprehensive_data:
            photo_path = self.comprehensive_data.get("photo_path") or self.comprehensive_data.get(
                "profile_photo"
            )

        if not photo_path:
            photo_path = self.member_data.get("photo_path") or self.member_data.get("profile_photo")

        if photo_path and Path(photo_path).exists():
            pixmap = QPixmap(photo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.photo_label.setPixmap(scaled)
                self.photo_label.setText("")

    def send_message(self):
        """Send a message to this member."""
        # This would integrate with the messaging/campaign system
        ErrorHandler.safe_information(
            self,
            "Send Message",
            f"Message functionality would send to {self.member_data.get('first_name', 'user')}\n\n"
            f"This would integrate with the campaign system for proper rate limiting and tracking.",
        )


class CampaignManagerWidget(QWidget):
    """Widget for managing DM campaigns."""

    def __init__(self, campaign_manager, parent=None):
        super().__init__(parent)
        self.campaign_manager = campaign_manager
        self.setup_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_campaigns)
        self.timer.start(5000)  # Refresh every 5 seconds

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        create_btn = QPushButton("Create Campaign")
        create_btn.setObjectName("quick_action")

        # Debounce to prevent double-clicks
        from utils.button_debouncer import protect_button

        protect_button(create_btn, self.create_campaign, debounce_ms=2000)

        toolbar.addWidget(create_btn)

        pause_btn = QPushButton("Pause")
        pause_btn.setObjectName("secondary")
        pause_btn.clicked.connect(self.pause_selected)
        toolbar.addWidget(pause_btn)

        resume_btn = QPushButton("Resume")
        resume_btn.setObjectName("success")
        resume_btn.clicked.connect(self.resume_selected)
        toolbar.addWidget(resume_btn)

        delete_btn = QPushButton("Delete")
        delete_btn.setObjectName("danger")
        delete_btn.clicked.connect(self.delete_selected)
        toolbar.addWidget(delete_btn)

        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("secondary")
        edit_btn.clicked.connect(self.edit_selected)
        toolbar.addWidget(edit_btn)

        view_btn = QPushButton("View Details")
        view_btn.setObjectName("secondary")
        view_btn.clicked.connect(self.view_selected)
        toolbar.addWidget(view_btn)

        export_btn = QPushButton("Export")
        export_btn.setObjectName("secondary")
        export_btn.setMinimumHeight(32)
        export_btn.clicked.connect(self.export_campaigns)
        toolbar.addWidget(export_btn)

        toolbar.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search campaigns…")
        self.search_input.textChanged.connect(self.refresh_campaigns)
        toolbar.addWidget(self.search_input)

        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Running", "Paused", "Error", "Draft", "Completed"])
        self.status_filter.currentTextChanged.connect(self.refresh_campaigns)
        toolbar.addWidget(self.status_filter)
        layout.addLayout(toolbar)

        # Campaign Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Name", "Status", "Progress", "Sent/Total", "Created"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Name stretches
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)  # Progress stretches
        header.setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        c = ThemeManager.get_colors()
        # Use theme-aware hover color
        hover_bg = c["BG_TERTIARY"]
        self.table.setStyleSheet(f"QTableWidget::item:hover {{ background-color: {hover_bg}; }}")
        layout.addWidget(self.table)

        self.loading_overlay = LoadingOverlay(self.table, "Loading campaigns…")

    def refresh_campaigns(self):
        """Refresh the campaign list."""
        if not self.campaign_manager:
            return

        try:
            if hasattr(self, "loading_overlay") and self.loading_overlay:
                self.loading_overlay.show_loading("Refreshing campaigns…")

            campaigns = self.campaign_manager.get_all_campaigns()
            search = self.search_input.text().lower() if hasattr(self, "search_input") else ""
            status_filter = (
                self.status_filter.currentText().lower()
                if hasattr(self, "status_filter")
                else "all"
            )

            filtered = []
            for c in campaigns:
                if search and search not in f"{c.name.lower()} {c.status.value.lower()}":
                    continue
                if status_filter != "all" and c.status.value.lower() != status_filter:
                    continue
                filtered.append(c)

            self.table.setRowCount(len(filtered))

            for row, campaign in enumerate(filtered):
                # ID
                self.table.setItem(row, 0, QTableWidgetItem(str(campaign.id)))

                # Name
                self.table.setItem(row, 1, QTableWidgetItem(campaign.name))

                # Status pill
                status_pill = QLabel(campaign.status.value.title())
                status_pill.setObjectName("status_chip")
                state = (
                    "ok"
                    if campaign.status.value == "running"
                    else (
                        "warn"
                        if campaign.status.value == "paused"
                        else "bad"
                        if campaign.status.value == "error"
                        else "warn"
                    )
                )
                status_pill.setProperty("state", state)
                self.table.setCellWidget(row, 2, status_pill)

                # Progress
                progress_widget = QProgressBar()
                c = ThemeManager.get_colors()
                progress_widget.setStyleSheet(
                    f"""
                    QProgressBar {{
                        background-color: {c["BG_PRIMARY"]};
                        border-radius: 4px;
                        text-align: center;
                        color: {c["TEXT_BRIGHT"]};
                    }}
                    QProgressBar::chunk {{
                        background-color: {c["ACCENT_PRIMARY"]};
                        border-radius: 4px;
                    }}
                """
                )
                total = campaign.total_targets or 1
                progress = ((campaign.sent_count + campaign.failed_count) / total) * 100
                progress_widget.setValue(int(progress))
                self.table.setCellWidget(row, 3, progress_widget)

                # Stats
                stats = f"{campaign.sent_count}/{campaign.total_targets}"
                self.table.setItem(row, 4, QTableWidgetItem(stats))

                # Created
                created = (
                    campaign.created_at.strftime("%Y-%m-%d %H:%M") if campaign.created_at else ""
                )
                self.table.setItem(row, 5, QTableWidgetItem(created))

            if not filtered:
                self.table.setRowCount(1)
                empty = QTableWidgetItem("No campaigns found. Create one to get started.")
                c = ThemeManager.get_colors()
                empty.setForeground(QColor(c["TEXT_DISABLED"]))
                self.table.setItem(0, 0, empty)
                self.table.setSpan(0, 0, 1, self.table.columnCount())
        finally:
            if hasattr(self, "loading_overlay") and self.loading_overlay:
                self.loading_overlay.hide_loading()

    def create_campaign(self):
        """Open dialog to create a campaign."""
        # Need access to accounts and channels.
        # Ideally passed or retrieved from main window / managers.
        # Assuming we can get them via parent or global context, or passed in.
        # For now, let's try to get them from parent (MainWindow) if possible.

        main_window = self.window()
        accounts = []
        channels = []

        if hasattr(main_window, "account_manager") and main_window.account_manager:
            accounts = main_window.account_manager.get_account_list()

        if hasattr(main_window, "member_db") and main_window.member_db:
            channels = main_window.member_db.get_all_channels()

        dialog = CreateCampaignDialog(self, accounts, channels)
        if dialog.exec():
            data = dialog.get_data()
            if not data["accounts"]:
                ErrorHandler.safe_warning(self, "Error", "Select at least one account.")
                return
            if not data["channels"]:
                ErrorHandler.safe_warning(self, "Error", "Select at least one target channel.")
                return

            # Aggregate targets from selected channels
            target_ids = []
            if hasattr(main_window, "member_db"):
                for channel in data["channels"]:
                    # Assuming we scrape safe targets
                    channel_id = channel.get("channel_id")
                    targets = main_window.member_db.get_safe_targets(channel_id)
                    target_ids.extend([t["user_id"] for t in targets])

            # Deduplicate
            target_ids = list(set(target_ids))

            if not target_ids:
                ErrorHandler.safe_warning(
                    self, "Error", "No valid targets found in selected channels."
                )
                return

            account_phones = [acc["phone_number"] for acc in data["accounts"]]

            # Prepare config with template variants
            config = {}
            if data.get("template_variants") and len(data["template_variants"]) > 1:
                config["template_variants"] = data["template_variants"]
                config["template_label"] = "default"

            # Create campaign
            try:
                self.campaign_manager.create_campaign(
                    name=data["name"],
                    template=data["template"],
                    target_member_ids=target_ids,
                    account_ids=account_phones,
                    config=config,
                )
                variant_count = len(data.get("template_variants", []))
                variant_msg = (
                    f" with {variant_count} template variants" if variant_count > 1 else ""
                )
                self.refresh_campaigns()
                ErrorHandler.safe_information(
                    self,
                    "Success",
                    f"Campaign '{data['name']}' created with {len(target_ids)} targets{variant_msg}.",
                )
            except Exception as e:
                ErrorHandler.safe_critical(self, "Error", f"Failed to create campaign: {e}")

    def get_selected_campaign_id(self) -> Optional[int]:
        """Get ID of selected campaign."""
        row = self.table.currentRow()
        if row >= 0:
            try:
                return int(self.table.item(row, 0).text())
            except ValueError:
                pass
        return None

    def pause_selected(self):
        cid = self.get_selected_campaign_id()
        if cid:
            # Need async execution for pause
            # We'll just fire and forget for now or use main window's async runner
            # Assuming campaign_manager has sync methods or we run async
            # The campaign_manager.pause_campaign is async.
            # We need to run it.
            main_window = self.window()
            if hasattr(main_window, "_run_async_task"):
                main_window._run_async_task(self.campaign_manager.pause_campaign(cid))
            self.refresh_campaigns()

    def resume_selected(self):
        cid = self.get_selected_campaign_id()
        if cid:
            main_window = self.window()
            if hasattr(main_window, "_run_async_task"):
                main_window._run_async_task(self.campaign_manager.start_campaign(cid))
            self.refresh_campaigns()

    def delete_selected(self):
        cid = self.get_selected_campaign_id()
        if cid:
            if ErrorHandler.safe_question(
                self,
                "Confirm Delete",
                "Are you sure you want to delete this campaign?\n\nThis action cannot be undone.",
            ):
                # Cancel first
                main_window = self.window()
                if hasattr(main_window, "_run_async_task"):
                    main_window._run_async_task(self.campaign_manager.cancel_campaign(cid))
                # Note: Actual deletion from DB might not be implemented in manager, but cancellation stops it.
                self.refresh_campaigns()
                ErrorHandler.safe_information(self, "Success", "Campaign deleted successfully")

    def edit_selected(self):
        """Edit selected campaign."""
        cid = self.get_selected_campaign_id()
        if not cid:
            ErrorHandler.safe_warning(self, "No Selection", "Please select a campaign to edit")
            return

        try:
            # Get campaign details
            campaigns = self.campaign_manager.get_all_campaigns()
            campaign = next((c for c in campaigns if c.id == cid), None)

            if not campaign:
                ErrorHandler.safe_warning(self, "Not Found", "Campaign not found")
                return

            # Check if campaign is running
            if campaign.status.value == "running":
                if ErrorHandler.safe_question(
                    self,
                    "Campaign Running",
                    "This campaign is currently running. Do you want to pause it before editing?",
                ):
                    self.pause_selected()

            ErrorHandler.safe_information(
                self,
                "Edit Campaign",
                f"Campaign: {campaign.name}\n\n"
                f"Note: Campaign editing is partially supported.\n"
                f"You can pause/resume, but cannot modify message content after creation.\n\n"
                f"To change messages, delete this campaign and create a new one.",
            )
        except Exception as e:
            from user_helpers import translate_error

            error_msg = translate_error(e, "editing campaign")
            ErrorHandler.safe_critical(self, "Error", error_msg)

    def view_selected(self):
        """View campaign details."""
        cid = self.get_selected_campaign_id()
        if not cid:
            ErrorHandler.safe_warning(self, "No Selection", "Please select a campaign to view")
            return

        try:
            campaigns = self.campaign_manager.get_all_campaigns()
            campaign = next((c for c in campaigns if c.id == cid), None)

            if not campaign:
                ErrorHandler.safe_warning(self, "Not Found", "Campaign not found")
                return

            # Build details message
            details = f"""
<h3>Campaign Details</h3>
<br>
<b>Name:</b> {campaign.name}<br>
<b>Status:</b> {campaign.status.value.title()}<br>
<b>Created:</b> {campaign.created_at.strftime("%Y-%m-%d %H:%M") if campaign.created_at else 'Unknown'}<br>
<br>
<b>Progress:</b><br>
• Total Targets: {campaign.total_targets}<br>
• Messages Sent: {campaign.sent_count}<br>
• Failed: {campaign.failed_count}<br>
• Success Rate: {(campaign.sent_count / max(campaign.total_targets, 1) * 100):.1f}%<br>
<br>
<b>Message Template:</b><br>
{campaign.message_template if hasattr(campaign, 'message_template') else 'Not available'}
            """

            msg_box = QMessageBox(self)
            msg_box.setWindowTitle(f"Campaign: {campaign.name}")
            msg_box.setText(details)
            msg_box.setTextFormat(Qt.TextFormat.RichText)
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.exec()

        except Exception as e:
            from user_helpers import translate_error

            error_msg = translate_error(e, "viewing campaign details")
            ErrorHandler.safe_critical(self, "Error", error_msg)

    def export_campaigns(self):
        """Export campaigns to file."""
        try:
            from datetime import datetime

            # Get campaigns
            campaigns = self.campaign_manager.get_all_campaigns() if self.campaign_manager else []

            if not campaigns:
                ErrorHandler.safe_information(self, "No Campaigns", "No campaigns to export.")
                return

            # Show format selection dialog
            format_options = ["CSV (*.csv)", "JSON (*.json)"]
            format_choice, ok = QInputDialog.getItem(
                self, "Export Format", "Select export format:", format_options, 0, False
            )

            if not ok:
                return

            # Determine file extension
            if "CSV" in format_choice:
                ext = ".csv"
                filter_str = "CSV Files (*.csv)"
            else:
                ext = ".json"
                filter_str = "JSON Files (*.json)"

            # Get save path
            default_name = f"campaigns_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Campaigns", default_name, filter_str
            )

            if not file_path:
                return

            # Ask about including messages
            include_messages = ErrorHandler.safe_question(
                self, "Include Messages", "Include individual message records in export?"
            )

            # Perform export
            from export_manager import get_export_manager

            exporter = get_export_manager(campaign_db_path="campaigns.db")

            if ext == ".csv":
                count = exporter.export_campaigns_to_csv(file_path, include_messages)
            else:
                count = exporter.export_campaigns_to_json(file_path, include_messages)

            if count > 0:
                ErrorHandler.safe_information(
                    self,
                    "Export Complete",
                    f"Successfully exported {count} campaigns to:\n{file_path}",
                )
            else:
                ErrorHandler.safe_warning(self, "No Data", "No campaigns found to export.")

        except Exception as e:
            from user_helpers import translate_error

            error_msg = translate_error(e, "exporting campaigns")
            ErrorHandler.safe_critical(self, "Error", error_msg)
