#!/usr/bin/env python3
"""
Progress Tracker - Enhanced progress tracking for long operations
Provides visual feedback and allows cancellation/pause
"""

import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class ProgressTracker(QDialog):
    """Enhanced progress dialog with detailed tracking."""

    cancelled = pyqtSignal()
    paused = pyqtSignal()
    resumed = pyqtSignal()

    def __init__(self, title: str, total_steps: int = 100, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(600, 400)

        self.total_steps = total_steps
        self.current_step = 0
        self.is_paused = False
        self.is_cancelled = False
        self.start_time = datetime.now()
        self.pause_time = None
        self.total_pause_duration = timedelta()

        self.setup_ui()

        # Update timer
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_stats)
        self.update_timer.start(1000)  # Update every second

    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        self.title_label = QLabel()
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        layout.addWidget(self.title_label)

        # Status label
        self.status_label = QLabel("Initializing...")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.total_steps)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v / %m (%p%)")
        layout.addWidget(self.progress_bar)

        # Stats frame
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        stats_layout = QVBoxLayout(stats_frame)

        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        stats_layout.addWidget(self.stats_label)

        layout.addWidget(stats_frame)

        # Details log
        self.details_log = QTextEdit()
        self.details_log.setReadOnly(True)
        self.details_log.setMaximumHeight(150)
        layout.addWidget(self.details_log)

        # Buttons
        button_layout = QHBoxLayout()

        self.pause_btn = QPushButton("⏸️ Pause")
        self.pause_btn.clicked.connect(self.toggle_pause)
        button_layout.addWidget(self.pause_btn)

        self.cancel_btn = QPushButton("❌ Cancel")
        self.cancel_btn.clicked.connect(self.cancel_operation)
        button_layout.addWidget(self.cancel_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setEnabled(False)
        button_layout.addWidget(self.close_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

    def update_progress(self, current: int, total: Optional[int] = None, message: str = ""):
        """Update progress."""
        if total:
            self.total_steps = total
            self.progress_bar.setMaximum(total)

        self.current_step = current
        self.progress_bar.setValue(current)

        if message:
            self.status_label.setText(message)
            self.add_log(message)

        self.update_stats()

    def set_status(self, message: str):
        """Set status message."""
        self.status_label.setText(message)
        self.add_log(message)

    def add_log(self, message: str):
        """Add message to log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.details_log.append(f"[{timestamp}] {message}")

        # Auto-scroll to bottom
        scrollbar = self.details_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def update_stats(self):
        """Update statistics display."""
        if self.is_cancelled:
            return

        elapsed = self.get_elapsed_time()

        # Calculate progress percentage
        if self.total_steps > 0:
            progress_pct = (self.current_step / self.total_steps) * 100
        else:
            progress_pct = 0

        # Calculate ETA
        if self.current_step > 0 and progress_pct > 0:
            time_per_step = elapsed.total_seconds() / self.current_step
            remaining_steps = self.total_steps - self.current_step
            eta_seconds = time_per_step * remaining_steps
            eta = timedelta(seconds=int(eta_seconds))
        else:
            eta = timedelta(0)

        # Calculate speed
        if elapsed.total_seconds() > 0:
            speed = self.current_step / elapsed.total_seconds()
        else:
            speed = 0

        # Format stats
        stats_text = f"""
<b>Progress:</b> {self.current_step} / {self.total_steps} ({progress_pct:.1f}%)<br>
<b>Elapsed Time:</b> {self.format_timedelta(elapsed)}<br>
<b>Estimated Time Remaining:</b> {self.format_timedelta(eta)}<br>
<b>Speed:</b> {speed:.2f} items/second
        """

        if self.is_paused:
            stats_text += "<br><br><b>⏸️ PAUSED</b>"

        self.stats_label.setText(stats_text.strip())

    def get_elapsed_time(self) -> timedelta:
        """Get elapsed time excluding pauses."""
        if self.is_paused:
            elapsed = self.pause_time - self.start_time - self.total_pause_duration
        else:
            elapsed = datetime.now() - self.start_time - self.total_pause_duration
        return elapsed

    @staticmethod
    def format_timedelta(td: timedelta) -> str:
        """Format timedelta as human-readable string."""
        seconds = int(td.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m {seconds % 60}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h {minutes}m"

    def toggle_pause(self):
        """Toggle pause state."""
        if self.is_paused:
            # Resume
            pause_duration = datetime.now() - self.pause_time
            self.total_pause_duration += pause_duration
            self.is_paused = False
            self.pause_btn.setText("⏸️ Pause")
            self.add_log("▶️ Resumed")
            self.resumed.emit()
        else:
            # Pause
            self.pause_time = datetime.now()
            self.is_paused = True
            self.pause_btn.setText("▶️ Resume")
            self.add_log("⏸️ Paused")
            self.paused.emit()

    def cancel_operation(self):
        """Cancel the operation."""
        self.is_cancelled = True
        self.add_log("❌ Operation cancelled by user")
        self.status_label.setText("❌ Cancelled")
        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)
        self.cancelled.emit()

    def mark_complete(self, message: str = "✅ Operation completed successfully!"):
        """Mark operation as complete."""
        self.current_step = self.total_steps
        self.progress_bar.setValue(self.total_steps)
        self.status_label.setText(message)
        self.add_log(message)

        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)

        self.update_stats()

    def mark_error(self, error_message: str):
        """Mark operation as failed."""
        self.status_label.setText(f"❌ Error: {error_message}")
        self.add_log(f"❌ Error: {error_message}")

        self.pause_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.close_btn.setEnabled(True)


class SimpleProgressDialog(QDialog):
    """Simplified progress dialog for quick operations."""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(400, 150)

        layout = QVBoxLayout(self)

        # Message
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        layout.addWidget(msg_label)

        # Progress bar (indeterminate)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def set_status(self, status: str):
        """Update status text."""
        self.status_label.setText(status)

    def set_progress(self, current: int, total: int):
        """Set determinate progress."""
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)


class ProgressCallback:
    """Callback handler for progress updates."""

    def __init__(self, progress_dialog: Optional[ProgressTracker] = None):
        self.dialog = progress_dialog
        self.callbacks = []

    def add_callback(self, callback: Callable[[int, int, str], None]):
        """Add a progress callback function."""
        self.callbacks.append(callback)

    def update(self, current: int, total: int, message: str = ""):
        """Update progress."""
        if self.dialog:
            self.dialog.update_progress(current, total, message)

        for callback in self.callbacks:
            try:
                callback(current, total, message)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

    def set_status(self, message: str):
        """Set status message."""
        if self.dialog:
            self.dialog.set_status(message)

    def is_cancelled(self) -> bool:
        """Check if operation was cancelled."""
        return self.dialog.is_cancelled if self.dialog else False

    def is_paused(self) -> bool:
        """Check if operation is paused."""
        return self.dialog.is_paused if self.dialog else False
