"""
Campaign Analytics Widget - Visualize campaign performance and metrics.

Features:
- Real-time campaign progress tracking
- Message delivery statistics
- Account performance comparison
- Error analysis and reporting
- Success rate trends
"""

import logging
from datetime import datetime
from typing import Dict, List

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)

# Try to import chart components
try:
    from PyQt6.QtCharts import (  # noqa: F401
        QBarCategoryAxis,
        QBarSeries,
        QBarSet,
        QChart,
        QChartView,
        QDateTimeAxis,
        QLineSeries,
        QPieSeries,
        QValueAxis,
    )

    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    logger.warning("PyQt6 Charts not available")


class CampaignSummaryCard(QFrame):
    """Summary card for campaign statistics."""

    def __init__(self, title: str, value: str, subtitle: str = "", color: str = None, parent=None):
        super().__init__(parent)
        if color is None:
            from ui.theme_manager import ThemeManager

            color = ThemeManager.get_color("ACCENT_PRIMARY")
        self.setup_ui(title, value, subtitle, color)

    def setup_ui(self, title: str, value: str, subtitle: str, color: str):
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: palette(base);
                border: 1px solid palette(mid);
                border-radius: 10px;
                border-left: 4px solid {color};
            }}
            QLabel {{ background: transparent; color: palette(text); }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 12, 15, 12)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(title_label)

        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: bold;")
        layout.addWidget(self.value_label)

        if subtitle:
            self.subtitle_label = QLabel(subtitle)
            self.subtitle_label.setStyleSheet("font-size: 10px; color: palette(mid);")
            layout.addWidget(self.subtitle_label)
        else:
            self.subtitle_label = None

    def update_value(self, value: str, subtitle: str = None):
        """Update the card value."""
        self.value_label.setText(value)
        if subtitle and self.subtitle_label:
            self.subtitle_label.setText(subtitle)


