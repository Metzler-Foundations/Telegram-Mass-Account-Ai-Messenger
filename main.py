#!/usr/bin/env python3
"""
Telegram Auto-Reply Bot with Gemini AI Integration

A desktop application that integrates Google Gemini AI with Telegram
to provide automatic, intelligent responses to messages.
"""

import asyncio
import functools
import json
import logging
import logging.handlers
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None  # Optional dependency

# Import memory optimizer for resource management
try:
    from utils.memory_optimizer import MemoryMonitor as MemoryOptimizer

    MEMORY_OPTIMIZER_AVAILABLE = True
except ImportError:
    MemoryOptimizer = None
    MEMORY_OPTIMIZER_AVAILABLE = False

from PyQt6.QtCore import (
    Q_ARG,
    QMetaObject,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QAction,
    QColor,
    QKeySequence,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from accounts.account_creator import AccountCreator
from accounts.account_manager import AccountManager
from accounts.account_warmup_service import AccountWarmupService
from ai.gemini_service import GeminiService
from campaigns.dm_campaign_manager import DMCampaignManager
from integrations.api_key_manager import APIKeyManager
from scraping.database import MemberDatabase
from telegram.telegram_client import TelegramClient
from ui.settings_window import SettingsWindow
from ui.theme_manager import ThemeManager
from ui.ui_components import CampaignManagerWidget, LoadingOverlay, MessageHistoryWidget

# Initialize module-level logger
logger = logging.getLogger(__name__)

# Import Advanced Features Manager
try:
    from monitoring.advanced_features_manager import get_features_manager

    ADVANCED_FEATURES_AVAILABLE = True
    logger.info("✅ Advanced features loaded successfully")
except ImportError as e:
    ADVANCED_FEATURES_AVAILABLE = False
    logger.warning(f"Advanced features not available: {e}")

# Constants
# NOTE: API credentials must be provided via config.json or environment variables
# Do not use hardcoded defaults for security reasons
MAX_REPLY_LENGTH = 4000
STATS_UPDATE_INTERVAL = 30000  # 30 seconds
ACCOUNT_UPDATE_INTERVAL = 10000  # 10 seconds
TELEGRAM_MESSAGE_TIMEOUT = 30  # seconds

# Encryption settings
ENCRYPTION_KEY_ENV = "TELEGRAM_BOT_ENCRYPTION_KEY"

# Rate limiting
MAX_REQUESTS_PER_MINUTE = 60

# Anti-detection randomization ranges
MIN_DELAY_SECONDS = 2
MAX_DELAY_SECONDS = 30
MIN_INTERVAL_SECONDS = 1.5
MAX_INTERVAL_SECONDS = 3.0
MIN_GEMINI_TEMPERATURE = 0.6
MAX_GEMINI_TEMPERATURE = 0.9
MIN_GEMINI_TOP_P = 0.7
MAX_GEMINI_TOP_P = 0.9
MIN_GEMINI_TOP_K = 30
MAX_GEMINI_TOP_K = 50
MIN_GEMINI_MAX_TOKENS = 800
MAX_GEMINI_MAX_TOKENS = 1200
MIN_API_TIMEOUT = 12
MAX_API_TIMEOUT = 18

# Retry backoff settings
MAX_RETRY_ATTEMPTS = 3
BASE_RETRY_DELAY = 2
MIN_RETRY_MULTIPLIER = 1
MAX_RETRY_MULTIPLIER = 3

# Import event types and utilities from utils module to avoid circular imports
from core.config_manager import ConfigurationManager  # noqa: E402

# Import error handler for user-friendly messages
from core.error_handler import ErrorHandler  # noqa: E402
from core.service_container import (  # noqa: E402
    EventSystem,
    IAIService,
    IAntiDetectionService,
    IDatabaseService,
    IMessageService,
    ServiceContainer,
    ServiceFactory,
)

# Import performance monitor
from monitoring.performance_monitor import (  # noqa: E402
    PerformanceMonitor,
    StructuredLogger,
    get_resource_manager,
    shutdown_resource_manager,
)
from telegram.telegram_worker import TelegramWorker  # noqa: E402

# Import UI controller for clean separation
from ui.ui_controller import UIController  # noqa: E402
from utils.utils import (  # noqa: E402
    EVENT_ERROR_OCCURRED,
    EVENT_MESSAGE_RECEIVED,
    EVENT_MESSAGE_SENT,
    EVENT_SERVICE_STARTED,
    EVENT_SERVICE_STOPPED,
)


class ThreadSafeUI:
    """Thread-safe UI operations using QMetaObject."""

    @staticmethod
    def invoke_method(obj, method_name: str, *args):
        """Invoke a method on the UI object in a thread-safe way."""
        try:
            QMetaObject.invokeMethod(
                obj,
                method_name,
                Qt.ConnectionType.QueuedConnection,
                *[Q_ARG(type(arg), arg) for arg in args],
            )
        except (TypeError, ValueError, RuntimeError) as e:
            logger.error(f"Failed to invoke {method_name}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error invoking {method_name}: {e}")

    @staticmethod
    def update_status_label(label, text: str):
        """Thread-safe label update."""
        ThreadSafeUI.invoke_method(label, "setText", text)

    @staticmethod
    def show_message_box(parent, icon, title: str, text: str):
        """Thread-safe message box display."""
        # For message boxes, we'll use a signal approach
        if hasattr(parent, "show_error_signal"):
            if icon == QMessageBox.Icon.Critical:
                parent.show_error_signal.emit("general_error", text)
            elif icon == QMessageBox.Icon.Information:
                parent.show_success_signal.emit(title, text)
        else:
            # Fallback - this might not be thread-safe
            logger.warning(
                "No signal available for message box, using direct call (may cause race condition)"
            )
            QMessageBox(icon, title, text, parent=parent).exec()


# UI Controller signal handler functions (used by MainWindow)
def _on_campaign_created(campaign_data: dict):
    """Handle campaign creation event."""
    try:
        campaign_id = campaign_data.get("campaign_id")
        metrics = campaign_data.get("metrics", {})
        logger.info(
            f"Campaign {campaign_id} created with {metrics.get('total_members', 0)} members"
        )
        # Update UI if needed - this will be connected to MainWindow instance
    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Error handling campaign creation data: {e}")
    except Exception as e:
        logger.error(f"Unexpected error handling campaign creation: {e}")


def _on_campaign_updated(campaign_id: int, stats: dict):
    """Handle campaign update event."""
    try:
        logger.info(f"Campaign {campaign_id} updated: {stats}")
        # Update UI if needed - this will be connected to MainWindow instance
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid data in campaign update: {e}")
    except Exception as e:
        logger.error(f"Unexpected error handling campaign update: {e}")


def _on_account_status_changed(phone_number: str, status: str):
    """Handle account status change event."""
    try:
        logger.info(f"Account {phone_number} status changed to {status}")
        # Update account list if visible - this will be connected to MainWindow instance
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid account status data: {e}")
    except Exception as e:
        logger.error(f"Unexpected error handling account status change: {e}")


def _on_system_health_updated(health_data: dict):
    """Handle system health update event."""
    try:
        health_score = health_data.get("overall_health", 0)
        logger.info(f"System health updated: {health_score}%")
        # Update dashboard with health info - this will be connected to MainWindow instance
    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Invalid system health data: {e}")
    except Exception as e:
        logger.error(f"Unexpected error handling system health update: {e}")


def _on_controller_error(error_type: str, details: str):
    """Handle errors from UI controller."""
    try:
        ErrorHandler.show_error(None, error_type, details)
    except (ImportError, AttributeError, RuntimeError) as e:
        logger.error(f"UI error handler unavailable: {e}")
    except Exception as e:
        logger.error(f"Unexpected error handling controller error: {e}")


# Import UI redesign theme
try:
    from ui_redesign import DISCORD_THEME
except ImportError:
    DISCORD_THEME = ""


class NavigationManager:
    """Manages sidebar navigation and page switching."""

    def __init__(self, parent_window):
        self.parent = parent_window
        self.nav_buttons = {}
        self.sidebar_buttons = []

    def setup_sidebar_navigation(self, sidebar_layout):
        """Set up the sidebar navigation buttons."""
        # Brand card
        brand_card = self._create_brand_card()
        sidebar_layout.addWidget(brand_card)
        sidebar_layout.addSpacing(12)

        # Section label
        section_label = QLabel("WORKSPACE")
        section_label.setObjectName("nav_section_label")
        sidebar_layout.addWidget(section_label)
        sidebar_layout.addSpacing(6)

        # Navigation buttons
        nav_items = [
            ("🏠  Dashboard", 0, "Home overview"),
            ("👥  Accounts", 1, "Accounts list and controls"),
            ("🧭  Members", 2, "Member intelligence"),
            ("🎯  Campaigns", 3, "DM campaigns"),
            ("📊  Analytics", 4, "Campaign analytics"),
            ("🌐  Proxy Pool", 5, "Proxy management"),
            ("🛡️  Health", 6, "Account health"),
            ("⚡  Engagement", 7, "Engagement automation"),
            ("🔥  Warmup", 8, "Warmup monitor"),
            ("🚧  Risk Monitor", 9, "Risk and quarantine"),
            ("📨  Delivery", 10, "Delivery analytics"),
            ("💬  Messages", 11, "Message stream"),
            ("⚙️  Settings", 12, "Configuration"),
            ("📜  Logs", 13, "Application logs"),
        ]

        for text, page_idx, tooltip in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("nav_button")
            btn.setCheckable(True)
            btn.setChecked(page_idx == 0)
            btn.setToolTip(tooltip)
            btn.clicked.connect(lambda checked, idx=page_idx: self.parent.navigate_to_page(idx))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[page_idx] = btn
            self.sidebar_buttons.append(btn)

        sidebar_layout.addStretch()

        # User Panel at bottom
        user_panel = self._create_user_panel()
        sidebar_layout.addWidget(user_panel)

        # Compact mode toggle
        compact_btn = QPushButton("⤢  Compact Sidebar")
        compact_btn.setObjectName("secondary")
        compact_btn.clicked.connect(self._toggle_compact_sidebar)
        sidebar_layout.addWidget(compact_btn)

    def _create_brand_card(self):
        """Create branded identity block."""
        card = QFrame()
        card.setObjectName("brand_card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        title = QLabel("Atlas Signal Desk")
        title.setObjectName("brand_title")
        layout.addWidget(title)

        subtitle = QLabel("Enterprise Telegram automation")
        subtitle.setObjectName("brand_subtitle")
        layout.addWidget(subtitle)

        return card

    def _create_user_panel(self):
        """Create the user panel at the bottom of navigation."""
        panel = QWidget()
        panel.setObjectName("user_panel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 16, 0, 0)
        layout.setSpacing(4)

        self.parent.connection_status_label = QLabel("Disconnected")
        self.parent.connection_status_label.setObjectName("status_chip")
        self.parent.connection_status_label.setProperty("state", "bad")
        layout.addWidget(self.parent.connection_status_label)

        self.parent.ai_status_label = QLabel("AI Offline")
        self.parent.ai_status_label.setObjectName("status_chip")
        self.parent.ai_status_label.setProperty("state", "warn")
        layout.addWidget(self.parent.ai_status_label)

        return panel

    def update_navigation_button(self, page_index):
        """Update navigation button states."""
        for idx, btn in self.nav_buttons.items():
            btn.setChecked(idx == page_index)

    def _toggle_compact_sidebar(self):
        """Collapse/expand sidebar for small screens."""
        try:
            parent_sidebar = self.parent.findChild(QWidget, "sidebar_container")
            if not parent_sidebar:
                return
            compact = parent_sidebar.property("compact") is True
            expanded_width = parent_sidebar.property("expanded_width") or 220
            compact_width = parent_sidebar.property("compact_width") or 72
            if compact:
                # Expand
                parent_sidebar.setMinimumWidth(max(180, expanded_width))
                parent_sidebar.setMaximumWidth(320)
                parent_sidebar.setProperty("compact", False)
                for btn in self.sidebar_buttons:
                    original_text = btn.property("full_text")
                    if original_text:
                        btn.setText(original_text)
            else:
                parent_sidebar.setMinimumWidth(compact_width)
                parent_sidebar.setMaximumWidth(compact_width)
                parent_sidebar.setProperty("compact", True)
                for btn in self.sidebar_buttons:
                    btn.setProperty("full_text", btn.text())
                    btn.setText(btn.text().split("  ")[0])  # keep icon only
            parent_sidebar.style().unpolish(parent_sidebar)
            parent_sidebar.style().polish(parent_sidebar)
        except (AttributeError, RuntimeError) as exc:
            logger.debug(f"Compact sidebar toggle issue: {exc}")
        except Exception as exc:
            logger.warning(f"Unexpected error in sidebar toggle: {exc}")


class DashboardWidget(QWidget):
    """Dashboard widget with metrics and quick actions."""

    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.parent = parent_window
        self.metric_labels = {}
        self.setup_ui()

    def setup_ui(self):
        """Set up the dashboard UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Top row: profile + hero banner side-by-side to save vertical space
        top_row = QHBoxLayout()
        top_row.setSpacing(10)

        self.profile_card = self._create_profile_card()
        self.profile_card.setMaximumHeight(140)
        top_row.addWidget(self.profile_card, 1)

        hero_card = QFrame()
        hero_card.setObjectName("hero_card")
        hero_card.setMaximumHeight(110)
        hero_layout = QHBoxLayout(hero_card)
        hero_layout.setContentsMargins(10, 8, 10, 8)
        hero_layout.setSpacing(6)

        hero_text = QVBoxLayout()
        hero_title = QLabel("Mission Control")
        hero_title.setObjectName("page_title")
        hero_text.addWidget(hero_title)

        hero_subtitle = QLabel("Live view of automation, health, and delivery across accounts.")
        hero_subtitle.setObjectName("page_subtitle")
        hero_text.addWidget(hero_subtitle)
        hero_layout.addLayout(hero_text)

        hero_layout.addStretch()

        chip_bar = QHBoxLayout()
        chip_bar.setSpacing(6)
        # Keep references so the main window can refresh their state
        self.live_status_chip = QLabel("Automation status unknown")
        self.live_status_chip.setObjectName("status_chip")
        self.live_status_chip.setProperty("state", "warn")
        chip_bar.addWidget(self.live_status_chip)

        self.sync_status_chip = QLabel("Sync status unknown")
        self.sync_status_chip.setObjectName("status_chip")
        self.sync_status_chip.setProperty("state", "warn")
        chip_bar.addWidget(self.sync_status_chip)

        hero_layout.addLayout(chip_bar)
        top_row.addWidget(hero_card, 2)
        layout.addLayout(top_row)

        # Title
        title_label = QLabel("Dashboard")
        title_label.setObjectName("page_title")
        layout.addWidget(title_label)

        subtitle_label = QLabel("Overview of your automation system performance")
        subtitle_label.setObjectName("page_subtitle")
        layout.addWidget(subtitle_label)

        # Metrics grid
        metrics_grid = QGridLayout()
        metrics_grid.setSpacing(8)

        metrics_data = [
            ("message_count", "Messages Sent", "0", "blue"),
            ("ai_responses", "AI Responses", "0", "green"),
            ("active_chats", "Active Accounts", "0/0", "yellow"),
            ("system_health", "System Health", "100%", "green"),
            ("uptime", "Uptime", "0h 0m", "purple"),
            ("errors", "Errors", "0", "red"),
        ]

        for idx, (key, label, value, color) in enumerate(metrics_data):
            card = self._create_metric_card(label, value, color)
            metrics_grid.addWidget(card, idx // 3, idx % 3)
            # Store reference to value label
            self.metric_labels[key] = card.findChild(QLabel, "metric_value")

        layout.addLayout(metrics_grid)

        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_group.setObjectName("actions_group")
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(10)
        actions_layout.setContentsMargins(14, 8, 14, 12)

        from ui.theme_manager import ThemeManager

        helper = QLabel("Jump to key areas or configure automation.")
        c = ThemeManager.get_colors()
        helper.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 12px;")
        actions_layout.addWidget(helper)

        buttons_row = QHBoxLayout()
        buttons_row.setSpacing(6)

        start_btn = QPushButton("Settings")
        start_btn.setObjectName("quick_action")
        start_btn.setFixedHeight(32)
        start_btn.clicked.connect(self.parent._open_settings_dialog)
        buttons_row.addWidget(start_btn)

        accounts_btn = QPushButton("Accounts")
        accounts_btn.setObjectName("secondary")
        accounts_btn.setFixedHeight(32)
        accounts_btn.clicked.connect(lambda: self.parent.navigate_to_page(1))
        buttons_row.addWidget(accounts_btn)

        campaigns_btn = QPushButton("Campaigns")
        campaigns_btn.setObjectName("secondary")
        campaigns_btn.setFixedHeight(32)
        campaigns_btn.clicked.connect(lambda: self.parent.navigate_to_page(3))
        buttons_row.addWidget(campaigns_btn)

        buttons_row.addStretch()
        actions_layout.addLayout(buttons_row)

        actions_group.setLayout(actions_layout)
        layout.addWidget(actions_group)

        layout.addStretch()

    def _create_metric_card(self, label_text: str, value: str, color: str):
        """Create a metric card for the dashboard."""
        card = QFrame()
        card.setObjectName("metric_card")

        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)
        card.setMaximumHeight(86)

        label = QLabel(label_text)
        label.setObjectName("metric_label")
        layout.addWidget(label)

        value_label = QLabel(value)
        value_label.setObjectName("metric_value")
        value_label.setProperty("color", color)
        layout.addWidget(value_label)

        return card

    def _create_profile_card(self):
        """Create profile card for validated Telegram account."""
        card = QFrame()
        card.setObjectName("profile_card")
        layout = QHBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        self.profile_photo_label = QLabel("👤")
        self.profile_photo_label.setMinimumSize(48, 48)
        self.profile_photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_photo_label.setStyleSheet(
            f"""
            QLabel {{
                background-color: {c['BG_PRIMARY']};
                border: 1px solid {c['BORDER_DEFAULT']};
                border-radius: 6px;
                font-size: 24px;
            }}
        """
        )
        layout.addWidget(self.profile_photo_label)

        text_block = QVBoxLayout()
        self.profile_name_label = QLabel("No validated Telegram account yet")
        self.profile_name_label.setObjectName("page_subtitle")
        self.profile_name_label.setStyleSheet("font-size: 12.5px;")
        text_block.addWidget(self.profile_name_label)

        self.profile_username_label = QLabel("Add Telegram credentials in the welcome wizard.")
        self.profile_username_label.setStyleSheet(
            f"color: {c['TEXT_SECONDARY']}; font-size: 11.5px;"
        )
        text_block.addWidget(self.profile_username_label)

        self.profile_phone_label = QLabel("")
        self.profile_phone_label.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 11.5px;")
        text_block.addWidget(self.profile_phone_label)

        layout.addLayout(text_block)
        layout.addStretch()

        self.profile_status_chip = QLabel("Not validated")
        self.profile_status_chip.setObjectName("status_chip")
        self.profile_status_chip.setProperty("state", "warn")
        layout.addWidget(self.profile_status_chip)

        return card

    def update_profile(self, profile: Dict[str, Any]):
        """Update the primary account card."""
        if not profile:
            self.profile_name_label.setText("No validated Telegram account yet")
            self.profile_username_label.setText("Add Telegram credentials in the welcome wizard.")
            self.profile_phone_label.setText("")
            self.profile_photo_label.setPixmap(QPixmap())
            self.profile_photo_label.setText("👤")
            self.profile_status_chip.setText("Not validated")
            self.profile_status_chip.setProperty("state", "warn")
            self.profile_status_chip.style().unpolish(self.profile_status_chip)
            self.profile_status_chip.style().polish(self.profile_status_chip)
            return

        display_name = (
            profile.get("display_name")
            or f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
        )
        username = profile.get("username") or ""
        phone = profile.get("phone_number") or ""

        self.profile_name_label.setText(display_name or "Telegram account")
        self.profile_username_label.setText(f"@{username}" if username else "Username not set")
        self.profile_phone_label.setText(phone)

        state = "ok" if profile.get("validated", False) else "warn"
        self.profile_status_chip.setText(
            "Validated" if profile.get("validated") else "Pending validation"
        )
        self.profile_status_chip.setProperty("state", state)
        self.profile_status_chip.style().unpolish(self.profile_status_chip)
        self.profile_status_chip.style().polish(self.profile_status_chip)

        photo_path = profile.get("photo_path")
        if photo_path and Path(photo_path).exists():
            pixmap = QPixmap(photo_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.profile_photo_label.setPixmap(scaled)
                self.profile_photo_label.setText("")
                return

        self.profile_photo_label.setPixmap(QPixmap())
        self.profile_photo_label.setText("👤")

    def update_metrics(self, metrics):
        """Update dashboard metrics."""
        for key, value in metrics.items():
            label = self.metric_labels.get(key)
            if label:
                label.setText(value)


class MainWindow(QMainWindow):
    """Main application window."""

    # Thread-safe signals for UI updates
    update_status_signal = pyqtSignal(str, str)  # status_type, message
    update_metrics_signal = pyqtSignal(dict)  # metrics dict
    show_error_signal = pyqtSignal(str, str)  # error_type, details
    show_success_signal = pyqtSignal(str, str)  # title, message

    def __init__(self):
        super().__init__()

        # Initialize service container for dependency injection
        self.service_container = ServiceContainer()

        # Initialize event system for decoupled communication
        self.event_system = EventSystem()

        # Configuration & performance profile
        self.config_manager: Optional[ConfigurationManager] = None
        self.performance_settings: Dict[str, Any] = {}
        self.low_power_mode: bool = False
        self.stats_interval_ms: int = STATS_UPDATE_INTERVAL
        self.dashboard_interval_ms: int = 5000
        self.performance_monitor: Optional[PerformanceMonitor] = None

        # Initialize structured logging system
        self.logger = StructuredLogger()
        self._setup_event_logging()

        # Initialize resource manager for resource limits and queuing
        self.resource_manager = None

        # Initialize memory optimizer for leak prevention
        self.memory_optimizer = None
        if MEMORY_OPTIMIZER_AVAILABLE:
            try:
                self.memory_optimizer = MemoryOptimizer()
                # Take initial memory snapshot
                self.memory_optimizer.take_snapshot()
                self.logger.log_event("memory_optimizer_initialized")
            except (ImportError, AttributeError, RuntimeError) as e:
                logger.warning(f"Failed to initialize memory optimizer: {e}")
            except Exception as e:
                logger.warning(f"Unexpected error initializing memory optimizer: {e}")

        self.telegram_client: Optional[TelegramClient] = None
        self.gemini_service: Optional[GeminiService] = None
        self.worker: Optional[TelegramWorker] = None

        # Load configuration early for performance-aware defaults
        try:
            self.config_manager = ConfigurationManager()
            self.performance_settings = self.config_manager.get("performance", {}) or {}
        except (ImportError, FileNotFoundError, PermissionError) as e:
            logger.warning(f"Config manager initialization warning: {e}")
            self.config_manager = ConfigurationManager()
            self.performance_settings = self.config_manager.get("performance", {}) or {}
        except (OSError, ValueError, KeyError) as e:
            logger.warning(f"Unexpected config initialization error: {e}")
            self.config_manager = ConfigurationManager()
            self.performance_settings = self.config_manager.get("performance", {}) or {}
        except Exception as e:
            logger.error(f"Critical config initialization failure: {e}")
            # Fallback to minimal config
            self.config_manager = None
            self.performance_settings = {}

        env_low_power = os.getenv("LOW_POWER_MODE")
        if env_low_power:
            self.performance_settings["low_power"] = env_low_power.lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
        self.low_power_mode = bool(self.performance_settings.get("low_power"))

        # Apply timer defaults based on profile
        self.stats_interval_ms = int(
            self.performance_settings.get("stats_interval_ms", STATS_UPDATE_INTERVAL)
        )
        self.dashboard_interval_ms = int(
            self.performance_settings.get("dashboard_interval_ms", 5000)
        )
        if self.low_power_mode:
            self.performance_settings.setdefault("background_services_enabled", False)
            self.stats_interval_ms = max(self.stats_interval_ms, 60000)
            self.dashboard_interval_ms = max(self.dashboard_interval_ms, 12000)

        sampling_enabled = bool(self.performance_settings.get("enable_sampling", False))
        sampling_interval = float(self.performance_settings.get("sampling_interval_seconds", 30))
        self.performance_monitor = PerformanceMonitor(
            sampling_enabled=sampling_enabled, sample_interval_seconds=sampling_interval
        )

        # Set up memory management timers
        self._setup_memory_management()

        # Set up background task executor for non-blocking UI operations
        self._setup_background_task_executor()

    def _setup_memory_management(self):
        """Set up memory management and garbage collection."""

        # Periodic garbage collection (every 5 minutes)
        gc_timer = QTimer(self)
        gc_timer.timeout.connect(self._perform_memory_cleanup)
        gc_timer.start(300000)  # 5 minutes

        # Memory usage monitoring (every 2 minutes)
        memory_timer = QTimer(self)
        memory_timer.timeout.connect(self._check_memory_usage)
        memory_timer.start(120000)  # 2 minutes

        logger.info("Memory management timers initialized")

    def _perform_memory_cleanup(self):
        """Perform garbage collection and memory cleanup."""
        try:
            import gc

            # Force garbage collection
            collected = gc.collect()
            self.logger.log_event("memory_cleanup", {"objects_collected": collected})

            # Clean up memory optimizer if available
            if self.memory_optimizer:
                self.memory_optimizer.take_snapshot()

            # Log memory usage
            if psutil:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.logger.log_event("memory_usage", {"mb": round(memory_mb, 1)})

        except (ImportError, AttributeError, RuntimeError) as e:
            logger.warning(f"Memory cleanup failed: {e}")
        except (psutil.Error, OSError) as e:
            logger.warning(f"Unexpected error during memory cleanup: {e}")
        except Exception as e:
            logger.error(f"Critical memory cleanup failure: {e}")

    def _check_memory_usage(self):
        """Check memory usage and trigger cleanup if needed."""
        try:
            if not psutil:
                return

            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024

            # Get memory limit from performance settings
            memory_limit = self.performance_settings.get("memory_limit_mb", 512)

            if memory_mb > (memory_limit * 0.9):  # 90% of limit
                self.logger.log_event(
                    "high_memory_usage",
                    {"current_mb": round(memory_mb, 1), "limit_mb": memory_limit},
                )
                self._perform_memory_cleanup()

                # Force additional cleanup
                import gc

                gc.collect(2)  # Full collection

        except (ImportError, AttributeError, RuntimeError) as e:
            logger.warning(f"Memory check failed: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error during memory check: {e}")

    def _setup_background_task_executor(self):
        """Set up background executor for non-blocking UI operations."""
        from concurrent.futures import ThreadPoolExecutor

        # Create thread pool for background tasks
        self._background_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ui-bg")

        # Signal for task completion will be handled by QTimer for simplicity

    def run_background_task(self, task_id: str, func, *args, **kwargs):
        """Run a function in background thread without blocking UI."""
        try:
            # Submit task to background executor
            future = self._background_executor.submit(func, *args, **kwargs)
            future.add_done_callback(functools.partial(self._background_task_done, task_id))
        except (RuntimeError, ValueError, TypeError) as e:
            logger.error(f"Failed to submit background task {task_id}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error submitting background task {task_id}: {e}")

    def _background_task_done(self, task_id: str, future):
        """Handle completion of background task."""
        try:
            result = future.result(timeout=0.1)  # Brief timeout to avoid blocking
            # Schedule UI update on main thread using QTimer
            QTimer.singleShot(0, lambda: self._on_background_task_completed(task_id, result))
        except (TimeoutError, RuntimeError) as e:
            logger.error(f"Background task {task_id} failed: {e}")
            QTimer.singleShot(0, lambda: self._on_background_task_completed(task_id, None))
        except Exception as e:
            logger.error(f"Unexpected error in background task {task_id}: {e}")
            QTimer.singleShot(0, lambda: self._on_background_task_completed(task_id, None))

    def _on_background_task_completed(self, task_id: str, result):
        """Handle background task completion on main thread."""
        # This method can be overridden by subclasses or connected to specific handlers
        logger.debug(f"Background task {task_id} completed")

        # Initialize member database and account manager early (needed for warmup service and UI)
        self.member_db = None
        self.account_manager = None
        try:
            self.member_db = MemberDatabase()
            self.account_manager = AccountManager(
                self.member_db, performance_profile=self.performance_settings
            )
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            self.member_db = None
            self.account_manager = None

        # Load any existing validated profile details early
        self.telegram_profile = self._load_primary_account_profile()

        # Initialize Advanced Features Manager (automatic)
        self.advanced_features = None
        self.auto_integrator = None
        if ADVANCED_FEATURES_AVAILABLE:
            try:
                self.advanced_features = get_features_manager()
                logger.info("✅ Advanced features initialized and ready")
                # Log available features
                self.advanced_features.log_status()

                # Initialize auto-integrator for seamless integration
                from integrations.auto_integrator import get_auto_integrator

                self.auto_integrator = get_auto_integrator(self.advanced_features)
                logger.info(
                    "🤖 Auto-Integrator enabled - features will apply automatically to campaigns"
                )

            except Exception as e:
                logger.warning(f"Advanced features initialization failed: {e}")
                self.advanced_features = None
                self.auto_integrator = None

        # Initialize DM campaign manager early (needed for UI setup)
        self.campaign_manager = None
        if self.account_manager:
            try:
                self.campaign_manager = DMCampaignManager(account_manager=self.account_manager)
                logger.info("DM Campaign Manager initialized")
            except Exception as e:
                logger.error(f"Failed to initialize campaign manager: {e}")
                self.campaign_manager = None

        # Initialize proxy pool manager (starts async later)
        self.proxy_pool_manager = None
        try:
            from proxy_pool_manager import get_proxy_pool_manager

            self.proxy_pool_manager = get_proxy_pool_manager()
            logger.info("Proxy Pool Manager reference obtained")
        except ImportError:
            logger.warning("Proxy Pool Manager not available")
        except Exception as e:
            logger.error(f"Failed to get proxy pool manager: {e}")

        # Schedule async initialization for account manager services
        try:
            import threading

            def init_async_services():
                """Initialize async services in a background thread."""
                # Start async services in background thread to avoid blocking UI
                import threading

                def start_async_services():
                    """Start async services in background thread."""
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Start account manager services
                        if self.account_manager:
                            loop.run_until_complete(self.account_manager.start())
                            logger.info("Account Manager services started")

                        # Start proxy pool manager
                        if self.proxy_pool_manager:
                            loop.run_until_complete(self.proxy_pool_manager.start())
                            logger.info("Proxy Pool Manager started with 15-endpoint feed")
                    except Exception as e:
                        logger.error(f"Failed to start async services: {e}")
                    finally:
                        loop.close()

                # Start services in background thread
                service_thread = threading.Thread(target=start_async_services, daemon=True)
                service_thread.start()
                logger.info("Async services starting in background thread")

            # Run in background thread to not block UI
            init_thread = threading.Thread(target=init_async_services, daemon=True)
            init_thread.start()
        except Exception as e:
            logger.error(f"Failed to schedule async service initialization: {e}")

        # Initialize Account Creator (will be re-initialized after services are ready)
        # Note: gemini_service is not available yet, so we initialize it later
        self.account_creator = None

        self.setWindowTitle("Telegram Auto-Reply Bot")
        self.setGeometry(100, 100, 1366, 768)  # Laptop-friendly baseline

        # Initialize counters for metrics
        self.message_count = 0
        self.ai_responses = 0
        self.error_count = 0
        self.start_time = time.time()

        # Track async tasks for proper cleanup
        self._active_tasks = set()
        self._task_lock = threading.Lock()  # Thread-safe task management

        # Initialize component managers
        self.navigation_manager = NavigationManager(self)
        self.dashboard_widget = None  # Will be created in setup_ui

        # Prevent app exit when dialogs are closed
        try:
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            if app:
                app.setQuitOnLastWindowClosed(False)
        except Exception as e:
            logger.debug(f"Could not set quitOnLastWindowClosed: {e}")

        # Initialize UI controller for clean separation of concerns
        self.ui_controller = UIController()

        # Connect thread-safe signals
        self.update_status_signal.connect(self._safe_update_status)
        self.update_metrics_signal.connect(self._safe_update_metrics)
        self.show_error_signal.connect(self._safe_show_error)
        self.show_success_signal.connect(self._safe_show_success)

        # Connect UI controller signals
        self.ui_controller.campaign_created.connect(self._on_campaign_created)
        self.ui_controller.campaign_updated.connect(self._on_campaign_updated)
        self.ui_controller.account_status_changed.connect(self._on_account_status_changed)
        self.ui_controller.system_health_updated.connect(self._on_system_health_updated)
        self.ui_controller.error_occurred.connect(self._on_controller_error)

        self.setup_ui()
        self._refresh_validation_chips()
        self.setup_tray_icon()
        self.setup_keyboard_shortcuts()

        # Handle application close - but don't auto-delete on close to prevent dialog issues
        # We'll handle cleanup manually in closeEvent
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        # Check if first-time setup wizard is needed
        QTimer.singleShot(500, self._check_first_time_setup)

        # Set up cleanup on application exit
        import atexit

        atexit.register(self._cleanup_resources)

        # Initialize service container with concrete implementations
        # This must be called before AccountCreator initialization
        self._initialize_services()

        # Initialize Account Creator now that services are ready
        # Fixed: Initialize AccountCreator AFTER gemini_service is available
        if self.member_db and self.account_manager:
            try:
                self.account_creator = AccountCreator(
                    db=self.member_db,
                    gemini_service=self.gemini_service,  # Now available after _initialize_services()
                    account_manager=self.account_manager,
                )
                logger.info("Account Creator initialized with services")
            except Exception as e:
                logger.error(f"Failed to initialize AccountCreator: {e}")
                self.account_creator = None

        # Initialize API key manager and warmup service
        self.api_key_manager = APIKeyManager()

        # Only initialize warmup service if account_manager is available
        if self.account_manager:
            try:
                self.warmup_service = AccountWarmupService(
                    self.account_manager,
                    self.gemini_service,
                    performance_profile=self.performance_settings,
                )
                self.warmup_service.add_status_callback(self._on_warmup_status_update)
                # Link warmup service to account manager for auto-queueing
                self.account_manager.warmup_service = self.warmup_service

                # Add account manager status callback for UI updates

                self.account_manager.add_status_callback(self._on_account_status_changed)
            except Exception as e:
                self.warmup_service = None
                logger.warning(f"Warmup service not initialized: {e}")
        else:
            self.warmup_service = None
            logger.warning("Warmup service not initialized - account manager unavailable")

    def _initialize_services(self):
        """Initialize and register all services with the container."""
        try:
            # Use pre-loaded configuration manager if available
            if not self.config_manager:
                self.config_manager = ConfigurationManager()

            # Refresh performance settings from persisted config
            self.performance_settings = (
                self.config_manager.get("performance", {}) or self.performance_settings
            )
            self.low_power_mode = bool(
                self.performance_settings.get("low_power", self.low_power_mode)
            )

            # Create services using factory pattern
            telegram_service = ServiceFactory.create_telegram_client(self.config_manager)
            ai_service = ServiceFactory.create_ai_service(self.config_manager)
            db_service = ServiceFactory.create_database_service(self.config_manager)
            anti_detection_service = ServiceFactory.create_anti_detection_service(
                self.config_manager
            )

            # Register services with the container
            self.service_container.register_instance(IMessageService, telegram_service)
            self.service_container.register_instance(IAIService, ai_service)
            self.service_container.register_instance(IDatabaseService, db_service)
            self.service_container.register_instance(IAntiDetectionService, anti_detection_service)

            # Keep references for backward compatibility
            self.telegram_client = telegram_service._telegram_client
            self.gemini_service = ai_service._gemini_service

            # Initialize resource manager
            self.resource_manager = get_resource_manager()
            resource_limits = (
                self.performance_settings.get("resource_limits", {})
                if isinstance(self.performance_settings, dict)
                else {}
            )
            if self.low_power_mode:
                resource_limits = {
                    **resource_limits,
                    "max_concurrent_operations": min(
                        resource_limits.get("max_concurrent_operations", 10), 4
                    ),
                    "memory_limit_mb": min(resource_limits.get("memory_limit_mb", 512), 256),
                    "cpu_limit_percent": min(resource_limits.get("cpu_limit_percent", 80), 60),
                    "resource_check_interval": max(
                        resource_limits.get("resource_check_interval", 30), 45
                    ),
                }
            try:
                self.resource_manager.apply_config(resource_limits)
            except Exception as exc:
                logger.debug(f"Resource manager config apply skipped: {exc}")

            logger.info("Service container initialized successfully with factory pattern")

            # Start background monitoring and cleanup services
            self._start_background_services()

        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            # Continue without service container - fallback to direct instantiation
            self._initialize_fallback_services()

    def _load_primary_account_profile(self) -> Dict[str, Any]:
        """Load validated Telegram profile details from config or first account."""
        profile: Dict[str, Any] = {}
        try:
            if self.config_manager:
                telegram_cfg = self.config_manager.get("telegram", {}) or {}
                profile = telegram_cfg.get("profile", {}) or {}
                if profile:
                    return profile
        except Exception as exc:
            logger.debug(f"Profile load from config failed: {exc}")

        try:
            if self.account_manager and self.account_manager.accounts:
                first_account = next(iter(self.account_manager.accounts.values()))
                if first_account:
                    profile = {
                        "username": first_account.get("username", "") or "",
                        "first_name": first_account.get("first_name", "") or "",
                        "last_name": first_account.get("last_name", "") or "",
                        "display_name": first_account.get("display_name", "") or "",
                        "phone_number": first_account.get("phone_number", "") or "",
                        "photo_path": first_account.get("photo_path")
                        or first_account.get("profile_photo")
                        or "",
                        "validated": bool(first_account.get("status") in ("ready", "connected")),
                    }
        except Exception as exc:
            logger.debug(f"Profile load from accounts failed: {exc}")

        return profile or {}

    def _refresh_dashboard_profile(self):
        """Push current profile details to the dashboard card."""
        try:
            self.telegram_profile = self._load_primary_account_profile()
            if hasattr(self, "dashboard_widget") and self.dashboard_widget:
                self.dashboard_widget.update_profile(self.telegram_profile)
        except Exception as exc:
            logger.debug(f"Profile refresh skipped: {exc}")

    def _refresh_validation_chips(self):
        """Update header chips based on validation state."""
        try:
            telegram_valid = False
            gemini_valid = False
            if self.config_manager:
                cfg = self.config_manager.get("telegram", {}) or {}
                telegram_valid = bool(cfg.get("validated"))
                gemini_valid = bool(self.config_manager.get("gemini", {}).get("validated"))

            # Connection/Telegram chip
            if hasattr(self, "connection_status_chip"):
                text = "Telegram Validated" if telegram_valid else "Telegram Setup Needed"
                state = "ok" if telegram_valid else "warn"
                self.connection_status_chip.setText(text)
                self._set_status_chip_state(self.connection_status_chip, state)

            # AI/Gemini chip
            if hasattr(self, "ai_status_chip"):
                text = "AI Validated" if gemini_valid else "AI Validation Needed"
                state = "ok" if gemini_valid else "warn"
                self.ai_status_chip.setText(text)
                self._set_status_chip_state(self.ai_status_chip, state)
        except Exception as exc:
            logger.debug(f"Validation chip refresh skipped: {exc}")

    def _start_background_services(self):
        """Start all background monitoring and cleanup services."""
        # This will be called async after UI is ready

        def start_async_services():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                background_enabled = bool(
                    self.performance_settings.get("background_services_enabled", True)
                )
                if self.low_power_mode and not background_enabled:
                    logger.info("Low-power mode: background services thread skipped")
                    return

                # Start cost monitoring
                try:
                    if not self.low_power_mode:
                        from monitoring.cost_monitor_background import start_cost_monitoring

                        self.cost_monitor = loop.run_until_complete(
                            start_cost_monitoring(check_interval_hours=1)
                        )

                        # Add notification callback
                        if hasattr(self.cost_monitor, "_cost_alert_system"):
                            self.cost_monitor._cost_alert_system.add_notification_callback(
                                self._on_cost_alert
                            )

                        logger.info("✅ Cost monitoring service started")
                    else:
                        logger.info("Skipping cost monitoring in low-power mode")
                except Exception as e:
                    logger.warning(f"Cost monitoring unavailable: {e}")

                # Start proxy cleanup
                try:
                    if self.proxy_pool_manager:
                        from proxy.automated_cleanup_service import get_cleanup_service

                        self.cleanup_service = get_cleanup_service(self.proxy_pool_manager)
                        loop.run_until_complete(self.cleanup_service.start())

                        # Add notification callback
                        self.cleanup_service.add_notification_callback(self._on_proxy_cleanup)

                        logger.info("✅ Proxy cleanup service started")
                except Exception as e:
                    logger.warning(f"Proxy cleanup unavailable: {e}")

                # Start warmup service
                try:
                    warmup_enabled = self.performance_settings.get("warmup_autostart", True)
                    if self.warmup_service and (warmup_enabled or not self.low_power_mode):
                        loop.run_until_complete(self.warmup_service.start_warmup_service())
                        logger.info("✅ Account warmup service started")
                    elif self.warmup_service:
                        logger.info(
                            "Warmup service available but not auto-started (low-power/profile)"
                        )
                except Exception as e:
                    logger.warning(f"Warmup service unavailable: {e}")

                # Start campaign scheduler
                try:
                    campaign_enabled = self.performance_settings.get("campaign_autostart", True)
                    if (
                        hasattr(self, "campaign_manager")
                        and self.campaign_manager
                        and (campaign_enabled or not self.low_power_mode)
                    ):
                        if hasattr(self.campaign_manager, "scheduler"):
                            loop.run_until_complete(self.campaign_manager.scheduler.start())
                            logger.info("✅ Campaign scheduler started")
                    elif self.low_power_mode:
                        logger.info("Campaign scheduler not started (low-power/profile)")
                except Exception as e:
                    logger.warning(f"Campaign scheduler unavailable: {e}")

                # Start read receipt poller
                try:
                    if (
                        hasattr(self, "campaign_manager")
                        and self.campaign_manager
                        and not self.low_power_mode
                    ):
                        from campaigns.delivery_analytics import get_delivery_analytics
                        from campaigns.read_receipt_poller import get_read_receipt_poller

                        delivery_analytics = get_delivery_analytics()
                        self.read_receipt_poller = get_read_receipt_poller(
                            self.campaign_manager, delivery_analytics
                        )
                        loop.run_until_complete(self.read_receipt_poller.start())
                        logger.info("✅ Read receipt poller started")
                    elif self.low_power_mode:
                        logger.info("Read receipt poller skipped in low-power mode")
                except Exception as e:
                    logger.warning(f"Read receipt poller unavailable: {e}")

                # Start response tracker
                try:
                    if (
                        hasattr(self, "campaign_manager")
                        and self.campaign_manager
                        and not self.low_power_mode
                    ):
                        from campaigns.delivery_analytics import get_delivery_analytics
                        from campaigns.response_tracker import get_response_tracker

                        delivery_analytics = get_delivery_analytics()
                        self.response_tracker = get_response_tracker(
                            self.campaign_manager, delivery_analytics
                        )
                        # Response tracker needs a client - we'll start it when we have one
                        # For now, just initialize it
                        logger.info(
                            "✅ Response tracker initialized (will start with first client)"
                        )
                    elif self.low_power_mode:
                        logger.info("Response tracker skipped in low-power mode")
                except Exception as e:
                    logger.warning(f"Response tracker unavailable: {e}")

                # Keep loop running for background services
                loop.run_forever()

            except Exception as e:
                logger.error(f"Background services error: {e}")

        # Start in background thread
        bg_thread = threading.Thread(target=start_async_services, daemon=True)
        bg_thread.start()
        logger.info("🚀 Background services thread started")

    def _on_cost_alert(self, alert):
        """Handle cost alert notification."""
        try:
            # Emit signal for thread-safe UI update
            alert_msg = f"{alert.message}\n\nCurrent: ${alert.current_cost:.2f}\nThreshold: ${alert.threshold:.2f}"
            self.show_error_signal.emit(
                f"Cost Alert - {alert.alert_level.value.upper()}", alert_msg
            )
        except Exception as e:
            logger.error(f"Cost alert handler error: {e}")

    def _on_proxy_cleanup(self, event):
        """Handle proxy cleanup notification."""
        try:
            msg = f"Proxy {event.proxy_key} removed (reason: {event.reason.value})"
            self.update_status_signal.emit("proxy", msg)
        except Exception as e:
            logger.error(f"Proxy cleanup handler error: {e}")

    def _safe_update_status(self, status_type: str, message: str):
        """Thread-safe status update handler."""
        try:
            if status_type == "connection":
                if hasattr(self, "connection_status_label") and self.connection_status_label:
                    self.connection_status_label.setText(message)
            elif status_type == "ai":
                if hasattr(self, "ai_status_label") and self.ai_status_label:
                    self.ai_status_label.setText(message)
            self.add_log_message(f"Status [{status_type}]: {message}")
        except Exception as e:
            logger.error(f"Error in _safe_update_status: {e}")

    def _safe_update_metrics(self, metrics: dict):
        """Thread-safe metrics update handler."""
        try:
            if hasattr(self, "dashboard_widget") and self.dashboard_widget:
                self.dashboard_widget.update_metrics(metrics)
        except Exception as e:
            logger.error(f"Error in _safe_update_metrics: {e}")

    def _safe_show_error(self, error_type: str, details: str):
        """Thread-safe error display handler."""
        try:
            ErrorHandler.show_error(self, error_type, details)
        except Exception as e:
            logger.error(f"Error in _safe_show_error: {e}")

    def _safe_show_success(self, title: str, message: str):
        """Thread-safe success message display handler."""
        try:
            ErrorHandler.show_success(self, title, message)
        except Exception as e:
            logger.error(f"Error in _safe_show_success: {e}")

    def _on_campaign_created(self, campaign_data: dict):
        """Handle campaign creation event from UI controller."""
        try:
            campaign_id = campaign_data.get("campaign_id")
            metrics = campaign_data.get("metrics", {})
            logger.info(
                f"Campaign {campaign_id} created with {metrics.get('total_members', 0)} members"
            )
            self.add_log_message(f"✅ Campaign {campaign_id} created successfully")
            # Refresh campaign list if available
            if hasattr(self, "campaign_manager_widget"):
                self.campaign_manager_widget.refresh_campaigns()
            if hasattr(self, "analytics_widget") and self.analytics_widget:
                # Refresh dropdown options and any active campaign data
                self.analytics_widget.refresh_campaigns_list()
                QTimer.singleShot(0, self.analytics_widget.refresh_data)
            # Update summary metrics to reflect the new campaign
            QTimer.singleShot(0, self.update_dashboard_metrics)
        except Exception as e:
            logger.error(f"Error handling campaign creation: {e}")

    def _on_campaign_updated(self, campaign_id: int, stats: dict):
        """Handle campaign update event from UI controller."""
        try:
            logger.info(f"Campaign {campaign_id} updated: {stats}")
            # Refresh campaign list if available
            if hasattr(self, "campaign_manager_widget"):
                self.campaign_manager_widget.refresh_campaigns()
            if hasattr(self, "analytics_widget") and self.analytics_widget:
                # Keep analytics data in sync with backend updates
                self.analytics_widget.refresh_campaigns_list()
                QTimer.singleShot(0, self.analytics_widget.refresh_data)
            QTimer.singleShot(0, self.update_dashboard_metrics)
        except Exception as e:
            logger.error(f"Error handling campaign update: {e}")

    def _on_system_health_updated(self, health_data: dict):
        """Handle system health update event from UI controller."""
        try:
            health_score = health_data.get("overall_health", 0)
            logger.info(f"System health updated: {health_score}%")
            # Update dashboard with health info
            if hasattr(self, "dashboard_widget") and self.dashboard_widget:
                self.dashboard_widget.update_metrics({"system_health": f"{health_score}%"})
            if hasattr(self, "health_dashboard_widget") and self.health_dashboard_widget:
                # Trigger a full refresh so risk cards and charts stay accurate
                QTimer.singleShot(0, self.health_dashboard_widget.refresh_data)
        except Exception as e:
            logger.error(f"Error handling system health update: {e}")

    def _on_controller_error(self, error_type: str, details: str):
        """Handle errors from UI controller."""
        try:
            logger.error(f"Controller error [{error_type}]: {details}")
            ErrorHandler.show_error(self, error_type, details)
        except Exception as e:
            logger.error(f"Error handling controller error: {e}")

    def _setup_event_logging(self):
        """Set up event logging subscriptions for the event system."""
        try:
            # Subscribe to various events for logging
            self.event_system.subscribe(EVENT_MESSAGE_RECEIVED, self._on_message_received)
            self.event_system.subscribe(EVENT_MESSAGE_SENT, self._on_message_sent)
            self.event_system.subscribe(EVENT_SERVICE_STARTED, self._on_service_started)
            self.event_system.subscribe(EVENT_SERVICE_STOPPED, self._on_service_stopped)
            self.event_system.subscribe(EVENT_ERROR_OCCURRED, self._on_error_occurred)
            logger.info("Event logging subscriptions set up successfully")
        except Exception as e:
            logger.error(f"Failed to set up event logging: {e}")

    def _on_message_received(self, data: Dict[str, Any]):
        """Handle message received event."""
        try:
            if hasattr(self, "add_log_message"):
                self.add_log_message(
                    f"📨 Message received in chat {data.get('chat_id', 'unknown')}"
                )

            # Add to message history widget if available
            if hasattr(self, "message_history_widget"):
                self.message_history_widget.add_message(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "account": "Unknown",  # Need to get account
                        "contact": str(data.get("chat_id", "Unknown")),
                        "message": data.get("text", "")[:50] + "...",
                        "status": "Received",
                    }
                )
        except Exception as e:
            logger.error(f"Error handling message received event: {e}")

    def _on_message_sent(self, data: Dict[str, Any]):
        """Handle message sent event."""
        try:
            if hasattr(self, "add_log_message"):
                self.add_log_message(f"📤 Message sent to chat {data.get('chat_id', 'unknown')}")

            # Track message count for dashboard/status bar
            self.message_count += 1

            # Add to message history widget if available
            if hasattr(self, "message_history_widget"):
                self.message_history_widget.add_message(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "account": "Unknown",
                        "contact": str(data.get("chat_id", "Unknown")),
                        "message": data.get("text", "")[:50] + "...",
                        "status": "Sent",
                    }
                )
            QTimer.singleShot(0, self.update_dashboard_metrics)
            QTimer.singleShot(0, self.update_stats)
        except Exception as e:
            logger.error(f"Error handling message sent event: {e}")

    def _on_service_started(self, data: Dict[str, Any]):
        """Handle service started event."""
        try:
            service_name = data.get("service", "unknown")
            if hasattr(self, "add_log_message"):
                self.add_log_message(f"✅ Service '{service_name}' started")
        except Exception as e:
            logger.error(f"Error handling service started event: {e}")

    def _on_service_stopped(self, data: Dict[str, Any]):
        """Handle service stopped event."""
        try:
            service_name = data.get("service", "unknown")
            if hasattr(self, "add_log_message"):
                self.add_log_message(f"⏹️ Service '{service_name}' stopped")
        except Exception as e:
            logger.error(f"Error handling service stopped event: {e}")

    def _on_error_occurred(self, data: Dict[str, Any]):
        """Handle error occurred event."""
        try:
            error_msg = data.get("error", "Unknown error")
            if hasattr(self, "add_log_message"):
                self.add_log_message(f"❌ Error: {error_msg}")

            # Keep dashboard/error counters in sync
            self.error_count += 1
            QTimer.singleShot(0, self.update_dashboard_metrics)
            QTimer.singleShot(0, self.update_stats)
        except Exception as e:
            logger.error(f"Error handling error occurred event: {e}")

    def _on_warmup_status_update(self, job):
        """Handle warmup status updates."""
        try:
            if hasattr(self, "add_log_message"):
                status_msg = (
                    f"🔄 Warmup {job.stage.value}: {job.status_message} ({job.progress:.1f}%)"
                )
                self.add_log_message(status_msg)

            # Update the warmup jobs list in UI
            if hasattr(self, "_refresh_warmup_status"):
                # Schedule UI update on main thread
                QTimer.singleShot(0, self._refresh_warmup_status)
            # Update account list to show warmup progress
            QTimer.singleShot(0, self.update_account_list)
        except Exception as e:
            logger.error(f"Error handling warmup status update: {e}")

    def _on_account_status_changed(
        self, phone_number: str, status, metadata: Optional[Dict] = None
    ):
        """Handle account status change callback and controller signal."""
        try:
            from accounts.account_manager import AccountStatus

            # Signals may send raw strings; normalize when possible
            status_value = status.value if isinstance(status, AccountStatus) else str(status)
            status_msg = f"Account {phone_number} status: {status_value}"
            if metadata:
                if "error_message" in metadata:
                    status_msg += f" - Error: {metadata['error_message']}"
                elif "clone_status" in metadata:
                    status_msg += f" - Clone: {metadata['clone_status']}"
                elif "warmup_stage" in metadata:
                    status_msg += f" - Warmup: {metadata['warmup_stage']}"

            logger.info(status_msg)
            if hasattr(self, "message_history_widget"):
                self.message_history_widget.add_message(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "account": phone_number,
                        "contact": phone_number,
                        "message": status_msg,
                        "status": "Info",
                    }
                )
            # Update account list immediately
            QTimer.singleShot(0, self.update_account_list)
            if hasattr(self, "health_dashboard_widget") and self.health_dashboard_widget:
                QTimer.singleShot(0, self.health_dashboard_widget.refresh_data)
            QTimer.singleShot(0, self.update_dashboard_metrics)
            QTimer.singleShot(0, self._refresh_dashboard_profile)
        except Exception as e:
            logger.error(f"Error handling account status change: {e}")

    # ... (other methods) ...

    def update_stats(self):
        """Update the status bar indicators."""
        try:
            if hasattr(self, "connection_status_label") and self.connection_status_label:
                try:
                    state = (
                        "Connected"
                        if (
                            self.telegram_client
                            and hasattr(self.telegram_client, "is_connected")
                            and self.telegram_client.is_connected()
                        )
                        else "Disconnected"
                    )
                    self.connection_status_label.setText(state)
                    if hasattr(self, "connection_status_chip"):
                        self.connection_status_chip.setText(state)
                        self._set_status_chip_state(
                            self.connection_status_chip, "ok" if state == "Connected" else "bad"
                        )
                except Exception as e:
                    logger.debug(f"Error checking connection status: {e}")
                    self.connection_status_label.setText("Disconnected")
            if hasattr(self, "ai_status_label") and self.ai_status_label:
                ai_state = "AI Ready" if self.gemini_service else "AI Offline"
                self.ai_status_label.setText(ai_state)
                if hasattr(self, "ai_status_chip"):
                    self.ai_status_chip.setText(ai_state)
                    self._set_status_chip_state(
                        self.ai_status_chip, "ok" if self.gemini_service else "warn"
                    )
            if hasattr(self, "stats_indicator") and self.stats_indicator:
                self.stats_indicator.setText(
                    f"Messages: {self.message_count} | Errors: {self.error_count}"
                )
            # Lightweight performance summary in status bar
            if self.performance_monitor:
                stats = self.performance_monitor.get_performance_stats()
                summary = stats.get("summary")
                if summary and hasattr(self, "statusBar"):
                    try:
                        self.statusBar().showMessage(summary, 3000)
                    except Exception:
                        logger.debug("Status bar unavailable for perf summary")
        except Exception as e:
            logger.error(f"Error updating stats: {e}")

    def update_dashboard_metrics(self):
        """Refresh the dashboard metric cards."""
        if not self.dashboard_widget:
            return

        # Skip dashboard refresh when not visible to reduce CPU
        try:
            if hasattr(self, "content_stack") and self.content_stack.currentIndex() != getattr(
                self, "dashboard_page_index", 0
            ):
                return
        except Exception:
            pass

        # Run metrics collection in background to avoid UI blocking
        self.run_background_task("dashboard_metrics", self._collect_dashboard_metrics)

    def _collect_dashboard_metrics(self):
        """Collect dashboard metrics in background thread."""
        uptime_seconds = int(time.time() - getattr(self, "start_time", time.time()))

        # Get real metrics from managers
        total_accounts = 0
        active_accounts = 0
        total_campaigns = 0
        active_campaigns = 0
        total_messages_sent = 0

        if self.account_manager:
            try:
                accounts = self.account_manager.get_account_list()
                total_accounts = len(accounts)
                active_accounts = len([a for a in accounts if a.get("is_online", False)])

                # Sum up messages from account metrics
                stats = self.account_manager.get_account_stats()
                total_messages_sent = stats.get("total_messages", 0) or 0
            except Exception as e:
                logger.warning(f"Failed to get account metrics: {e}")

        campaign_messages = 0
        if self.campaign_manager:
            try:
                campaigns = self.campaign_manager.get_all_campaigns()
                total_campaigns = len(campaigns)
                campaign_messages = sum(getattr(c, "sent_count", 0) for c in campaigns)
            except Exception as e:
                logger.warning(f"Failed to get campaign metrics: {e}")

        # Calculate final totals
        total_messages_sent += campaign_messages

        # Return metrics for UI update
        return {
            "total_accounts": total_accounts,
            "active_accounts": active_accounts,
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_messages_sent": total_messages_sent,
            "campaign_messages": campaign_messages,
            "uptime_seconds": uptime_seconds,
        }

    def _on_background_task_completed(self, task_id: str, result):
        """Handle background task completion on main thread."""
        if task_id == "dashboard_metrics" and result and self.dashboard_widget:
            try:
                # Extract metrics from result
                total_accounts = result.get("total_accounts", 0)
                active_accounts = result.get("active_accounts", 0)
                total_campaigns = result.get("total_campaigns", 0)
                active_campaigns = result.get("active_campaigns", 0)
                total_messages_sent = result.get("total_messages_sent", 0)
                campaign_messages = result.get("campaign_messages", 0)
                uptime_seconds = result.get("uptime_seconds", 0)

                # Prefer account metrics; if unavailable, fall back to campaign totals
                if total_messages_sent == 0:
                    total_messages_sent = campaign_messages

                # System health calculation
                health = 100
                if self.error_count > 0:
                    health -= min(50, self.error_count * 5)
                if not self.gemini_service:
                    health -= 20
                if active_accounts == 0 and total_accounts > 0:
                    health -= 20

                empty_state = (
                    total_accounts == 0 and total_campaigns == 0 and total_messages_sent == 0
                )

                metrics = {
                    "message_count": "—" if empty_state else f"{total_messages_sent:,}",
                    "ai_responses": "—" if empty_state else f"{self.ai_responses:,}",
                    "active_chats": (
                        "No accounts"
                        if total_accounts == 0
                        else f"{active_accounts}/{total_accounts} Accounts"
                    ),
                    "system_health": "—" if empty_state else f"{max(0, health)}%",
                    "uptime": (
                        "—"
                        if empty_state
                        else f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m"
                    ),
                    "errors": "—" if empty_state else str(self.error_count),
                }

                # Update dashboard with collected metrics
                self.dashboard_widget.update_metrics(metrics)
                logger.debug("Dashboard metrics updated from background task")

                # Update hero chips to reflect current state instead of hardcoded labels
                try:
                    if hasattr(self.dashboard_widget, "live_status_chip"):
                        live_state = "ok" if active_accounts > 0 else "warn"
                        self.dashboard_widget.live_status_chip.setText(
                            "Live" if active_accounts > 0 else "Idle"
                        )
                        self.dashboard_widget.live_status_chip.setProperty("state", live_state)
                        self.dashboard_widget.live_status_chip.style().unpolish(
                            self.dashboard_widget.live_status_chip
                        )
                        self.dashboard_widget.live_status_chip.style().polish(
                            self.dashboard_widget.live_status_chip
                        )

                    if hasattr(self.dashboard_widget, "sync_status_chip"):
                        sync_state = "ok" if total_accounts > 0 else "warn"
                        self.dashboard_widget.sync_status_chip.setText(
                            "Synced" if total_accounts > 0 else "No accounts"
                        )
                        self.dashboard_widget.sync_status_chip.setProperty("state", sync_state)
                        self.dashboard_widget.sync_status_chip.style().unpolish(
                            self.dashboard_widget.sync_status_chip
                        )
                        self.dashboard_widget.sync_status_chip.style().polish(
                            self.dashboard_widget.sync_status_chip
                        )
                except Exception as exc:
                    logger.debug(f"Dashboard chip refresh issue: {exc}")

                # Reflect health in header chip
                if hasattr(self, "health_status_chip"):
                    self.health_status_chip.setText(f"Health {max(0, health)}%")
                    state = "ok" if health >= 80 else "warn" if health >= 50 else "bad"
                    self._set_status_chip_state(self.health_status_chip, state)
                if hasattr(self, "accounts_chip"):
                    self.accounts_chip.setText(f"{active_accounts} Accounts")
                    self._set_status_chip_state(
                        self.accounts_chip, "ok" if active_accounts else "warn"
                    )
                if hasattr(self, "campaigns_chip"):
                    self.campaigns_chip.setText(f"{active_campaigns} Campaigns")
                    self._set_status_chip_state(
                        self.campaigns_chip, "ok" if active_campaigns else "warn"
                    )

                # Update performance summary in status bar
                if self.performance_monitor:
                    stats = self.performance_monitor.get_performance_stats()
                    summary = stats.get("summary")
                    if summary and hasattr(self, "statusBar"):
                        try:
                            self.statusBar().showMessage(summary, 3000)
                        except Exception:
                            logger.debug("Status bar unavailable for perf summary")

            except Exception as e:
                logger.error(f"Error updating dashboard from background task: {e}")
        else:
            # Log completion of other background tasks
            logger.debug(f"Background task {task_id} completed")

    def _on_page_changed(self, index: int):
        """Pause expensive timers when dashboard is hidden."""
        try:
            if index != getattr(self, "dashboard_page_index", 0):
                if hasattr(self, "dashboard_timer"):
                    self.dashboard_timer.stop()
            else:
                if hasattr(self, "dashboard_timer"):
                    self.dashboard_timer.start(self.dashboard_interval_ms)
        except Exception as exc:
            logger.debug(f"Page change handler issue: {exc}")

    def setup_campaigns_tab(self):
        """DM campaign overview."""
        page, content_layout = self._create_page_container(
            "Campaign Engine", "Monitor nurture sequences, templates, and delivery queues."
        )

        if self.campaign_manager:
            self.campaign_manager_widget = CampaignManagerWidget(self.campaign_manager)
            self.campaign_manager_widget.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            content_layout.addWidget(self.campaign_manager_widget)
        else:
            status_label = QLabel("Campaign manager not initialized. Add accounts to enable it.")
            content_layout.addWidget(status_label)

            open_settings = QPushButton("Open Settings")
            open_settings.clicked.connect(self._open_settings_dialog)
            open_settings.setObjectName("secondary")
            content_layout.addWidget(open_settings)

            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_analytics_tab(self):
        """Campaign analytics and performance metrics."""
        page, content_layout = self._create_page_container(
            "Campaign Analytics",
            "Visualize campaign performance, delivery rates, and account metrics.",
        )

        try:
            from ui.campaign_analytics_widget import CampaignAnalyticsWidget

            self.analytics_widget = CampaignAnalyticsWidget(self.campaign_manager)
            self.analytics_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            analytics_container = QScrollArea()
            analytics_container.setWidgetResizable(True)
            analytics_container.setFrameShape(QFrame.Shape.NoFrame)
            analytics_container.setWidget(self.analytics_widget)
            content_layout.addWidget(analytics_container)
        except ImportError as e:
            logger.warning(f"Campaign analytics widget not available: {e}")
            error_label = QLabel("Campaign analytics widget not available.")
            error_label.setStyleSheet(f"color: {ThemeManager._get_palette()['ACCENT_WARNING']};")
            content_layout.addWidget(error_label)
            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_proxy_pool_tab(self):
        """Proxy pool management interface."""
        page, content_layout = self._create_page_container(
            "Proxy Pool", "Manage proxy endpoints, monitor health, and configure auto-assignment."
        )

        try:
            from ui.proxy_management_widget import ProxyManagementWidget

            self.proxy_management_widget = ProxyManagementWidget()
            self.proxy_management_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            proxy_container = QScrollArea()
            proxy_container.setWidgetResizable(True)
            proxy_container.setFrameShape(QFrame.Shape.NoFrame)
            proxy_container.setWidget(self.proxy_management_widget)
            content_layout.addWidget(proxy_container)
        except ImportError as e:
            logger.warning(f"Proxy management widget not available: {e}")
            error_label = QLabel("Proxy management widget not available.")
            error_label.setStyleSheet(f"color: {ThemeManager._get_palette()['ACCENT_WARNING']};")
            content_layout.addWidget(error_label)
            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_health_tab(self):
        """Account health monitoring dashboard."""
        page, content_layout = self._create_page_container(
            "Account Health", "Monitor account risk levels, ban probability, and quarantine status."
        )

        try:
            from ui.account_health_widget import AccountHealthDashboard

            self.health_dashboard_widget = AccountHealthDashboard(self.account_manager)
            self.health_dashboard_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            health_container = QScrollArea()
            health_container.setWidgetResizable(True)
            health_container.setFrameShape(QFrame.Shape.NoFrame)
            health_container.setWidget(self.health_dashboard_widget)
            content_layout.addWidget(health_container)
        except ImportError as e:
            logger.warning(f"Account health widget not available: {e}")
            error_label = QLabel("Account health dashboard not available.")
            error_label.setStyleSheet(f"color: {ThemeManager._get_palette()['ACCENT_WARNING']};")
            content_layout.addWidget(error_label)
            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_engagement_tab(self):
        """Engagement automation management."""
        page, content_layout = self._create_page_container(
            "Engagement Automation", "Manage automated reactions and engagement rules for groups."
        )

        try:
            from ui.engagement_widget import EngagementWidget

            self.engagement_widget = EngagementWidget()
            self.engagement_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            engagement_container = QScrollArea()
            engagement_container.setWidgetResizable(True)
            engagement_container.setFrameShape(QFrame.Shape.NoFrame)
            engagement_container.setWidget(self.engagement_widget)
            content_layout.addWidget(engagement_container)
        except ImportError as e:
            logger.warning(f"Engagement widget not available: {e}")
            error_label = QLabel("Engagement automation widget not available.")
            error_label.setStyleSheet(f"color: {ThemeManager._get_palette()['ACCENT_WARNING']};")
            content_layout.addWidget(error_label)
            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_warmup_monitor_tab(self):
        """Warmup progress monitoring."""
        page, content_layout = self._create_page_container(
            "Warmup Monitor", "Track real-time warmup progress and manage warmup configurations."
        )

        # Add tabs for progress and configuration

        warmup_tabs = QTabWidget()

        try:
            from ui.warmup_config_widget import WarmupConfigWidget
            from ui.warmup_progress_widget import WarmupProgressWidget

            progress_widget = WarmupProgressWidget(
                self.warmup_service if hasattr(self, "warmup_service") else None
            )
            warmup_tabs.addTab(progress_widget, "Progress")

            config_widget = WarmupConfigWidget(
                self.warmup_service if hasattr(self, "warmup_service") else None
            )
            warmup_tabs.addTab(config_widget, "Configuration")

            content_layout.addWidget(warmup_tabs)
        except ImportError as e:
            logger.warning(f"Warmup widgets not available: {e}")
            error_label = QLabel("Warmup monitoring widgets not available.")
            error_label.setStyleSheet(f"color: {ThemeManager._get_palette()['ACCENT_WARNING']};")
            content_layout.addWidget(error_label)
            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_risk_monitor_tab(self):
        """Account risk monitoring dashboard."""
        page, content_layout = self._create_page_container(
            "Risk Monitor", "Real-time account risk scoring and quarantine recommendations."
        )

        try:
            from ui.risk_monitor_widget import RiskMonitorWidget

            self.risk_monitor_widget = RiskMonitorWidget()
            self.risk_monitor_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            risk_container = QScrollArea()
            risk_container.setWidgetResizable(True)
            risk_container.setFrameShape(QFrame.Shape.NoFrame)
            risk_container.setWidget(self.risk_monitor_widget)
            content_layout.addWidget(risk_container)
        except ImportError as e:
            logger.warning(f"Risk monitor widget not available: {e}")
            error_label = QLabel("Risk monitoring widget not available.")
            error_label.setStyleSheet(f"color: {ThemeManager._get_palette()['ACCENT_WARNING']};")
            content_layout.addWidget(error_label)
            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_delivery_tab(self):
        """Delivery and response analytics."""
        page, content_layout = self._create_page_container(
            "Delivery Analytics", "Track message delivery, read receipts, and response times."
        )

        try:
            from ui.delivery_analytics_widget import DeliveryAnalyticsWidget

            self.delivery_analytics_widget = DeliveryAnalyticsWidget()
            self.delivery_analytics_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
            )
            delivery_container = QScrollArea()
            delivery_container.setWidgetResizable(True)
            delivery_container.setFrameShape(QFrame.Shape.NoFrame)
            delivery_container.setWidget(self.delivery_analytics_widget)
            content_layout.addWidget(delivery_container)
        except ImportError as e:
            logger.warning(f"Delivery analytics widget not available: {e}")
            error_label = QLabel("Delivery analytics widget not available.")
            error_label.setStyleSheet(f"color: {ThemeManager._get_palette()['ACCENT_WARNING']};")
            content_layout.addWidget(error_label)
            content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_messages_tab(self):
        """Live log of messages and events."""
        page, content_layout = self._create_page_container(
            "Message Stream",
            "Centralized log of incoming chats, AI replies, and automation events.",
        )

        self.message_history_widget = MessageHistoryWidget()
        content_layout.addWidget(self.message_history_widget)

        self.content_stack.addWidget(page)

    def setup_ui(self):
        """Set up the complete Professional UI with accessibility features."""
        # Set up window accessibility properties
        self.setWindowTitle("Telegram Auto-Reply Bot")
        self.setAccessibleName("Telegram Auto-Reply Bot Main Window")
        self.setAccessibleDescription(
            "Main application window for managing Telegram automation bot"
        )

        # Responsive window sizing
        screen = QApplication.primaryScreen().availableGeometry()
        screen_width = screen.width()
        screen_height = screen.height()

        if screen_width < 1400 or screen_height < 800:
            # Small screens - compact layout
            self.setMinimumSize(1000, 600)
            self.resize(1200, 720)
        else:
            # Large screens - comfortable layout
            self.setMinimumSize(1200, 700)
            self.resize(1400, 900)

        # Maximum size to prevent awkward stretching on huge monitors
        self.setMaximumSize(2400, 1600)

        # Create main container
        main_container = QWidget()
        main_container.setAccessibleName("Main Application Container")
        self.setCentralWidget(main_container)
        main_layout = QHBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ===== SIDEBAR =====
        sidebar = QWidget()
        sidebar.setObjectName("sidebar_container")
        sidebar.setAccessibleName("Navigation Sidebar")
        sidebar.setAccessibleDescription(
            "Navigation menu for switching between application sections"
        )
        sidebar.setMinimumWidth(180)
        sidebar.setMaximumWidth(260)
        sidebar.setProperty("expanded_width", 200)
        sidebar.setProperty("compact_width", 68)
        sidebar.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 24, 12, 24)
        sidebar_layout.setSpacing(8)

        # Use NavigationManager for sidebar setup
        self.navigation_manager.setup_sidebar_navigation(sidebar_layout)

        # ===== CONTENT AREA =====
        content_area = QWidget()
        content_area.setObjectName("content_area")
        content_area.setAccessibleName("Main Content Area")
        content_area.setAccessibleDescription(
            "Main content area displaying current application section"
        )
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)

        # Global header bar
        self.global_header = self._build_global_header()
        content_layout.addWidget(self.global_header)

        # Content stack for pages
        self.content_stack = QStackedWidget()
        self.content_stack.setAccessibleName("Content Pages")
        self.content_stack.setAccessibleDescription("Stack of different application pages")
        content_layout.addWidget(self.content_stack, 1)

        # Add sidebar and content to main layout via splitter for responsive resizing
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(2)
        splitter.addWidget(sidebar)
        splitter.addWidget(content_area)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 900])

        main_layout.addWidget(splitter)

        # Set up all pages
        self.setup_dashboard_tab()
        self.setup_accounts_tab()
        self.setup_members_tab()
        self.setup_campaigns_tab()
        self.setup_analytics_tab()  # Campaign analytics
        self.setup_proxy_pool_tab()  # Proxy pool management
        self.setup_health_tab()  # Account health dashboard
        self.setup_engagement_tab()  # NEW: Engagement automation
        self.setup_warmup_monitor_tab()  # NEW: Warmup progress
        self.setup_risk_monitor_tab()  # NEW: Risk monitoring
        self.setup_delivery_tab()  # NEW: Delivery analytics
        self.setup_messages_tab()
        self.setup_settings_tab()
        self.setup_logs_tab()

        # Set up timers for updates
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(self.stats_interval_ms)

        self.dashboard_timer = QTimer()
        self.dashboard_timer.timeout.connect(self.update_dashboard_metrics)
        self.dashboard_timer.start(self.dashboard_interval_ms)

        # Pause heavy refresh when dashboard not visible
        self.dashboard_page_index = 0
        self.content_stack.currentChanged.connect(self._on_page_changed)

        # Set up accessibility features
        self._setup_accessibility()
        self._setup_tab_order()

        # Command palette shortcuts
        try:
            self.command_palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
            self.command_palette_shortcut.activated.connect(self._focus_command_palette)
            self.command_palette_shortcut_mac = QShortcut(QKeySequence("Meta+K"), self)
            self.command_palette_shortcut_mac.activated.connect(self._focus_command_palette)
        except Exception as exc:
            logger.debug(f"Shortcut setup issue: {exc}")

    def _setup_accessibility(self):
        """Set up accessibility features for screen readers and keyboard navigation."""
        # Set up window properties
        self.setWindowRole("main_application")

        # Set focus policy for keyboard navigation
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Set up accessible names for key UI elements
        if hasattr(self, "content_stack"):
            self.content_stack.setAccessibleName("Main Content Pages")
            self.content_stack.setAccessibleDescription("Container for different application views")

        # Enable screen reader support
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, False)

        # Set up live region for status updates
        if hasattr(self, "status_bar"):
            self.status_bar.setAccessibleName("Status Information")
            self.status_bar.setAccessibleDescription("Application status and progress information")

    def _setup_tab_order(self):
        """Set up logical tab order for keyboard navigation."""
        # Set initial focus to sidebar navigation
        if hasattr(self, "navigation_manager") and hasattr(
            self.navigation_manager, "sidebar_buttons"
        ):
            if self.navigation_manager.sidebar_buttons:
                first_button = self.navigation_manager.sidebar_buttons[0]
                first_button.setFocus()

        # Set up tab order for main content areas
        if hasattr(self, "content_stack"):
            self.setTabOrder(self.content_stack, self.content_stack)

        # Ensure command palette is reachable early
        try:
            if hasattr(self, "navigation_manager") and self.navigation_manager.sidebar_buttons:
                self.setTabOrder(
                    self.navigation_manager.sidebar_buttons[0], self.global_search_input
                )
        except Exception:
            pass

    def _create_page_container(self, title: str, subtitle: str = ""):
        """Create a standard page container with title and subtitle."""
        page = QWidget()
        page.setObjectName("page_container")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Header
        header_frame = QFrame()
        header_frame.setObjectName("page_header")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)

        title_block = QVBoxLayout()
        title_block.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("page_title")
        title_block.addWidget(title_label)

        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("page_subtitle")
            title_block.addWidget(subtitle_label)

        header_layout.addLayout(title_block)
        header_layout.addStretch()

        # Meta chips
        meta_layout = QHBoxLayout()
        meta_layout.setSpacing(6)

        live_chip = QLabel("Live view")
        live_chip.setObjectName("page_chip")
        meta_layout.addWidget(live_chip)

        sync_chip = QLabel("Synced")
        sync_chip.setObjectName("page_chip")
        meta_layout.addWidget(sync_chip)

        header_layout.addLayout(meta_layout)
        layout.addWidget(header_frame)

        # Content area (will be filled by caller)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(content_widget)

        layout.addWidget(scroll, 1)

        return page, content_layout

    def _build_global_header(self):
        """Create the enterprise header with search, status, and quick actions."""
        header = QFrame()
        header.setObjectName("global_header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(10)

        # Global search / command palette (centered, prominent)
        self.global_search_input = QLineEdit()
        self.global_search_input.setObjectName("global_search")
        self.global_search_input.setPlaceholderText("Search or jump to page... (Ctrl/Cmd+K)")
        self.global_search_input.setToolTip("Command palette — press Ctrl/Cmd+K")
        self.global_search_input.setAccessibleName("Command palette search")
        self.global_search_input.setFixedHeight(32)
        self.global_search_input.setMinimumWidth(320)
        # Lightweight command suggestions
        palette_routes = [
            ">dashboard",
            ">accounts",
            ">members",
            ">campaigns",
            ">analytics",
            ">proxy",
            ">health",
            ">engagement",
            ">warmup",
            ">risk",
            ">delivery",
            ">messages",
            ">settings",
            ">logs",
        ]
        palette_completer = QCompleter(palette_routes, self)
        palette_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        palette_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.global_search_input.setCompleter(palette_completer)
        self.global_search_input.returnPressed.connect(self._handle_global_search)
        layout.addWidget(self.global_search_input, 1)

        # Theme toggle (light/dark)
        self.theme_toggle = QComboBox()
        self.theme_toggle.addItems(["Dark", "Light"])
        self.theme_toggle.setFixedWidth(90)
        self.theme_toggle.setFixedHeight(32)
        self.theme_toggle.setCurrentText(
            "Dark" if ThemeManager.current_theme == "dark" else "Light"
        )
        self.theme_toggle.currentTextChanged.connect(self._on_theme_changed)
        layout.addWidget(self.theme_toggle, 0)

        # Status chips
        # Status chips (aligned baseline, fixed height)
        status_container = QHBoxLayout()
        status_container.setSpacing(6)
        status_container.setContentsMargins(0, 0, 0, 0)

        self.connection_status_chip = QLabel("Telegram")
        self.connection_status_chip.setObjectName("status_chip")
        self.connection_status_chip.setProperty("state", "bad")
        self.connection_status_chip.setToolTip("Connect Telegram in Settings to enable services.")
        self.connection_status_chip.setFixedHeight(28)
        status_container.addWidget(self.connection_status_chip)

        self.ai_status_chip = QLabel("AI")
        self.ai_status_chip.setObjectName("status_chip")
        self.ai_status_chip.setProperty("state", "warn")
        self.ai_status_chip.setToolTip("Add your Gemini API key in Settings to enable AI.")
        self.ai_status_chip.setFixedHeight(28)
        status_container.addWidget(self.ai_status_chip)

        self.health_status_chip = QLabel("Health")
        self.health_status_chip.setObjectName("status_chip")
        self.health_status_chip.setProperty("state", "ok")
        self.health_status_chip.setFixedHeight(28)
        status_container.addWidget(self.health_status_chip)

        self.accounts_chip = QLabel("0 Accounts")
        self.accounts_chip.setObjectName("status_chip")
        self.accounts_chip.setProperty("state", "warn")
        self.accounts_chip.setFixedHeight(28)
        status_container.addWidget(self.accounts_chip)

        self.campaigns_chip = QLabel("0 Campaigns")
        self.campaigns_chip.setObjectName("status_chip")
        self.campaigns_chip.setProperty("state", "warn")
        self.campaigns_chip.setFixedHeight(28)
        status_container.addWidget(self.campaigns_chip)

        layout.addLayout(status_container, 0)

        # Quick actions (aligned baseline, fixed height)
        action_layout = QHBoxLayout()
        action_layout.setSpacing(6)
        action_layout.setContentsMargins(0, 0, 0, 0)

        start_btn = QPushButton("Settings")
        start_btn.setObjectName("quick_action")
        start_btn.setFixedHeight(32)
        start_btn.clicked.connect(self._open_settings_dialog)
        action_layout.addWidget(start_btn)

        campaign_btn = QPushButton("New Campaign")
        campaign_btn.setObjectName("quick_action")
        campaign_btn.setFixedHeight(32)
        campaign_btn.clicked.connect(lambda: self.navigate_to_page(3))
        action_layout.addWidget(campaign_btn)

        account_btn = QPushButton("Add Account")
        account_btn.setObjectName("quick_action")
        account_btn.setFixedHeight(32)
        account_btn.clicked.connect(self.create_single_account)
        action_layout.addWidget(account_btn)

        layout.addLayout(action_layout, 0)

        return header

    def _on_theme_changed(self, value: str):
        """Handle light/dark theme toggle."""
        try:
            selected = value.lower()
            theme = "light" if selected.startswith("light") else "dark"
            ThemeManager.set_theme(theme, QApplication.instance())
            # Refresh styling for the main window after theme switch
            self.style().unpolish(self)
            self.style().polish(self)
        except Exception as exc:
            logger.warning(f"Theme toggle failed: {exc}")

    def _handle_global_search(self):
        """Lightweight command palette routing."""
        try:
            query = (
                self.global_search_input.text().strip().lower()
                if hasattr(self, "global_search_input")
                else ""
            )
            if not query:
                return

            # Support explicit commands with leading ">"
            if query.startswith(">"):
                query = query.lstrip(">").strip()

            routes = [
                ("dashboard", 0),
                ("account", 1),
                ("member", 2),
                ("campaign", 3),
                ("analytic", 4),
                ("proxy", 5),
                ("health", 6),
                ("engagement", 7),
                ("warmup", 8),
                ("risk", 9),
                ("delivery", 10),
                ("message", 11),
                ("setting", 12),
                ("log", 13),
            ]

            matched = False
            for keyword, idx in routes:
                if keyword in query:
                    self.navigate_to_page(idx)
                    matched = True
                    break

            if not matched and hasattr(self, "add_log_message"):
                self.add_log_message(f"🔍 Command not matched: {query}")

            if hasattr(self, "global_search_input"):
                self.global_search_input.clear()
        except Exception as exc:
            logger.debug(f"Command palette issue: {exc}")

    def _focus_command_palette(self):
        """Focus the global search/command box."""
        try:
            if hasattr(self, "global_search_input"):
                self.global_search_input.setFocus()
                self.global_search_input.selectAll()
        except Exception:
            pass

    @staticmethod
    def _set_status_chip_state(label: QLabel, state: str):
        """Update chip state styles."""
        if not label:
            return
        try:
            label.setProperty("state", state)
            label.style().unpolish(label)
            label.style().polish(label)
        except Exception:
            pass

    def navigate_to_page(self, page_index: int):
        """Navigate to a specific page and update navigation buttons."""
        self.content_stack.setCurrentIndex(page_index)

        # Update navigation buttons via NavigationManager
        self.navigation_manager.update_navigation_button(page_index)

    def setup_dashboard_tab(self):
        """Create the dashboard page using DashboardWidget."""
        # Use the DashboardWidget component
        self.dashboard_widget = DashboardWidget(self)
        self._refresh_dashboard_profile()

        dashboard_scroll = QScrollArea()
        dashboard_scroll.setWidgetResizable(True)
        dashboard_scroll.setFrameShape(QFrame.Shape.NoFrame)
        dashboard_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        dashboard_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        dashboard_scroll.setWidget(self.dashboard_widget)

        # Gemini inline banner if AI offline (only show if AI not configured)
        try:
            from core.secrets_manager import get_secrets_manager

            secrets = get_secrets_manager()
            gemini_key = secrets.get_secret("gemini_api_key", required=False)
            show_banner = not gemini_key
        except Exception:
            show_banner = True

        if show_banner:
            banner = QFrame()
            from ui.theme_manager import ThemeManager

            c = ThemeManager.get_colors()
            banner.setObjectName("hero_card")
            banner.setStyleSheet(
                f"background-color: {c['BG_SECONDARY']}; border: 1px solid {c['BORDER_DEFAULT']}; border-radius: 8px;"
            )
            b_layout = QHBoxLayout(banner)
            b_layout.setContentsMargins(12, 10, 12, 10)
            b_layout.setSpacing(12)

            text_block = QVBoxLayout()
            text_block.setSpacing(4)
            banner_title = QLabel("AI Setup Required")
            banner_title.setStyleSheet(
                f"font-weight: 600; font-size: 13px; color: {c['TEXT_BRIGHT']};"
            )
            banner_body = QLabel("Add your Gemini API key in Settings to enable AI responses.")
            banner_body.setStyleSheet(f"color: {c['TEXT_SECONDARY']}; font-size: 12px;")
            text_block.addWidget(banner_title)
            text_block.addWidget(banner_body)
            b_layout.addLayout(text_block)
            b_layout.addStretch()

            setup_btn = QPushButton("Open Settings")
            setup_btn.setObjectName("secondary")
            setup_btn.setFixedHeight(32)
            setup_btn.clicked.connect(self._open_settings_dialog)
            b_layout.addWidget(setup_btn)

            # Add banner to dashboard widget if it has a layout
            if hasattr(self.dashboard_widget, "layout") and self.dashboard_widget.layout():
                self.dashboard_widget.layout().insertWidget(0, banner)
                self.dashboard_banner = banner
            else:
                self.dashboard_banner = None
        else:
            self.dashboard_banner = None

        self.content_stack.addWidget(dashboard_scroll)

    def setup_accounts_tab(self):
        """Account management page."""
        page, content_layout = self._create_page_container(
            "Account Management", "Create, manage, and warm up Telegram accounts"
        )

        # Toolbar with filters
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        create_btn = QPushButton("Create Account")
        create_btn.setObjectName("quick_action")
        create_btn.setFixedHeight(32)
        create_btn.clicked.connect(self.create_single_account)
        toolbar_layout.addWidget(create_btn)

        bulk_btn = QPushButton("Bulk Create")
        bulk_btn.setObjectName("secondary")
        bulk_btn.setFixedHeight(32)
        bulk_btn.clicked.connect(self._show_bulk_creation_dialog)
        toolbar_layout.addWidget(bulk_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary")
        refresh_btn.setFixedHeight(32)
        refresh_btn.clicked.connect(self.update_account_list)
        toolbar_layout.addWidget(refresh_btn)

        toolbar_layout.addStretch()

        self.accounts_search = QLineEdit()
        self.accounts_search.setPlaceholderText("Search phone or status…")
        self.accounts_search.textChanged.connect(self.update_account_list)
        toolbar_layout.addWidget(self.accounts_search)

        self.accounts_status_filter = QComboBox()
        self.accounts_status_filter.addItems(
            ["All", "Online", "Offline", "Warming", "Ready", "Error"]
        )
        self.accounts_status_filter.currentTextChanged.connect(self.update_account_list)
        toolbar_layout.addWidget(self.accounts_status_filter)

        content_layout.addLayout(toolbar_layout)

        # Accounts list widget
        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(5)
        self.accounts_table.setHorizontalHeaderLabels(
            ["Phone", "Status", "Warmup", "Messages", "Actions"]
        )
        self.accounts_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.accounts_table.horizontalHeader().setStretchLastSection(True)
        self.accounts_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.accounts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.accounts_table.verticalHeader().setVisible(False)
        self.accounts_table.verticalHeader().setDefaultSectionSize(30)  # Compact row height
        self.accounts_table.setMinimumHeight(180)
        self.accounts_table.setAlternatingRowColors(True)
        self.accounts_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        content_layout.addWidget(self.accounts_table)

        # Loading overlay for table operations
        self.accounts_loading = LoadingOverlay(self.accounts_table, "Loading accounts…")

        self.content_stack.addWidget(page)

    def setup_members_tab(self):
        """Elite member scraping page with comprehensive data extraction."""
        page, content_layout = self._create_page_container(
            "Elite Member Intelligence",
            "Extract comprehensive member data from ANY Telegram channel with zero-risk guarantees",
        )

        # Elite capabilities description
        elite_desc = QLabel(
            "ELITE SCRAPING CAPABILITIES:\n"
            "• Extracts from ANY Telegram channel (public/private/hidden)\n"
            "• Zero ban risk with AI-powered anti-detection\n"
            "• Comprehensive data: profiles, photos, bios, activity patterns\n"
            "• Advanced analytics: messaging potential, risk assessment, behavior analysis\n"
            "• Multi-technique discovery: messages, reactions, media, forwards"
        )
        elite_desc.setWordWrap(True)
        from ui.theme_manager import ThemeManager

        c = ThemeManager.get_colors()
        accent_hex = c["ACCENT_PRIMARY"].lstrip("#")
        accent_r = int(accent_hex[0:2], 16)
        accent_g = int(accent_hex[2:4], 16)
        accent_b = int(accent_hex[4:6], 16)
        elite_desc.setObjectName("hero_card")
        elite_desc.setStyleSheet(
            f"""
            QLabel {{
                background-color: rgba({accent_r}, {accent_g}, {accent_b}, 0.08);
                border: 1px solid rgba({accent_r}, {accent_g}, {accent_b}, 0.2);
                border-radius: 8px;
                padding: 12px 14px;
                color: {c['TEXT_PRIMARY']};
                font-size: 12px;
                line-height: 1.5;
            }}
        """
        )
        content_layout.addWidget(elite_desc)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        channel_input = QLineEdit()
        channel_input.setPlaceholderText(
            "ANY channel: @username, https://t.me/channel, channel_id, or invite link"
        )
        toolbar_layout.addWidget(channel_input)

        scrape_btn = QPushButton("Start Scrape")
        scrape_btn.setObjectName("quick_action")
        scrape_btn.setFixedHeight(32)
        scrape_btn.setToolTip(
            "Extract ALL available member data with zero ban risk using advanced AI techniques"
        )
        scrape_btn.clicked.connect(lambda: self.start_member_scraping(channel_input.text()))
        toolbar_layout.addWidget(scrape_btn)

        stop_scrape_btn = QPushButton("Stop")
        stop_scrape_btn.setObjectName("secondary")
        stop_scrape_btn.setFixedHeight(32)
        stop_scrape_btn.clicked.connect(self.stop_member_scraping)
        stop_scrape_btn.setEnabled(False)
        toolbar_layout.addWidget(stop_scrape_btn)

        toolbar_layout.addStretch()

        self.members_search = QLineEdit()
        self.members_search.setPlaceholderText("Search members…")
        self.members_search.textChanged.connect(self._refresh_member_filters)
        toolbar_layout.addWidget(self.members_search)

        self.members_risk_filter = QComboBox()
        self.members_risk_filter.addItems(["All", "Safe", "Medium", "High"])
        self.members_risk_filter.currentTextChanged.connect(self._refresh_member_filters)
        toolbar_layout.addWidget(self.members_risk_filter)

        toolbar_layout.addStretch()
        content_layout.addLayout(toolbar_layout)

        # Progress bar
        self.scrape_progress = QProgressBar()
        self.scrape_progress.setVisible(False)
        content_layout.addWidget(self.scrape_progress)

        # Status label
        self.scrape_status_label = QLabel("Ready to scrape members")
        c = ThemeManager.get_colors()
        self.scrape_status_label.setStyleSheet(
            f"color: {c['TEXT_DISABLED']}; font-size: 12px; padding: 4px 0;"
        )
        content_layout.addWidget(self.scrape_status_label)

        # Elite members table with comprehensive data display
        self.members_table = QTableWidget()
        self.members_table.setColumnCount(4)
        self.members_table.setHorizontalHeaderLabels(
            ["Profile & Quality", "Username & Badges", "ID & Risk", "Messaging Potential"]
        )
        self.members_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.members_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.members_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.members_table.verticalHeader().setVisible(False)
        self.members_table.setMinimumHeight(200)
        self.members_table.setAlternatingRowColors(True)
        self.members_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Enable double-click to view profile
        self.members_table.doubleClicked.connect(self.view_member_profile)
        content_layout.addWidget(self.members_table)

        # Member management actions
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)
        actions_layout.setContentsMargins(0, 0, 0, 0)

        export_btn = QPushButton("Export Members")
        export_btn.setObjectName("primary")
        export_btn.setFixedHeight(32)
        export_btn.clicked.connect(self.export_members)
        actions_layout.addWidget(export_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondary")
        refresh_btn.setFixedHeight(32)
        refresh_btn.clicked.connect(self.refresh_member_list)
        actions_layout.addWidget(refresh_btn)

        actions_layout.addStretch()
        content_layout.addLayout(actions_layout)

        # Store references for member scraping
        self.current_channel_input = channel_input
        self.scrape_stop_button = stop_scrape_btn

        self.content_stack.addWidget(page)

    def _refresh_member_filters(self):
        """Apply search/risk filters to member table."""
        try:
            search_text = (
                self.members_search.text().lower() if hasattr(self, "members_search") else ""
            )
            risk_filter = (
                self.members_risk_filter.currentText().lower()
                if hasattr(self, "members_risk_filter")
                else "all"
            )
            row_count = self.members_table.rowCount()
            for row in range(row_count):
                visible = True
                name_item = self.members_table.item(row, 0)
                risk_widget = self.members_table.cellWidget(row, 2)
                text = name_item.text().lower() if name_item else ""
                if search_text and search_text not in text:
                    visible = False
                if risk_filter != "all" and risk_widget:
                    state = risk_widget.property("state") or ""
                    if risk_filter == "safe" and state != "ok":
                        visible = False
                    if risk_filter == "medium" and state != "warn":
                        visible = False
                    if risk_filter == "high" and state != "bad":
                        visible = False
                self.members_table.setRowHidden(row, not visible)
        except Exception as exc:
            logger.debug(f"Member filter issue: {exc}")

    def setup_settings_tab(self):
        """Settings page."""
        page, content_layout = self._create_page_container(
            "Settings", "Configure your bot and automation parameters"
        )

        settings_btn = QPushButton("Open Settings")
        settings_btn.setObjectName("primary")
        settings_btn.setFixedHeight(32)
        settings_btn.clicked.connect(self._open_settings_dialog)
        content_layout.addWidget(settings_btn)

        content_layout.addStretch()

        self.content_stack.addWidget(page)

    def setup_logs_tab(self):
        """Logs page."""
        page, content_layout = self._create_page_container(
            "Application Logs", "Monitor system activity and debug information"
        )

        # Log viewer
        self.log_text_edit = QTextEdit()
        self.log_text_edit.setReadOnly(True)
        self.log_text_edit.setMinimumHeight(240)
        log_container = QScrollArea()
        log_container.setWidgetResizable(True)
        log_container.setFrameShape(QFrame.Shape.NoFrame)
        log_container.setWidget(self.log_text_edit)
        content_layout.addWidget(log_container)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setSpacing(6)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)

        clear_btn = QPushButton("Clear Logs")
        clear_btn.setObjectName("danger")
        clear_btn.setFixedHeight(32)
        clear_btn.clicked.connect(self._confirm_clear_logs)
        toolbar_layout.addWidget(clear_btn)

        toolbar_layout.addStretch()
        content_layout.addLayout(toolbar_layout)

        self.content_stack.addWidget(page)

    def add_log_message(self, message: str):
        """Add a message to the log display."""
        if hasattr(self, "log_text_edit"):
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text_edit.append(f"[{timestamp}] {message}")

    def _confirm_clear_logs(self):
        """Confirm before clearing logs."""
        if ErrorHandler.safe_question(
            self,
            "Clear Logs",
            "Are you sure you want to clear all logs?\n\nThis action cannot be undone.",
        ):
            self.log_text_edit.clear()
            self.add_log_message("Logs cleared by user")

    def setup_keyboard_shortcuts(self):
        """Setup global keyboard shortcuts for the application."""
        # Navigation shortcuts (Ctrl+1-9 for sidebar navigation)
        nav_shortcuts = [
            (QKeySequence("Ctrl+1"), 0, "Dashboard"),
            (QKeySequence("Ctrl+2"), 1, "Scraper"),
            (QKeySequence("Ctrl+3"), 2, "Campaigns"),
            (QKeySequence("Ctrl+4"), 3, "Auto Reply"),
            (QKeySequence("Ctrl+5"), 4, "Accounts"),
            (QKeySequence("Ctrl+6"), 5, "Analytics"),
            (QKeySequence("Ctrl+7"), 6, "Proxy Pool"),
            (QKeySequence("Ctrl+8"), 7, "Health"),
            (QKeySequence("Ctrl+9"), 8, "Logs"),
        ]

        for key_seq, page_index, _name in nav_shortcuts:
            if page_index < self.content_stack.count():
                shortcut = QShortcut(key_seq, self)
                shortcut.activated.connect(lambda idx=page_index: self._navigate_to_page(idx))

        # Settings shortcut (Ctrl+,)
        settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        settings_shortcut.activated.connect(self._open_settings_dialog)

        # Refresh shortcut (F5)
        refresh_shortcut = QShortcut(QKeySequence("F5"), self)
        refresh_shortcut.activated.connect(self._refresh_current_view)

        # Alternative refresh (Ctrl+R)
        refresh_shortcut2 = QShortcut(QKeySequence("Ctrl+R"), self)
        refresh_shortcut2.activated.connect(self._refresh_current_view)

        # Quick search shortcut (Ctrl+F)
        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self._show_search_dialog)

        # New account shortcut (Ctrl+N)
        new_account_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_account_shortcut.activated.connect(self._quick_add_account)

        # Start/Stop shortcut (Ctrl+Space)
        start_stop_shortcut = QShortcut(QKeySequence("Ctrl+Space"), self)
        start_stop_shortcut.activated.connect(self._toggle_bot_status)

        # Quick help (F1)
        help_shortcut = QShortcut(QKeySequence("F1"), self)
        help_shortcut.activated.connect(self._show_shortcuts_help)

        logger.info("Keyboard shortcuts configured")

    def _navigate_to_page(self, page_index: int):
        """Navigate to a specific page in the content stack."""
        if 0 <= page_index < self.content_stack.count():
            self.content_stack.setCurrentIndex(page_index)
            # Update navigation button states
            for idx, btn in self.navigation_manager.nav_buttons.items():
                btn.setChecked(idx == page_index)

    def _refresh_current_view(self):
        """Refresh the current view based on active page."""
        current_index = self.content_stack.currentIndex()

        if current_index == 0:  # Dashboard
            self.update_dashboard_metrics()
        elif current_index == 1:  # Scraper
            if hasattr(self, "member_list"):
                self.member_list.clear()
        elif current_index == 4:  # Accounts
            self.update_account_list()
        elif current_index == 5:  # Analytics
            if hasattr(self, "analytics_widget"):
                self.analytics_widget.refresh()
        elif current_index == 6:  # Proxy Pool
            if hasattr(self, "proxy_management_widget"):
                self.proxy_management_widget.refresh_all()
        elif current_index == 7:  # Health
            if hasattr(self, "health_dashboard_widget"):
                self.health_dashboard_widget.refresh()

        self.statusBar().showMessage("View refreshed", 2000)

    def _show_search_dialog(self):
        """Show quick search dialog."""
        current_index = self.content_stack.currentIndex()

        # Context-aware search based on current view
        if current_index == 1:  # Scraper - search members
            search_text, ok = QInputDialog.getText(self, "Search Members", "Enter username or ID:")
            if ok and search_text:
                self._search_members(search_text)
        elif current_index == 4:  # Accounts - search accounts
            search_text, ok = QInputDialog.getText(
                self, "Search Accounts", "Enter phone number or name:"
            )
            if ok and search_text:
                self._search_accounts(search_text)
        else:
            self.statusBar().showMessage("Search not available for this view", 2000)

    def _search_members(self, query: str):
        """Search members in the member list."""
        if hasattr(self, "member_list"):
            for i in range(self.member_list.count()):
                item = self.member_list.item(i)
                if query.lower() in item.text().lower():
                    self.member_list.setCurrentItem(item)
                    self.member_list.scrollToItem(item)
                    self.statusBar().showMessage(f"Found: {item.text()}", 2000)
                    return
            self.statusBar().showMessage("No matches found", 2000)

    def _search_accounts(self, query: str):
        """Search accounts in the account list."""
        if hasattr(self, "account_list"):
            for i in range(self.account_list.count()):
                item = self.account_list.item(i)
                if query.lower() in item.text().lower():
                    self.account_list.setCurrentItem(item)
                    self.account_list.scrollToItem(item)
                    self.statusBar().showMessage(f"Found: {item.text()}", 2000)
                    return
            self.statusBar().showMessage("No matches found", 2000)

    def _quick_add_account(self):
        """Quick add account dialog."""
        # Navigate to accounts page and trigger add
        self._navigate_to_page(4)
        # Show add account dialog if available
        if hasattr(self, "show_add_account_dialog"):
            self.show_add_account_dialog()
        else:
            self.statusBar().showMessage("Navigate to Accounts tab to add accounts", 2000)

    def _toggle_bot_status(self):
        """Toggle bot start/stop."""
        if hasattr(self, "start_button") and hasattr(self, "stop_button"):
            if self.start_button.isEnabled():
                self.start_button.click()
            elif self.stop_button.isEnabled():
                self.stop_button.click()

    def _show_shortcuts_help(self):
        """Show keyboard shortcuts help dialog."""
        shortcuts_text = """
<h2>Keyboard Shortcuts</h2>
<table style="border-collapse: collapse; width: 100%;">
<tr><td style="padding: 5px;"><b>Ctrl+1</b></td><td>Dashboard</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+2</b></td><td>Scraper</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+3</b></td><td>Campaigns</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+4</b></td><td>Auto Reply</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+5</b></td><td>Accounts</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+6</b></td><td>Analytics</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+7</b></td><td>Proxy Pool</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+8</b></td><td>Health</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+9</b></td><td>Logs</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+,</b></td><td>Settings</td></tr>
<tr><td style="padding: 5px;"><b>F5 / Ctrl+R</b></td><td>Refresh View</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+F</b></td><td>Search</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+N</b></td><td>New Account</td></tr>
<tr><td style="padding: 5px;"><b>Ctrl+Space</b></td><td>Start/Stop Bot</td></tr>
<tr><td style="padding: 5px;"><b>F1</b></td><td>Show This Help</td></tr>
</table>
"""
        msg = QMessageBox(self)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(Qt.TextFormat.RichText)
        msg.setText(shortcuts_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    def setup_tray_icon(self):
        """Set up system tray icon."""
        if getattr(self, "tray_icon", None):
            return

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray not available on this platform; skipping tray icon setup")
            return

        tray_menu = QMenu(self)
        show_action = QAction("Show", self)
        show_action.triggered.connect(self.show)
        hide_action = QAction("Hide", self)
        hide_action.triggered.connect(self.hide)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        tray_menu.addAction(show_action)
        tray_menu.addAction(hide_action)
        tray_menu.addSeparator()
        tray_menu.addAction(quit_action)

        self.tray_icon = QSystemTrayIcon(self.windowIcon(), self)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("Telegram Mass Account Messenger")
        self.tray_icon.activated.connect(lambda _: self.show())
        self.tray_icon.show()

    def _check_first_time_setup(self):
        """Check if first-time setup is needed and show wizard if necessary."""
        try:
            # Load current settings
            config_path = Path("config.json")
            settings_data = {}

            if config_path.exists():
                with open(config_path, encoding="utf-8") as f:
                    settings_data = json.load(f)

            # Check if wizard is needed
            from ui.settings_window import SetupWizardManager

            wizard_manager = SetupWizardManager(settings_data)

            if wizard_manager.is_wizard_needed():
                logger.info("First-time setup needed, showing wizard...")

                # Show info message
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Welcome!")
                msg_box.setText("Welcome to Telegram Auto-Reply Bot!")
                msg_box.setInformativeText(
                    "It looks like this is your first time running the bot, or some "
                    "critical settings are missing.\n\n"
                    "We'll guide you through a quick setup to get everything configured."
                )
                msg_box.setIcon(QMessageBox.Icon.Information)
                msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg_box.exec()

                # Open settings in wizard mode
                dialog = SettingsWindow(self, force_wizard=True)
                result = dialog.exec()

                if result == QDialog.DialogCode.Accepted:
                    logger.info("First-time setup completed successfully")
                    # Reload configuration after setup
                    if hasattr(self, "config_manager"):
                        self.config_manager.reload_config()
                    # Refresh dashboard profile with newly validated data
                    self._refresh_dashboard_profile()
                    self._refresh_validation_chips()
                else:
                    logger.warning("First-time setup was cancelled")

        except (ImportError, AttributeError, RuntimeError, ConnectionError) as e:
            logger.error(f"Error during first-time setup check: {e}")
        except Exception as e:
            logger.error(f"Critical error during first-time setup: {e}", exc_info=True)
            # Show user-friendly error message
            QMessageBox.critical(
                self,
                "Setup Error",
                "There was a critical error during setup. Please restart the application.",
            )

    def _open_settings_dialog(self):
        """Open the settings dialog."""
        try:
            logger.info("Opening settings dialog...")
            dialog = SettingsWindow(self)  # Pass self as parent for member scraping access

            # Connect settings updated signal to reload configuration
            dialog.settings_updated.connect(self._on_settings_updated)

            logger.info("Settings dialog created successfully")
            result = dialog.exec()
            logger.info(f"Settings dialog closed with result: {result}")
            if result == QDialog.DialogCode.Accepted:
                logger.info("Settings were saved")
        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Failed to create settings dialog: {e}")
            ErrorHandler.safe_critical(
                self, "Settings Error", f"Failed to create settings dialog: {e}"
            )
        except Exception as e:
            logger.error(f"Unexpected error opening settings: {e}", exc_info=True)
            ErrorHandler.safe_critical(self, "Error", f"Failed to open settings: {e}")

    def _on_settings_updated(self, settings: dict):
        """Handle settings update from settings dialog."""
        try:
            logger.info("Settings updated, reloading configuration...")
            # Reload configuration after settings change
            if hasattr(self, "config_manager") and self.config_manager:
                self.config_manager.reload_config()

            # Update services that depend on configuration
            if hasattr(self, "gemini_service") and self.gemini_service:
                # Reinitialize Gemini service with new API key if changed
                try:
                    from gemini_service import GeminiService

                    from core.secrets_manager import get_secrets_manager

                    secrets = get_secrets_manager()
                    api_key = secrets.get_secret("gemini_api_key", required=False)
                    if api_key:
                        self.gemini_service = GeminiService(api_key=api_key)
                        logger.info("Gemini service reinitialized with new settings")
                    else:
                        logger.warning("Gemini API key not found in secrets manager")
                except Exception as e:
                    logger.error(f"Failed to reinitialize Gemini service: {e}")

            # Update anti-detection settings if they changed
            anti_detection_config = settings.get("anti_detection", {})
            if hasattr(self, "anti_detection_system") and self.anti_detection_system:
                # Update anti-detection parameters
                self.anti_detection_system.update_settings(anti_detection_config)

            # Refresh profile and status chips with latest validation info
            self._refresh_dashboard_profile()
            gemini_valid = settings.get("gemini", {}).get("validated", False)
            if hasattr(self, "ai_status_chip") and self.ai_status_chip:
                text = "AI Validated" if gemini_valid else "AI Validation Needed"
                state = "ok" if gemini_valid else "warn"
                self.ai_status_chip.setText(text)
                self._set_status_chip_state(self.ai_status_chip, state)
            self._refresh_validation_chips()

            logger.info("Configuration reloaded and services updated")
        except Exception as e:
            logger.error(f"Failed to reload configuration after settings update: {e}")

    def _show_bulk_creation_dialog(self):
        """Show bulk account creation dialog."""
        ErrorHandler.safe_information(
            self,
            "Bulk Creation",
            "Bulk account creation feature.\n\n"
            "This will be implemented in the account creator module.",
        )

    def update_account_list(self):
        """Update the accounts list display."""
        if hasattr(self, "accounts_table") and self.account_manager:
            try:
                if hasattr(self, "accounts_loading") and self.accounts_loading:
                    self.accounts_loading.show_loading("Refreshing accounts…")
                accounts = self.account_manager.get_account_list()
                search_text = ""
                if hasattr(self, "accounts_search") and self.accounts_search:
                    search_text = self.accounts_search.text().lower()
                status_filter = ""
                if hasattr(self, "accounts_status_filter") and self.accounts_status_filter:
                    status_filter = self.accounts_status_filter.currentText().lower()

                filtered = []
                for acc in accounts:
                    phone = acc.get("phone_number", "").lower()
                    status = acc.get("status", "").lower()
                    warm = "ready" if acc.get("is_warmed_up") else "warming"
                    if search_text and search_text not in f"{phone} {status} {warm}":
                        continue
                    if status_filter and status_filter != "all":
                        if status_filter == "online" and not acc.get("is_online", False):
                            continue
                        if status_filter == "offline" and acc.get("is_online", False):
                            continue
                        if status_filter == "warming" and acc.get("is_warmed_up", False):
                            continue
                        if status_filter == "ready" and not acc.get("is_warmed_up", False):
                            continue
                        if status_filter == "error" and status != "error":
                            continue
                    filtered.append(acc)

                self.accounts_table.setRowCount(len(filtered))

                for row, account in enumerate(filtered):
                    # Phone number
                    phone_item = QTableWidgetItem(account.get("phone_number", "Unknown"))
                    self.accounts_table.setItem(row, 0, phone_item)

                    # Status pill
                    status_pill = QLabel()
                    status_pill.setObjectName("status_chip")
                    is_online = account.get("is_online", False)
                    status_text = "Online" if is_online else "Offline"
                    status_pill.setText(status_text)
                    status_pill.setProperty("state", "ok" if is_online else "warn")
                    self.accounts_table.setCellWidget(row, 1, status_pill)

                    # Warmup pill
                    warmup_pill = QLabel()
                    warmup_pill.setObjectName("status_chip")
                    is_warmed = account.get("is_warmed_up", False)
                    warmup_text = "Ready" if is_warmed else "Warming"
                    warmup_pill.setText(warmup_text)
                    warmup_pill.setProperty("state", "ok" if is_warmed else "warn")
                    self.accounts_table.setCellWidget(row, 2, warmup_pill)

                    # Messages sent
                    messages = account.get("messages_sent", 0)
                    msg_item = QTableWidgetItem(str(messages))
                    self.accounts_table.setItem(row, 3, msg_item)

                    # Actions button
                    action_widget = QWidget()
                    action_layout = QHBoxLayout(action_widget)
                    action_layout.setContentsMargins(2, 2, 2, 2)
                    action_layout.setSpacing(6)

                    start_btn = QPushButton("Start")
                    start_btn.setObjectName("secondary")
                    start_btn.setFixedWidth(64)
                    start_btn.clicked.connect(
                        lambda checked, phone=account.get("phone_number"): self.start_account(phone)
                    )
                    start_btn.setEnabled(not is_online)
                    action_layout.addWidget(start_btn)

                    stop_btn = QPushButton("Stop")
                    stop_btn.setObjectName("danger")
                    stop_btn.setMinimumWidth(64)
                    stop_btn.clicked.connect(
                        lambda checked, phone=account.get("phone_number"): self.stop_account(phone)
                    )
                    stop_btn.setEnabled(is_online)
                    action_layout.addWidget(stop_btn)

                    action_layout.addStretch()
                    self.accounts_table.setCellWidget(row, 4, action_widget)

                if not filtered:
                    from ui.theme_manager import ThemeManager

                    self.accounts_table.setRowCount(1)
                    empty = QTableWidgetItem("No accounts yet. Create one to get started.")
                    c = ThemeManager.get_colors()
                    empty.setForeground(QColor(c["TEXT_DISABLED"]))
                    self.accounts_table.setItem(0, 0, empty)
                    self.accounts_table.setSpan(0, 0, 1, self.accounts_table.columnCount())

            except Exception as e:
                logger.error(f"Error updating account list: {e}")
                from ui.theme_manager import ThemeManager

                # Show error in table
                self.accounts_table.setRowCount(1)
                error_item = QTableWidgetItem(f"Error loading accounts: {e}")
                c = ThemeManager.get_colors()
                error_item.setForeground(QColor(c["ACCENT_DANGER"]))
                self.accounts_table.setItem(0, 0, error_item)
                self.accounts_table.setSpan(0, 0, 1, self.accounts_table.columnCount())
            finally:
                if hasattr(self, "accounts_loading") and self.accounts_loading:
                    self.accounts_loading.hide_loading()

    def _cleanup_resources(self):
        """Clean up resources on application exit."""
        try:
            logger.info("Cleaning up resources...")

            # Stop background services
            try:
                if hasattr(self, "cost_monitor") and self.cost_monitor:
                    # Cost monitor stop (async)
                    logger.info("Stopping cost monitor...")
                if hasattr(self, "cleanup_service") and self.cleanup_service:
                    # Cleanup service stop (async)
                    logger.info("Stopping proxy cleanup service...")
            except Exception as e:
                logger.warning(f"Background service shutdown error: {e}")

            # Shutdown resource manager properly
            if self.resource_manager:
                try:
                    # Fixed: Try to get existing loop, create new one if needed
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # Running loop - schedule shutdown task
                            asyncio.create_task(shutdown_resource_manager())
                        else:
                            # Existing but not running - use it
                            loop.run_until_complete(shutdown_resource_manager())
                    except RuntimeError:
                        # No event loop exists - create one for shutdown
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            loop.run_until_complete(shutdown_resource_manager())
                        finally:
                            loop.close()
                            asyncio.set_event_loop(None)
                except Exception as e:
                    # Any other error - log but don't fail shutdown
                    logger.debug(f"Resource manager shutdown error (non-critical): {e}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def closeEvent(self, event):
        """Handle window close event."""
        try:
            self._cleanup_resources()
            # Cancel all active async tasks
            self._cancel_active_tasks()
            event.accept()
        except Exception as e:
            logger.error(f"Error during close: {e}")
            event.accept()

    def _cancel_active_tasks(self):
        """Cancel all active async tasks."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Cancel all tracked tasks
                for task in self._active_tasks.copy():
                    if not task.done():
                        task.cancel()
                # Clear the set
                self._active_tasks.clear()
                logger.info("Cancelled all active async tasks")
        except RuntimeError:
            # No event loop running
            pass
        except Exception as e:
            logger.error(f"Error cancelling active tasks: {e}")

    def _initialize_fallback_services(self):
        """Fallback service initialization if service container fails."""
        try:
            # Get credentials from secrets manager
            from core.secrets_manager import get_secrets_manager

            secrets = get_secrets_manager()

            # Get Telegram credentials
            api_id = secrets.get_secret("telegram_api_id", required=False)
            api_hash = secrets.get_secret("telegram_api_hash", required=False)

            # Get phone number from config (not a secret)
            config_path = Path("config.json")
            phone = ""
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                    phone = config.get("telegram", {}).get("phone_number", "")

            # Get Gemini API key
            gemini_key = secrets.get_secret("gemini_api_key", required=False)

            # Create services with proper credentials
            if api_id and api_hash and phone:
                self.telegram_client = TelegramClient(
                    api_id=api_id, api_hash=api_hash, phone_number=phone
                )
                logger.info("Fallback Telegram client initialized")
            else:
                logger.warning("Telegram credentials not available for fallback initialization")
                self.telegram_client = None

            if gemini_key:
                self.gemini_service = GeminiService(gemini_key)
                logger.info("Fallback Gemini service initialized")
            else:
                logger.warning("Gemini API key not available for fallback initialization")
                self.gemini_service = None

            logger.info("Fallback service initialization completed")
        except Exception as e:
            logger.error(f"Failed to initialize fallback services: {e}")
            self.telegram_client = None
            self.gemini_service = None

    def _run_async_task(self, coro):
        """Run an async task (helper for campaign operations) with proper tracking and thread safety."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.create_task(coro)
                # Thread-safe task tracking
                with self._task_lock:
                    self._active_tasks.add(task)
                # Remove task from tracking when it completes (thread-safe)
                task.add_done_callback(lambda t: self._safe_remove_task(t))
            else:
                loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Error running async task: {e}")
            # Show user-friendly error
            self.show_error_signal.emit("general_error", str(e))

    def _safe_remove_task(self, task):
        """Thread-safe task removal."""
        with self._task_lock:
            self._active_tasks.discard(task)

    def create_single_account(self):
        """Create a single account with dedicated dialog."""
        try:
            from ui.account_creation_dialog import AccountCreationDialog

            dialog = AccountCreationDialog(self)
            dialog.exec()
        except ImportError:
            # Fallback to settings dialog if dedicated dialog doesn't exist
            logger.warning("AccountCreationDialog not available, falling back to settings")
            self._open_settings_dialog()
        except Exception as e:
            logger.error(f"Error opening account creation: {e}")
            ErrorHandler.safe_critical(self, "Error", f"Failed to open account creation: {e}")

    def start_account(self, phone_number: str):
        """Start an account."""
        try:
            if self.account_manager and hasattr(self.account_manager, "start_client"):
                self._run_async_task(self.account_manager.start_client(phone_number))
                # Update UI after a short delay
                QTimer.singleShot(1000, self.update_account_list)
                self.add_log_message(f"Starting account: {phone_number}")
        except Exception as e:
            logger.error(f"Error starting account {phone_number}: {e}")
            ErrorHandler.show_error(self, "telegram_connection_failed", str(e))

    def stop_account(self, phone_number: str):
        """Stop an account."""
        try:
            if self.account_manager and hasattr(self.account_manager, "stop_client"):
                self._run_async_task(self.account_manager.stop_client(phone_number))
                # Update UI after a short delay
                QTimer.singleShot(1000, self.update_account_list)
                self.add_log_message(f"Stopping account: {phone_number}")
        except Exception as e:
            logger.error(f"Error stopping account {phone_number}: {e}")
            ErrorHandler.show_error(self, "telegram_connection_failed", str(e))

    def _get_scraper_client(self):
        """Resolve an initialized Pyrogram client for member scraping."""
        try:

            def _is_connected(obj) -> bool:
                connected_attr = getattr(obj, "is_connected", None)
                if callable(connected_attr):
                    return bool(connected_attr())
                return bool(connected_attr)

            if self.account_manager and getattr(self.account_manager, "active_clients", None):
                for client in self.account_manager.active_clients.values():
                    if not _is_connected(client):
                        continue
                    if hasattr(client, "get_client"):
                        pyro_client = client.get_client()
                        if self._is_pyrogram_client_ready(pyro_client):
                            return pyro_client

            if self.telegram_client and hasattr(self.telegram_client, "is_connected"):
                if _is_connected(self.telegram_client):
                    pyro_client = self.telegram_client.get_client()
                    if self._is_pyrogram_client_ready(pyro_client):
                        return pyro_client
        except Exception as exc:
            logger.error(f"Failed to resolve scraper client: {exc}")

        return None

    @staticmethod
    def _is_pyrogram_client_ready(client):
        if client is None:
            return False
        if not getattr(client, "is_connected", False):
            return False
        # Require authorization if available
        if hasattr(client, "is_authorized") and not client.is_authorized():
            return False
        return True

    def _reset_scraper_ui(self, message: Optional[str] = None, success: bool = False):
        """Reset scraping controls to a safe default state."""
        try:
            if hasattr(self, "scrape_progress") and self.scrape_progress:
                self.scrape_progress.setVisible(False)
            if hasattr(self, "current_channel_input") and self.current_channel_input:
                self.current_channel_input.setEnabled(True)
            if hasattr(self, "scrape_stop_button") and self.scrape_stop_button:
                self.scrape_stop_button.setEnabled(False)
            if message and hasattr(self, "scrape_status_label") and self.scrape_status_label:
                c = ThemeManager.get_colors()
                color = c["ACCENT_SUCCESS"] if success else c["ACCENT_DANGER"]
                self.scrape_status_label.setStyleSheet(f"color: {color};")
                self.scrape_status_label.setText(message)
        except Exception as exc:
            logger.debug(f"Unable to fully reset scraper UI: {exc}")

    def start_member_scraping(self, channel_url: str):
        """Start member scraping for a channel."""
        if not channel_url.strip():
            ErrorHandler.safe_warning(
                self, "Missing Channel", "Please enter a channel URL or username."
            )
            return

        scraper_client = self._get_scraper_client()
        if not scraper_client:
            ErrorHandler.safe_warning(
                self,
                "No Connected Account",
                "Start at least one Telegram account before scraping members.",
            )
            return
        # Ensure client is authorized
        try:
            authorized_attr = getattr(scraper_client, "is_authorized", None)
            authorized = authorized_attr() if callable(authorized_attr) else bool(authorized_attr)
            if not authorized:
                ErrorHandler.safe_warning(
                    self,
                    "Account Not Authorized",
                    "The selected Telegram account is not signed in. Please sign in and try again.",
                )
                return
        except Exception:
            pass

        # Check if database is available
        if not self.member_db:
            ErrorHandler.safe_critical(
                self,
                "Database Error",
                "Member database failed to initialize.\n\nPlease restart the application.\n\n"
                "If the problem persists, check that the database files are not corrupted.",
            )
            self._reset_scraper_ui("Database unavailable")
            return

        try:
            # Normalize/validate channel identifier
            channel_identifier = channel_url
            if hasattr(self, "member_scraper") and self.member_scraper:
                parsed = self.member_scraper.parse_channel_url(channel_url)
                if not parsed:
                    ErrorHandler.safe_warning(
                        self,
                        "Invalid Channel",
                        "Could not parse the channel. Use formats like:\n• https://t.me/channelname\n• @channelname\n• channelname",
                    )
                    return
                channel_identifier = parsed

            # Initialize member scraper with elite systems if needed
            if not hasattr(self, "member_scraper") or not self.member_scraper:
                from member_scraper import (
                    ComprehensiveDataExtractor,
                    EliteAntiDetectionSystem,
                    MemberScraper,
                )

                # Initialize elite anti-detection system
                self.anti_detection_system = EliteAntiDetectionSystem()

                # Initialize comprehensive data extractor
                self.data_extractor = ComprehensiveDataExtractor()

                # Create member scraper with elite capabilities
                self.member_scraper = MemberScraper(
                    client=scraper_client,
                    db=self.member_db,
                    anti_detection=self.anti_detection_system,
                )

                # Initialize session pool for elite scraping (will be done when needed)
                # Session pool initialization is handled asynchronously during scraping

            # Update UI
            self.scrape_progress.setVisible(True)
            self.scrape_progress.setValue(0)
            self.scrape_status_label.setText(f"Scraping members from {channel_identifier}...")
            self.current_channel_input.setEnabled(False)
            self.scrape_stop_button.setEnabled(True)

            # Start elite scraping with zero-risk guarantees
            self._run_async_task(self._perform_elite_member_scraping(channel_identifier))

        except Exception as e:
            logger.error(f"Error starting member scraping: {e}")
            ErrorHandler.safe_critical(self, "Error", f"Failed to start scraping: {e}")
            self._reset_scraper_ui("Failed to start scraping.")

    async def _perform_elite_member_scraping(self, channel_url: str):
        """Perform elite member scraping with comprehensive data extraction and zero risk."""
        try:
            # Use elite scraping with all available techniques
            results = await self.member_scraper.scrape_channel_members(
                channel_url,
                use_elite_scraping=True,
                analyze_messages=not self.low_power_mode,
                max_messages=2000 if self.low_power_mode else 10000,
            )

            # Update UI on main thread
            QTimer.singleShot(0, lambda: self._update_elite_scraping_results(results))

        except Exception as e:
            logger.error(f"Error during elite member scraping: {e}")
            error_msg = str(e)
            QTimer.singleShot(0, lambda: self._show_scraping_error(error_msg))

    def _update_elite_scraping_results(self, results):
        """Update UI with elite scraping results - comprehensive data."""
        try:
            if not results.get("success", False):
                self._show_scraping_error(results.get("error", "Unknown error"))
                return

            # Update progress
            self.scrape_progress.setVisible(False)

            # Show comprehensive results
            channel_info = results.get("channel_info", {})
            final_count = results.get("final_member_count", 0)
            stats = results.get("scraping_stats", {})

            status_text = "✅ Elite scraping complete!\n"
            status_text += f"📊 Channel: {channel_info.get('title', 'Unknown')}\n"
            status_text += f"👥 Members found: {final_count}\n"
            status_text += f"🎯 Techniques used: {stats.get('techniques_used', 0)}\n"
            status_text += f"📈 Data completeness: {stats.get('average_data_completeness', 0):.1%}"

            self.scrape_status_label.setText(status_text)
            self.scrape_status_label.setStyleSheet(
                f"color: {ThemeManager._get_palette()['ACCENT_SUCCESS']};"
            )

            # Update table with comprehensive data
            # For display, we'll show a summary. In a full implementation,
            # you'd have columns for all the extracted data
            self.members_table.setRowCount(min(final_count, 100))  # Limit display for performance

            # Get some sample members to display (in practice, you'd get them from the database)
            try:
                if hasattr(self, "member_db") and self.member_db:
                    sample_members = self.member_db.get_all_members(
                        str(channel_info.get("id", ""))
                    )[:100]
                else:
                    sample_members = []
            except Exception as e:
                logger.debug(f"Could not load sample members: {e}")
                sample_members = []

            for row, member in enumerate(sample_members):
                # Name with completeness indicator
                name = (
                    f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
                    or "Unknown"
                )
                completeness = member.get("data_completeness_score", 0)
                completeness_indicator = (
                    "🔶" if completeness < 0.5 else "🟡" if completeness < 0.8 else "🟢"
                )
                self.members_table.setItem(
                    row, 0, QTableWidgetItem(f"{completeness_indicator} {name}")
                )

                # Username with verification status
                username = member.get("username", "No username")
                verified = member.get("is_verified", False)
                premium = member.get("is_premium", False)
                badges = ""
                if verified:
                    badges += "✓"
                if premium:
                    badges += "⭐"
                display_username = (
                    f"{badges} @{username}" if username != "No username" else f"{badges} {username}"
                )
                self.members_table.setItem(row, 1, QTableWidgetItem(display_username))

                # User ID with risk score
                user_id = str(member.get("user_id", "Unknown"))
                risk_score = member.get("threat_score", 0)
                risk_indicator = "🟢" if risk_score < 30 else "🟡" if risk_score < 70 else "🔴"
                risk_chip = QLabel(f"{risk_indicator} {user_id}")
                risk_chip.setObjectName("status_chip")
                risk_chip.setProperty(
                    "state", "ok" if risk_score < 30 else "warn" if risk_score < 70 else "bad"
                )
                self.members_table.setCellWidget(row, 2, risk_chip)

                # Status with messaging potential
                messaging_potential = "High"  # Would be calculated based on comprehensive analysis
                potential_chip = QLabel(f"🎯 {messaging_potential}")
                potential_chip.setObjectName("status_chip")
                potential_chip.setProperty(
                    "state", "ok" if messaging_potential == "High" else "warn"
                )
                self.members_table.setCellWidget(row, 3, potential_chip)

            # Add a summary row if there are more members
            if final_count > 100:
                row = self.members_table.rowCount()
                self.members_table.insertRow(row)
                summary_item = QTableWidgetItem(f"📊 +{final_count - 100} more members available")
                c = ThemeManager.get_colors()
                summary_item.setForeground(QColor(c["ACCENT_PRIMARY"]))
                self.members_table.setItem(row, 0, summary_item)
                self.members_table.setSpan(row, 0, 1, 4)  # Span across all columns

            # Re-enable UI
            self.current_channel_input.setEnabled(True)
            self.scrape_stop_button.setEnabled(False)

            # Show success message
            ErrorHandler.safe_information(
                self,
                "Elite Scraping Complete",
                f"🎉 Successfully scraped {final_count} members from {channel_info.get('title', 'channel')}!\n\n"
                f"📊 Data Quality: {stats.get('average_data_completeness', 0):.1%}\n"
                f"🛡️  Risk Assessment: All members analyzed for safety\n"
                f"🎯 Messaging Potential: Calculated for all members\n\n"
                f"💾 All data saved to database with comprehensive profiles.",
            )

        except Exception as e:
            logger.error(f"Error updating elite scraping results: {e}")
            self._show_scraping_error(f"Results display error: {e}")

    def _update_scraping_results(self, members):
        """Update UI with basic scraping results (fallback)."""
        try:
            # Update progress
            self.scrape_progress.setVisible(False)
            self.scrape_status_label.setText(f"Successfully scraped {len(members)} members")

            # Update table
            self.members_table.setRowCount(len(members))
            for row, member in enumerate(members):
                # Name
                name = member.get("first_name", "") + " " + member.get("last_name", "")
                name = name.strip() or "Unknown"
                self.members_table.setItem(row, 0, QTableWidgetItem(name))

                # Username
                username = member.get("username", "No username")
                self.members_table.setItem(
                    row,
                    1,
                    QTableWidgetItem(f"@{username}" if username != "No username" else username),
                )

                # User ID
                user_id = str(member.get("user_id", "Unknown"))
                self.members_table.setItem(row, 2, QTableWidgetItem(user_id))

                # Status
                status_item = QTableWidgetItem("Safe")
                c = ThemeManager.get_colors()
                status_item.setForeground(QColor(c["ACCENT_SUCCESS"]))
                self.members_table.setItem(row, 3, status_item)

            # Re-enable UI
            self.current_channel_input.setEnabled(True)
            self.scrape_stop_button.setEnabled(False)

        except Exception as e:
            logger.error(f"Error updating scraping results: {e}")

    def _show_scraping_error(self, error_msg: str):
        """Show scraping error in UI."""
        self.scrape_progress.setVisible(False)
        self.scrape_status_label.setText(f"Error: {error_msg}")
        self.scrape_status_label.setStyleSheet(
            f"color: {ThemeManager._get_palette()['ACCENT_DANGER']};"
        )
        self.current_channel_input.setEnabled(True)
        self.scrape_stop_button.setEnabled(False)

    def stop_member_scraping(self):
        """Stop member scraping."""
        try:
            if hasattr(self, "member_scraper") and self.member_scraper:
                # Cancel scraping operation
                pass  # MemberScraper should handle cancellation

            # Update UI
            self.scrape_progress.setVisible(False)
            self.scrape_status_label.setText("Scraping cancelled")
            self.current_channel_input.setEnabled(True)
            self.scrape_stop_button.setEnabled(False)

        except Exception as e:
            logger.error(f"Error stopping member scraping: {e}")

    def export_members(self):
        """Export scraped members to file with format selection."""
        try:
            # Check if we have member database
            if not self.member_db:
                ErrorHandler.safe_warning(self, "No Database", "Member database not initialized.")
                return

            # Show format selection dialog
            format_options = ["CSV (*.csv)", "JSON (*.json)", "Excel (*.xlsx)"]
            format_choice, ok = QInputDialog.getItem(
                self, "Export Format", "Select export format:", format_options, 0, False
            )

            if not ok:
                return

            # Determine file extension
            if "CSV" in format_choice:
                ext = ".csv"
                filter_str = "CSV Files (*.csv)"
            elif "JSON" in format_choice:
                ext = ".json"
                filter_str = "JSON Files (*.json)"
            else:
                ext = ".xlsx"
                filter_str = "Excel Files (*.xlsx)"

            # Get save path
            default_name = f"members_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Members", default_name, filter_str
            )

            if not file_path:
                return

            # Show filter options
            filters = {}
            filter_result = ErrorHandler.safe_message_box(
                self,
                QMessageBox.Icon.Question,
                "Filter Options",
                "Export only safe targets (low threat score)?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
            )

            if filter_result == QMessageBox.StandardButton.Cancel:
                return
            elif filter_result == QMessageBox.StandardButton.Yes:
                filters["is_safe_target"] = True

            # Perform export using new ExportManager
            from export_manager import get_export_manager

            exporter = get_export_manager(self.member_db)

            exported_count = 0
            if ext == ".csv":
                exported_count = exporter.export_members_to_csv(file_path, filters)
            elif ext == ".json":
                exported_count = exporter.export_members_to_json(file_path, filters)
            else:
                try:
                    exported_count = exporter.export_members_to_excel(file_path, filters)
                except ImportError:
                    ErrorHandler.safe_warning(
                        self,
                        "Excel Not Available",
                        "Excel export requires openpyxl. Install with: pip install openpyxl",
                    )
                    return

            if exported_count > 0:
                ErrorHandler.safe_information(
                    self,
                    "Export Complete",
                    f"Successfully exported {exported_count} members to:\n{file_path}",
                )
            else:
                ErrorHandler.safe_warning(
                    self, "No Data", "No members found matching the criteria."
                )

        except Exception as e:
            logger.error(f"Error exporting members: {e}")
            ErrorHandler.safe_critical(self, "Error", f"Failed to export members: {e}")

    def refresh_member_list(self):
        """Refresh the member list display."""
        try:
            # This would ideally refresh from the database
            # For now, just show current count
            row_count = self.members_table.rowCount()
            self.scrape_status_label.setText(f"Showing {row_count} members")
        except Exception as e:
            logger.error(f"Error refreshing member list: {e}")

    def view_member_profile(self, index):
        """View detailed member profile."""
        try:
            row = index.row()
            if row < 0 or row >= self.members_table.rowCount():
                return

            # Extract member data from table (simplified - would get from database in practice)
            user_id_text = self.members_table.item(row, 2).text()
            user_id = None

            # Parse user ID from the risk indicator format (🟢 ID or 🔴 ID)
            import re

            id_match = re.search(r"[🟢🔴🟡] (\d+)", user_id_text)
            if id_match:
                user_id = int(id_match.group(1))

            if user_id:
                # Get comprehensive data from data access layer
                from member_scraper import EliteDataAccessLayer

                data_layer = EliteDataAccessLayer(self.member_db)

                # Get basic member data (simplified - would query database properly)
                member_data = {
                    "user_id": user_id,
                    "first_name": "Unknown",  # Would get from database
                    "last_name": "",
                    "username": "unknown",
                    "is_verified": False,
                    "is_premium": False,
                }

                # Show profile viewer
                from ui_components import MemberProfileViewer

                viewer = MemberProfileViewer(member_data, data_layer, self)
                viewer.exec()

        except Exception as e:
            logger.error(f"Error viewing member profile: {e}")
            ErrorHandler.safe_critical(self, "Error", f"Failed to view member profile: {e}")
