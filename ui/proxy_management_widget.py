"""
Proxy Management Widget - UI for managing the proxy pool.

Features:
- Real-time proxy pool statistics
- Proxy health monitoring
- Manual proxy testing
- Endpoint configuration
- Auto-refresh with configurable intervals
"""

import asyncio
import logging
import re
import socket
import time
from typing import Dict, List, Optional, Any
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
    QHeaderView,
    QGroupBox,
    QProgressBar,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QTabWidget,
    QFrame,
    QGridLayout,
    QMessageBox,
    QSplitter,
    QTextEdit,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont

from core.error_handler import ErrorHandler
from ui.theme_manager import ThemeManager

logger = logging.getLogger(__name__)

try:
    from ui.ui_components import LoadingOverlay
except ImportError:
    LoadingOverlay = None

# Try to import ProxyPoolManager
try:
    from proxy.proxy_pool_manager import (
        ProxyPoolManager,
        get_proxy_pool_manager,
        ProxyStatus,
        ProxyTier,
        Proxy,
    )

    PROXY_POOL_AVAILABLE = True
except ImportError:
    PROXY_POOL_AVAILABLE = False
    logger.warning("ProxyPoolManager not available")


class ProxyStatsWidget(QWidget):
    """Widget showing proxy pool statistics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QGridLayout(self)
        layout.setSpacing(15)

        # Colors from palette
        c = ThemeManager._get_palette()

        # Total Proxies Card
        self.total_card = self._create_stat_card("Total Proxies", "0", c["ACCENT_PRIMARY"])
        layout.addWidget(self.total_card, 0, 0)

        # Active Proxies Card
        self.active_card = self._create_stat_card("Active", "0", c["ACCENT_SUCCESS"])
        layout.addWidget(self.active_card, 0, 1)

        # Available Proxies Card
        self.available_card = self._create_stat_card("Available", "0", c["ACCENT_WARNING"])
        layout.addWidget(self.available_card, 0, 2)

        # Assigned Proxies Card
        self.assigned_card = self._create_stat_card("Assigned", "0", c["ACCENT_PRIMARY"])
        layout.addWidget(self.assigned_card, 0, 3)

        # Average Latency Card
        self.latency_card = self._create_stat_card("Avg Latency", "0 ms", c["ACCENT_DANGER"])
        layout.addWidget(self.latency_card, 1, 0)

        # Average Score Card
        self.score_card = self._create_stat_card("Avg Score", "0", c["ACCENT_SUCCESS"])
        layout.addWidget(self.score_card, 1, 1)

        # Endpoints Card
        self.endpoints_card = self._create_stat_card("Endpoints", "15", c["ACCENT_DANGER"])
        layout.addWidget(self.endpoints_card, 1, 2)

        # Last Poll Card
        self.poll_card = self._create_stat_card("Last Poll", "Never", c["ACCENT_PRIMARY"])
        layout.addWidget(self.poll_card, 1, 3)

    def _create_stat_card(self, title: str, value: str, color: str) -> QFrame:
        """Create a statistics card widget."""
        frame = QFrame()
        ThemeManager.apply_to_widget(frame, "card")
        # Override border for accent
        c = ThemeManager._get_palette()
        frame.setStyleSheet(
            frame.styleSheet()
            + f"""
            QFrame {{
                border-left: 4px solid {color};
            }}
        """
        )

        layout = QVBoxLayout(frame)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {c['TEXT_SECONDARY']}; text-transform: uppercase;"
        )
        layout.addWidget(title_label)

        # Value
        value_label = QLabel(value)
        value_label.setObjectName(f"{title.lower().replace(' ', '_')}_value")
        value_label.setStyleSheet(f"color: {c['TEXT_BRIGHT']}; font-size: 24px; font-weight: 800;")
        layout.addWidget(value_label)

        return frame

    def update_stats(self, stats: Dict[str, Any]):
        """Update statistics display."""

        def find_value_label(card: QFrame, title: str) -> Optional[QLabel]:
            name = f"{title.lower().replace(' ', '_')}_value"
            return card.findChild(QLabel, name)

        if "total" in stats:
            label = find_value_label(self.total_card, "Total Proxies")
            if label:
                label.setText(str(stats["total"]))

        if "active" in stats:
            label = find_value_label(self.active_card, "Active")
            if label:
                label.setText(str(stats["active"]))

        if "available" in stats:
            label = find_value_label(self.available_card, "Available")
            if label:
                label.setText(str(stats["available"]))

        if "assigned" in stats:
            label = find_value_label(self.assigned_card, "Assigned")
            if label:
                label.setText(str(stats["assigned"]))

        if "avg_latency_ms" in stats:
            label = find_value_label(self.latency_card, "Avg Latency")
            if label:
                label.setText(f"{stats['avg_latency_ms']:.0f} ms")

        if "avg_score" in stats:
            label = find_value_label(self.score_card, "Avg Score")
            if label:
                label.setText(f"{stats['avg_score']:.1f}")

        if "endpoints" in stats:
            label = find_value_label(self.endpoints_card, "Endpoints")
            if label:
                label.setText(str(stats["endpoints"]))

        if "last_full_poll" in stats and stats["last_full_poll"]:
            label = find_value_label(self.poll_card, "Last Poll")
            if label:
                label.setText(
                    stats["last_full_poll"][:19]
                    if isinstance(stats["last_full_poll"], str)
                    else "Just now"
                )


class ProxyTableWidget(QWidget):
    """Widget showing proxy table with health information and pagination."""

    proxy_selected = pyqtSignal(str)  # Emits proxy_key

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proxies: Dict[str, Dict] = {}
        self.current_page = 1
        self.page_size = 100
        self.total_count = 0
        self.proxy_pool_manager = None
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        # Filter by tier
        toolbar.addWidget(QLabel("Filter by Tier:"))
        self.tier_filter = QComboBox()
        self.tier_filter.addItems(["All", "Premium", "Standard", "Economy", "Low"])
        self.tier_filter.setAccessibleName("Proxy tier filter")
        self.tier_filter.currentTextChanged.connect(self.apply_filter)
        toolbar.addWidget(self.tier_filter)

        # Filter by status
        toolbar.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Active", "Testing", "Cooldown", "Failed"])
        self.status_filter.setAccessibleName("Proxy status filter")
        self.status_filter.currentTextChanged.connect(self.on_filter_changed)
        toolbar.addWidget(self.status_filter)

        # Display mode filter
        toolbar.addWidget(QLabel("View:"))
        self.display_mode = QComboBox()
        self.display_mode.addItems(["Active Only", "Assigned Only", "All"])
        self.display_mode.setCurrentText("Active Only")  # Default to Active Only
        self.display_mode.setAccessibleName("Proxy display mode")
        self.display_mode.currentTextChanged.connect(self.on_filter_changed)
        toolbar.addWidget(self.display_mode)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search host or assignee…")
        self.search_input.setAccessibleName("Proxy search")
        self.search_input.textChanged.connect(self.apply_filter)
        toolbar.addWidget(self.search_input)

        toolbar.addStretch()

        # Test selected button
        self.test_btn = QPushButton("Test Selected")
        self.test_btn.clicked.connect(self.test_selected)
        toolbar.addWidget(self.test_btn)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_table)
        toolbar.addWidget(self.refresh_btn)

        layout.addLayout(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(
            [
                "IP:Port",
                "Status",
                "Tier",
                "Latency",
                "Score",
                "Uptime %",
                "Assigned To",
                "Source",
                "Last Tested",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)  # Cleaner look

        # Style table - handled by global theme, but ensure specific overrides if needed
        # We rely on ThemeManager application logic or global stylesheet

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 8):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

        # Pagination controls
        pagination_layout = QHBoxLayout()

        self.page_info_label = QLabel("Showing 0-0 of 0")
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
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
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
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

        pagination_layout.addWidget(QLabel("Page size:"))
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(50, 500)
        self.page_size_spin.setValue(100)
        self.page_size_spin.setSingleStep(50)
        self.page_size_spin.valueChanged.connect(self.on_page_size_changed)
        pagination_layout.addWidget(self.page_size_spin)

        layout.addLayout(pagination_layout)

        self.loading_overlay = (
            LoadingOverlay(self.table, "Refreshing proxies…") if LoadingOverlay else None
        )

    def set_proxy_pool_manager(self, manager):
        """Set the proxy pool manager for database queries."""
        self.proxy_pool_manager = manager

    def update_proxies(self, proxies: List[Dict]):
        """Update proxy table (deprecated - use load_page instead)."""
        self.proxies = {p.get("proxy_key", f"{p.get('ip')}:{p.get('port')}"): p for p in proxies}
        self.total_count = len(proxies)
        self.apply_filter()

    def load_page(self):
        """Load current page from database with filters."""
        if not self.proxy_pool_manager:
            # Fallback to old method
            self.apply_filter()
            return

        # Determine filters based on display mode
        tier_filter = self.tier_filter.currentText().lower()
        status_filter = self.status_filter.currentText().lower()
        display_mode = self.display_mode.currentText()
        search = self.search_input.text().lower() if hasattr(self, "search_input") else ""

        # Map display mode to filters
        active_only = display_mode == "Active Only"
        assigned_only = display_mode == "Assigned Only"

        # Map UI filters to database filters
        tier = None if tier_filter == "all" else tier_filter
        status = None if status_filter == "all" else status_filter

        # Query database with pagination
        try:
            if self.loading_overlay:
                self.loading_overlay.show_loading("Refreshing proxies…")
            proxies, total_count = self.proxy_pool_manager.get_proxies_paginated(
                page=self.current_page,
                page_size=self.page_size,
                status_filter=status,
                tier_filter=tier,
                assigned_only=assigned_only,
                active_only=active_only,
            )

            if search:
                proxies = [
                    p
                    for p in proxies
                    if search in f"{p.get('ip','')}:{p.get('port','')}".lower()
                    or search in str(p.get("assigned_account", "")).lower()
                ]
            self.total_count = total_count
            self.proxies = {
                p.get("proxy_key", f"{p.get('ip')}:{p.get('port')}"): p for p in proxies
            }
            self.render_table(proxies)
            self.update_pagination_controls()

        except Exception as e:
            logger.error(f"Failed to load page: {e}")
        finally:
            if self.loading_overlay:
                self.loading_overlay.hide_loading()

    def apply_filter(self):
        """Apply current filters to table (in-memory filtering for backwards compatibility)."""
        tier_filter = self.tier_filter.currentText().lower()
        status_filter = self.status_filter.currentText().lower()
        display_mode = self.display_mode.currentText()
        search = self.search_input.text().lower() if hasattr(self, "search_input") else ""

        filtered = []
        for key, proxy in self.proxies.items():
            # Apply tier filter
            if tier_filter != "all" and proxy.get("tier", "").lower() != tier_filter:
                continue

            # Apply status filter
            if status_filter != "all" and proxy.get("status", "").lower() != status_filter:
                continue

            # Apply display mode filter
            if display_mode == "Active Only" and proxy.get("status", "").lower() != "active":
                continue
            if display_mode == "Assigned Only" and not proxy.get("assigned_account"):
                continue
            if (
                search
                and search not in f"{proxy.get('ip','')}:{proxy.get('port','')}".lower()
                and search not in str(proxy.get("assigned_account", "")).lower()
            ):
                continue

            filtered.append(proxy)

        self.render_table(filtered)
        self.update_pagination_controls()

    def render_table(self, proxies: List[Dict]):
        """Render proxies in the table."""
        # Disable updates for better performance
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)

        c = ThemeManager._get_palette()

        # Update table
        if not proxies:
            self.table.setRowCount(1)
            empty = QTableWidgetItem("No proxies match the filters.")
            empty.setForeground(QColor(c["TEXT_DISABLED"]))
            self.table.setItem(0, 0, empty)
            self.table.setSpan(0, 0, 1, self.table.columnCount())
            self.table.setUpdatesEnabled(True)
            self.table.setSortingEnabled(True)
            return

        self.table.setRowCount(len(proxies))

        for row, proxy in enumerate(proxies):
            # IP:Port
            ip_port = f"{proxy.get('ip', 'Unknown')}:{proxy.get('port', 0)}"
            self.table.setItem(row, 0, QTableWidgetItem(ip_port))

            # Status with color
            status = proxy.get("status", "unknown")
            status_chip = QLabel(status.capitalize())
            status_chip.setObjectName("status_chip")
            status_chip.setProperty(
                "state",
                {
                    "active": "ok",
                    "testing": "warn",
                    "cooldown": "warn",
                    "failed": "bad",
                    "blacklisted": "bad",
                }.get(status, "info"),
            )
            status_chip.setStyleSheet("padding: 4px 10px;")
            self.table.setCellWidget(row, 1, status_chip)

            # Tier with color
            tier = proxy.get("tier", "standard")
            tier_chip = QLabel(tier.capitalize())
            tier_chip.setObjectName("status_chip")
            tier_chip.setProperty(
                "state",
                {"premium": "ok", "standard": "info", "economy": "warn", "low": "warn"}.get(
                    tier, "info"
                ),
            )
            tier_chip.setStyleSheet("padding: 4px 10px;")
            self.table.setCellWidget(row, 2, tier_chip)

            # Latency
            latency = proxy.get("latency_ms", 0)
            latency_item = QTableWidgetItem(f"{latency:.0f} ms")
            if latency < 200:
                latency_item.setForeground(QColor(c["ACCENT_SUCCESS"]))
            elif latency < 500:
                latency_item.setForeground(QColor(c["ACCENT_WARNING"]))
            else:
                latency_item.setForeground(QColor(c["ACCENT_DANGER"]))
            self.table.setItem(row, 3, latency_item)

            # Score
            score = proxy.get("score", 0)
            score_item = QTableWidgetItem(f"{score:.1f}")
            if score >= 80:
                score_item.setForeground(QColor(c["ACCENT_SUCCESS"]))
            elif score >= 50:
                score_item.setForeground(QColor(c["ACCENT_WARNING"]))
            else:
                score_item.setForeground(QColor(c["ACCENT_DANGER"]))
            self.table.setItem(row, 4, score_item)

            # Uptime %
            uptime = proxy.get("uptime_percent", 100)
            self.table.setItem(row, 5, QTableWidgetItem(f"{uptime:.1f}%"))

            # Assigned To
            assigned = proxy.get("assigned_account", "None")
            self.table.setItem(row, 6, QTableWidgetItem(assigned or "None"))

            # Source
            source = proxy.get("source_endpoint", "Unknown")
            self.table.setItem(row, 7, QTableWidgetItem(source))

            # Last tested
            last_tested = proxy.get("last_tested") or proxy.get("last_check")
            last_tested_display = (
                last_tested
                if isinstance(last_tested, str)
                else (
                    last_tested.strftime("%Y-%m-%d %H:%M")
                    if hasattr(last_tested, "strftime")
                    else "—"
                )
            )
            self.table.setItem(row, 8, QTableWidgetItem(last_tested_display or "—"))

        # Re-enable updates
        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(False)  # Keep sorting disabled to prevent lag

    def update_pagination_controls(self):
        """Update pagination control states and labels."""
        total_pages = (
            (self.total_count + self.page_size - 1) // self.page_size if self.page_size > 0 else 1
        )

        # Update labels
        start_idx = (self.current_page - 1) * self.page_size + 1
        end_idx = min(self.current_page * self.page_size, self.total_count)
        self.page_info_label.setText(f"Showing {start_idx}-{end_idx} of {self.total_count}")
        self.page_label.setText(f"Page {self.current_page} of {total_pages}")

        # Enable/disable buttons
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        self.last_page_btn.setEnabled(self.current_page < total_pages)

    def first_page(self):
        """Go to first page."""
        self.current_page = 1
        self.load_page()

    def prev_page(self):
        """Go to previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self.load_page()

    def next_page(self):
        """Go to next page."""
        total_pages = (self.total_count + self.page_size - 1) // self.page_size
        if self.current_page < total_pages:
            self.current_page += 1
            self.load_page()

    def last_page(self):
        """Go to last page."""
        total_pages = (self.total_count + self.page_size - 1) // self.page_size
        if total_pages > 0:
            self.current_page = total_pages
            self.load_page()

    def on_page_size_changed(self, new_size: int):
        """Handle page size change."""
        self.page_size = new_size
        self.current_page = 1  # Reset to first page
        self.load_page()

    def on_filter_changed(self):
        """Handle filter change."""
        self.current_page = 1  # Reset to first page when filter changes
        if self.proxy_pool_manager:
            self.load_page()
        else:
            self.apply_filter()

    def _on_selection_changed(self):
        """Handle selection change."""
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            ip_port = self.table.item(row, 0).text()
            self.proxy_selected.emit(ip_port)

    def test_selected(self):
        """Test selected proxy."""
        selected = self.table.selectedItems()
        if not selected:
            ErrorHandler.safe_information(self, "No Selection", "Please select a proxy to test.")
            return

        row = selected[0].row()
        ip_port = self.table.item(row, 0).text()
        # This would trigger a proxy test
        logger.info(f"Testing proxy: {ip_port}")

    def refresh_table(self):
        """Refresh table data."""
        if self.proxy_pool_manager:
            self.load_page()
        else:
            self.apply_filter()


