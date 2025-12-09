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
    QProgressBar, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor

from ui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)

try:
    from ui.ui_components import LoadingOverlay
except ImportError:
    LoadingOverlay = None

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
        self.all_accounts = []
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
        c = ThemeManager.get_colors()
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("Account Risk Monitor")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search phone…")
        self.search_input.setFixedWidth(200)
        self.search_input.setAccessibleName("Risk monitor search")
        self.search_input.textChanged.connect(self._on_filter_change)
        header_layout.addWidget(self.search_input)

        self.risk_filter = QComboBox()
        self.risk_filter.addItems(["All", "Safe", "Low", "Medium", "High", "Critical", "Quarantine"])
        self.risk_filter.setAccessibleName("Risk level filter")
        self.risk_filter.currentTextChanged.connect(self._on_filter_change)
        header_layout.addWidget(self.risk_filter)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary")
        refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Summary stats
        summary_group = QGroupBox("Risk Summary")
        summary_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 0.5px solid {c['BORDER_DEFAULT']};
                border-radius: 10px;
                margin-top: 8px;
                padding: 10px 12px 8px 12px;
                color: {c['TEXT_PRIMARY']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['TEXT_SECONDARY']};
            }}
            QLabel {{
                color: {c['TEXT_PRIMARY']};
            }}
        """
        )
        summary_layout = QHBoxLayout(summary_group)
        
        self.total_accounts_label = QLabel("Total: 0")
        summary_layout.addWidget(self.total_accounts_label)
        
        self.safe_label = QLabel("Safe: 0")
        summary_layout.addWidget(self.safe_label)
        
        self.low_label = QLabel("Low: 0")
        summary_layout.addWidget(self.low_label)
        
        self.medium_label = QLabel("Medium: 0")
        summary_layout.addWidget(self.medium_label)
        
        self.high_label = QLabel("High: 0")
        summary_layout.addWidget(self.high_label)
        
        self.critical_label = QLabel("Critical: 0")
        summary_layout.addWidget(self.critical_label)
        
        self.quarantine_label = QLabel("Quarantine: 0")
        summary_layout.addWidget(self.quarantine_label)
        
        summary_layout.addStretch()
        layout.addWidget(summary_group)
        
        # High-risk accounts table
        accounts_group = QGroupBox("High-Risk Accounts")
        accounts_group.setStyleSheet(
            f"""
            QGroupBox {{
                background-color: {c['BG_SECONDARY']};
                border: 0.5px solid {c['BORDER_DEFAULT']};
                border-radius: 10px;
                margin-top: 8px;
                padding: 10px 12px 12px 12px;
                color: {c['TEXT_PRIMARY']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['TEXT_SECONDARY']};
            }}
        """
        )
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
        
        self.accounts_table.setStyleSheet(
            f"""
            QTableWidget {{
                background-color: {c['BG_SECONDARY']};
                color: {c['TEXT_PRIMARY']};
                gridline-color: {c['BORDER_DEFAULT']};
                border: 0.5px solid {c['BORDER_DEFAULT']};
                border-radius: 8px;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QHeaderView::section {{
                background-color: {c['BG_TERTIARY']};
                color: {c['TEXT_PRIMARY']};
                padding: 8px;
                border: none;
            }}
        """
        )
        
        accounts_layout.addWidget(self.accounts_table)
        layout.addWidget(accounts_group)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {c['TEXT_DISABLED']}; font-size: 11px; padding: 5px;")
        layout.addWidget(self.status_label)
        self.loading_overlay = LoadingOverlay(self.accounts_table, "Refreshing risk data…") if LoadingOverlay else None
    
    def refresh_data(self):
        """Refresh risk monitoring data."""
        if not self.risk_monitor:
            self.status_label.setText("Risk monitor not available")
            return
        
        try:
            if self.loading_overlay:
                self.loading_overlay.show_loading("Refreshing risk data…")
            # Get summary
            summary = self.risk_monitor.get_risk_summary()
            
            self.total_accounts_label.setText(f"Total: {summary['total_accounts']}")
            self.safe_label.setText(f"Safe: {summary['safe']}")
            self.low_label.setText(f"Low: {summary['low']}")
            self.medium_label.setText(f"Medium: {summary['medium']}")
            self.high_label.setText(f"High: {summary['high']}")
            self.critical_label.setText(f"Critical: {summary['critical']}")
            self.quarantine_label.setText(f"Quarantine: {summary['quarantine_candidates']}")
            
            # Get all accounts (safe through critical) for filtering
            self.all_accounts = self.risk_monitor.get_high_risk_accounts(RiskLevel.SAFE)
            self._render_accounts(self._apply_filters())
            self.status_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Failed to refresh risk data: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")
        finally:
            if self.loading_overlay:
                self.loading_overlay.hide_loading()

    def _apply_filters(self):
        """Apply search and risk filters to cached accounts."""
        filtered = list(self.all_accounts)
        search_text = self.search_input.text().lower() if hasattr(self, "search_input") else ""
        risk_text = self.risk_filter.currentText().lower() if hasattr(self, "risk_filter") else "all"

        if search_text:
            filtered = [a for a in filtered if search_text in a.phone_number.lower()]

        if risk_text != "all":
            if risk_text == "quarantine":
                filtered = [a for a in filtered if getattr(a, "should_quarantine", False)]
            else:
                try:
                    desired = RiskLevel[risk_text.upper()]
                    filtered = [a for a in filtered if a.risk_level == desired]
                except KeyError:
                    pass
        return filtered

    def _render_accounts(self, accounts):
        """Render the accounts table with chips and empty states."""
        self.accounts_table.setRowCount(0)

        if not accounts:
            c = ThemeManager.get_colors()
            self.accounts_table.setRowCount(1)
            empty_item = QTableWidgetItem("No accounts match the current filters.")
            empty_item.setForeground(QColor(c['TEXT_DISABLED']))
            self.accounts_table.setItem(0, 0, empty_item)
            self.accounts_table.setSpan(0, 0, 1, self.accounts_table.columnCount())
            return

        self.accounts_table.setRowCount(len(accounts))
        for row, account in enumerate(accounts):
            # Phone number
            phone_item = QTableWidgetItem(account.phone_number)
            self.accounts_table.setItem(row, 0, phone_item)
            
            # Risk score with color
            score_item = QTableWidgetItem(f"{account.overall_score:.1f}")
            score_color = self._get_risk_color(account.risk_level)
            score_item.setForeground(score_color)
            self.accounts_table.setItem(row, 1, score_item)
            
            # Risk level pill
            level_pill = QLabel(account.risk_level.value.upper())
            level_pill.setObjectName("status_chip")
            state_map = {
                RiskLevel.SAFE: "ok",
                RiskLevel.LOW: "ok",
                RiskLevel.MEDIUM: "warn",
                RiskLevel.HIGH: "bad",
                RiskLevel.CRITICAL: "bad"
            }
            level_pill.setProperty("state", state_map.get(account.risk_level, "warn"))
            self.accounts_table.setCellWidget(row, 2, level_pill)
            
            # FloodWaits severity pill
            flood_chip = QLabel(str(account.total_floodwaits_24h))
            flood_chip.setObjectName("status_chip")
            flood_chip.setProperty("state", self._severity_state(account.total_floodwaits_24h, [0, 1, 3]))
            self.accounts_table.setCellWidget(row, 3, flood_chip)
            
            # Errors severity pill
            error_chip = QLabel(str(account.total_errors_24h))
            error_chip.setObjectName("status_chip")
            error_chip.setProperty("state", self._severity_state(account.total_errors_24h, [0, 5, 20]))
            self.accounts_table.setCellWidget(row, 4, error_chip)
            
            # Recommendations
            recs = "; ".join(account.recommended_actions[:2])
            recs_item = QTableWidgetItem(recs)
            self.accounts_table.setItem(row, 5, recs_item)

    def _on_filter_change(self):
        """Handle filter change events without refetching data."""
        self._render_accounts(self._apply_filters())
    
    @staticmethod
    def _get_risk_color(risk_level: RiskLevel) -> QColor:
        """Get color for risk level."""
        from ui.theme_manager import ThemeManager
        c = ThemeManager.get_colors()
        colors = {
            RiskLevel.SAFE: QColor(c["ACCENT_SUCCESS"]),      # Green
            RiskLevel.LOW: QColor(c["ACCENT_WARNING"]),       # Yellow
            RiskLevel.MEDIUM: QColor(c["ACCENT_WARNING"]),    # Use warning for medium
            RiskLevel.HIGH: QColor(c["ACCENT_DANGER"]),       # Red
            RiskLevel.CRITICAL: QColor(c["ACCENT_DANGER"])    # Dark red - use danger color
        }
        return colors.get(risk_level, QColor(c["TEXT_SECONDARY"]))

    @staticmethod
    def _severity_state(value: int, thresholds: list[int]) -> str:
        """
        Map integer value to chip state.
        thresholds: [ok_max, warn_max, bad_max] inclusive bands.
        """
        try:
            ok_max, warn_max, bad_max = thresholds
        except Exception:
            return "info"
        if value <= ok_max:
            return "ok"
        if value <= warn_max:
            return "warn"
        if value <= bad_max:
            return "bad"
        return "bad"