class DeliveryRateChart(QWidget):
    """Chart showing message delivery rates over time."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        from ui.theme_manager import ThemeManager

        chart_colors = ThemeManager.get_chart_colors()
        ThemeManager.get_colors()

        if not CHARTS_AVAILABLE:
            label = QLabel("Charts require PyQt6-Charts package")
            label.setStyleSheet(f"color: {chart_colors['text_secondary']}; font-size: 14px;")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            return

        # Create chart
        self.chart = QChart()
        self.chart.setTitle("Delivery Rate Over Time")
        self.chart.setTitleBrush(QColor(chart_colors["text"]))
        self.chart.setBackgroundBrush(QColor(chart_colors["surface"]))
        self.chart.legend().setVisible(True)
        self.chart.legend().setLabelColor(QColor(chart_colors["text_secondary"]))

        # Create chart view
        self.chart_view = QChartView(self.chart)
        self.chart_view.setRenderHint(self.chart_view.renderHints())
        layout.addWidget(self.chart_view)

    def update_data(self, data: List[Dict]):
        """Update chart with new data."""
        if not CHARTS_AVAILABLE:
            return

        self.chart.removeAllSeries()

        from ui.theme_manager import ThemeManager

        chart_colors = ThemeManager.get_chart_colors()

        # Create series for sent and failed
        sent_series = QLineSeries()
        sent_series.setName("Sent")
        sent_series.setColor(QColor(chart_colors["success"]))

        failed_series = QLineSeries()
        failed_series.setName("Failed")
        failed_series.setColor(QColor(chart_colors["danger"]))

        for point in data:
            timestamp = point.get("timestamp", 0)
            sent_series.append(timestamp, point.get("sent", 0))
            failed_series.append(timestamp, point.get("failed", 0))

        self.chart.addSeries(sent_series)
        self.chart.addSeries(failed_series)

        self.chart.createDefaultAxes()


class AccountPerformanceTable(QWidget):
    """Table showing account performance in campaigns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        title = QLabel("📱 Account Performance")
        title.setStyleSheet(f"color: {c['TEXT_BRIGHT']}; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Account", "Messages Sent", "Delivered", "Failed", "Blocked", "Success Rate", "Status"]
        )

        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 7):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

    def update_data(self, accounts: List[Dict]):
        """Update table with account performance data."""
        self.table.setRowCount(len(accounts))

        for row, account in enumerate(accounts):
            # Account phone
            self.table.setItem(row, 0, QTableWidgetItem(account.get("phone", "Unknown")))

            # Messages sent
            sent = account.get("sent", 0)
            self.table.setItem(row, 1, QTableWidgetItem(str(sent)))

            # Delivered
            delivered = account.get("delivered", 0)
            self.table.setItem(row, 2, QTableWidgetItem(str(delivered)))

            from ui.theme_manager import ThemeManager

            c = ThemeManager.get_colors()
            # Failed
            failed = account.get("failed", 0)
            failed_item = QTableWidgetItem(str(failed))
            if failed > 0:
                failed_item.setForeground(QColor(c["ACCENT_DANGER"]))
            self.table.setItem(row, 3, failed_item)

            # Blocked
            blocked = account.get("blocked", 0)
            blocked_item = QTableWidgetItem(str(blocked))
            if blocked > 0:
                blocked_item.setForeground(QColor(c["ACCENT_WARNING"]))
            self.table.setItem(row, 4, blocked_item)

            # Success rate
            if sent > 0:
                rate = (delivered / sent) * 100
            else:
                rate = 0

            rate_item = QTableWidgetItem(f"{rate:.1f}%")
            if rate >= 90:
                rate_item.setForeground(QColor(c["ACCENT_SUCCESS"]))
            elif rate >= 70:
                rate_item.setForeground(QColor(c["ACCENT_WARNING"]))
            else:
                rate_item.setForeground(QColor(c["ACCENT_DANGER"]))
            self.table.setItem(row, 5, rate_item)

            # Status
            status = account.get("status", "unknown")
            status_item = QTableWidgetItem(status.capitalize())
            status_colors = {
                "active": c["ACCENT_SUCCESS"],
                "paused": c["ACCENT_WARNING"],
                "error": c["ACCENT_DANGER"],
                "quarantined": c["ACCENT_DANGER"],
            }
            status_item.setForeground(QColor(status_colors.get(status, c["TEXT_SECONDARY"])))
            self.table.setItem(row, 6, status_item)