class EndpointStatusWidget(QWidget):
    """Widget showing endpoint status and configuration."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Endpoint table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["Endpoint", "Type", "Interval", "Last Poll", "Success", "Proxies Found"]
        )

        # Style table - handled by global theme

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 6):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)
        self.loading_overlay = (
            LoadingOverlay(self.table, "Refreshing endpoints…") if LoadingOverlay else None
        )

    def update_endpoints(self, endpoints: List[Dict]):
        """Update endpoint table."""
        try:
            if self.loading_overlay:
                self.loading_overlay.show_loading("Refreshing endpoints…")

            c = ThemeManager._get_palette()

            if not endpoints:
                self.table.setRowCount(1)
                empty = QTableWidgetItem("No endpoints found.")
                empty.setForeground(QColor(c["TEXT_DISABLED"]))
                self.table.setItem(0, 0, empty)
                self.table.setSpan(0, 0, 1, self.table.columnCount())
                return

            self.table.setRowCount(len(endpoints))

            for row, endpoint in enumerate(endpoints):
                self.table.setItem(row, 0, QTableWidgetItem(endpoint.get("name", "Unknown")))

                feed_type = endpoint.get("feed_type", "unknown")
                type_item = QTableWidgetItem(feed_type.capitalize())
                type_colors = {
                    "primary": c["ACCENT_SUCCESS"],
                    "secondary": c["ACCENT_PRIMARY"],
                    "obscure": c["ACCENT_WARNING"],
                }
                type_item.setForeground(QColor(type_colors.get(feed_type, c["TEXT_SECONDARY"])))
                self.table.setItem(row, 1, type_item)

                interval = endpoint.get("poll_interval", 0)
                self.table.setItem(row, 2, QTableWidgetItem(f"{interval // 60}m"))

                last_poll = endpoint.get("last_poll", "Never")
                self.table.setItem(
                    row, 3, QTableWidgetItem(str(last_poll)[:19] if last_poll else "Never")
                )

                success = endpoint.get("success_count", 0)
                self.table.setItem(row, 4, QTableWidgetItem(str(success)))

                self.table.setItem(row, 5, QTableWidgetItem(str(endpoint.get("proxies_found", 0))))
        finally:
            if self.loading_overlay:
                self.loading_overlay.hide_loading()


class ProxyManagementWidget(QWidget):
    """Complete proxy management widget combining all components."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proxy_pool_manager = None
        self.manual_mode = not PROXY_POOL_AVAILABLE
        self.setup_ui()
        self.setup_timer()

        # Try to get proxy pool manager
        if PROXY_POOL_AVAILABLE:
            try:
                self.proxy_pool_manager = get_proxy_pool_manager()
                self.manual_mode = self.proxy_pool_manager is None
                if self.proxy_pool_manager:
                    # Ensure table wiring happens even though UI was built first
                    self.proxy_table.set_proxy_pool_manager(self.proxy_pool_manager)
            except Exception as e:
                logger.warning(f"Failed to get proxy pool manager: {e}")
                self.manual_mode = True
        else:
            self.manual_mode = True

        # Toggle manual controls based on availability
        self._configure_mode()

    def setup_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(14)

        # Title
        title = QLabel("Proxy Pool Management")
        title.setStyleSheet(ThemeManager.get_label_style("header"))
        scroll_layout.addWidget(title)

        if not PROXY_POOL_AVAILABLE:
            error_label = QLabel(
                "Proxy Pool Manager not available. Falling back to manual proxy entry and testing."
            )
            c = ThemeManager._get_palette()
            error_label.setStyleSheet(f"color: {c['ACCENT_DANGER']}; font-size: 14px;")
            scroll_layout.addWidget(error_label)

        # Stats Section
        self.stats_widget = ProxyStatsWidget()
        self.stats_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        scroll_layout.addWidget(self.stats_widget)

        # Tabs for different views
        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Proxy List Tab
        self.proxy_table = ProxyTableWidget()
        if self.proxy_pool_manager:
            self.proxy_table.set_proxy_pool_manager(self.proxy_pool_manager)
        tabs.addTab(self.proxy_table, "📋 Proxy List")

        # Endpoints Tab
        self.endpoints_widget = EndpointStatusWidget()
        tabs.addTab(self.endpoints_widget, "🔌 Endpoints")

        # Controls Tab
        controls_widget = self._create_controls_tab()
        tabs.addTab(controls_widget, "Controls")

        scroll_layout.addWidget(tabs)

        # Status bar
        status_layout = QHBoxLayout()
        status_layout.setSpacing(8)

        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)

        status_layout.addStretch()

        self.auto_refresh_check = QCheckBox("Auto-refresh")
        self.auto_refresh_check.setChecked(True)
        status_layout.addWidget(self.auto_refresh_check)

        self.refresh_interval = QSpinBox()
        self.refresh_interval.setRange(5, 300)
        self.refresh_interval.setValue(30)
        self.refresh_interval.setSuffix(" sec")
        self.refresh_interval.valueChanged.connect(self._update_timer_interval)
        status_layout.addWidget(self.refresh_interval)

        scroll_layout.addLayout(status_layout)

        scroll_widget.setLayout(scroll_layout)
        scroll.setWidget(scroll_widget)
        outer_layout.addWidget(scroll)

    def _create_controls_tab(self) -> QWidget:
        """Create controls tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Actions group
        actions_group = QGroupBox("Actions")
        # Global theme handles QGroupBox styling
        actions_layout = QHBoxLayout(actions_group)

        self.fetch_btn = QPushButton("Fetch All Endpoints")
        self.fetch_btn.clicked.connect(self._fetch_all_endpoints)
        actions_layout.addWidget(self.fetch_btn)

        self.test_all_btn = QPushButton("Test All Proxies")
        self.test_all_btn.clicked.connect(self._test_all_proxies)
        actions_layout.addWidget(self.test_all_btn)

        self.cleanup_btn = QPushButton("Cleanup Failed")
        self.cleanup_btn.clicked.connect(self._cleanup_failed)
        actions_layout.addWidget(self.cleanup_btn)

        self.export_btn = QPushButton("Export Health")
        self.export_btn.clicked.connect(self._export_health_results)
        actions_layout.addWidget(self.export_btn)

        layout.addWidget(actions_group)

        # Configuration group
        config_group = QGroupBox("Configuration")
        config_layout = QGridLayout(config_group)

        config_layout.addWidget(QLabel("Min Score:"), 0, 0)
        self.min_score_spin = QSpinBox()
        self.min_score_spin.setRange(0, 100)
        self.min_score_spin.setValue(30)
        config_layout.addWidget(self.min_score_spin, 0, 1)

        config_layout.addWidget(QLabel("Health Check Interval:"), 0, 2)
        self.health_interval_spin = QSpinBox()
        self.health_interval_spin.setRange(30, 600)
        self.health_interval_spin.setValue(60)
        self.health_interval_spin.setSuffix(" sec")
        config_layout.addWidget(self.health_interval_spin, 0, 3)

        config_layout.addWidget(QLabel("Max Failures:"), 1, 0)
        self.max_failures_spin = QSpinBox()
        self.max_failures_spin.setRange(1, 20)
        self.max_failures_spin.setValue(5)
        config_layout.addWidget(self.max_failures_spin, 1, 1)

        config_layout.addWidget(QLabel("Cooldown Duration:"), 1, 2)
        self.cooldown_spin = QSpinBox()
        self.cooldown_spin.setRange(60, 3600)
        self.cooldown_spin.setValue(300)
        self.cooldown_spin.setSuffix(" sec")
        config_layout.addWidget(self.cooldown_spin, 1, 3)

        apply_config_btn = QPushButton("Apply Configuration")
        apply_config_btn.clicked.connect(self._apply_configuration)
        config_layout.addWidget(apply_config_btn, 2, 0, 1, 4)

        layout.addWidget(config_group)

        # Manual fallback controls (visible when proxy pool manager is unavailable)
        self.manual_controls_group = QGroupBox("Manual Proxy Entry (Fallback Mode)")
        manual_layout = QVBoxLayout(self.manual_controls_group)

        manual_layout.addWidget(
            QLabel("Paste proxies as one per line (protocol://user:pass@ip:port or ip:port).")
        )

        self.manual_proxy_input = QTextEdit()
        self.manual_proxy_input.setPlaceholderText("socks5://1.2.3.4:1080")
        self.manual_proxy_input.setFixedHeight(120)
        # Global theme handles QTextEdit
        manual_layout.addWidget(self.manual_proxy_input)

        timeout_row = QHBoxLayout()
        timeout_row.addWidget(QLabel("Manual test timeout (sec):"))
        self.manual_timeout_spin = QSpinBox()
        self.manual_timeout_spin.setRange(1, 30)
        self.manual_timeout_spin.setValue(3)
        timeout_row.addWidget(self.manual_timeout_spin)
        timeout_row.addStretch()
        manual_layout.addLayout(timeout_row)

        manual_buttons = QHBoxLayout()
        self.manual_add_btn = QPushButton("➕ Add/Replace Table")
        self.manual_add_btn.clicked.connect(self._add_manual_proxies)
        manual_buttons.addWidget(self.manual_add_btn)

        self.manual_test_btn = QPushButton("Test Manually")
        self.manual_test_btn.clicked.connect(self._test_manual_proxies)
        manual_buttons.addWidget(self.manual_test_btn)

        manual_buttons.addStretch()
        manual_layout.addLayout(manual_buttons)

        layout.addWidget(self.manual_controls_group)

        # Log output
        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout(log_group)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)
        # Apply specific font for logs but keep theme colors
        c = ThemeManager._get_palette()
        self.log_output.setStyleSheet(
            f"font-family: monospace; font-size: 12px; color: {c['TEXT_SECONDARY']};"
        )
        log_layout.addWidget(self.log_output)

        layout.addWidget(log_group)
        layout.addStretch()

        return widget

    def setup_timer(self):
        """Set up auto-refresh timer."""
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(30000)  # 30 seconds default

    def _update_timer_interval(self, value: int):
        """Update timer interval."""
        self.refresh_timer.setInterval(value * 1000)

    def _configure_mode(self):
        """Enable or disable controls based on proxy pool availability."""
        manual = self.manual_mode or not self.proxy_pool_manager
        self.fetch_btn.setEnabled(not manual)
        self.test_all_btn.setEnabled(not manual)
        self.cleanup_btn.setEnabled(not manual)
        self.min_score_spin.setEnabled(not manual)
        self.health_interval_spin.setEnabled(not manual)
        self.max_failures_spin.setEnabled(not manual)
        self.cooldown_spin.setEnabled(not manual)
        self.manual_controls_group.setVisible(manual)
        if manual:
            self.status_label.setText("Manual mode: proxy pool manager unavailable")
            self._update_manual_stats([])
        else:
            self.status_label.setText("Ready")

    def refresh_data(self):
        """Refresh all data using pagination."""
        if not self.auto_refresh_check.isChecked():
            return

        if self.manual_mode:
            self._update_manual_stats(list(self.proxy_table.proxies.values()))
            self.status_label.setText(
                f"Manual mode: {len(self.proxy_table.proxies)} proxies loaded"
            )
            return

        if not self.proxy_pool_manager:
            return

        try:
            # Set proxy pool manager reference if not already set
            if not self.proxy_table.proxy_pool_manager:
                self.proxy_table.set_proxy_pool_manager(self.proxy_pool_manager)

            # Get stats
            stats = self.proxy_pool_manager.get_proxy_stats()
            self.stats_widget.update_stats(stats)

            # Check for backup errors and surface them
            if (
                hasattr(self.proxy_pool_manager, "_last_backup_error")
                and self.proxy_pool_manager._last_backup_error
            ):
                error_msg = self.proxy_pool_manager._last_backup_error
                self._log(f"Proxy backup error: {error_msg}")
                # Show warning banner if backup failed recently (only once per error)
                if (
                    not hasattr(self, "_last_shown_backup_error")
                    or self._last_shown_backup_error != error_msg
                ):
                    self._last_shown_backup_error = error_msg
                    from PyQt6.QtWidgets import QMessageBox

                    QMessageBox.warning(
                        self,
                        "Proxy Backup Failure",
                        f"Proxy database backup failed:\n{error_msg}\n\n"
                        "Please check disk space and permissions.",
                    )

            # Load current page (uses pagination)
            self.proxy_table.load_page()

            # Get endpoints
            endpoints = [
                {
                    "name": e.name,
                    "feed_type": e.feed_type,
                    "poll_interval": e.poll_interval,
                    "last_poll": e.last_poll.isoformat() if e.last_poll else None,
                    "success_count": e.success_count,
                    "proxies_found": 0,  # Would need to track this
                }
                for e in self.proxy_pool_manager.endpoints
            ]
            self.endpoints_widget.update_endpoints(endpoints)

            self.status_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")

        except Exception as e:
            logger.error(f"Failed to refresh proxy data: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")

    def _parse_manual_proxy_lines(self) -> List[Dict[str, Any]]:
        """Parse manual proxy input into proxy dictionaries."""
        proxies: List[Dict[str, Any]] = []
        lines = self.manual_proxy_input.toPlainText().splitlines()
        for line in lines:
            raw = line.strip()
            if not raw or raw.startswith("#"):
                continue

            protocol = "socks5"
            auth_part = ""
            host_part = raw

            if "://" in raw:
                protocol, remainder = raw.split("://", 1)
                host_part = remainder

            if "@" in host_part:
                auth_part, host_part = host_part.split("@", 1)

            if ":" not in host_part:
                logger.warning(f"Invalid proxy line (missing port): {raw}")
                continue

            host, port_str = host_part.split(":", 1)
            try:
                port = int(port_str)
            except ValueError:
                logger.warning(f"Invalid proxy line (bad port): {raw}")
                continue

            username = None
            password = None
            if auth_part:
                if ":" in auth_part:
                    username, password = auth_part.split(":", 1)
                else:
                    username = auth_part

            proxies.append(
                {
                    "ip": host,
                    "port": port,
                    "protocol": protocol or "socks5",
                    "username": username,
                    "password": password,
                    "status": "untested",
                }
            )

        return proxies

    def _add_manual_proxies(self):
        """Load manual proxies into the table without external dependencies."""
        proxies = self._parse_manual_proxy_lines()
        if not proxies:
            ErrorHandler.safe_warning(self, "No Proxies", "Add at least one proxy to proceed.")
            return

        self.proxy_table.update_proxies(proxies)
        self.proxy_table.apply_filter()
        self._update_manual_stats(proxies)
        self.status_label.setText(f"Loaded {len(proxies)} proxies (manual mode)")

    def _test_manual_proxies(self):
        """Perform a lightweight connectivity probe for manual proxies."""
        proxies = self._parse_manual_proxy_lines()
        if not proxies:
            ErrorHandler.safe_warning(self, "No Proxies", "Add proxies before testing.")
            return

        tested = []
        for proxy in proxies:
            start = time.perf_counter()
            status = "failed"
            latency_ms = 0.0
            try:
                with socket.create_connection(
                    (proxy["ip"], proxy["port"]), timeout=self.manual_timeout_spin.value()
                ):
                    latency_ms = (time.perf_counter() - start) * 1000
                    status = "active"
            except Exception as e:
                logger.debug(f"Manual proxy test failed for {proxy['ip']}:{proxy['port']} - {e}")

            proxy["status"] = status
            proxy["latency_ms"] = latency_ms
            proxy["score"] = max(0, 100 - (latency_ms / 10)) if latency_ms else 0
            proxy["last_tested"] = datetime.now().strftime("%Y-%m-%d %H:%M")
            tested.append(proxy)

        self.proxy_table.update_proxies(tested)
        self.proxy_table.apply_filter()
        self._update_manual_stats(tested)
        self.status_label.setText(f"Tested {len(tested)} proxies (manual mode)")

    def _update_manual_stats(self, proxies: List[Dict[str, Any]]):
        """Update stat cards based on manual entries."""
        total = len(proxies)
        active = sum(1 for p in proxies if p.get("status") == "active")
        failed = sum(1 for p in proxies if p.get("status") == "failed")
        avg_latency = (
            sum(p.get("latency_ms", 0) for p in proxies if p.get("latency_ms")) / max(1, active)
            if active
            else 0
        )
        stats = {
            "total": total,
            "active": active,
            "available": max(0, total - failed),
            "assigned": 0,
            "avg_latency_ms": avg_latency,
            "avg_score": (sum(p.get("score", 0) for p in proxies) / max(total, 1) if total else 0),
            "endpoints": 0,
            "last_full_poll": "Manual",
        }
        self.stats_widget.update_stats(stats)

    def _fetch_all_endpoints(self):
        """Trigger fetch from all endpoints."""
        if not self.proxy_pool_manager:
            ErrorHandler.safe_warning(self, "Not Available", "Proxy pool manager not initialized.")
            return

        self._log("Fetching from all endpoints...")
        # This would need to be async
        try:
            import asyncio

            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.proxy_pool_manager._fetch_all_endpoints())
            else:
                loop.run_until_complete(self.proxy_pool_manager._fetch_all_endpoints())
            self._log("Fetch completed")
        except Exception as e:
            self._log(f"Error: {e}")

    def _test_all_proxies(self):
        """Test all proxies."""
        # In manual mode, reuse the lightweight tester
        if self.manual_mode or not self.proxy_pool_manager:
            self._log("Testing manual proxies...")
            self._test_manual_proxies()
            return

        self._log("Testing all proxies via health checks...")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.proxy_pool_manager._run_health_checks())
            else:
                loop.run_until_complete(self.proxy_pool_manager._run_health_checks())
            self.status_label.setText("Health checks running...")
        except Exception as e:
            logger.error(f"Failed to trigger proxy health checks: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")
        else:
            self.refresh_data()
            self._log("Health checks completed")

    def _cleanup_failed(self):
        """Cleanup failed proxies."""
        if self.manual_mode or not self.proxy_pool_manager:
            # Remove failed entries from the table in manual mode
            cleaned = [p for p in self.proxy_table.proxies.values() if p.get("status") != "failed"]
            self.proxy_table.update_proxies(cleaned)
            self.proxy_table.apply_filter()
            self._update_manual_stats(cleaned)
            if cleaned:
                self.status_label.setText(f"Manual mode: {len(cleaned)} proxies active")
            else:
                self.status_label.setText("Manual mode: no proxies loaded")
            self._log("Removed failed manual proxies from view")
            return

        self._log("Cleaning up failed/low-quality proxies...")
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.proxy_pool_manager._cleanup_low_quality_proxies())
                asyncio.create_task(self.proxy_pool_manager._cleanup_cooldowns())
            else:
                loop.run_until_complete(self.proxy_pool_manager._cleanup_low_quality_proxies())
                loop.run_until_complete(self.proxy_pool_manager._cleanup_cooldowns())
            self.status_label.setText("Cleanup triggered")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")
        else:
            self.refresh_data()
            self._log("Cleanup complete")

    def _export_health_results(self):
        """Export current proxy health data for audits with optional encryption."""
        import csv
        from PyQt6.QtWidgets import QMessageBox, QInputDialog

        now = datetime.now().astimezone()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        tz_name = re.sub(r"[^A-Za-z0-9_.-]", "_", now.tzname() or "UTC")
        safe_suffix = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{timestamp}_{tz_name}")
        filepath = Path.cwd() / f"proxy_health_{safe_suffix}.csv"

        try:
            # Ask if user wants encrypted export with full credentials
            reply = QMessageBox.question(
                self,
                "Export Options",
                "Do you want to export with full credentials (encrypted)?\n\n"
                "YES: Export with encrypted credentials (password protected)\n"
                "NO: Export with redacted credentials (no password)",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return

            include_credentials = reply == QMessageBox.StandardButton.Yes
            encryption_password = None

            if include_credentials:
                password, ok = QInputDialog.getText(
                    self,
                    "Encryption Password",
                    "Enter a password to encrypt the export file:",
                    echo=QInputDialog.EchoMode.Password,
                )
                if not ok or not password:
                    self.status_label.setText("Export cancelled - no password provided")
                    return
                encryption_password = password

            proxies: List[Dict[str, Any]] = []
            if self.manual_mode or not self.proxy_pool_manager:
                proxies = list(self.proxy_table.proxies.values())
            else:
                page = 1
                page_size = 500
                while True:
                    batch, total = self.proxy_pool_manager.get_proxies_paginated(
                        page=page,
                        page_size=page_size,
                        status_filter=None,
                        tier_filter=None,
                        assigned_only=False,
                        active_only=False,
                    )
                    proxies.extend(batch)
                    if len(proxies) >= total or not batch:
                        break
                    page += 1

            if not proxies:
                ErrorHandler.safe_information(self, "No Data", "No proxy data available to export.")
                return

            def _redact(value: Optional[str]) -> str:
                if not value:
                    return ""
                text = str(value)
                if len(text) <= 2:
                    return "*" * len(text)
                return f"{text[0]}***{text[-1]}"

            # Write to temporary CSV
            temp_filepath = (
                filepath if not encryption_password else filepath.with_suffix(".csv.tmp")
            )

            with open(temp_filepath, "w", newline="") as csvfile:
                if include_credentials:
                    fieldnames = [
                        "proxy_key",
                        "ip",
                        "port",
                        "protocol",
                        "username",
                        "password",
                        "status",
                        "score",
                        "latency_ms",
                        "last_tested",
                        "timezone",
                    ]
                else:
                    fieldnames = [
                        "proxy_key",
                        "ip",
                        "port",
                        "protocol",
                        "username_redacted",
                        "password_redacted",
                        "status",
                        "score",
                        "latency_ms",
                        "last_tested",
                        "timezone",
                    ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for proxy in proxies:
                    if include_credentials:
                        writer.writerow(
                            {
                                "proxy_key": proxy.get("proxy_key")
                                or f"{proxy.get('ip')}:{proxy.get('port')}",
                                "ip": proxy.get("ip"),
                                "port": proxy.get("port"),
                                "protocol": proxy.get("protocol"),
                                "username": proxy.get("username", ""),
                                "password": proxy.get("password", ""),
                                "status": proxy.get("status"),
                                "score": proxy.get("score"),
                                "latency_ms": proxy.get("latency_ms"),
                                "last_tested": proxy.get("last_tested") or proxy.get("last_check"),
                                "timezone": tz_name,
                            }
                        )
                    else:
                        writer.writerow(
                            {
                                "proxy_key": proxy.get("proxy_key")
                                or f"{proxy.get('ip')}:{proxy.get('port')}",
                                "ip": proxy.get("ip"),
                                "port": proxy.get("port"),
                                "protocol": proxy.get("protocol"),
                                "username_redacted": _redact(proxy.get("username")),
                                "password_redacted": _redact(proxy.get("password")),
                                "status": proxy.get("status"),
                                "score": proxy.get("score"),
                                "latency_ms": proxy.get("latency_ms"),
                                "last_tested": proxy.get("last_tested") or proxy.get("last_check"),
                                "timezone": tz_name,
                            }
                        )

            # Encrypt the file if password was provided
            if encryption_password:
                try:
                    from cryptography.fernet import Fernet
                    from cryptography.hazmat.primitives import hashes
                    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
                    import base64

                    # Read the CSV content
                    with open(temp_filepath, "rb") as f:
                        csv_data = f.read()

                    # Derive encryption key from password
                    salt = b"proxy_export_salt_v1"  # Static salt for consistency
                    kdf = PBKDF2(
                        algorithm=hashes.SHA256(),
                        length=32,
                        salt=salt,
                        iterations=100000,
                    )
                    key = base64.urlsafe_b64encode(kdf.derive(encryption_password.encode()))
                    cipher = Fernet(key)

                    # Encrypt the data
                    encrypted_data = cipher.encrypt(csv_data)

                    # Write encrypted file
                    final_filepath = filepath.with_suffix(".enc")
                    with open(final_filepath, "wb") as f:
                        f.write(encrypted_data)

                    # Remove temporary file
                    temp_filepath.unlink()
                    filepath = final_filepath

                    self._log(f"Exported {len(proxies)} proxies to encrypted file {filepath}")
                    self.status_label.setText(f"Exported encrypted proxy data to {filepath.name}")

                    QMessageBox.information(
                        self,
                        "Export Complete",
                        f"Encrypted export saved to:\n{filepath}\n\n"
                        "To decrypt, you'll need the password you provided.\n"
                        "Keep this file secure!",
                    )

                except ImportError:
                    # Cryptography not available, save unencrypted but warn
                    logger.error("cryptography package not available for encryption")
                    filepath = temp_filepath
                    ErrorHandler.safe_warning(
                        self,
                        "Encryption Unavailable",
                        "Could not encrypt export (cryptography package not installed).\n"
                        "File saved unencrypted - handle with care!",
                    )
                except Exception as e:
                    logger.error(f"Failed to encrypt export: {e}")
                    # Clean up temp file
                    if temp_filepath.exists():
                        temp_filepath.unlink()
                    raise

            safe_path = filepath.resolve()
            try:
                safe_path.relative_to(Path.cwd())
            except ValueError:
                logger.warning(
                    "Export path escaped working directory; normalizing to current directory"
                )
                safe_path = Path.cwd() / filepath.name

            if not encryption_password:
                self._log(f"Exported {len(proxies)} proxies to {safe_path}")
                self.status_label.setText(f"Exported proxy health to {safe_path}")

        except Exception as exc:
            logger.error(f"Failed to export proxy health: {exc}")
            self.status_label.setText(f"Export failed: {str(exc)[:50]}")

    def _apply_configuration(self):
        """Apply configuration changes."""
        if not self.proxy_pool_manager:
            return

        self.proxy_pool_manager.config["min_score"] = self.min_score_spin.value()
        self.proxy_pool_manager.config["health_check_interval"] = self.health_interval_spin.value()
        self.proxy_pool_manager.config["max_failures"] = self.max_failures_spin.value()
        self.proxy_pool_manager.config["cooldown_duration"] = self.cooldown_spin.value()

        self._log("Configuration applied")
        ErrorHandler.safe_information(self, "Success", "Configuration has been applied.")

    def _log(self, message: str):
        """Add message to log output."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_output.append(f"[{timestamp}] {message}")

    def showEvent(self, event):
        """Called when widget is shown."""
        super().showEvent(event)
        # Set proxy pool manager reference on first show
        if self.proxy_pool_manager and not self.proxy_table.proxy_pool_manager:
            self.proxy_table.set_proxy_pool_manager(self.proxy_pool_manager)
        self.refresh_data()
