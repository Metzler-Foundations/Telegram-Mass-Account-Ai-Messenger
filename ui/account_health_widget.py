"""
Account Health Dashboard Widget - Monitor account status and ban risk.

Features:
- Real-time account health monitoring
- Ban risk visualization
- Quarantine management
- Account metrics display
- Connection status tracking
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.error_handler import ErrorHandler
from ui.theme_manager import ThemeManager

try:
    from ui.ui_components import LoadingOverlay
except ImportError:
    LoadingOverlay = None

logger = logging.getLogger(__name__)

# Try to import chart components (optional)
try:
    from PyQt6.QtCharts import (  # noqa: F401
        QBarCategoryAxis,
        QBarSeries,
        QBarSet,
        QChart,
        QChartView,
        QPieSeries,
        QValueAxis,
    )

    CHARTS_AVAILABLE = True
except ImportError:
    CHARTS_AVAILABLE = False
    logger.info("PyQt6.QtCharts not available - charts will be disabled")

# Try to import enhanced anti-detection
try:
    from anti_detection.anti_detection_system import (
        AccountRiskMetrics,  # noqa: F401
        BanRiskLevel,  # noqa: F401
        EnhancedAntiDetectionSystem,
        QuarantineReason,  # noqa: F401
    )

    ANTI_DETECTION_AVAILABLE = True
except ImportError:
    ANTI_DETECTION_AVAILABLE = False
    logger.warning("Enhanced anti-detection not available")


class RiskGaugeWidget(QWidget):
    """Custom widget showing risk level as a gauge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.risk_value = 0.0
        self.setMinimumSize(150, 150)

    def set_risk(self, value: float):
        """Set risk value (0.0 - 1.0)."""
        self.risk_value = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, event):
        """Custom paint for gauge."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate dimensions
        size = min(self.width(), self.height()) - 20
        x = (self.width() - size) // 2
        y = (self.height() - size) // 2

        c = ThemeManager.get_colors()
        # Draw background arc
        pen = QPen(QColor(c["BORDER_DEFAULT"]), 10)
        painter.setPen(pen)
        painter.drawArc(x, y, size, size, 30 * 16, 120 * 16)

        # Draw risk arc
        if self.risk_value < 0.3:
            color = QColor(c["ACCENT_SUCCESS"])  # Green
        elif self.risk_value < 0.5:
            color = QColor(c["ACCENT_WARNING"])  # Yellow
        elif self.risk_value < 0.7:
            # Use warning for moderate-high risk
            color = QColor(c["ACCENT_WARNING"])
        else:
            color = QColor(c["ACCENT_DANGER"])  # Red

        pen = QPen(color, 10)
        painter.setPen(pen)

        # Draw arc based on risk value
        arc_angle = int(120 * self.risk_value * 16)
        painter.drawArc(x, y, size, size, 150 * 16, -arc_angle)

        # Draw center text
        painter.setPen(QColor(c["TEXT_BRIGHT"]))
        font = QFont()
        font.setPointSize(18)
        font.setBold(True)
        painter.setFont(font)

        risk_percent = int(self.risk_value * 100)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{risk_percent}%")

        # Draw label
        font.setPointSize(10)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(c["TEXT_SECONDARY"]))

        label_rect = self.rect().adjusted(0, 40, 0, 0)
        painter.drawText(
            label_rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, "Ban Risk"
        )


class AccountHealthCard(QFrame):
    """Individual account health card."""

    action_requested = pyqtSignal(str, str)  # phone, action

    def __init__(self, account_data: Dict, parent=None):
        super().__init__(parent)
        self.account_data = account_data
        self.phone_number = account_data.get("phone_number", "Unknown")
        self.setup_ui()

    def setup_ui(self):
        c = ThemeManager.get_colors()
        self.setStyleSheet(
            f"""
            QFrame {{
                background-color: {c['BG_TERTIARY']};
                border-radius: 12px;
                border: 1px solid {c['BORDER_DEFAULT']};
            }}
            QFrame:hover {{
                border: 1px solid {c['ACCENT_PRIMARY']};
            }}
        """
        )
        self.setMinimumWidth(240)
        self.setMaximumWidth(360)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header = QHBoxLayout()

        # Status indicator
        c = ThemeManager.get_colors()
        status = self.account_data.get("status", "unknown")
        status_colors = {
            "ready": c["ACCENT_SUCCESS"],
            "connected": c["ACCENT_SUCCESS"],
            "warming_up": c["ACCENT_WARNING"],
            "suspended": c["ACCENT_WARNING"],  # Use warning color
            "error": c["ACCENT_DANGER"],
            "banned": c["ACCENT_DANGER"],
        }
        indicator = QLabel("●")
        indicator.setStyleSheet(
            f"color: {status_colors.get(status, c['TEXT_SECONDARY'])}; font-size: 16px;"
        )
        header.addWidget(indicator)

        # Phone number
        phone_label = QLabel(self.phone_number)
        phone_label.setStyleSheet(f"color: {c['TEXT_BRIGHT']}; font-size: 14px; font-weight: bold;")
        header.addWidget(phone_label)

        header.addStretch()

        # Online indicator
        if self.account_data.get("is_online"):
            online_label = QLabel("Online")
            online_label.setStyleSheet(
                f"color: {c['ACCENT_SUCCESS']}; font-size: 12px; font-weight: 600;"
            )
        else:
            online_label = QLabel("Offline")
            online_label.setStyleSheet(
                f"color: {c['TEXT_DISABLED']}; font-size: 12px; font-weight: 600;"
            )
        header.addWidget(online_label)

        layout.addLayout(header)

        # Status / risk chips
        chips_row = QHBoxLayout()
        status_chip = self._create_chip(
            status.capitalize(),
            {
                "ready": "ok",
                "connected": "ok",
                "warming_up": "warn",
                "suspended": "warn",
                "error": "bad",
                "banned": "bad",
            }.get(status, "info"),
        )
        chips_row.addWidget(status_chip)

        risk_level = self.account_data.get("risk_level", "safe")
        risk_chip = self._create_chip(
            risk_level.upper(),
            {
                "safe": "ok",
                "low": "ok",
                "moderate": "warn",
                "medium": "warn",
                "high": "bad",
                "critical": "bad",
                "quarantined": "bad",
            }.get(risk_level, "warn"),
        )
        chips_row.addWidget(risk_chip)
        chips_row.addStretch()
        layout.addLayout(chips_row)

        # Risk Level
        c = ThemeManager.get_colors()
        risk_layout = QHBoxLayout()
        risk_label = QLabel("Risk Level:")
        risk_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 12px;")
        risk_layout.addWidget(risk_label)

        risk_colors = {
            "safe": c["ACCENT_SUCCESS"],
            "low": c["ACCENT_SUCCESS"],
            "moderate": c["ACCENT_WARNING"],
            "high": c["ACCENT_WARNING"],
            "critical": c["ACCENT_DANGER"],
            "quarantined": c["ACCENT_DANGER"],
        }
        risk_level = self.account_data.get("risk_level", "safe")
        risk_value = QLabel(risk_level.upper())
        risk_value.setStyleSheet(
            f"color: {risk_colors.get(risk_level, c['TEXT_SECONDARY'])}; "
            f"font-size: 12px; font-weight: bold;"
        )
        risk_layout.addWidget(risk_value)

        risk_layout.addStretch()

        # Ban probability
        ban_prob = self.account_data.get("ban_probability", 0.0)
        prob_label = QLabel(f"Ban: {int(ban_prob * 100)}%")
        prob_label.setStyleSheet(
            f"color: {risk_colors.get(risk_level, c['TEXT_SECONDARY'])}; font-size: 12px;"
        )
        risk_layout.addWidget(prob_label)

        layout.addLayout(risk_layout)

        # Progress bar for ban probability
        self.risk_bar = QProgressBar()
        self.risk_bar.setRange(0, 100)
        self.risk_bar.setValue(int(ban_prob * 100))
        self.risk_bar.setTextVisible(False)
        self.risk_bar.setMaximumHeight(6)
        c = ThemeManager.get_colors()
        self.risk_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: {c['BG_PRIMARY']};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {risk_colors.get(risk_level, c['TEXT_SECONDARY'])};
                border-radius: 3px;
            }}
        """
        )
        layout.addWidget(self.risk_bar)

        # Metrics
        metrics_layout = QGridLayout()
        metrics_layout.setSpacing(8)

        # Messages sent
        metrics_layout.addWidget(
            self._create_metric("Sent 24h", str(self.account_data.get("messages_sent_24h", 0))),
            0,
            0,
        )

        # Errors
        metrics_layout.addWidget(
            self._create_metric("Errors", str(self.account_data.get("errors_24h", 0))), 0, 1
        )

        # Diversity score
        diversity = self.account_data.get("message_diversity", 1.0)
        metrics_layout.addWidget(self._create_metric("Diversity", f"{diversity:.0%}"), 1, 0)

        # Last activity
        last_activity = self.account_data.get("last_activity", "Never")
        if isinstance(last_activity, str):
            activity_str = last_activity[:10] if len(last_activity) > 10 else last_activity
        else:
            activity_str = last_activity.strftime("%H:%M") if last_activity else "Never"
        metrics_layout.addWidget(self._create_metric("🕐 Activity", activity_str), 1, 1)

        layout.addLayout(metrics_layout)

        # Actions
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(5)

        c = ThemeManager.get_colors()
        if self.account_data.get("is_quarantined"):
            release_btn = QPushButton("🔓 Release")
            release_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {c['ACCENT_SUCCESS']};
                    color: {c['TEXT_BRIGHT']};
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {c['ACCENT_SUCCESS']};
                    opacity: 0.9;
                }}
            """
            )
            release_btn.clicked.connect(
                lambda: self.action_requested.emit(self.phone_number, "release")
            )
            actions_layout.addWidget(release_btn)
        else:
            pause_btn = QPushButton("⏸️ Pause")
            pause_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {c['ACCENT_WARNING']};
                    color: {c['TEXT_BRIGHT']};
                    border: none;
                    border-radius: 4px;
                    padding: 5px 10px;
                    font-size: 11px;
                }}
                QPushButton:hover {{
                    background-color: {c['ACCENT_WARNING']};
                    opacity: 0.9;
                }}
            """
            )
            pause_btn.clicked.connect(
                lambda: self.action_requested.emit(self.phone_number, "pause")
            )
            actions_layout.addWidget(pause_btn)

        details_btn = QPushButton("📋 Details")
        details_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {c['ACCENT_PRIMARY']};
                color: {c['TEXT_BRIGHT']};
                border: none;
                border-radius: 4px;
                padding: 5px 10px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                background-color: {c['ACCENT_PRIMARY']};
                opacity: 0.9;
            }}
        """
        )
        details_btn.clicked.connect(
            lambda: self.action_requested.emit(self.phone_number, "details")
        )
        actions_layout.addWidget(details_btn)

        layout.addLayout(actions_layout)

    def _create_metric(self, label: str, value: str) -> QWidget:
        """Create a metric display widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        c = ThemeManager.get_colors()
        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 10px;")
        layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet(
            f"color: {c['TEXT_BRIGHT']}; font-size: 12px; font-weight: bold;"
        )
        layout.addWidget(value_widget)

        return widget

    def _create_chip(self, text: str, state: str) -> QLabel:
        """Create a status/risk chip with Aurora styling."""
        chip = QLabel(text)
        chip.setObjectName("status_chip")
        chip.setProperty("state", state)
        chip.setStyleSheet("padding: 4px 10px; border-radius: 10px;")
        return chip

    def update_data(self, data: Dict):
        """Update card with new data."""
        self.account_data = data
        # Would need to update individual widgets here


