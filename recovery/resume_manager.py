#!/usr/bin/env python3
"""
Resume Manager - Manages resumable operations
Allows users to resume interrupted operations from where they left off
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from utils.retry_helper import OperationRecovery

logger = logging.getLogger(__name__)


class ResumeManagerDialog(QDialog):
    """Dialog for managing resumable operations."""

    operation_resumed = pyqtSignal(str, dict)  # operation_id, data

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Resume Incomplete Operations")
        self.resize(700, 400)

        self.recovery = OperationRecovery()
        self.setup_ui()
        self.load_operations()

    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("🔄 Resume Incomplete Operations")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Description
        desc = QLabel(
            "The following operations were interrupted and can be resumed.\n"
            "Select an operation and click 'Resume' to continue from where it left off."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Operation Type", "Started", "Age", "Progress", "Details"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        # Buttons
        button_layout = QHBoxLayout()

        self.resume_btn = QPushButton("▶️ Resume Selected")
        self.resume_btn.clicked.connect(self.resume_selected)
        self.resume_btn.setObjectName("success")
        button_layout.addWidget(self.resume_btn)

        self.delete_btn = QPushButton("🗑️ Delete Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        self.delete_btn.setObjectName("danger")
        button_layout.addWidget(self.delete_btn)

        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all)
        self.clear_all_btn.setObjectName("secondary")
        button_layout.addWidget(self.clear_all_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def load_operations(self):
        """Load incomplete operations."""
        operations = self.recovery.list_incomplete_operations()

        self.table.setRowCount(len(operations))

        for row, op in enumerate(operations):
            # Operation type
            op_type = op["data"].get("type", "Unknown")
            self.table.setItem(row, 0, QTableWidgetItem(op_type))

            # Started time
            started = datetime.fromtimestamp(op["timestamp"])
            self.table.setItem(row, 1, QTableWidgetItem(started.strftime("%Y-%m-%d %H:%M")))

            # Age
            age_hours = op["age_hours"]
            if age_hours < 1:
                age_str = f"{int(age_hours * 60)} min"
            elif age_hours < 24:
                age_str = f"{int(age_hours)} hours"
            else:
                age_str = f"{int(age_hours / 24)} days"
            self.table.setItem(row, 2, QTableWidgetItem(age_str))

            # Progress
            progress = op["data"].get("progress", {})
            current = progress.get("current", 0)
            total = progress.get("total", 0)
            if total > 0:
                progress_str = f"{current}/{total} ({int(current/total*100)}%)"
            else:
                progress_str = "Unknown"
            self.table.setItem(row, 3, QTableWidgetItem(progress_str))

            # Details
            details = op["data"].get("details", "No details")
            self.table.setItem(row, 4, QTableWidgetItem(str(details)))

            # Store operation ID in first column
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, op["operation_id"])

    def resume_selected(self):
        """Resume selected operation."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an operation to resume")
            return

        row = self.table.currentRow()
        operation_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        # Get operation data
        checkpoint_data = self.recovery.get_checkpoint(operation_id)

        if not checkpoint_data:
            QMessageBox.warning(self, "Not Found", "Operation data not found")
            return

        # Confirm resume
        op_type = checkpoint_data.get("type", "Unknown")
        reply = QMessageBox.question(
            self,
            "Confirm Resume",
            f"Resume operation: {op_type}?\n\n"
            f"This will continue from where it was interrupted.",
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.operation_resumed.emit(operation_id, checkpoint_data)
            self.accept()

    def delete_selected(self):
        """Delete selected operation."""
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, "No Selection", "Please select an operation to delete")
            return

        row = self.table.currentRow()
        operation_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self, "Confirm Delete", "Delete this operation checkpoint?\n\n" "This cannot be undone."
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.recovery.clear_checkpoint(operation_id)
            self.load_operations()
            QMessageBox.information(self, "Deleted", "Operation checkpoint deleted")

    def clear_all(self):
        """Clear all operations."""
        if self.table.rowCount() == 0:
            QMessageBox.information(self, "No Operations", "No operations to clear")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Clear All",
            f"Delete all {self.table.rowCount()} operation checkpoints?\n\n"
            "This cannot be undone.",
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Clear all
            operations = self.recovery.list_incomplete_operations()
            for op in operations:
                self.recovery.clear_checkpoint(op["operation_id"])

            self.load_operations()
            QMessageBox.information(self, "Cleared", "All operation checkpoints deleted")


def check_for_incomplete_operations() -> int:
    """Check if there are incomplete operations."""
    recovery = OperationRecovery()
    operations = recovery.list_incomplete_operations()
    return len(operations)


def show_resume_dialog(parent=None) -> Optional[tuple]:
    """Show resume dialog and return selected operation if any."""
    dialog = ResumeManagerDialog(parent)

    result = []

    def on_resume(op_id, data):
        result.append((op_id, data))

    dialog.operation_resumed.connect(on_resume)
    dialog.exec()

    return result[0] if result else None


def save_operation_checkpoint(
    operation_id: str, operation_type: str, current: int, total: int, details: Any = None
):
    """Save a checkpoint for an operation."""
    recovery = OperationRecovery()

    checkpoint_data = {
        "type": operation_type,
        "progress": {"current": current, "total": total},
        "details": details,
    }

    recovery.save_checkpoint(operation_id, checkpoint_data)
    logger.info(f"Saved checkpoint for {operation_type}: {current}/{total}")


def clear_operation_checkpoint(operation_id: str):
    """Clear a checkpoint when operation completes."""
    recovery = OperationRecovery()
    recovery.clear_checkpoint(operation_id)
    logger.info(f"Cleared checkpoint for {operation_id}")
