"""
Engagement Automation Widget - UI for managing automated engagement rules.

Features:
- View all engagement rules
- Enable/disable entire rules
- Enable/disable specific groups for rules
- View engagement statistics
- Create and edit rules
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox,
    QCheckBox, QMessageBox, QDialog, QFormLayout, QLineEdit,
    QSpinBox, QDoubleSpinBox, QComboBox, QListWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont

logger = logging.getLogger(__name__)

# Try to import EngagementAutomation
try:
    from campaigns.engagement_automation import EngagementAutomation, EngagementRule
    ENGAGEMENT_AVAILABLE = True
except ImportError:
    ENGAGEMENT_AVAILABLE = False
    logger.warning("EngagementAutomation not available")


class EngagementRuleDialog(QDialog):
    """Dialog for creating/editing engagement rules."""
    
    def __init__(self, rule: Optional[EngagementRule] = None, parent=None):
        super().__init__(parent)
        self.rule = rule
        self.setWindowTitle("Engagement Rule" if not rule else f"Edit Rule: {rule.name}")
        self.setMinimumWidth(500)
        self.setup_ui()
        
        if rule:
            self.load_rule_data()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QFormLayout(self)
        
        # Rule name
        self.name_input = QLineEdit()
        layout.addRow("Rule Name:", self.name_input)
        
        # Enabled toggle
        self.enabled_check = QCheckBox("Rule Enabled")
        self.enabled_check.setChecked(True)
        layout.addRow("", self.enabled_check)
        
        # Reaction probability
        self.probability_spin = QDoubleSpinBox()
        self.probability_spin.setRange(0.0, 1.0)
        self.probability_spin.setSingleStep(0.1)
        self.probability_spin.setValue(0.3)
        layout.addRow("Reaction Probability:", self.probability_spin)
        
        # Rate limits
        self.max_per_hour_spin = QSpinBox()
        self.max_per_hour_spin.setRange(1, 1000)
        self.max_per_hour_spin.setValue(20)
        layout.addRow("Max Reactions/Hour:", self.max_per_hour_spin)
        
        self.max_per_group_spin = QSpinBox()
        self.max_per_group_spin.setRange(1, 100)
        self.max_per_group_spin.setValue(10)
        layout.addRow("Max Reactions/Group/Hour:", self.max_per_group_spin)
        
        # Timing
        self.min_delay_spin = QSpinBox()
        self.min_delay_spin.setRange(1, 300)
        self.min_delay_spin.setValue(5)
        layout.addRow("Min Delay (seconds):", self.min_delay_spin)
        
        self.max_delay_spin = QSpinBox()
        self.max_delay_spin.setRange(1, 600)
        self.max_delay_spin.setValue(120)
        layout.addRow("Max Delay (seconds):", self.max_delay_spin)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        
        # Debounce to prevent double-clicks
        from utils.button_debouncer import protect_button
        protect_button(save_btn, self.accept, debounce_ms=1000)
        
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addRow("", button_layout)
    
    def load_rule_data(self):
        """Load rule data into form."""
        if not self.rule:
            return
        
        self.name_input.setText(self.rule.name)
        self.enabled_check.setChecked(self.rule.enabled)
        self.probability_spin.setValue(self.rule.reaction_probability)
        self.max_per_hour_spin.setValue(self.rule.max_reactions_per_hour)
        self.max_per_group_spin.setValue(self.rule.max_reactions_per_group_per_hour)
        self.min_delay_spin.setValue(self.rule.min_delay_seconds)
        self.max_delay_spin.setValue(self.rule.max_delay_seconds)
    
    def get_rule_data(self) -> Dict:
        """Get rule data from form."""
        return {
            'name': self.name_input.text(),
            'enabled': self.enabled_check.isChecked(),
            'reaction_probability': self.probability_spin.value(),
            'max_reactions_per_hour': self.max_per_hour_spin.value(),
            'max_reactions_per_group_per_hour': self.max_per_group_spin.value(),
            'min_delay_seconds': self.min_delay_spin.value(),
            'max_delay_seconds': self.max_delay_spin.value()
        }


class EngagementWidget(QWidget):
    """Widget for managing engagement automation."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.engagement_automation: Optional[EngagementAutomation] = None
        self.setup_ui()
        
        # Auto-refresh timer
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(10000)  # 10 seconds
        
        # Try to initialize engagement automation
        self.initialize_engagement_automation()
    
    def initialize_engagement_automation(self):
        """Initialize engagement automation."""
        if not ENGAGEMENT_AVAILABLE:
            return
        
        try:
            self.engagement_automation = EngagementAutomation()
            self.refresh_data()
        except Exception as e:
            logger.error(f"Failed to initialize engagement automation: {e}")
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title = QLabel("🎯 Engagement Automation")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        header_layout.addWidget(refresh_btn)
        
        # Add rule button
        add_btn = QPushButton("➕ Add Rule")
        add_btn.clicked.connect(self.add_rule)
        header_layout.addWidget(add_btn)
        
        layout.addLayout(header_layout)
        
        # Rules table
        rules_group = QGroupBox("Engagement Rules")
        rules_layout = QVBoxLayout(rules_group)
        
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(7)
        self.rules_table.setHorizontalHeaderLabels([
            "Rule Name",
            "Enabled",
            "Reaction Prob",
            "Max/Hour",
            "Disabled Groups",
            "Actions",
            "Edit"
        ])
        
        header = self.rules_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        
        self.rules_table.setColumnWidth(1, 80)
        self.rules_table.setColumnWidth(2, 100)
        self.rules_table.setColumnWidth(3, 80)
        self.rules_table.setColumnWidth(5, 120)
        self.rules_table.setColumnWidth(6, 80)
        
        self.rules_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1f22;
                color: #b5bac1;
                gridline-color: #2b2d31;
                border: none;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #404249;
            }
            QHeaderView::section {
                background-color: #2b2d31;
                color: #b5bac1;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #5865f2;
            }
        """)
        
        rules_layout.addWidget(self.rules_table)
        layout.addWidget(rules_group)
        
        # Statistics
        stats_group = QGroupBox("Statistics")
        stats_layout = QHBoxLayout(stats_group)
        
        self.total_rules_label = QLabel("Total Rules: 0")
        stats_layout.addWidget(self.total_rules_label)
        
        self.enabled_rules_label = QLabel("Enabled: 0")
        stats_layout.addWidget(self.enabled_rules_label)
        
        self.total_reactions_label = QLabel("Total Reactions: 0")
        stats_layout.addWidget(self.total_reactions_label)
        
        stats_layout.addStretch()
        layout.addWidget(stats_group)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #949ba4; font-size: 11px; padding: 5px;")
        layout.addWidget(self.status_label)
    
    def refresh_data(self):
        """Refresh engagement rules data."""
        if not self.engagement_automation:
            self.status_label.setText("Engagement automation not available")
            return
        
        try:
            rules = self.engagement_automation.get_all_rules()
            
            # Update table
            self.rules_table.setRowCount(len(rules))
            
            for row, rule in enumerate(rules):
                # Rule name
                name_item = QTableWidgetItem(rule.name)
                self.rules_table.setItem(row, 0, name_item)
                
                # Enabled checkbox
                enabled_check = QCheckBox()
                enabled_check.setChecked(rule.enabled)
                enabled_check.stateChanged.connect(
                    lambda state, rule_id=rule.rule_id: self.toggle_rule_enabled(rule_id, state == Qt.CheckState.Checked.value)
                )
                enabled_widget = QWidget()
                enabled_layout = QHBoxLayout(enabled_widget)
                enabled_layout.addWidget(enabled_check)
                enabled_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                enabled_layout.setContentsMargins(0, 0, 0, 0)
                self.rules_table.setCellWidget(row, 1, enabled_widget)
                
                # Reaction probability
                prob_item = QTableWidgetItem(f"{rule.reaction_probability:.1%}")
                self.rules_table.setItem(row, 2, prob_item)
                
                # Max per hour
                max_item = QTableWidgetItem(str(rule.max_reactions_per_hour))
                self.rules_table.setItem(row, 3, max_item)
                
                # Disabled groups
                disabled_count = len(rule.disabled_groups) if rule.disabled_groups else 0
                disabled_item = QTableWidgetItem(f"{disabled_count} groups disabled")
                self.rules_table.setItem(row, 4, disabled_item)
                
                # Actions (Manage Groups)
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(2, 2, 2, 2)
                
                manage_btn = QPushButton("Manage Groups")
                manage_btn.clicked.connect(
                    lambda checked, rule_id=rule.rule_id: self.manage_rule_groups(rule_id)
                )
                actions_layout.addWidget(manage_btn)
                
                self.rules_table.setCellWidget(row, 5, actions_widget)
                
                # Edit button
                edit_widget = QWidget()
                edit_layout = QHBoxLayout(edit_widget)
                edit_layout.setContentsMargins(2, 2, 2, 2)
                
                edit_btn = QPushButton("Edit")
                edit_btn.clicked.connect(
                    lambda checked, r=rule: self.edit_rule(r)
                )
                edit_layout.addWidget(edit_btn)
                
                self.rules_table.setCellWidget(row, 6, edit_widget)
            
            # Update statistics
            total = len(rules)
            enabled = sum(1 for r in rules if r.enabled)
            
            self.total_rules_label.setText(f"Total Rules: {total}")
            self.enabled_rules_label.setText(f"Enabled: {enabled}")
            
            # Get engagement stats
            stats = self.engagement_automation.get_engagement_stats()
            total_reactions = stats.get('total_reactions', 0)
            self.total_reactions_label.setText(f"Total Reactions: {total_reactions:,}")
            
            self.status_label.setText(f"Last updated: {datetime.now().strftime('%H:%M:%S')}")
            
        except Exception as e:
            logger.error(f"Failed to refresh engagement data: {e}")
            self.status_label.setText(f"Error: {str(e)[:50]}")
    
    def toggle_rule_enabled(self, rule_id: str, enabled: bool):
        """Toggle rule enabled state."""
        if not self.engagement_automation:
            return
        
        try:
            rule = self.engagement_automation.get_rule(rule_id)
            if rule:
                rule.enabled = enabled
                self.engagement_automation.add_rule(rule)
                self.status_label.setText(f"Rule {'enabled' if enabled else 'disabled'}")
                logger.info(f"Rule {rule_id} {'enabled' if enabled else 'disabled'}")
        except Exception as e:
            logger.error(f"Failed to toggle rule: {e}")
            QMessageBox.warning(self, "Error", f"Failed to toggle rule: {e}")
    
    def manage_rule_groups(self, rule_id: str):
        """Open dialog to manage groups for a rule."""
        if not self.engagement_automation:
            return
        
        rule = self.engagement_automation.get_rule(rule_id)
        if not rule:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Manage Groups - {rule.name}")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Info
        info = QLabel(f"Manage group enable/disable for rule: {rule.name}")
        layout.addWidget(info)
        
        # List of target groups
        if rule.target_groups:
            groups_label = QLabel(f"Target Groups ({len(rule.target_groups)}):")
            layout.addWidget(groups_label)
            
            groups_list = QListWidget()
            
            for group_id in rule.target_groups:
                item_widget = QWidget()
                item_layout = QHBoxLayout(item_widget)
                
                group_label = QLabel(f"Group ID: {group_id}")
                item_layout.addWidget(group_label)
                
                item_layout.addStretch()
                
                is_disabled = group_id in (rule.disabled_groups or [])
                toggle_btn = QPushButton("Enable" if is_disabled else "Disable")
                toggle_btn.clicked.connect(
                    lambda checked, gid=group_id, rule=rule: self.toggle_group_for_rule(rule.rule_id, gid, dialog)
                )
                item_layout.addWidget(toggle_btn)
                
                groups_list.addItem(f"Group {group_id}")
                # Note: In a real implementation, you'd set the widget for the list item
            
            layout.addWidget(groups_list)
        else:
            layout.addWidget(QLabel("No target groups configured"))
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()
    
    def toggle_group_for_rule(self, rule_id: str, group_id: int, dialog: QDialog):
        """Toggle group enabled/disabled for a rule."""
        if not self.engagement_automation:
            return
        
        try:
            rule = self.engagement_automation.get_rule(rule_id)
            if not rule:
                return
            
            is_disabled = group_id in (rule.disabled_groups or [])
            
            if is_disabled:
                success = self.engagement_automation.enable_group_for_rule(rule_id, group_id)
                action = "enabled"
            else:
                success = self.engagement_automation.disable_group_for_rule(rule_id, group_id)
                action = "disabled"
            
            if success:
                self.status_label.setText(f"Group {group_id} {action}")
                dialog.accept()  # Close and refresh
                self.refresh_data()
            else:
                QMessageBox.warning(self, "Error", f"Failed to toggle group {group_id}")
                
        except Exception as e:
            logger.error(f"Failed to toggle group: {e}")
            QMessageBox.warning(self, "Error", f"Failed to toggle group: {e}")
    
    def add_rule(self):
        """Add a new engagement rule."""
        dialog = EngagementRuleDialog(parent=self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            rule_data = dialog.get_rule_data()
            
            try:
                import uuid
                from campaigns.engagement_automation import EngagementRule
                from dataclasses import replace
                
                rule_id = f"rule_{uuid.uuid4().hex[:8]}"
                
                rule = EngagementRule(
                    rule_id=rule_id,
                    name=rule_data['name'],
                    enabled=rule_data['enabled'],
                    reaction_probability=rule_data['reaction_probability'],
                    max_reactions_per_hour=rule_data['max_reactions_per_hour'],
                    max_reactions_per_group_per_hour=rule_data['max_reactions_per_group_per_hour'],
                    min_delay_seconds=rule_data['min_delay_seconds'],
                    max_delay_seconds=rule_data['max_delay_seconds']
                )
                
                if self.engagement_automation:
                    self.engagement_automation.add_rule(rule)
                    self.refresh_data()
                    QMessageBox.information(self, "Success", f"Rule '{rule.name}' created successfully!")
                
            except Exception as e:
                logger.error(f"Failed to create rule: {e}")
                QMessageBox.warning(self, "Error", f"Failed to create rule: {e}")
    
    def edit_rule(self, rule: EngagementRule):
        """Edit an existing engagement rule."""
        dialog = EngagementRuleDialog(rule=rule, parent=self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            rule_data = dialog.get_rule_data()
            
            try:
                from dataclasses import replace
                
                updated_rule = replace(
                    rule,
                    name=rule_data['name'],
                    enabled=rule_data['enabled'],
                    reaction_probability=rule_data['reaction_probability'],
                    max_reactions_per_hour=rule_data['max_reactions_per_hour'],
                    max_reactions_per_group_per_hour=rule_data['max_reactions_per_group_per_hour'],
                    min_delay_seconds=rule_data['min_delay_seconds'],
                    max_delay_seconds=rule_data['max_delay_seconds'],
                    updated_at=datetime.now()
                )
                
                if self.engagement_automation:
                    self.engagement_automation.add_rule(updated_rule)
                    self.refresh_data()
                    QMessageBox.information(self, "Success", f"Rule '{updated_rule.name}' updated successfully!")
                
            except Exception as e:
                logger.error(f"Failed to update rule: {e}")
                QMessageBox.warning(self, "Error", f"Failed to update rule: {e}")