class AccountHealthDashboard(QWidget):
    """Main account health dashboard widget."""

    def __init__(self, account_manager=None, parent=None):
        super().__init__(parent)
        self.account_manager = account_manager
        self.anti_detection = None
        self.accounts_cache: List[Dict[str, Any]] = []

        # Pagination state
        self.current_page = 1
        self.page_size = 30  # Show 30 accounts per page (10 rows x 3 cols)
        self.total_accounts_filtered = 0

        if ANTI_DETECTION_AVAILABLE:
            try:
                self.anti_detection = EnhancedAntiDetectionSystem()
            except Exception as e:
                logger.warning(f"Failed to init anti-detection: {e}")

        self.setup_ui()
        self.setup_timer()
        self.loading_overlay = (
            LoadingOverlay(self, "Refreshing account health…") if LoadingOverlay else None
        )

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        c = ThemeManager.get_colors()
        # Title
        title = QLabel("Account Health Dashboard")
        title.setStyleSheet(f"font-size: 20px; font-weight: bold; color: {c['TEXT_BRIGHT']};")
        layout.addWidget(title)

        # Summary Stats
        stats_layout = QHBoxLayout()

        # Total accounts
        self.total_accounts_card = self._create_summary_card(
            "Total Accounts", "0", c["ACCENT_PRIMARY"]
        )
        stats_layout.addWidget(self.total_accounts_card)

        # Healthy accounts
        self.healthy_accounts_card = self._create_summary_card("Healthy", "0", c["ACCENT_SUCCESS"])
        stats_layout.addWidget(self.healthy_accounts_card)

        # At risk accounts
        self.at_risk_card = self._create_summary_card("At Risk", "0", c["ACCENT_WARNING"])
        stats_layout.addWidget(self.at_risk_card)

        # Quarantined accounts
        self.quarantined_card = self._create_summary_card("Quarantined", "0", c["ACCENT_DANGER"])
        stats_layout.addWidget(self.quarantined_card)

        # Overall risk gauge
        self.risk_gauge = RiskGaugeWidget()
        stats_layout.addWidget(self.risk_gauge)

        layout.addLayout(stats_layout)

        # Filter and actions bar
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search phone number…")
        self.search_input.setAccessibleName("Account search")
        self.search_input.textChanged.connect(self.refresh_accounts)
        filter_layout.addWidget(self.search_input)

        filter_layout.addWidget(QLabel("Risk:"))
        self.risk_filter = QComboBox()
        self.risk_filter.addItems(
            ["All Risks", "Safe", "Low", "Moderate", "High", "Critical", "Quarantined"]
        )
        self.risk_filter.setAccessibleName("Risk filter")
        self.risk_filter.currentTextChanged.connect(self.refresh_accounts)
        filter_layout.addWidget(self.risk_filter)

        filter_layout.addStretch()

        # Bulk actions
        self.pause_all_btn = QPushButton("⏸️ Pause All At Risk")
        self.pause_all_btn.clicked.connect(self.pause_all_at_risk)
        filter_layout.addWidget(self.pause_all_btn)

        self.release_all_btn = QPushButton("🔓 Release All")
        self.release_all_btn.clicked.connect(self.release_all_quarantined)
        filter_layout.addWidget(self.release_all_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        filter_layout.addWidget(self.refresh_btn)

        layout.addLayout(filter_layout)

        # Pagination controls
        pagination_layout = QHBoxLayout()

        c = ThemeManager.get_colors()
        self.page_info_label = QLabel("Showing 0-0 of 0")
        self.page_info_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
        pagination_layout.addWidget(self.page_info_label)

        pagination_layout.addStretch()

        self.first_page_btn = QPushButton("First")
        self.first_page_btn.clicked.connect(self.first_page)
        pagination_layout.addWidget(self.first_page_btn)

        self.prev_page_btn = QPushButton("Previous")
        self.prev_page_btn.clicked.connect(self.prev_page)
        pagination_layout.addWidget(self.prev_page_btn)

        self.page_label = QLabel("Page 1")
        self.page_label.setStyleSheet(
            f"color: {c['TEXT_BRIGHT']}; font-weight: bold; margin: 0 10px;"
        )
        pagination_layout.addWidget(self.page_label)

        self.next_page_btn = QPushButton("Next")
        self.next_page_btn.clicked.connect(self.next_page)
        pagination_layout.addWidget(self.next_page_btn)

        self.last_page_btn = QPushButton("Last")
        self.last_page_btn.clicked.connect(self.last_page)
        pagination_layout.addWidget(self.last_page_btn)

        layout.addLayout(pagination_layout)

        # Account cards scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background-color: transparent;
            }
        """
        )

        self.cards_container = QWidget()
        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setSpacing(15)

        scroll.setWidget(self.cards_container)
        layout.addWidget(scroll)

        c = ThemeManager.get_colors()
        # Status bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.auto_refresh = QCheckBox("Auto-refresh")
        self.auto_refresh.setChecked(True)
        self.auto_refresh.setStyleSheet(f"color: {c['TEXT_SECONDARY']};")
        status_layout.addWidget(self.auto_refresh)

        layout.addLayout(status_layout)

    def _create_summary_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a summary statistic card."""
        c = ThemeManager.get_colors()
        frame = QFrame()
        frame.setStyleSheet(
            f"""
            QFrame {{
                background-color: {c['BG_TERTIARY']};
                border-radius: 10px;
                border-left: 4px solid {color};
                min-width: 120px;
            }}
        """
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 10, 15, 10)

        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 11px;")
        layout.addWidget(title_label)

        value_label = QLabel(value)
        value_label.setObjectName("value")
        value_label.setStyleSheet(f"color: {color}; font-size: 20px; font-weight: bold;")
        layout.addWidget(value_label)

        return frame

    def _update_summary_card(self, card: QFrame, value: str):
        """Update a summary card's value."""
        label = card.findChild(QLabel, "value")
        if label:
            label.setText(value)

    def setup_timer(self):
        """Set up auto-refresh timer."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(10000)  # 10 seconds

    def refresh_data(self):
        """Refresh all data."""
        if not self.auto_refresh.isChecked():
            return

        if not ANTI_DETECTION_AVAILABLE and not self.account_manager:
            self.status_label.setText("Risk monitoring unavailable (anti-detection module missing)")
            return
        try:
            if self.loading_overlay:
                self.loading_overlay.show_loading("Refreshing account health…")
            accounts = self._get_account_data()
            self.accounts_cache = accounts
            self._update_summary(accounts)
            self.refresh_accounts()
            self.status_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
        except Exception as exc:
            logger.error(f"Failed to refresh account health: {exc}")
            self.status_label.setText(f"Error: {str(exc)[:60]}")
        finally:
            if self.loading_overlay:
                self.loading_overlay.hide_loading()

    def _get_account_data(self) -> List[Dict]:
        """Get account data from account manager."""
        if not self.account_manager:
            return []

        accounts = []

        try:
            for phone in self.account_manager.accounts.keys():
                status = self.account_manager.account_status.get(phone, {})
                metrics = self.account_manager.account_metrics.get(phone)

                account_data = {
                    "phone_number": phone,
                    "status": status.get("status", "unknown"),
                    "is_online": status.get("is_online", False),
                    "risk_level": "safe",
                    "ban_probability": 0.0,
                    "messages_sent_24h": 0,
                    "errors_24h": 0,
                    "message_diversity": 1.0,
                    "last_activity": status.get("last_seen"),
                    "is_quarantined": False,
                }

                # Get risk data from anti-detection
                if self.anti_detection:
                    try:
                        ad_status = self.anti_detection.get_account_status(phone)
                        account_data["risk_level"] = ad_status.get("risk_level", "safe")
                        account_data["ban_probability"] = ad_status.get("ban_probability", 0.0)
                        account_data["message_diversity"] = ad_status.get(
                            "message_diversity_score", 1.0
                        )
                        account_data["is_quarantined"] = ad_status.get("is_quarantined", False)
                        account_data["messages_sent_24h"] = ad_status.get("messages_sent_24h", 0)
                    except Exception as e:
                        logger.debug(f"Failed to get anti-detection status for {phone}: {e}")

                # Get metrics
                if metrics:
                    account_data["messages_sent_24h"] = metrics.messages_sent
                    account_data["errors_24h"] = metrics.errors_count

                accounts.append(account_data)

        except Exception as e:
            logger.error(f"Failed to get account data: {e}")

        return accounts

    def _update_summary(self, accounts: List[Dict]):
        """Update summary statistics."""
        total = len(accounts)
        healthy = sum(1 for a in accounts if a.get("risk_level") in ["safe", "low"])
        at_risk = sum(1 for a in accounts if a.get("risk_level") in ["moderate", "high"])
        quarantined = sum(1 for a in accounts if a.get("is_quarantined"))

        self._update_summary_card(self.total_accounts_card, str(total))
        self._update_summary_card(self.healthy_accounts_card, str(healthy))
        self._update_summary_card(self.at_risk_card, str(at_risk))
        self._update_summary_card(self.quarantined_card, str(quarantined))

        # Calculate overall risk
        if total > 0:
            avg_risk = sum(a.get("ban_probability", 0) for a in accounts) / total
            self.risk_gauge.set_risk(avg_risk)
        else:
            self.risk_gauge.set_risk(0)

    def refresh_accounts(self):
        """Refresh account cards display with pagination."""
        # Clear existing cards
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        accounts = self.accounts_cache or self._get_account_data()

        # Apply search filter
        search_text = self.search_input.text().lower() if hasattr(self, "search_input") else ""
        if search_text:
            accounts = [
                a
                for a in accounts
                if search_text in str(a.get("phone_number", "")).lower()
                or search_text in str(a.get("status", "")).lower()
            ]

        # Apply risk filter
        filter_text = (
            self.risk_filter.currentText().lower() if hasattr(self, "risk_filter") else "all"
        )
        if filter_text != "all risks":
            if filter_text == "safe":
                accounts = [a for a in accounts if a.get("risk_level") in ["safe"]]
            elif filter_text == "low":
                accounts = [a for a in accounts if a.get("risk_level") in ["low"]]
            elif filter_text in ["moderate", "medium", "med"]:
                accounts = [a for a in accounts if a.get("risk_level") in ["moderate", "medium"]]
            elif filter_text == "high":
                accounts = [a for a in accounts if a.get("risk_level") == "high"]
            elif filter_text == "critical":
                accounts = [a for a in accounts if a.get("risk_level") == "critical"]
            elif filter_text == "quarantined":
                accounts = [a for a in accounts if a.get("is_quarantined")]

        # Store total for pagination
        self.total_accounts_filtered = len(accounts)

        # Apply pagination
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = start_idx + self.page_size
        paginated_accounts = accounts[start_idx:end_idx]

        # Empty state
        if not paginated_accounts:
            from ui.theme_manager import ThemeManager

            empty_frame = QFrame()
            empty_frame.setObjectName("empty_state")
            empty_frame.setStyleSheet(ThemeManager.get_empty_state_style())
            empty_layout = QVBoxLayout(empty_frame)
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            empty_icon = QLabel("📋")
            empty_icon.setObjectName("empty_state_icon")
            empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(empty_icon)

            empty_title = QLabel("No Accounts Found")
            empty_title.setObjectName("empty_state_title")
            empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(empty_title)

            empty_msg = QLabel("No accounts match the current filters.")
            empty_msg.setObjectName("empty_state_message")
            empty_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.addWidget(empty_msg)

            self.cards_layout.addWidget(empty_frame, 0, 0, 1, 3)
            self.update_pagination_controls()
            return

        # Create cards
        cols = 3
        for i, account in enumerate(paginated_accounts):
            card = AccountHealthCard(account)
            card.action_requested.connect(self._handle_account_action)

            row = i // cols
            col = i % cols
            self.cards_layout.addWidget(card, row, col)

        # Update pagination controls
        self.update_pagination_controls()

    def update_pagination_controls(self):
        """Update pagination control states and labels."""
        total_pages = (
            (self.total_accounts_filtered + self.page_size - 1) // self.page_size
            if self.page_size > 0
            else 1
        )

        # Update labels
        if self.total_accounts_filtered == 0:
            start_idx = 0
            end_idx = 0
        else:
            start_idx = (self.current_page - 1) * self.page_size + 1
            end_idx = min(self.current_page * self.page_size, self.total_accounts_filtered)
        self.page_info_label.setText(
            f"Showing {start_idx}-{end_idx} of {self.total_accounts_filtered}"
        )
        self.page_label.setText(f"Page {self.current_page} of {total_pages}")

        # Enable/disable buttons
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        self.last_page_btn.setEnabled(self.current_page < total_pages)

    def first_page(self):
        """Go to first page."""
        self.current_page = 1
        self.refresh_accounts()

    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_accounts()

    def next_page(self):
        """Go to next page."""
        total_pages = (self.total_accounts_filtered + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_accounts()

    def last_page(self):
        """Go to last page."""
        total_pages = (self.total_accounts_filtered + self.page_size - 1) // self.page_size
        if total_pages > 0:
            self.current_page = total_pages
            self.refresh_accounts()

    def _handle_account_action(self, phone: str, action: str):
        """Handle action requested from account card."""
        if action == "release":
            self._release_account(phone)
        elif action == "pause":
            self._pause_account(phone)
        elif action == "details":
            self._show_account_details(phone)

    def _release_account(self, phone: str):
        """Release account from quarantine."""
        if self.anti_detection:
            try:
                self.anti_detection.quarantine_manager.release_account(phone)
                ErrorHandler.safe_information(
                    self, "Success", f"Account {phone} released from quarantine."
                )
                self.refresh_data()
            except Exception as e:
                ErrorHandler.safe_critical(self, "Error", f"Failed to release account: {e}")

    def _pause_account(self, phone: str):
        """Pause/quarantine an account."""
        if self.anti_detection:
            try:
                from anti_detection.anti_detection_system import (  # noqa: F811
                    QuarantineReason,
                )

                self.anti_detection.quarantine_account(phone, QuarantineReason.MANUAL, 60)
                ErrorHandler.safe_information(
                    self, "Success", f"Account {phone} paused for 60 minutes."
                )
                self.refresh_data()
            except Exception as e:
                ErrorHandler.safe_critical(self, "Error", f"Failed to pause account: {e}")

    def _show_account_details(self, phone: str):
        """Show detailed account information."""
        ErrorHandler.safe_information(
            self,
            "Account Details",
            f"Showing details for {phone}\n(Full dialog would be implemented here)",
        )

    def pause_all_at_risk(self):
        """Pause all at-risk accounts."""
        accounts = self._get_account_data()
        at_risk = [a for a in accounts if a.get("risk_level") in ["high", "critical"]]

        if not at_risk:
            ErrorHandler.safe_information(
                self, "No At-Risk Accounts", "No accounts are currently at high risk."
            )
            return

        if ErrorHandler.safe_question(
            self, "Confirm Pause", f"This will pause {len(at_risk)} at-risk accounts. Continue?"
        ):
            for account in at_risk:
                self._pause_account(account["phone_number"])
            self.refresh_data()

    def release_all_quarantined(self):
        """Release all quarantined accounts."""
        accounts = self._get_account_data()
        quarantined = [a for a in accounts if a.get("is_quarantined")]

        if not quarantined:
            ErrorHandler.safe_information(
                self, "No Quarantined Accounts", "No accounts are currently quarantined."
            )
            return

        if ErrorHandler.safe_question(
            self,
            "Confirm Release",
            f"This will release {len(quarantined)} quarantined accounts. Continue?",
        ):
            for account in quarantined:
                self._release_account(account["phone_number"])
            self.refresh_data()

    def showEvent(self, event):
        """Called when widget is shown."""
        super().showEvent(event)
        self.refresh_data()
