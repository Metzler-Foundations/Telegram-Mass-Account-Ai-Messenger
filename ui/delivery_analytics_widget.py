"""
Delivery Analytics Widget - UI for message delivery and response tracking.

Features:
- Real-time delivery rate monitoring
- Read receipt tracking
- Response time analytics
- Per-campaign and per-account metrics
- Response time distribution charts
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGroupBox,
    QGridLayout, QPushButton, QComboBox, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)

# Try to import delivery analytics
try:
    from campaigns.delivery_analytics import DeliveryAnalytics, get_delivery_analytics
    DELIVERY_ANALYTICS_AVAILABLE = True
except ImportError:
    DELIVERY_ANALYTICS_AVAILABLE = False
    logger.warning("DeliveryAnalytics not available")


class DeliveryMetricCard(QWidget):
    """Card displaying a delivery metric."""
    
    def __init__(self, title: str, icon: str = "📊", parent=None):
        super().__init__(parent)
        self.setup_ui(title, icon)
    
    def setup_ui(self, title: str, icon: str):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        self.setStyleSheet("""
            DeliveryMetricCard {
                background-color: #2b2d31;
                border-radius: 8px;
                padding: 15px;
            }
        """)
        
        # Header
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(icon)
        icon_font = QFont()
        icon_font.setPointSize(18)
        icon_label.setFont(icon_font)
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #b5bac1; font-size: 11px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Value
        self.value_label = QLabel("--")
        value_font = QFont()
        value_font.setPointSize(20)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.value_label)
        
        # Subtext
        self.subtext_label = QLabel("")
        self.subtext_label.setStyleSheet("color: #949ba4; font-size: 10px;")
        layout.addWidget(self.subtext_label)
    
    def set_value(self, value: str, subtext: str = ""):
        """Update the metric."""
        self.value_label.setText(value)
        self.subtext_label.setText(subtext)


class DeliveryAnalyticsWidget(QWidget):
    """Widget for delivery and response analytics."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.analytics: Optional[DeliveryAnalytics] = None
        self.selected_campaign_id: Optional[int] = None
        self.setup_ui()
        
        # Auto-refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(15000)  # 15 seconds
        
        # Initialize
        if DELIVERY_ANALYTICS_AVAILABLE:
            self.analytics = get_delivery_analytics()
            self.refresh_data()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("📬 Delivery & Response Analytics")
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
        
        # Overall metrics
        overall_group = QGroupBox("📊 Overall Performance (Last 7 Days)")
        overall_layout = QGridLayout(overall_group)
        
        self.overall_sent_card = DeliveryMetricCard("Messages Sent", "📤")
        overall_layout.addWidget(self.overall_sent_card, 0, 0)
        
        self.overall_delivered_card = DeliveryMetricCard("Delivered", "✅")
        overall_layout.addWidget(self.overall_delivered_card, 0, 1)
        
        self.overall_read_card = DeliveryMetricCard("Read", "👁")
        overall_layout.addWidget(self.overall_read_card, 0, 2)
        
        self.overall_replied_card = DeliveryMetricCard("Replied", "💬")
        overall_layout.addWidget(self.overall_replied_card, 0, 3)
        
        self.delivery_rate_card = DeliveryMetricCard("Delivery Rate", "📈")
        overall_layout.addWidget(self.delivery_rate_card, 1, 0)
        
        self.read_rate_card = DeliveryMetricCard("Read Rate", "📖")
        overall_layout.addWidget(self.read_rate_card, 1, 1)
        
        self.response_rate_card = DeliveryMetricCard("Response Rate", "💯")
        overall_layout.addWidget(self.response_rate_card, 1, 2)
        
        self.avg_response_time_card = DeliveryMetricCard("Avg Response Time", "⏱")
        overall_layout.addWidget(self.avg_response_time_card, 1, 3)
        
        layout.addWidget(overall_group)
        
        # Campaign selector
        campaign_group = QGroupBox("🎯 Campaign-Specific Analytics")
        campaign_layout = QVBoxLayout(campaign_group)
        
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Campaign:"))
        
        self.campaign_selector = QComboBox()
        self.campaign_selector.currentIndexChanged.connect(self.on_campaign_selected)
        selector_layout.addWidget(self.campaign_selector)
        selector_layout.addStretch()
        
        campaign_layout.addLayout(selector_layout)
        
        # Campaign metrics
        campaign_metrics_layout = QGridLayout()
        
        self.campaign_sent_card = DeliveryMetricCard("Sent", "📤")
        campaign_metrics_layout.addWidget(self.campaign_sent_card, 0, 0)
        
        self.campaign_delivered_card = DeliveryMetricCard("Delivered", "✅")
        campaign_metrics_layout.addWidget(self.campaign_delivered_card, 0, 1)
        
        self.campaign_read_card = DeliveryMetricCard("Read", "👁")
        campaign_metrics_layout.addWidget(self.campaign_read_card, 0, 2)
        
        self.campaign_replied_card = DeliveryMetricCard("Replied", "💬")
        campaign_metrics_layout.addWidget(self.campaign_replied_card, 0, 3)
        
        campaign_layout.addLayout(campaign_metrics_layout)
        layout.addWidget(campaign_group)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #949ba4; font-size: 11px; padding: 5px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def refresh_data(self):
        """Refresh analytics data."""
        if not self.analytics:
            self.status_label.setText("Delivery analytics not available")
            return
        
        try:
            # Get overall stats
            overall = self.analytics.get_overall_delivery_stats(days=7)
            
            self.overall_sent_card.set_value(
                f"{overall.get('total_sent', 0):,}",
                f"{overall.get('campaigns_tracked', 0)} campaigns"
            )
            
            self.overall_delivered_card.set_value(
                f"{overall.get('total_delivered', 0):,}",
                f"{overall.get('delivery_rate', 0):.1f}%"
            )
            
            self.overall_read_card.set_value(
                f"{overall.get('total_read', 0):,}",
                f"{overall.get('read_rate', 0):.1f}%"
            )
            
            self.overall_replied_card.set_value(
                f"{overall.get('total_replied', 0):,}",
                f"{overall.get('response_rate', 0):.1f}%"
            )
            
            self.delivery_rate_card.set_value(
                f"{overall.get('delivery_rate', 0):.1f}%",
                "of sent messages"
            )
            
            self.read_rate_card.set_value(
                f"{overall.get('read_rate', 0):.1f}%",
                "of sent messages"
            )
            
            self.response_rate_card.set_value(
                f"{overall.get('response_rate', 0):.1f}%",
                "of sent messages"
            )
            
            avg_response = overall.get('avg_response_time_seconds')
            if avg_response:
                if avg_response < 60:
                    time_str = f"{avg_response:.0f}s"
                elif avg_response < 3600:
                    time_str = f"{avg_response/60:.1f}m"
                else:
                    time_str = f"{avg_response/3600:.1f}h"
                self.avg_response_time_card.set_value(time_str, "average")
            else:
                self.avg_response_time_card.set_value("--", "no data")
            
            # Update campaign selector
            self._update_campaign_selector()
            
            # Update campaign-specific stats if selected
            if self.selected_campaign_id:
                self._refresh_campaign_stats(self.selected_campaign_id)
            
            self.status_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Failed to refresh delivery analytics: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")
    
    def _update_campaign_selector(self):
        """Update campaign selector with active campaigns."""
        try:
            # Get campaigns from database
            import sqlite3
            with sqlite3.connect('campaigns.db') as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute('''
                    SELECT id, name, status FROM campaigns
                    WHERE status IN ('running', 'completed')
                    ORDER BY id DESC
                    LIMIT 50
                ''')
                
                current_index = self.campaign_selector.currentIndex()
                current_data = self.campaign_selector.currentData()
                
                self.campaign_selector.clear()
                self.campaign_selector.addItem("Select a campaign...", None)
                
                for row in cursor:
                    self.campaign_selector.addItem(
                        f"{row['name']} (ID: {row['id']}) - {row['status']}",
                        row['id']
                    )
                
                # Restore selection if possible
                if current_data:
                    index = self.campaign_selector.findData(current_data)
                    if index >= 0:
                        self.campaign_selector.setCurrentIndex(index)
                
        except Exception as e:
            logger.debug(f"Could not update campaign selector: {e}")
    
    def on_campaign_selected(self, index: int):
        """Handle campaign selection."""
        campaign_id = self.campaign_selector.currentData()
        self.selected_campaign_id = campaign_id
        
        if campaign_id:
            self._refresh_campaign_stats(campaign_id)
    
    def _refresh_campaign_stats(self, campaign_id: int):
        """Refresh campaign-specific statistics."""
        if not self.analytics:
            return
        
        try:
            stats = self.analytics.get_campaign_delivery_stats(campaign_id)
            
            self.campaign_sent_card.set_value(
                f"{stats.get('total_sent', 0):,}",
                "messages"
            )
            
            self.campaign_delivered_card.set_value(
                f"{stats.get('total_delivered', 0):,}",
                f"{stats.get('delivery_rate', 0):.1f}%"
            )
            
            self.campaign_read_card.set_value(
                f"{stats.get('total_read', 0):,}",
                f"{stats.get('read_rate', 0):.1f}%"
            )
            
            self.campaign_replied_card.set_value(
                f"{stats.get('total_replied', 0):,}",
                f"{stats.get('response_rate', 0):.1f}%"
            )
            
        except Exception as e:
            logger.error(f"Failed to refresh campaign stats: {e}")


