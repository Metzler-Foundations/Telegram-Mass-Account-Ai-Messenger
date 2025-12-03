#!/usr/bin/env python3
"""
Campaign Tracker - REAL campaign progress tracking with database persistence
Tracks actual message sending, not simulated
"""

import logging
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QTextEdit, QPushButton, QFrame, QGroupBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class CampaignProgressTracker(QWidget):
    """Widget showing REAL campaign progress."""
    
    def __init__(self, campaign_id: int, parent=None):
        super().__init__(parent)
        self.campaign_id = campaign_id
        self.setup_ui()
        
        # Auto-refresh
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_stats)
        self.refresh_timer.start(2000)  # Every 2 seconds for real-time updates
        
        # Initial load
        self.refresh_stats()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Campaign name
        self.name_label = QLabel()
        name_font = QFont()
        name_font.setPointSize(14)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        layout.addWidget(self.name_label)
        
        # Status
        self.status_label = QLabel()
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Stats grid
        stats_frame = QFrame()
        stats_frame.setFrameShape(QFrame.Shape.StyledPanel)
        stats_layout = QHBoxLayout(stats_frame)
        
        self.sent_label = QLabel()
        stats_layout.addWidget(self.sent_label)
        
        self.failed_label = QLabel()
        stats_layout.addWidget(self.failed_label)
        
        self.rate_label = QLabel()
        stats_layout.addWidget(self.rate_label)
        
        self.eta_label = QLabel()
        stats_layout.addWidget(self.eta_label)
        
        layout.addWidget(stats_frame)
        
        # Activity log
        log_group = QGroupBox("Recent Activity")
        log_layout = QVBoxLayout()
        
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumHeight(150)
        log_layout.addWidget(self.activity_log)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
    
    def refresh_stats(self):
        """Refresh with REAL data from database."""
        try:
            # Query REAL campaign data
            conn = sqlite3.connect('campaigns.db')
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    name, status, message_template,
                    total_targets, sent_count, failed_count,
                    created_at, started_at, completed_at
                FROM campaigns
                WHERE id = ?
            """, (self.campaign_id,))
            
            row = cursor.fetchone()
            
            if not row:
                self.status_label.setText("❌ Campaign not found")
                conn.close()
                return
            
            campaign = dict(row)
            
            # Get recent messages for activity log
            cursor.execute("""
                SELECT 
                    target_user_id, sent_at, status, error_message
                FROM campaign_messages
                WHERE campaign_id = ?
                ORDER BY sent_at DESC
                LIMIT 10
            """, (self.campaign_id,))
            
            recent_messages = [dict(r) for r in cursor.fetchall()]
            
            conn.close()
            
            # Update UI with REAL data
            self.name_label.setText(f"📧 {campaign['name']}")
            
            status = campaign['status']
            if status == 'running':
                self.status_label.setText("▶️ Running")
            elif status == 'paused':
                self.status_label.setText("⏸️ Paused")
            elif status == 'completed':
                self.status_label.setText("✅ Completed")
            elif status == 'error':
                self.status_label.setText("❌ Error")
            else:
                self.status_label.setText(f"📋 {status.title()}")
            
            # Progress
            total = campaign['total_targets']
            sent = campaign['sent_count']
            failed = campaign['failed_count']
            completed = sent + failed
            
            if total > 0:
                progress_pct = int((completed / total) * 100)
                self.progress_bar.setValue(progress_pct)
                self.progress_bar.setFormat(f"{completed}/{total} ({progress_pct}%)")
            
            # Stats
            self.sent_label.setText(f"✅ Sent: {sent:,}")
            self.failed_label.setText(f"❌ Failed: {failed:,}")
            
            # Success rate
            if completed > 0:
                success_rate = (sent / completed) * 100
                self.rate_label.setText(f"📊 Success: {success_rate:.1f}%")
            else:
                self.rate_label.setText("📊 Success: N/A")
            
            # ETA
            if status == 'running' and completed > 0 and total > completed:
                # Calculate REAL ETA based on actual sending rate
                if campaign.get('started_at'):
                    started = datetime.fromisoformat(campaign['started_at'])
                    elapsed = (datetime.now() - started).total_seconds()
                    rate = completed / max(elapsed, 1)  # items per second
                    remaining = total - completed
                    eta_seconds = remaining / max(rate, 0.001)
                    
                    if eta_seconds < 60:
                        eta_str = f"{int(eta_seconds)}s"
                    elif eta_seconds < 3600:
                        eta_str = f"{int(eta_seconds / 60)}m"
                    else:
                        eta_str = f"{int(eta_seconds / 3600)}h {int((eta_seconds % 3600) / 60)}m"
                    
                    self.eta_label.setText(f"⏱️ ETA: {eta_str}")
                else:
                    self.eta_label.setText("⏱️ ETA: Calculating...")
            else:
                self.eta_label.setText("")
            
            # Update activity log with REAL message data
            if recent_messages:
                log_text = ""
                for msg in recent_messages:
                    timestamp = datetime.fromisoformat(msg['sent_at']).strftime("%H:%M:%S")
                    user_id = msg['target_user_id']
                    status = msg['status']
                    
                    if status == 'sent':
                        log_text += f"[{timestamp}] ✅ Sent to user {user_id}\n"
                    else:
                        error = msg.get('error_message', 'Unknown error')
                        log_text += f"[{timestamp}] ❌ Failed to {user_id}: {error[:30]}\n"
                
                self.activity_log.setPlainText(log_text)
        
        except Exception as e:
            logger.error(f"Failed to refresh campaign stats: {e}", exc_info=True)
            self.status_label.setText(f"❌ Error loading data: {e}")


def initialize_campaign_database():
    """Initialize REAL campaign tracking database."""
    try:
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        
        # Create campaigns table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaigns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                message_template TEXT,
                total_targets INTEGER,
                sent_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                accounts_used TEXT,
                delay_seconds REAL,
                target_channels TEXT
            )
        """)
        
        # Create campaign_messages table for detailed tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS campaign_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id INTEGER,
                target_user_id INTEGER,
                sent_at TEXT,
                status TEXT,
                error_message TEXT,
                account_used TEXT,
                FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
            )
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_campaign_messages_campaign 
            ON campaign_messages(campaign_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_campaign_messages_sent_at 
            ON campaign_messages(sent_at)
        """)
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Campaign database initialized with REAL tables")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize campaign database: {e}")
        return False


def save_campaign_message(campaign_id: int, target_user_id: int, account: str, 
                          status: str, error: str = None):
    """Save ACTUAL campaign message to database for tracking."""
    try:
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO campaign_messages (
                campaign_id, target_user_id, sent_at, status, error_message, account_used
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            campaign_id,
            target_user_id,
            datetime.now().isoformat(),
            status,
            error,
            account
        ))
        
        # Update campaign counters
        if status == 'sent':
            cursor.execute("""
                UPDATE campaigns 
                SET sent_count = sent_count + 1
                WHERE id = ?
            """, (campaign_id,))
        else:
            cursor.execute("""
                UPDATE campaigns 
                SET failed_count = failed_count + 1
                WHERE id = ?
            """, (campaign_id,))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Saved campaign message: {status} to user {target_user_id}")
        
    except Exception as e:
        logger.error(f"Failed to save campaign message: {e}")


def update_campaign_status(campaign_id: int, status: str):
    """Update REAL campaign status in database."""
    try:
        conn = sqlite3.connect('campaigns.db')
        cursor = conn.cursor()
        
        update_fields = {'status': status}
        
        if status == 'running' and not cursor.execute(
            "SELECT started_at FROM campaigns WHERE id = ?", (campaign_id,)
        ).fetchone()[0]:
            update_fields['started_at'] = datetime.now().isoformat()
        
        if status == 'completed':
            update_fields['completed_at'] = datetime.now().isoformat()
        
        set_clause = ", ".join([f"{k} = ?" for k in update_fields.keys()])
        values = list(update_fields.values()) + [campaign_id]
        
        cursor.execute(f"UPDATE campaigns SET {set_clause} WHERE id = ?", values)
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Updated campaign {campaign_id} status to: {status}")
        
    except Exception as e:
        logger.error(f"Failed to update campaign status: {e}")


# Initialize database on import
initialize_campaign_database()

