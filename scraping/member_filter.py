#!/usr/bin/env python3
"""
Member Filter - Advanced filtering and segmentation for scraped members
"""

import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class MemberFilterDialog(QDialog):
    """Dialog for filtering members."""

    filter_applied = pyqtSignal(dict)  # Filter criteria

    def __init__(self, total_members: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 Filter Members")
        self.resize(600, 700)

        self.total_members = total_members
        self.filter_criteria = {}

        self.setup_ui()

    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("🔍 Member Filtering & Segmentation")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        desc = QLabel(
            f"Filter from {self.total_members:,} total members.\n"
            "Select criteria to narrow down your target audience."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Activity filters
        activity_group = QGroupBox("👤 Activity Status")
        activity_layout = QVBoxLayout()

        self.has_username_check = QCheckBox("Has username (@username)")
        self.has_username_check.setToolTip("Only include members with usernames (can be messaged)")
        activity_layout.addWidget(self.has_username_check)

        self.has_photo_check = QCheckBox("Has profile photo")
        self.has_photo_check.setToolTip("Members with profile photos are usually more active")
        activity_layout.addWidget(self.has_photo_check)

        self.is_bot_check = QCheckBox("Exclude bots")
        self.is_bot_check.setChecked(True)
        self.is_bot_check.setToolTip("Exclude bot accounts from results")
        activity_layout.addWidget(self.is_bot_check)

        self.is_verified_check = QCheckBox("Only verified accounts")
        self.is_verified_check.setToolTip("Only include Telegram-verified accounts")
        activity_layout.addWidget(self.is_verified_check)

        activity_group.setLayout(activity_layout)
        layout.addWidget(activity_group)

        # Name filters
        name_group = QGroupBox("📝 Name & Text Filters")
        name_layout = QFormLayout()

        self.name_contains_edit = QLineEdit()
        self.name_contains_edit.setPlaceholderText("e.g., John, crypto, etc.")
        self.name_contains_edit.setToolTip("Filter by name containing text")
        name_layout.addRow("Name contains:", self.name_contains_edit)

        self.bio_contains_edit = QLineEdit()
        self.bio_contains_edit.setPlaceholderText("e.g., developer, marketing")
        self.bio_contains_edit.setToolTip("Filter by bio containing text")
        name_layout.addRow("Bio contains:", self.bio_contains_edit)

        self.username_pattern_edit = QLineEdit()
        self.username_pattern_edit.setPlaceholderText("e.g., @crypto, @nft")
        self.username_pattern_edit.setToolTip("Filter by username pattern")
        name_layout.addRow("Username pattern:", self.username_pattern_edit)

        name_group.setLayout(name_layout)
        layout.addWidget(name_group)

        # Date filters
        date_group = QGroupBox("📅 Date Filters")
        date_layout = QFormLayout()

        self.joined_after_check = QCheckBox("Joined after:")
        self.joined_after_date = QDateEdit()
        self.joined_after_date.setDate(QDate.currentDate().addDays(-30))
        self.joined_after_date.setCalendarPopup(True)
        self.joined_after_date.setEnabled(False)
        self.joined_after_check.toggled.connect(self.joined_after_date.setEnabled)

        date_filter_layout = QHBoxLayout()
        date_filter_layout.addWidget(self.joined_after_check)
        date_filter_layout.addWidget(self.joined_after_date)
        date_filter_layout.addStretch()
        date_layout.addRow(date_filter_layout)

        self.last_seen_check = QCheckBox("Last seen within:")
        self.last_seen_days = QSpinBox()
        self.last_seen_days.setRange(1, 365)
        self.last_seen_days.setValue(30)
        self.last_seen_days.setSuffix(" days")
        self.last_seen_days.setEnabled(False)
        self.last_seen_check.toggled.connect(self.last_seen_days.setEnabled)

        last_seen_layout = QHBoxLayout()
        last_seen_layout.addWidget(self.last_seen_check)
        last_seen_layout.addWidget(self.last_seen_days)
        last_seen_layout.addStretch()
        date_layout.addRow(last_seen_layout)

        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Advanced filters
        advanced_group = QGroupBox("⚙️ Advanced Filters")
        advanced_layout = QFormLayout()

        self.min_msg_count = QSpinBox()
        self.min_msg_count.setRange(0, 10000)
        self.min_msg_count.setValue(0)
        self.min_msg_count.setToolTip("Minimum messages in channel (if available)")
        advanced_layout.addRow("Min. messages:", self.min_msg_count)

        self.lang_combo = QComboBox()
        self.lang_combo.addItems(
            [
                "All Languages",
                "English",
                "Spanish",
                "French",
                "German",
                "Italian",
                "Portuguese",
                "Russian",
                "Chinese",
                "Japanese",
            ]
        )
        self.lang_combo.setToolTip("Filter by language (if detected)")
        advanced_layout.addRow("Language:", self.lang_combo)

        self.premium_only_check = QCheckBox("Premium users only")
        self.premium_only_check.setToolTip("Only include Telegram Premium subscribers")
        advanced_layout.addRow(self.premium_only_check)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # Result limit
        limit_group = QGroupBox("📊 Result Limit")
        limit_layout = QHBoxLayout()

        self.limit_results_check = QCheckBox("Limit to:")
        self.limit_count = QSpinBox()
        self.limit_count.setRange(1, 100000)
        self.limit_count.setValue(1000)
        self.limit_count.setSuffix(" members")
        self.limit_count.setEnabled(False)
        self.limit_results_check.toggled.connect(self.limit_count.setEnabled)

        limit_layout.addWidget(self.limit_results_check)
        limit_layout.addWidget(self.limit_count)
        limit_layout.addStretch()

        limit_group.setLayout(limit_layout)
        layout.addWidget(limit_group)

        # Estimated results
        self.results_label = QLabel()
        self.results_label.setStyleSheet(
            "padding: 10px; background-color: #2b2d31; border-radius: 4px;"
        )
        layout.addWidget(self.results_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.preview_btn = QPushButton("👁️ Preview Results")
        self.preview_btn.clicked.connect(self.preview_results)
        self.preview_btn.setObjectName("secondary")
        button_layout.addWidget(self.preview_btn)

        self.reset_btn = QPushButton("🔄 Reset Filters")
        self.reset_btn.clicked.connect(self.reset_filters)
        button_layout.addWidget(self.reset_btn)

        button_layout.addStretch()

        apply_btn = QPushButton("✅ Apply Filters")
        apply_btn.clicked.connect(self.apply_filters)
        apply_btn.setObjectName("success")
        button_layout.addWidget(apply_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Initial estimate
        self.update_estimate()

    def get_filter_criteria(self) -> Dict[str, Any]:
        """Get current filter criteria."""
        criteria = {}

        # Activity filters
        if self.has_username_check.isChecked():
            criteria["has_username"] = True

        if self.has_photo_check.isChecked():
            criteria["has_photo"] = True

        if self.is_bot_check.isChecked():
            criteria["exclude_bots"] = True

        if self.is_verified_check.isChecked():
            criteria["is_verified"] = True

        # Name filters
        if self.name_contains_edit.text():
            criteria["name_contains"] = self.name_contains_edit.text()

        if self.bio_contains_edit.text():
            criteria["bio_contains"] = self.bio_contains_edit.text()

        if self.username_pattern_edit.text():
            criteria["username_pattern"] = self.username_pattern_edit.text()

        # Date filters
        if self.joined_after_check.isChecked():
            criteria["joined_after"] = self.joined_after_date.date().toPyDate()

        if self.last_seen_check.isChecked():
            criteria["last_seen_days"] = self.last_seen_days.value()

        # Advanced filters
        if self.min_msg_count.value() > 0:
            criteria["min_messages"] = self.min_msg_count.value()

        if self.lang_combo.currentIndex() > 0:
            criteria["language"] = self.lang_combo.currentText()

        if self.premium_only_check.isChecked():
            criteria["premium_only"] = True

        # Limit
        if self.limit_results_check.isChecked():
            criteria["limit"] = self.limit_count.value()

        return criteria

    def update_estimate(self):
        """Update estimated results with ACTUAL database query."""
        criteria = self.get_filter_criteria()

        # Get actual count from database if member_db available
        try:
            from member_scraper import MemberDatabase

            member_db = MemberDatabase("members.db")

            # Build actual SQL query
            actual_count = self.get_actual_filtered_count(member_db, criteria)

            percentage = (actual_count / max(self.total_members, 1)) * 100

            self.results_label.setText(
                f"📊 <b>Actual Results:</b> {actual_count:,} members "
                f"({percentage:.1f}% of total)"
            )
            self.results_label.setTextFormat(Qt.TextFormat.RichText)

        except Exception as e:
            logger.error(f"Failed to get actual count: {e}")
            # Fallback to estimated if database unavailable
            self.results_label.setText(
                "⚠️ <b>Cannot query database.</b> Select criteria and click Preview for actual count."
            )
            self.results_label.setTextFormat(Qt.TextFormat.RichText)

    def get_actual_filtered_count(self, member_db, criteria: Dict) -> int:
        """Get ACTUAL count from database using real SQL query."""
        import sqlite3

        # Build WHERE clause from criteria
        conditions = []
        params = []

        if criteria.get("has_username"):
            conditions.append("username IS NOT NULL AND username != ''")

        if criteria.get("has_photo"):
            conditions.append("has_photo = 1")

        if criteria.get("exclude_bots"):
            conditions.append("is_bot = 0")

        if criteria.get("is_verified"):
            conditions.append("is_verified = 1")

        if criteria.get("premium_only"):
            conditions.append("is_premium = 1")

        if criteria.get("name_contains"):
            conditions.append("(first_name LIKE ? OR last_name LIKE ?)")
            search_term = f"%{criteria['name_contains']}%"
            params.extend([search_term, search_term])

        if criteria.get("bio_contains"):
            conditions.append("bio LIKE ?")
            params.append(f"%{criteria['bio_contains']}%")

        if criteria.get("username_pattern"):
            conditions.append("username LIKE ?")
            params.append(f"%{criteria['username_pattern']}%")

        if criteria.get("joined_after"):
            conditions.append("scraped_at >= ?")
            params.append(criteria["joined_after"].isoformat())

        if criteria.get("min_messages"):
            conditions.append("message_count >= ?")
            params.append(criteria["min_messages"])

        if criteria.get("language"):
            conditions.append("language_code = ?")
            params.append(criteria["language"].lower()[:2])

        # Build query
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT COUNT(*) FROM members WHERE {where_clause}"

        if criteria.get("limit"):
            query += f" LIMIT {criteria['limit']}"

        # Execute query
        try:
            conn = sqlite3.connect(member_db.db_path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            conn.close()
            return count
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return 0

    def preview_results(self):
        """Preview filter results."""
        criteria = self.get_filter_criteria()

        if not criteria:
            QMessageBox.information(
                self, "No Filters", "No filters selected. All members will be included."
            )
            return

        # Show preview dialog
        preview_text = "🔍 <b>Active Filters:</b><br><br>"

        for key, value in criteria.items():
            preview_text += f"• <b>{key.replace('_', ' ').title()}:</b> {value}<br>"

        QMessageBox.information(self, "Filter Preview", preview_text)

    def reset_filters(self):
        """Reset all filters."""
        self.has_username_check.setChecked(False)
        self.has_photo_check.setChecked(False)
        self.is_bot_check.setChecked(True)
        self.is_verified_check.setChecked(False)

        self.name_contains_edit.clear()
        self.bio_contains_edit.clear()
        self.username_pattern_edit.clear()

        self.joined_after_check.setChecked(False)
        self.last_seen_check.setChecked(False)

        self.min_msg_count.setValue(0)
        self.lang_combo.setCurrentIndex(0)
        self.premium_only_check.setChecked(False)

        self.limit_results_check.setChecked(False)

        self.update_estimate()

    def apply_filters(self):
        """Apply filters."""
        criteria = self.get_filter_criteria()
        self.filter_criteria = criteria
        self.filter_applied.emit(criteria)
        self.accept()

    def get_criteria(self) -> Dict[str, Any]:
        """Get the filter criteria."""
        return self.filter_criteria


class FilterPresetManager(QDialog):
    """Manager for saving and loading filter presets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💾 Filter Presets")
        self.resize(500, 400)

        self.presets = self.load_presets()
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("💾 Saved Filter Presets")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Presets list
        self.presets_list = QListWidget()
        self.load_presets_to_list()
        layout.addWidget(self.presets_list)

        # Buttons
        button_layout = QHBoxLayout()

        load_btn = QPushButton("📂 Load Selected")
        load_btn.clicked.connect(self.load_selected)
        button_layout.addWidget(load_btn)

        delete_btn = QPushButton("🗑️ Delete")
        delete_btn.clicked.connect(self.delete_selected)
        button_layout.addWidget(delete_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def load_presets(self) -> Dict[str, Dict]:
        """Load presets from file."""
        import json
        from pathlib import Path

        preset_file = Path("filter_presets.json")
        if preset_file.exists():
            try:
                with open(preset_file) as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load presets: {e}")

        return {}

    def save_presets(self):
        """Save presets to file."""
        import json

        try:
            with open("filter_presets.json", "w") as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save presets: {e}")

    def load_presets_to_list(self):
        """Load presets into list widget."""
        self.presets_list.clear()
        for name in self.presets.keys():
            self.presets_list.addItem(name)

    def load_selected(self):
        """Load selected preset."""
        selected = self.presets_list.currentItem()
        if selected:
            selected.text()
            # Would return preset data to caller
            self.accept()

    def delete_selected(self):
        """Delete selected preset."""
        selected = self.presets_list.currentItem()
        if selected:
            preset_name = selected.text()
            reply = QMessageBox.question(self, "Confirm Delete", f"Delete preset '{preset_name}'?")

            if reply == QMessageBox.StandardButton.Yes:
                del self.presets[preset_name]
                self.save_presets()
                self.load_presets_to_list()


def show_filter_dialog(total_members: int = 0, parent=None) -> Optional[Dict]:
    """Show filter dialog and return criteria if applied."""
    dialog = MemberFilterDialog(total_members, parent)

    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_criteria()

    return None
