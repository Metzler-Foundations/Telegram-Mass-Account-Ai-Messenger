"""
Account Risk Monitor Widget - Real-time display of account health and ban risk.

Features:
- Risk level visualization
- High-risk account alerts
- Quarantine recommendations
- Real-time risk scoring
- Per-account risk details
"""

import logging
from typing import Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

logger = logging.getLogger(__name__)

# Try to import risk monitor
try:
    from monitoring.account_risk_monitor import (
        AccountRiskMonitor, RiskLevel, get_risk_monitor
    )
    RISK_MONITOR_AVAILABLE = True
except ImportError:
    RISK_MONITOR_AVAILABLE = False
    logger.warning("AccountRiskMonitor not available")


class RiskMonitorWidget(QWidget):
    """Widget for monitoring account risk levels."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.risk_monitor: Optional[AccountRiskMonitor] = None
        self.setup_ui()
        
        # Auto-refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # 30 seconds
        
        # Initialize
        if RISK_MONITOR_AVAILABLE:
            self.risk_monitor = get_risk_monitor()
            self.refresh_data()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("🛡️ Account Risk Monitor")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Summary stats
        summary_group = QGroupBox("📊 Risk Summary")
        summary_layout = QHBoxLayout(summary_group)
        
        self.total_accounts_label = QLabel("Total: 0")
        summary_layout.addWidget(self.total_accounts_label)
        
        self.safe_label = QLabel("🟢 Safe: 0")
        summary_layout.addWidget(self.safe_label)
        
        self.low_label = QLabel("🟡 Low: 0")
        summary_layout.addWidget(self.low_label)
        
        self.medium_label = QLabel("🟠 Medium: 0")
        summary_layout.addWidget(self.medium_label)
        
        self.high_label = QLabel("🔴 High: 0")
        summary_layout.addWidget(self.high_label)
        
        self.critical_label = QLabel("🚨 Critical: 0")
        summary_layout.addWidget(self.critical_label)
        
        self.quarantine_label = QLabel("🔒 Quarantine: 0")
        summary_layout.addWidget(self.quarantine_label)
        
        summary_layout.addStretch()
        layout.addWidget(summary_group)
        
        # High-risk accounts table
        accounts_group = QGroupBox("⚠️ High-Risk Accounts")
        accounts_layout = QVBoxLayout(accounts_group)
        
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(6)
        self.accounts_table.setHorizontalHeaderLabels([
            "Phone Number",
            "Risk Score",
            "Risk Level",
            "FloodWaits (24h)",
            "Errors (24h)",
            "Recommendations"
        ])
        
        header = self.accounts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        
        self.accounts_table.setColumnWidth(0, 150)
        self.accounts_table.setColumnWidth(1, 100)
        self.accounts_table.setColumnWidth(2, 100)
        self.accounts_table.setColumnWidth(3, 120)
        self.accounts_table.setColumnWidth(4, 100)
        
        self.accounts_table.setStyleSheet("""
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
        
        accounts_layout.addWidget(self.accounts_table)
        layout.addWidget(accounts_group)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #949ba4; font-size: 11px; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def refresh_data(self):
        """Refresh risk monitoring data."""
        if not self.risk_monitor:
            self.status_label.setText("Risk monitor not available")
            return
        
        try:
            # Get summary
            summary = self.risk_monitor.get_risk_summary()
            
            self.total_accounts_label.setText(f"Total: {summary['total_accounts']}")
            self.safe_label.setText(f"🟢 Safe: {summary['safe']}")
            self.low_label.setText(f"🟡 Low: {summary['low']}")
            self.medium_label.setText(f"🟠 Medium: {summary['medium']}")
            self.high_label.setText(f"🔴 High: {summary['high']}")
            self.critical_label.setText(f"🚨 Critical: {summary['critical']}")
            self.quarantine_label.setText(f"🔒 Quarantine: {summary['quarantine_candidates']}")
            
            # Get high-risk accounts
            high_risk = self.risk_monitor.get_high_risk_accounts(RiskLevel.MEDIUM)
            
            self.accounts_table.setRowCount(len(high_risk))
            
            for row, account in enumerate(high_risk):
                # Phone number
                phone_item = QTableWidgetItem(account.phone_number)
                self.accounts_table.setItem(row, 0, phone_item)
                
                # Risk score with color
                score_item = QTableWidgetItem(f"{account.overall_score:.1f}")
                score_color = self._get_risk_color(account.risk_level)
                score_item.setForeground(score_color)
                self.accounts_table.setItem(row, 1, score_item)
                
                # Risk level
                level_item = QTableWidgetItem(account.risk_level.value.upper())
                level_item.setForeground(score_color)
                self.accounts_table.setItem(row, 2, level_item)
                
                # FloodWaits
                floodwait_item = QTableWidgetItem(str(account.total_floodwaits_24h))
                self.accounts_table.setItem(row, 3, floodwait_item)
                
                # Errors
                errors_item = QTableWidgetItem(str(account.total_errors_24h))
                self.accounts_table.setItem(row, 4, errors_item)
                
                # Recommendations
                recs = "; ".join(account.recommended_actions[:2])
                recs_item = QTableWidgetItem(recs)
                self.accounts_table.setItem(row, 5, recs_item)
            
            self.status_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Failed to refresh risk data: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")
    
    @staticmethod
    def _get_risk_color(risk_level: RiskLevel) -> QColor:
        """Get color for risk level."""
        colors = {
            RiskLevel.SAFE: QColor("#23a559"),      # Green
            RiskLevel.LOW: QColor("#f0b232"),       # Yellow
            RiskLevel.MEDIUM: QColor("#eb459e"),    # Pink
            RiskLevel.HIGH: QColor("#ed4245"),      # Red
            RiskLevel.CRITICAL: QColor("#992d22")   # Dark red
        }
        return colors.get(risk_level, QColor("#b5bac1"))








