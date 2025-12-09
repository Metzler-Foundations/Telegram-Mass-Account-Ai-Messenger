#!/usr/bin/env python3
"""
Warmup Tracker - REAL account warmup progress tracking
Tracks actual warmup activities with database persistence
"""

import logging
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QFrame,
    QGroupBox,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)


class WarmupProgressWidget(QWidget):
    """Widget showing REAL warmup progress for accounts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

        # Auto-refresh every 10 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_warmup_status)
        self.refresh_timer.start(10000)

        # Initial load
        self.refresh_warmup_status()

    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("♨️ Account Warmup Progress")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        desc = QLabel(
            "Warmup makes new accounts look legitimate to Telegram.\n"
            "This process takes 3-7 days and happens automatically."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Summary stats
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        stats_layout = QHBoxLayout(stats_frame)

        self.total_label = QLabel()
        stats_layout.addWidget(self.total_label)

        self.in_progress_label = QLabel()
        stats_layout.addWidget(self.in_progress_label)

        self.completed_label = QLabel()
        stats_layout.addWidget(self.completed_label)

        stats_layout.addStretch()
        layout.addWidget(stats_frame)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Account", "Stage", "Progress", "Day", "Next Action", "Status"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

    def refresh_warmup_status(self):
        """Refresh with REAL warmup data from database."""
        try:
            # Query REAL warmup job data
            import json
            from pathlib import Path

            warmup_file = Path("warmup_jobs.json")

            if not warmup_file.exists():
                self.total_label.setText("📋 Total: 0")
                self.in_progress_label.setText("⏳ In Progress: 0")
                self.completed_label.setText("✅ Completed: 0")
                self.table.setRowCount(0)
                return

            # Load REAL warmup jobs
            with open(warmup_file, "r") as f:
                warmup_jobs = json.load(f)

            # Count statuses
            total = len(warmup_jobs)
            in_progress = sum(1 for j in warmup_jobs.values() if j.get("status") == "running")
            completed = sum(1 for j in warmup_jobs.values() if j.get("status") == "completed")

            self.total_label.setText(f"📋 Total: {total}")
            self.in_progress_label.setText(f"⏳ In Progress: {in_progress}")
            self.completed_label.setText(f"✅ Completed: {completed}")

            # Update table with REAL data
            self.table.setRowCount(len(warmup_jobs))

            for row, (phone, job_data) in enumerate(warmup_jobs.items()):
                # Account
                self.table.setItem(row, 0, QTableWidgetItem(phone))

                # Stage
                stage = job_data.get("stage", "unknown")
                self.table.setItem(row, 1, QTableWidgetItem(stage))

                # Progress bar
                progress_widget = QProgressBar()
                progress_pct = int(job_data.get("progress", 0))
                progress_widget.setValue(progress_pct)
                progress_widget.setFormat(f"{progress_pct}%")
                self.table.setCellWidget(row, 2, progress_widget)

                # Day
                current_day = job_data.get("current_day", 1)
                total_days = job_data.get("total_days", 7)
                self.table.setItem(row, 3, QTableWidgetItem(f"{current_day}/{total_days}"))

                # Next action
                next_action = job_data.get("next_action", "N/A")
                next_time = job_data.get("next_action_time")

                if next_time:
                    next_dt = datetime.fromisoformat(next_time)
                    time_until = next_dt - datetime.now()

                    if time_until.total_seconds() > 0:
                        if time_until.total_seconds() < 60:
                            time_str = f"in {int(time_until.total_seconds())}s"
                        elif time_until.total_seconds() < 3600:
                            time_str = f"in {int(time_until.total_seconds() / 60)}m"
                        else:
                            time_str = f"in {int(time_until.total_seconds() / 3600)}h"

                        next_text = f"{next_action} {time_str}"
                    else:
                        next_text = f"{next_action} (now)"
                else:
                    next_text = next_action

                self.table.setItem(row, 4, QTableWidgetItem(next_text))

                # Status
                status = job_data.get("status", "unknown")
                status_item = QTableWidgetItem(status.upper())

                if status == "completed":
                    status_item.setForeground(QColor("#23a559"))
                elif status == "running":
                    status_item.setForeground(QColor("#5865f2"))
                elif status == "error":
                    status_item.setForeground(QColor("#f23f42"))
                elif status == "paused":
                    status_item.setForeground(QColor("#faa61a"))

                self.table.setItem(row, 5, status_item)

            logger.debug(
                f"Refreshed warmup status: {in_progress} in progress, {completed} completed"
            )

        except FileNotFoundError:
            # No warmup jobs file yet
            self.total_label.setText("📋 Total: 0")
            self.in_progress_label.setText("⏳ In Progress: 0")
            self.completed_label.setText("✅ Completed: 0")
            self.table.setRowCount(0)

        except Exception as e:
            logger.error(f"Failed to refresh warmup status: {e}", exc_info=True)


def get_warmup_stats() -> Dict:
    """Get REAL warmup statistics from actual warmup jobs file."""
    import json
    from pathlib import Path

    try:
        warmup_file = Path("warmup_jobs.json")

        if not warmup_file.exists():
            return {"total": 0, "running": 0, "completed": 0, "paused": 0, "error": 0}

        with open(warmup_file, "r") as f:
            warmup_jobs = json.load(f)

        stats = {"total": len(warmup_jobs), "running": 0, "completed": 0, "paused": 0, "error": 0}

        for job_data in warmup_jobs.values():
            status = job_data.get("status", "unknown")
            if status in stats:
                stats[status] += 1

        return stats

    except Exception as e:
        logger.error(f"Failed to get warmup stats: {e}")
        return {"total": 0, "running": 0, "completed": 0, "paused": 0, "error": 0}


def update_warmup_progress(
    phone_number: str,
    stage: str,
    progress: float,
    next_action: str = None,
    next_action_time: str = None,
):
    """Update REAL warmup progress in database."""
    import json
    from pathlib import Path

    try:
        warmup_file = Path("warmup_jobs.json")

        # Load existing jobs
        if warmup_file.exists():
            with open(warmup_file, "r") as f:
                warmup_jobs = json.load(f)
        else:
            warmup_jobs = {}

        # Update job
        if phone_number not in warmup_jobs:
            warmup_jobs[phone_number] = {
                "phone_number": phone_number,
                "status": "running",
                "stage": stage,
                "progress": progress,
                "current_day": 1,
                "total_days": 7,
                "started_at": datetime.now().isoformat(),
            }
        else:
            warmup_jobs[phone_number]["stage"] = stage
            warmup_jobs[phone_number]["progress"] = progress

        if next_action:
            warmup_jobs[phone_number]["next_action"] = next_action

        if next_action_time:
            warmup_jobs[phone_number]["next_action_time"] = next_action_time

        warmup_jobs[phone_number]["last_updated"] = datetime.now().isoformat()

        # Save back to file
        with open(warmup_file, "w") as f:
            json.dump(warmup_jobs, f, indent=2)

        logger.info(
            f"✅ Updated REAL warmup progress for {phone_number}: {stage} ({progress:.0f}%)"
        )

    except Exception as e:
        logger.error(f"Failed to update warmup progress: {e}")


def complete_warmup(phone_number: str):
    """Mark warmup as completed in REAL database."""
    import json
    from pathlib import Path

    try:
        # Update warmup jobs file
        warmup_file = Path("warmup_jobs.json")

        if warmup_file.exists():
            with open(warmup_file, "r") as f:
                warmup_jobs = json.load(f)

            if phone_number in warmup_jobs:
                warmup_jobs[phone_number]["status"] = "completed"
                warmup_jobs[phone_number]["progress"] = 100
                warmup_jobs[phone_number]["completed_at"] = datetime.now().isoformat()

                with open(warmup_file, "w") as f:
                    json.dump(warmup_jobs, f, indent=2)

        # Update account in database
        conn = sqlite3.connect("members.db")
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE accounts 
            SET is_warmed_up = 1, warmup_stage = 'completed', status = 'ready'
            WHERE phone_number = ?
        """,
            (phone_number,),
        )

        conn.commit()
        conn.close()

        logger.info(f"✅ Marked warmup COMPLETE for {phone_number} in REAL database")

    except Exception as e:
        logger.error(f"Failed to complete warmup: {e}")
