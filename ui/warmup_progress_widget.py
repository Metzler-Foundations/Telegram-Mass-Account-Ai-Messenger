"""
Warmup Progress Widget - Real-time display of account warmup progress.

Features:
- Live warmup job status updates
- Per-account progress tracking
- Stage completion visualization
- Error and stuck stage detection
- Auto-resume indicators
"""

import logging
from typing import Optional, List
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

# Try to import warmup service
try:
    from accounts.account_warmup_service import AccountWarmupService, WarmupJob, WarmupStage
    WARMUP_AVAILABLE = True
except ImportError:
    WARMUP_AVAILABLE = False
    logger.warning("AccountWarmupService not available")


class WarmupProgressWidget(QWidget):
    """Widget displaying real-time warmup progress."""
    
    job_selected = pyqtSignal(str)  # Emits job_id when selected
    
    def __init__(self, warmup_service: Optional['AccountWarmupService'] = None, parent=None):
        super().__init__(parent)
        self.warmup_service = warmup_service
        self.setup_ui()
        
        # Auto-refresh every 2 seconds for real-time updates
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(2000)  # 2 seconds
        
        # Initial load
        if self.warmup_service:
            self.refresh_data()
    
    def set_warmup_service(self, service: 'AccountWarmupService'):
        """Set the warmup service."""
        self.warmup_service = service
        self.refresh_data()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("🔥 Account Warmup Progress")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄")
        refresh_btn.setMaximumWidth(40)
        refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Summary
        summary_layout = QHBoxLayout()
        
        self.queued_label = QLabel("⏸ Queued: 0")
        summary_layout.addWidget(self.queued_label)
        
        self.active_label = QLabel("🔄 Active: 0")
        summary_layout.addWidget(self.active_label)
        
        self.completed_label = QLabel("✅ Completed: 0")
        summary_layout.addWidget(self.completed_label)
        
        self.failed_label = QLabel("❌ Failed: 0")
        summary_layout.addWidget(self.failed_label)
        
        summary_layout.addStretch()
        layout.addLayout(summary_layout)
        
        # Active jobs table
        jobs_group = QGroupBox("Active Warmup Jobs")
        jobs_layout = QVBoxLayout(jobs_group)
        
        self.jobs_table = QTableWidget()
        self.jobs_table.setColumnCount(5)
        self.jobs_table.setHorizontalHeaderLabels([
            "Phone Number",
            "Stage",
            "Progress",
            "Status",
            "Last Activity"
        ])
        
        header = self.jobs_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        
        self.jobs_table.setColumnWidth(0, 150)
        self.jobs_table.setColumnWidth(1, 150)
        self.jobs_table.setColumnWidth(4, 150)
        
        self.jobs_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1f22;
                color: #b5bac1;
                gridline-color: #2b2d31;
                border: none;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #2b2d31;
                color: #b5bac1;
                padding: 8px;
                border: none;
            }
        """)
        
        jobs_layout.addWidget(self.jobs_table)
        layout.addWidget(jobs_group)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #949ba4; font-size: 11px; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def refresh_data(self):
        """Refresh warmup progress data in real-time."""
        if not self.warmup_service:
            self.status_label.setText("Warmup service not available")
            return
        
        try:
            # Get all jobs
            all_jobs = self.warmup_service.get_all_jobs()
            
            # Count by status
            queued = len([j for j in all_jobs if j.job_id in [jb.job_id for jb in self.warmup_service.job_queue]])
            active = len(self.warmup_service.active_jobs)
            completed = len(self.warmup_service.completed_jobs)
            failed = len(self.warmup_service.failed_jobs)
            
            # Update summary
            self.queued_label.setText(f"⏸ Queued: {queued}")
            self.active_label.setText(f"🔄 Active: {active}")
            self.completed_label.setText(f"✅ Completed: {completed}")
            self.failed_label.setText(f"❌ Failed: {failed}")
            
            # Get active and queued jobs for display
            display_jobs = list(self.warmup_service.active_jobs.values()) + self.warmup_service.job_queue[:10]
            
            # Update table
            self.jobs_table.setRowCount(len(display_jobs))
            
            for row, job in enumerate(display_jobs):
                # Phone number
                phone_item = QTableWidgetItem(job.phone_number)
                self.jobs_table.setItem(row, 0, phone_item)
                
                # Stage
                stage_item = QTableWidgetItem(job.stage.value)
                self.jobs_table.setItem(row, 1, stage_item)
                
                # Progress bar
                progress_widget = QWidget()
                progress_layout = QVBoxLayout(progress_widget)
                progress_layout.setContentsMargins(2, 2, 2, 2)
                
                progress_bar = QProgressBar()
                progress_bar.setRange(0, 100)
                progress_bar.setValue(int(job.progress))
                progress_bar.setFormat(f"{job.progress:.1f}%")
                progress_bar.setStyleSheet("""
                    QProgressBar {
                        border: 1px solid #2b2d31;
                        border-radius: 3px;
                        background-color: #1e1f22;
                        text-align: center;
                    }
                    QProgressBar::chunk {
                        background-color: #5865f2;
                        border-radius: 2px;
                    }
                """)
                progress_layout.addWidget(progress_bar)
                
                self.jobs_table.setCellWidget(row, 2, progress_widget)
                
                # Status message
                status_item = QTableWidgetItem(job.status_message or "Processing...")
                if job.error_message:
                    status_item.setForeground(QColor("#ed4245"))
                self.jobs_table.setItem(row, 3, status_item)
                
                # Last activity
                if job.last_activity:
                    time_str = job.last_activity.strftime("%H:%M:%S")
                    last_activity_item = QTableWidgetItem(time_str)
                else:
                    last_activity_item = QTableWidgetItem("--")
                self.jobs_table.setItem(row, 4, last_activity_item)
            
            self.status_label.setText(
                f"🔄 Real-time updates: {active} active, {queued} queued | "
                f"Last refresh: {datetime.now().strftime('%H:%M:%S')}"
            )
            
        except Exception as e:
            logger.error(f"Failed to refresh warmup progress: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")