class ErrorBreakdownWidget(QWidget):
    """Widget showing breakdown of errors in campaigns."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        title = QLabel("Error Breakdown")
        title.setStyleSheet(f"color: {c['TEXT_BRIGHT']}; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Error list
        self.errors_layout = QVBoxLayout()
        self.errors_container = QWidget()
        self.errors_container.setLayout(self.errors_layout)

        scroll = QScrollArea()
        scroll.setWidget(self.errors_container)
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(200)
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        scroll.setStyleSheet(
            f"""
            QScrollArea {{
                border: none;
                background-color: {c['BG_TERTIARY']};
                border-radius: 8px;
            }}
        """
        )

        layout.addWidget(scroll)

    def update_errors(self, errors: Dict[str, int]):
        """Update error breakdown display."""
        # Clear existing items
        while self.errors_layout.count():
            item = self.errors_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not errors:
            from ui.theme_manager import ThemeManager

            c = ThemeManager.get_colors()
            label = QLabel("No errors recorded")
            label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; padding: 10px;")
            self.errors_layout.addWidget(label)
            return

        total_errors = sum(errors.values())

        # Sort by count
        sorted_errors = sorted(errors.items(), key=lambda x: x[1], reverse=True)

        for error_type, count in sorted_errors:
            error_widget = self._create_error_row(error_type, count, total_errors)
            self.errors_layout.addWidget(error_widget)

        self.errors_layout.addStretch()

    def _create_error_row(self, error_type: str, count: int, total: int) -> QWidget:
        """Create a row for an error type."""
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(10, 5, 10, 5)

        # Error type label
        type_label = QLabel(error_type)
        type_label.setStyleSheet(f"color: {c['TEXT_PRIMARY']}; font-size: 12px;")
        layout.addWidget(type_label)

        layout.addStretch()

        # Count
        count_label = QLabel(str(count))
        count_label.setStyleSheet(
            f"color: {c['ACCENT_DANGER']}; font-size: 12px; font-weight: bold;"
        )
        layout.addWidget(count_label)

        # Percentage
        percent = (count / total) * 100 if total > 0 else 0
        percent_label = QLabel(f"({percent:.1f}%)")
        percent_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 11px;")
        layout.addWidget(percent_label)

        return widget


class CampaignAnalyticsWidget(QWidget):
    """Main campaign analytics widget combining all components."""

    def __init__(self, campaign_manager=None, parent=None):
        super().__init__(parent)
        self.campaign_manager = campaign_manager
        self.selected_campaign_id = None
        self._has_campaigns = False
        self.setup_ui()
        self.setup_timer()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()

        # Header
        header = QHBoxLayout()

        title = QLabel("📈 Campaign Analytics")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['TEXT_BRIGHT']};")
        header.addWidget(title)

        header.addStretch()

        # Empty state (initially hidden)
        self.empty_state_frame = QFrame()
        self.empty_state_frame.setObjectName("empty_state")
        self.empty_state_frame.setStyleSheet(ThemeManager.get_empty_state_style())
        empty_layout = QVBoxLayout(self.empty_state_frame)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        empty_icon = QLabel("📭")
        empty_icon.setObjectName("empty_state_icon")
        empty_icon_font = QFont()
        empty_icon_font.setPointSize(64)
        empty_icon.setFont(empty_icon_font)
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)

        empty_title = QLabel("No Campaigns Yet")
        empty_title.setObjectName("empty_state_title")
        empty_title_font = QFont()
        empty_title_font.setPointSize(20)
        empty_title_font.setBold(True)
        empty_title.setFont(empty_title_font)
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)

        self.empty_desc = QLabel(
            "Create your first campaign to start tracking delivery and engagement metrics."
        )
        self.empty_desc.setObjectName("empty_state_message")
        self.empty_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_desc.setWordWrap(True)
        empty_layout.addWidget(self.empty_desc)

        empty_layout.addStretch()
        self.empty_state_frame.setVisible(False)

        # Campaign selector
        header.addWidget(QLabel("Campaign:"))
        self.campaign_selector = QComboBox()
        self.campaign_selector.setMinimumWidth(200)
        self.campaign_selector.currentIndexChanged.connect(self._on_campaign_selected)
        header.addWidget(self.campaign_selector)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(refresh_btn)

        # Export button
        export_btn = QPushButton("📥 Export")
        export_btn.clicked.connect(self.export_analytics)
        header.addWidget(export_btn)

        layout.addLayout(header)

        # Add empty state widget to layout
        layout.addWidget(self.empty_state_frame)

        # Summary cards
        summary_layout = QHBoxLayout()

        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        self.total_messages_card = CampaignSummaryCard(
            "Total Messages", "0", "Queued + Sent", c["ACCENT_PRIMARY"]
        )
        summary_layout.addWidget(self.total_messages_card)

        self.sent_card = CampaignSummaryCard(
            "Successfully Sent", "0", "Delivered to users", c["ACCENT_SUCCESS"]
        )
        summary_layout.addWidget(self.sent_card)

        self.failed_card = CampaignSummaryCard(
            "Failed", "0", "Could not deliver", c["ACCENT_DANGER"]
        )
        summary_layout.addWidget(self.failed_card)

        self.blocked_card = CampaignSummaryCard(
            "Blocked/Privacy", "0", "User restrictions", c["ACCENT_WARNING"]
        )
        summary_layout.addWidget(self.blocked_card)

        self.success_rate_card = CampaignSummaryCard(
            "Success Rate", "0%", "Overall delivery rate", c["ACCENT_WARNING"]
        )
        summary_layout.addWidget(self.success_rate_card)

        layout.addLayout(summary_layout)

        # Progress bar for active campaign
        progress_group = QGroupBox("Campaign Progress")
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        progress_group.setStyleSheet(
            f"""
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {c['BORDER_DEFAULT']};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                color: {c['TEXT_SECONDARY']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """
        )
        progress_layout = QVBoxLayout(progress_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                border: none;
                border-radius: 5px;
                background-color: {c['BG_PRIMARY']};
                height: 20px;
                text-align: center;
                color: {c['TEXT_BRIGHT']};
            }}
            QProgressBar::chunk {{
                border-radius: 5px;
                background: {c['ACCENT_PRIMARY']};
            }}
        """
        )
        progress_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("0 / 0 messages processed")
        self.progress_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        progress_layout.addWidget(self.progress_label)

        layout.addWidget(progress_group)

        # Tabs for different analytics views
        tabs = QTabWidget()
        tabs.setStyleSheet(
            f"""
            QTabWidget::pane {{
                border: none;
                background-color: transparent;
            }}
            QTabBar::tab {{
                background-color: {c['BG_PRIMARY']};
                color: {c['TEXT_SECONDARY']};
                padding: 10px 20px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }}
            QTabBar::tab:selected {{
                background-color: {c['ACCENT_PRIMARY']};
                color: {c['TEXT_BRIGHT']};
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {c['BG_TERTIARY']};
            }}
        """
        )

        # Account Performance Tab
        self.account_table = AccountPerformanceTable()
        tabs.addTab(self.account_table, "📱 Account Performance")

        # Delivery Chart Tab
        self.delivery_chart = DeliveryRateChart()
        tabs.addTab(self.delivery_chart, "Delivery Trends")

        # Error Breakdown Tab
        self.error_breakdown = ErrorBreakdownWidget()
        tabs.addTab(self.error_breakdown, "Error Analysis")

        # Risk Analysis Tab
        risk_widget = self._create_risk_tab()
        tabs.addTab(risk_widget, "Risk Analysis")

        layout.addWidget(tabs)

        # Status bar
        status_layout = QHBoxLayout()

        self.status_label = QLabel("Select a campaign to view analytics")
        self.status_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.auto_refresh = QCheckBox("Auto-refresh")
        self.auto_refresh.setChecked(True)
        self.auto_refresh.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
        status_layout.addWidget(self.auto_refresh)

        layout.addLayout(status_layout)

    def _create_risk_tab(self) -> QWidget:
        """Create risk analysis tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()

        # Risk report section
        report_group = QGroupBox("Campaign Risk Report")
        report_group.setStyleSheet(
            f"""
            QGroupBox {{
                font-weight: 700;
                border: 0.5px solid {c['BORDER_DEFAULT']};
                border-radius: 10px;
                margin-top: 10px;
                padding: 10px 12px 12px 12px;
                color: {c['TEXT_PRIMARY']};
                background-color: {c['BG_SECONDARY']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
                color: {c['TEXT_SECONDARY']};
            }}
        """
        )
        report_layout = QVBoxLayout(report_group)

        self.risk_text = QLabel("No risk analysis available. Select a campaign.")
        self.risk_text.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; padding: 15px;")
        self.risk_text.setWordWrap(True)
        report_layout.addWidget(self.risk_text)

        layout.addWidget(report_group)

        # Recommendations section
        rec_group = QGroupBox("Recommendations")
        rec_group.setStyleSheet(report_group.styleSheet())
        rec_layout = QVBoxLayout(rec_group)

        self.recommendations_text = QLabel("No recommendations available.")
        self.recommendations_text.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; padding: 15px;")
        self.recommendations_text.setWordWrap(True)
        rec_layout.addWidget(self.recommendations_text)

        layout.addWidget(rec_group)

        layout.addStretch()

        return widget

    def setup_timer(self):
        """Set up auto-refresh timer."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(5000)  # 5 seconds

    def refresh_campaigns_list(self):
        """Refresh the campaign selector dropdown."""
        self.campaign_selector.clear()
        self.campaign_selector.addItem("-- Select Campaign --", None)

        if not self.campaign_manager:
            self._show_empty_state("Campaign manager not available. Check configuration.")
            return

        try:
            campaigns = self.campaign_manager.get_all_campaigns()

            if not campaigns or len(campaigns) == 0:
                self._show_empty_state(
                    "No campaigns created yet. Create your first campaign to see analytics!"
                )
                self._has_campaigns = False
            else:
                self._hide_empty_state()
                self._has_campaigns = True
                for campaign in campaigns:
                    self.campaign_selector.addItem(
                        f"{campaign.name} ({campaign.status.value})", campaign.id
                    )
        except Exception as e:
            logger.error(f"Failed to load campaigns: {e}")
            self._show_empty_state(f"Error loading campaigns: {str(e)[:100]}")

    def _show_empty_state(self, message: str):
        """Show empty state with custom message."""
        self.empty_desc.setText(message)
        self.empty_state_frame.setVisible(True)

        # Hide data widgets
        for child in self.findChildren(QGroupBox):
            if child != self.empty_state_frame:
                child.setVisible(False)

    def _hide_empty_state(self):
        """Hide empty state and show data widgets."""
        self.empty_state_frame.setVisible(False)

        # Show data widgets
        for child in self.findChildren(QGroupBox):
            child.setVisible(True)

    def _on_campaign_selected(self, index: int):
        """Handle campaign selection."""
        campaign_id = self.campaign_selector.itemData(index)
        self.selected_campaign_id = campaign_id
        self.refresh_data()

    def refresh_data(self):
        """Refresh analytics data."""
        if not self.auto_refresh.isChecked():
            return

        if not self.selected_campaign_id or not self.campaign_manager:
            return

        try:
            # Get campaign data
            campaign = self.campaign_manager.get_campaign(self.selected_campaign_id)
            if not campaign:
                return

            # Update summary cards
            total = campaign.total_targets
            sent = campaign.sent_count
            failed = campaign.failed_count
            blocked = campaign.blocked_count

            self.total_messages_card.update_value(str(total))
            self.sent_card.update_value(str(sent))
            self.failed_card.update_value(str(failed))
            self.blocked_card.update_value(str(blocked))

            # Calculate success rate
            processed = sent + failed + blocked
            if processed > 0:
                success_rate = (sent / processed) * 100
                self.success_rate_card.update_value(f"{success_rate:.1f}%")
            else:
                self.success_rate_card.update_value("0%")

            # Update progress bar
            if total > 0:
                progress = int((processed / total) * 100)
                self.progress_bar.setValue(progress)
                self.progress_label.setText(f"{processed} / {total} messages processed")

            # Update account performance table
            account_stats = self._get_account_stats(self.selected_campaign_id)
            self.account_table.update_data(account_stats)

            # Update error breakdown
            error_stats = self._get_error_stats(self.selected_campaign_id)
            self.error_breakdown.update_errors(error_stats)

            # Update risk analysis
            self._update_risk_analysis(self.selected_campaign_id)

            self.status_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"Failed to refresh analytics: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")

    def _get_account_stats(self, campaign_id: int) -> List[Dict]:
        """Get account statistics for a campaign."""
        if not self.campaign_manager:
            return []

        try:
            campaign = self.campaign_manager.get_campaign(campaign_id)
            if not campaign:
                return []

            stats = []
            for phone in campaign.account_ids:
                # Get stats from rate limiters or database
                limiter = self.campaign_manager.rate_limiters.get(phone, {})

                account_stat = {
                    "phone": phone,
                    "sent": limiter.get("messages_sent", 0),
                    "delivered": limiter.get("messages_sent", 0),  # Would track separately
                    "failed": 0,
                    "blocked": 0,
                    "status": "active",
                }
                stats.append(account_stat)

            return stats

        except Exception as e:
            logger.error(f"Failed to get account stats: {e}")
            return []

    def _get_error_stats(self, campaign_id: int) -> Dict[str, int]:
        """Get error statistics for a campaign."""
        # This would query the message records for error types
        # For now, return sample data
        return {
            "UserPrivacyRestricted": 0,
            "UserBlocked": 0,
            "FloodWait": 0,
            "PeerIdInvalid": 0,
            "Other": 0,
        }

    def _update_risk_analysis(self, campaign_id: int):
        """Update risk analysis display."""
        if not self.campaign_manager:
            return

        try:
            # Get risk report from campaign manager
            report = self.campaign_manager.get_campaign_risk_report(campaign_id)

            if "error" in report:
                self.risk_text.setText(report["error"])
                return

            # Build risk text
            from ui.theme_manager import ThemeManager

            c = ThemeManager.get_colors()
            risk_level = report.get("overall_risk", "unknown")
            risk_colors = {
                "low": c["ACCENT_SUCCESS"],
                "high": c["ACCENT_WARNING"],
                "critical": c["ACCENT_DANGER"],
            }

            risk_html = f"""
            <p style="color: {risk_colors.get(risk_level, c['TEXT_SECONDARY'])}; font-size: 14px; font-weight: bold;">
                Overall Risk: {risk_level.upper()}
            </p>
            <p style="color: {c['TEXT_SECONDARY']}; font-size: 12px;">
                Accounts monitored: {len(report.get('accounts', []))}
            </p>
            """

            # Add high risk accounts
            high_risk = [
                a for a in report.get("accounts", []) if a.get("risk_level") in ["high", "critical"]
            ]
            if high_risk:
                risk_html += f"""
                <p style="color: {c['ACCENT_DANGER']}; font-size: 12px;">
                    {len(high_risk)} accounts at high risk
                </p>
                """

            self.risk_text.setText(risk_html)

            # Update recommendations
            recommendations = report.get("recommendations", [])
            if recommendations:
                rec_html = f"<ul style='color: {c['TEXT_SECONDARY']};'>"
                for rec in recommendations:
                    rec_html += f"<li>{rec}</li>"
                rec_html += "</ul>"
                self.recommendations_text.setText(rec_html)
            else:
                self.recommendations_text.setText("No recommendations - campaign is healthy")

        except Exception as e:
            logger.error(f"Failed to get risk analysis: {e}")
            self.risk_text.setText(f"Error getting risk analysis: {e}")

    def export_analytics(self):
        """Export analytics to file."""
        if not self.selected_campaign_id:
            QMessageBox.information(self, "No Campaign", "Please select a campaign first.")
            return

        try:
            from PyQt6.QtWidgets import QFileDialog, QInputDialog

            from utils.export_manager import get_export_manager

            # Ask for format
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
            default_name = f"campaign_{self.selected_campaign_id}_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Campaign Analytics", default_name, filter_str
            )

            if not file_path:
                return

            # Perform export
            exporter = get_export_manager()

            if ext == ".csv":
                success = exporter.export_campaign_analytics_to_csv(
                    self.selected_campaign_id, file_path
                )
            else:
                # For JSON, use campaign export
                success = exporter.export_campaigns_to_json(file_path, include_messages=True)

            if success:
                QMessageBox.information(
                    self, "Export Successful", f"Campaign analytics exported to:\n{file_path}"
                )
            else:
                QMessageBox.warning(self, "Export Failed", "No data found for export.")

        except Exception as e:
            logger.error(f"Failed to export analytics: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export analytics:\n{str(e)}")

    def showEvent(self, event):
        """Called when widget is shown."""
        super().showEvent(event)
        self.refresh_campaigns_list()
