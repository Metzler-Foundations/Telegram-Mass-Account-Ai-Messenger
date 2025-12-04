"""
Warmup Configuration Widget - UI for managing account warmup settings.

Features:
- Configure blackout windows (hours when warmup should not run)
- Set stage-level weights and priorities
- Adjust daily activity limits and pacing
- Configure timing delays between actions
"""

import logging
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox, QGridLayout,
    QTimeEdit, QComboBox, QMessageBox, QFormLayout
)
from PyQt6.QtCore import Qt, QTime, pyqtSignal
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)

# Try to import warmup service
try:
    from accounts.account_warmup_service import AccountWarmupService, WarmupConfig, WarmupPriority
    WARMUP_AVAILABLE = True
except ImportError:
    WARMUP_AVAILABLE = False
    logger.warning("AccountWarmupService not available")


class WarmupConfigWidget(QWidget):
    """Widget for configuring account warmup settings."""
    
    config_changed = pyqtSignal(dict)
    
    def __init__(self, warmup_service: Optional['AccountWarmupService'] = None, parent=None):
        super().__init__(parent)
        self.warmup_service = warmup_service
        self.config = warmup_service.config if warmup_service else None
        self.setup_ui()
        
        if self.config:
            self.load_config()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("⚙️ Warmup Configuration")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Save button
        save_btn = QPushButton("💾 Save Configuration")
        save_btn.clicked.connect(self.save_config)
        header_layout.addWidget(save_btn)
        
        # Reset button
        reset_btn = QPushButton("🔄 Reset to Defaults")
        reset_btn.clicked.connect(self.reset_to_defaults)
        header_layout.addWidget(reset_btn)
        
        layout.addLayout(header_layout)
        
        # Blackout Windows
        blackout_group = QGroupBox("🌙 Blackout Windows")
        blackout_layout = QVBoxLayout(blackout_group)
        
        blackout_info = QLabel(
            "Configure time windows when warmup activities should NOT run.\n"
            "Useful for avoiding detection patterns or matching timezone behavior."
        )
        blackout_info.setStyleSheet("color: #949ba4; font-size: 11px;")
        blackout_info.setWordWrap(True)
        blackout_layout.addWidget(blackout_info)
        
        # Blackout window 1
        blackout1_layout = QHBoxLayout()
        blackout1_layout.addWidget(QLabel("Blackout Window 1:"))
        
        self.blackout1_enabled = QCheckBox("Enabled")
        blackout1_layout.addWidget(self.blackout1_enabled)
        
        blackout1_layout.addWidget(QLabel("From:"))
        self.blackout1_start = QTimeEdit()
        self.blackout1_start.setTime(QTime(2, 0))  # Default 2 AM
        blackout1_layout.addWidget(self.blackout1_start)
        
        blackout1_layout.addWidget(QLabel("To:"))
        self.blackout1_end = QTimeEdit()
        self.blackout1_end.setTime(QTime(6, 0))  # Default 6 AM
        blackout1_layout.addWidget(self.blackout1_end)
        
        blackout1_layout.addStretch()
        blackout_layout.addLayout(blackout1_layout)
        
        # Blackout window 2
        blackout2_layout = QHBoxLayout()
        blackout2_layout.addWidget(QLabel("Blackout Window 2:"))
        
        self.blackout2_enabled = QCheckBox("Enabled")
        blackout2_layout.addWidget(self.blackout2_enabled)
        
        blackout2_layout.addWidget(QLabel("From:"))
        self.blackout2_start = QTimeEdit()
        self.blackout2_start.setTime(QTime(12, 0))  # Default noon
        blackout2_layout.addWidget(self.blackout2_start)
        
        blackout2_layout.addWidget(QLabel("To:"))
        self.blackout2_end = QTimeEdit()
        self.blackout2_end.setTime(QTime(14, 0))  # Default 2 PM
        blackout2_layout.addWidget(self.blackout2_end)
        
        blackout2_layout.addStretch()
        blackout_layout.addLayout(blackout2_layout)
        
        layout.addWidget(blackout_group)
        
        # Stage Weights and Priorities
        stages_group = QGroupBox("📊 Stage Weights & Priorities")
        stages_layout = QVBoxLayout(stages_group)
        
        stages_info = QLabel(
            "Configure priority and weight for each warmup stage.\n"
            "Higher weights = more time spent on that stage."
        )
        stages_info.setStyleSheet("color: #949ba4; font-size: 11px;")
        stages_info.setWordWrap(True)
        stages_layout.addWidget(stages_info)
        
        # Create stage controls
        stages_grid = QGridLayout()
        stages_grid.addWidget(QLabel("<b>Stage</b>"), 0, 0)
        stages_grid.addWidget(QLabel("<b>Priority</b>"), 0, 1)
        stages_grid.addWidget(QLabel("<b>Weight</b>"), 0, 2)
        stages_grid.addWidget(QLabel("<b>Days</b>"), 0, 3)
        
        self.stage_controls = {}
        stages = [
            ('initial_setup', 'Initial Setup', 6),
            ('profile_completion', 'Profile Completion', 12),
            ('contact_building', 'Contact Building', 24),
            ('group_joining', 'Group Joining', 48),
            ('conversation_starters', 'Conversation Starters', 72),
            ('activity_increase', 'Activity Increase', 96),
            ('advanced_interactions', 'Advanced Interactions', 120),
            ('stabilization', 'Stabilization', 168)
        ]
        
        for row, (stage_key, stage_name, default_hours) in enumerate(stages, start=1):
            # Stage name
            stages_grid.addWidget(QLabel(stage_name), row, 0)
            
            # Priority dropdown
            priority_combo = QComboBox()
            priority_combo.addItems(['Low', 'Normal', 'High', 'Critical'])
            priority_combo.setCurrentText('Normal')
            stages_grid.addWidget(priority_combo, row, 1)
            
            # Weight spinner
            weight_spin = QDoubleSpinBox()
            weight_spin.setRange(0.1, 5.0)
            weight_spin.setSingleStep(0.1)
            weight_spin.setValue(1.0)
            weight_spin.setDecimals(1)
            stages_grid.addWidget(weight_spin, row, 2)
            
            # Days/hours spinner
            days_spin = QSpinBox()
            days_spin.setRange(1, 720)  # 1 hour to 30 days
            days_spin.setValue(default_hours)
            days_spin.setSuffix(" hours")
            stages_grid.addWidget(days_spin, row, 3)
            
            self.stage_controls[stage_key] = {
                'priority': priority_combo,
                'weight': weight_spin,
                'hours': days_spin
            }
        
        stages_layout.addLayout(stages_grid)
        layout.addWidget(stages_group)
        
        # Daily Limits
        limits_group = QGroupBox("📅 Daily Activity Limits")
        limits_layout = QFormLayout(limits_group)
        
        self.daily_activity_limit = QSpinBox()
        self.daily_activity_limit.setRange(1, 100)
        self.daily_activity_limit.setValue(20)
        limits_layout.addRow("Max Activities/Day:", self.daily_activity_limit)
        
        self.contacts_per_day = QSpinBox()
        self.contacts_per_day.setRange(0, 50)
        self.contacts_per_day.setValue(5)
        limits_layout.addRow("Contacts/Day:", self.contacts_per_day)
        
        self.groups_per_day = QSpinBox()
        self.groups_per_day.setRange(0, 20)
        self.groups_per_day.setValue(2)
        limits_layout.addRow("Groups/Day:", self.groups_per_day)
        
        self.messages_per_day = QSpinBox()
        self.messages_per_day.setRange(0, 100)
        self.messages_per_day.setValue(10)
        limits_layout.addRow("Messages/Day:", self.messages_per_day)
        
        layout.addWidget(limits_group)
        
        # Timing Delays
        timing_group = QGroupBox("⏱️ Timing & Delays")
        timing_layout = QFormLayout(timing_group)
        
        self.min_delay = QSpinBox()
        self.min_delay.setRange(10, 300)
        self.min_delay.setValue(30)
        self.min_delay.setSuffix(" seconds")
        timing_layout.addRow("Min Delay Between Actions:", self.min_delay)
        
        self.max_delay = QSpinBox()
        self.max_delay.setRange(60, 600)
        self.max_delay.setValue(300)
        self.max_delay.setSuffix(" seconds")
        timing_layout.addRow("Max Delay Between Actions:", self.max_delay)
        
        self.session_max_duration = QSpinBox()
        self.session_max_duration.setRange(5, 120)
        self.session_max_duration.setValue(30)
        self.session_max_duration.setSuffix(" minutes")
        timing_layout.addRow("Max Session Duration:", self.session_max_duration)
        
        layout.addWidget(timing_group)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #949ba4; font-size: 11px; padding: 5px;")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
    
    def load_config(self):
        """Load current configuration."""
        if not self.config:
            return
        
        try:
            # Load daily limits
            self.daily_activity_limit.setValue(self.config.daily_activity_limit)
            self.contacts_per_day.setValue(self.config.contacts_per_day)
            self.groups_per_day.setValue(self.config.groups_per_day)
            self.messages_per_day.setValue(self.config.messages_per_day)
            
            # Load timing
            self.min_delay.setValue(self.config.min_delay_between_actions)
            self.max_delay.setValue(self.config.max_delay_between_actions)
            self.session_max_duration.setValue(self.config.session_max_duration)
            
            # Load stage delays
            if self.config.stage_delays:
                for stage_key, hours in self.config.stage_delays.items():
                    if stage_key in self.stage_controls:
                        self.stage_controls[stage_key]['hours'].setValue(hours)
            
            self.status_label.setText("Configuration loaded")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            self.status_label.setText(f"Error loading config: {str(e)[:50]}")
    
    def save_config(self):
        """Save configuration."""
        if not self.warmup_service:
            QMessageBox.warning(self, "Not Available", "Warmup service not initialized")
            return
        
        try:
            # Update config object
            self.config.daily_activity_limit = self.daily_activity_limit.value()
            self.config.contacts_per_day = self.contacts_per_day.value()
            self.config.groups_per_day = self.groups_per_day.value()
            self.config.messages_per_day = self.messages_per_day.value()
            
            self.config.min_delay_between_actions = self.min_delay.value()
            self.config.max_delay_between_actions = self.max_delay.value()
            self.config.session_max_duration = self.session_max_duration.value()
            
            # Update stage delays
            stage_delays = {}
            for stage_key, controls in self.stage_controls.items():
                stage_delays[stage_key] = controls['hours'].value()
            self.config.stage_delays = stage_delays
            
            # Collect blackout windows
            blackout_windows = []
            if self.blackout1_enabled.isChecked():
                blackout_windows.append({
                    'start': self.blackout1_start.time().toString("HH:mm"),
                    'end': self.blackout1_end.time().toString("HH:mm")
                })
            if self.blackout2_enabled.isChecked():
                blackout_windows.append({
                    'start': self.blackout2_start.time().toString("HH:mm"),
                    'end': self.blackout2_end.time().toString("HH:mm")
                })
            
            # Emit config changed signal
            config_dict = {
                'daily_limits': {
                    'activities': self.daily_activity_limit.value(),
                    'contacts': self.contacts_per_day.value(),
                    'groups': self.groups_per_day.value(),
                    'messages': self.messages_per_day.value()
                },
                'timing': {
                    'min_delay': self.min_delay.value(),
                    'max_delay': self.max_delay.value(),
                    'session_max': self.session_max_duration.value()
                },
                'stage_delays': stage_delays,
                'blackout_windows': blackout_windows
            }
            
            self.config_changed.emit(config_dict)
            self.status_label.setText("✓ Configuration saved")
            
            QMessageBox.information(
                self,
                "Configuration Saved",
                "Warmup configuration has been updated successfully.\n\n"
                "Changes will apply to new warmup jobs."
            )
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")
            QMessageBox.critical(self, "Error", f"Failed to save configuration:\n{e}")
    
    def reset_to_defaults(self):
        """Reset configuration to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if WARMUP_AVAILABLE:
                    self.config = WarmupConfig()  # Create new default config
                    if self.warmup_service:
                        self.warmup_service.config = self.config
                    self.load_config()
                    self.status_label.setText("✓ Reset to defaults")
                else:
                    QMessageBox.warning(self, "Not Available", "Warmup service not available")
            except Exception as e:
                logger.error(f"Failed to reset configuration: {e}")
                QMessageBox.critical(self, "Error", f"Failed to reset:\n{e}")
    
    def get_stage_weights(self) -> Dict[str, float]:
        """Get configured stage weights."""
        weights = {}
        for stage_key, controls in self.stage_controls.items():
            weights[stage_key] = controls['weight'].value()
        return weights
    
    def get_stage_priorities(self) -> Dict[str, str]:
        """Get configured stage priorities."""
        priorities = {}
        for stage_key, controls in self.stage_controls.items():
            priorities[stage_key] = controls['priority'].currentText().lower()
        return priorities




