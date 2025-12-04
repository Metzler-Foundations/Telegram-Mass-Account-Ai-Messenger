#!/usr/bin/env python3
"""
Analytics Dashboard - REAL analytics with actual database data
All metrics pulled from production database - NO MOCK DATA
"""

import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGridLayout, QGroupBox, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from database.database_queries import member_queries, campaign_queries, account_queries

logger = logging.getLogger(__name__)


class MetricCard(QFrame):
    """Widget displaying a single metric with REAL data."""
    
    def __init__(self, title: str, icon: str = "📊", parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            MetricCard {
                background-color: #2b2d31;
                border-radius: 8px;
                padding: 15px;
            }
            MetricCard:hover {
                background-color: #32353b;
            }
        """)
        
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        icon_label = QLabel(icon)
        icon_font = QFont()
        icon_font.setPointSize(20)
        icon_label.setFont(icon_font)
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #b5bac1; font-size: 12px;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Value
        self.value_label = QLabel("Loading...")
        value_font = QFont()
        value_font.setPointSize(24)
        value_font.setBold(True)
        self.value_label.setFont(value_font)
        self.value_label.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.value_label)
        
        # Subtext
        self.subtext_label = QLabel("")
        self.subtext_label.setStyleSheet("color: #949ba4; font-size: 11px;")
        layout.addWidget(self.subtext_label)
    
    def set_value(self, value: str, subtext: str = ""):
        """Update the metric value."""
        self.value_label.setText(value)
        self.subtext_label.setText(subtext)


class AnalyticsDashboard(QWidget):
    """Analytics dashboard with REAL data from database."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_refresh_at: Optional[datetime] = None
        self._min_refresh_interval = timedelta(seconds=5)
        self.setup_ui()

        # Auto-refresh every 30 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_all_metrics)
        self.refresh_timer.start(30000)  # 30 seconds
        
        # Initial load
        self.refresh_all_metrics()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title = QLabel("📊 Real-Time Analytics")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        
        # Overview metrics
        overview_group = QGroupBox("📈 Overview")
        overview_layout = QGridLayout()
        
        self.total_members_card = MetricCard("Total Members", "👥")
        overview_layout.addWidget(self.total_members_card, 0, 0)
        
        self.total_accounts_card = MetricCard("Active Accounts", "📱")
        overview_layout.addWidget(self.total_accounts_card, 0, 1)
        
        self.total_campaigns_card = MetricCard("Total Campaigns", "📧")
        overview_layout.addWidget(self.total_campaigns_card, 0, 2)
        
        self.messages_sent_card = MetricCard("Messages Sent", "📤")
        overview_layout.addWidget(self.messages_sent_card, 1, 0)
        
        self.success_rate_card = MetricCard("Success Rate", "✅")
        overview_layout.addWidget(self.success_rate_card, 1, 1)
        
        self.accounts_warmed_card = MetricCard("Warmed Accounts", "♨️")
        overview_layout.addWidget(self.accounts_warmed_card, 1, 2)
        
        overview_group.setLayout(overview_layout)
        content_layout.addWidget(overview_group)
        
        # Campaign metrics
        campaign_group = QGroupBox("📧 Campaign Performance")
        campaign_layout = QGridLayout()
        
        self.active_campaigns_card = MetricCard("Running", "▶️")
        campaign_layout.addWidget(self.active_campaigns_card, 0, 0)
        
        self.completed_campaigns_card = MetricCard("Completed", "✅")
        campaign_layout.addWidget(self.completed_campaigns_card, 0, 1)
        
        self.campaign_success_card = MetricCard("Campaign Success", "🎯")
        campaign_layout.addWidget(self.campaign_success_card, 0, 2)
        
        self.failed_messages_card = MetricCard("Failed Messages", "❌")
        campaign_layout.addWidget(self.failed_messages_card, 1, 0)
        
        self.avg_delivery_card = MetricCard("Avg Delivery Rate", "📊")
        campaign_layout.addWidget(self.avg_delivery_card, 1, 1)
        
        self.messages_today_card = MetricCard("Messages Today", "📅")
        campaign_layout.addWidget(self.messages_today_card, 1, 2)
        
        campaign_group.setLayout(campaign_layout)
        content_layout.addWidget(campaign_group)
        
        # Member insights
        member_group = QGroupBox("👥 Member Insights")
        member_layout = QGridLayout()
        
        self.members_with_username_card = MetricCard("With Username", "📇")
        member_layout.addWidget(self.members_with_username_card, 0, 0)
        
        self.verified_members_card = MetricCard("Verified", "✓")
        member_layout.addWidget(self.verified_members_card, 0, 1)
        
        self.premium_members_card = MetricCard("Premium", "⭐")
        member_layout.addWidget(self.premium_members_card, 0, 2)
        
        self.active_members_card = MetricCard("Active Recently", "🟢")
        member_layout.addWidget(self.active_members_card, 1, 0)
        
        self.channels_tracked_card = MetricCard("Channels Tracked", "📺")
        member_layout.addWidget(self.channels_tracked_card, 1, 1)
        
        self.avg_per_channel_card = MetricCard("Avg Per Channel", "📊")
        member_layout.addWidget(self.avg_per_channel_card, 1, 2)
        
        member_group.setLayout(member_layout)
        content_layout.addWidget(member_group)
        
        # Last update timestamp
        self.last_update_label = QLabel()
        self.last_update_label.setStyleSheet("color: #949ba4; font-size: 11px; padding: 10px;")
        content_layout.addWidget(self.last_update_label)

        # Empty-state and degraded-mode banner
        self.partial_data_label = QLabel()
        self.partial_data_label.setStyleSheet("color: #f0b232; font-size: 11px; padding: 4px 10px;")
        self.partial_data_label.setVisible(False)
        content_layout.addWidget(self.partial_data_label)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def refresh_all_metrics(self):
        """Refresh ALL metrics with REAL database data."""
        now = datetime.now()
        if self._last_refresh_at and (now - self._last_refresh_at) < self._min_refresh_interval:
            logger.info("Skipping analytics refresh: rate limit in effect")
            return
        try:
            logger.info("Refreshing ALL analytics with REAL database data...")

            # Track any sources that failed to load so we can surface a partial-data message
            errors: List[str] = []

            # Get REAL data from database with defensive fallbacks
            member_stats = self._safe_fetch(self.get_real_member_stats, self._empty_member_stats(), "member stats", errors)
            campaign_stats = self._safe_fetch(self.get_real_campaign_stats, self._empty_campaign_stats(), "campaign stats", errors)
            account_stats = self._safe_fetch(self.get_real_account_stats, self._empty_account_stats(), "account stats", errors)

            # Update overview cards
            self.total_members_card.set_value(
                f"{member_stats['total']:,}",
                f"{member_stats['new_today']} added today"
            )
            
            self.total_accounts_card.set_value(
                f"{account_stats['active']}/{account_stats['total']}",
                f"{account_stats['percentage']:.0f}% active"
            )
            
            self.total_campaigns_card.set_value(
                f"{campaign_stats['total']:,}",
                f"{campaign_stats['running']} running now"
            )
            
            self.messages_sent_card.set_value(
                f"{campaign_stats['total_sent']:,}",
                f"{campaign_stats['sent_today']} today"
            )
            
            # Calculate success rate
            total_attempts = campaign_stats['total_sent'] + campaign_stats['total_failed']
            if total_attempts > 0:
                success_rate = (campaign_stats['total_sent'] / total_attempts) * 100
            else:
                success_rate = 0
            
            self.success_rate_card.set_value(
                f"{success_rate:.1f}%",
                f"{campaign_stats['total_failed']:,} failed"
            )
            
            self.accounts_warmed_card.set_value(
                f"{account_stats['warmed_up']}/{account_stats['total']}",
                f"{account_stats['warmup_pct']:.0f}% ready"
            )
            
            # Update campaign cards
            self.active_campaigns_card.set_value(
                f"{campaign_stats['running']:,}",
                "Active campaigns"
            )
            
            self.completed_campaigns_card.set_value(
                f"{campaign_stats['completed']:,}",
                f"{campaign_stats['completion_rate']:.0f}% completion rate"
            )
            
            self.campaign_success_card.set_value(
                f"{success_rate:.0f}%",
                "Overall success"
            )
            
            self.failed_messages_card.set_value(
                f"{campaign_stats['total_failed']:,}",
                f"{campaign_stats['failed_today']} today"
            )
            
            # Average delivery rate
            self.avg_delivery_card.set_value(
                f"{success_rate:.1f}%",
                "Avg across all campaigns"
            )
            
            self.messages_today_card.set_value(
                f"{campaign_stats['sent_today']:,}",
                f"{campaign_stats['yesterday_sent']} yesterday"
            )
            
            # Update member cards
            self.members_with_username_card.set_value(
                f"{member_stats['with_username']:,}",
                f"{member_stats['username_pct']:.0f}% have username"
            )
            
            self.verified_members_card.set_value(
                f"{member_stats['verified']:,}",
                f"{member_stats['verified_pct']:.1f}% verified"
            )
            
            self.premium_members_card.set_value(
                f"{member_stats['premium']:,}",
                f"{member_stats['premium_pct']:.1f}% premium"
            )
            
            self.active_members_card.set_value(
                f"{member_stats['active_30d']:,}",
                "Active in last 30 days"
            )
            
            self.channels_tracked_card.set_value(
                f"{member_stats['total_channels']:,}",
                "Unique channels"
            )
            
            if member_stats['total_channels'] > 0:
                avg_per_channel = member_stats['total'] / member_stats['total_channels']
            else:
                avg_per_channel = 0
            
            self.avg_per_channel_card.set_value(
                f"{avg_per_channel:.0f}",
                "Members per channel"
            )

            # Update timestamp
            if errors:
                self.last_update_label.setText(
                    f"⚠️ Partial data: {', '.join(errors)} — last attempted refresh at "
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                self.partial_data_label.setText(
                    "Database unavailable for " + ', '.join(errors) +
                    ". Showing cached defaults. Check DB connections and retry."
                )
                self.partial_data_label.setVisible(True)
            else:
                self.last_update_label.setText(
                    f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} "
                    f"(Refreshes every 30 seconds)"
                )
                self.partial_data_label.setVisible(False)

            logger.info("✅ Analytics refreshed with REAL data")
            self._last_refresh_at = datetime.now()

        except Exception as e:
            logger.error(f"Failed to refresh analytics: {e}", exc_info=True)
            # Don't fail silently - show error to user
            self.last_update_label.setText(
                f"❌ Update failed: {str(e)[:50]}... Check logs for details."
            )

    @staticmethod
    def _empty_member_stats() -> Dict[str, float]:
        """Provide zeroed-out member stats to keep the UI stable on failures."""
        return {
            'total': 0,
            'new_today': 0,
            'with_username': 0,
            'username_pct': 0.0,
            'verified': 0,
            'verified_pct': 0.0,
            'premium': 0,
            'premium_pct': 0.0,
            'active_30d': 0,
            'total_channels': 0
        }

    @staticmethod
    def _empty_campaign_stats() -> Dict[str, float]:
        """Provide zeroed-out campaign stats to keep the UI stable on failures."""
        return {
            'total': 0,
            'running': 0,
            'completed': 0,
            'completion_rate': 0.0,
            'total_sent': 0,
            'sent_today': 0,
            'total_failed': 0
        }

    @staticmethod
    def _empty_account_stats() -> Dict[str, float]:
        """Provide zeroed-out account stats to keep the UI stable on failures."""
        return {
            'total': 0,
            'active': 0,
            'percentage': 0.0,
            'warmed_up': 0,
            'warmup_pct': 0.0
        }

    def _safe_fetch(self, func, default: Dict[str, float], name: str, errors: List[str]) -> Dict[str, float]:
        """Run a stats function and fall back gracefully if it fails."""
        try:
            return func()
        except Exception as e:
            logger.warning(f"Falling back to defaults for {name}: {e}", exc_info=True)
            errors.append(name)
            return default
    
    def get_real_member_stats(self) -> Dict:
        """Get REAL member statistics from database."""
        raw_stats = member_queries.get_member_statistics()
        total = max(raw_stats.get('total', 0), 1)

        return {
            'total': raw_stats.get('total', 0),
            'new_today': raw_stats.get('new_today', 0),
            'with_username': raw_stats.get('with_username', 0),
            'username_pct': (raw_stats.get('with_username', 0) / total) * 100,
            'verified': raw_stats.get('verified', 0),
            'verified_pct': (raw_stats.get('verified', 0) / total) * 100,
            'premium': raw_stats.get('premium', 0),
            'premium_pct': (raw_stats.get('premium', 0) / total) * 100,
            'active_30d': raw_stats.get('active_30d', 0),
            'total_channels': raw_stats.get('total_channels', 0)
        }
    
    def get_real_campaign_stats(self) -> Dict:
        """Get REAL campaign statistics from database."""
        campaign_data = campaign_queries.get_campaign_stats()
        
        # Get campaigns for additional stats
        all_campaigns = campaign_queries.get_all_campaigns()
        
        # Today's stats
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        sent_today = 0
        failed_today = 0
        yesterday_sent = 0
        
        for campaign in all_campaigns:
            created = datetime.fromisoformat(campaign['created_at']).date() if campaign.get('created_at') else None
            
            if created == today:
                sent_today += campaign.get('sent_count', 0)
                failed_today += campaign.get('failed_count', 0)
            elif created == yesterday:
                yesterday_sent += campaign.get('sent_count', 0)
        
        stats = {
            'total': campaign_data.get('total_campaigns', 0),
            'running': campaign_data.get('running', 0),
            'completed': campaign_data.get('completed', 0),
            'total_sent': campaign_data.get('total_sent', 0),
            'total_failed': campaign_data.get('total_failed', 0),
            'sent_today': sent_today,
            'failed_today': failed_today,
            'yesterday_sent': yesterday_sent
        }
        
        # Completion rate
        if stats['total'] > 0:
            stats['completion_rate'] = (stats['completed'] / stats['total']) * 100
        else:
            stats['completion_rate'] = 0
        
        return stats
    
    def get_real_account_stats(self) -> Dict:
        """Get REAL account statistics from database."""
        account_data = account_queries.get_account_stats()
        
        stats = {
            'total': account_data.get('total_accounts', 0),
            'active': account_data.get('active', 0),
            'warmed_up': account_data.get('warmed_up', 0),
            'total_messages': account_data.get('total_messages', 0)
        }
        
        # Percentages
        if stats['total'] > 0:
            stats['percentage'] = (stats['active'] / stats['total']) * 100
            stats['warmup_pct'] = (stats['warmed_up'] / stats['total']) * 100
        else:
            stats['percentage'] = 0
            stats['warmup_pct'] = 0
        
        return stats

