#!/usr/bin/env python3
"""
Template Tester - Test message templates before sending campaigns
Preview how messages will look with actual data
"""

import logging
import re
from typing import Dict, List, Optional
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QGroupBox, QFormLayout,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class TemplateTestDialog(QDialog):
    """Dialog for testing message templates."""
    
    def __init__(self, template: str = "", members: Optional[List[Dict]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📝 Test Message Template")
        self.resize(800, 600)
        
        self.template = template
        self.members = members or []
        self.variables = self.extract_variables(template)
        
        self.setup_ui()
        self.update_preview()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("📝 Message Template Tester")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        desc = QLabel(
            "Test your message template with real member data.\n"
            "See how your message will look before sending to all recipients."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Split layout
        content_layout = QHBoxLayout()
        
        # Left side - Template and test data
        left_layout = QVBoxLayout()
        
        # Template input
        template_group = QGroupBox("Message Template")
        template_layout = QVBoxLayout()
        
        self.template_edit = QTextEdit()
        self.template_edit.setPlaceholderText(
            "Enter your message template here.\n\n"
            "Use variables like:\n"
            "• {first_name} - Recipient's first name\n"
            "• {last_name} - Recipient's last name\n"
            "• {username} - Recipient's username\n"
            "• {custom} - Any custom field"
        )
        self.template_edit.setText(self.template)
        self.template_edit.textChanged.connect(self.on_template_changed)
        template_layout.addWidget(self.template_edit)
        
        template_group.setLayout(template_layout)
        left_layout.addWidget(template_group)
        
        # Variables section
        if self.variables:
            var_group = QGroupBox(f"Found Variables ({len(self.variables)})")
            var_layout = QVBoxLayout()
            
            var_label = QLabel("Variables in template: " + ", ".join(f"<code>{v}</code>" for v in self.variables))
            var_label.setWordWrap(True)
            var_label.setTextFormat(Qt.TextFormat.RichText)
            var_layout.addWidget(var_label)
            
            var_group.setLayout(var_layout)
            left_layout.addWidget(var_group)
        
        # Test data input
        test_group = QGroupBox("Test Data")
        test_layout = QFormLayout()
        
        self.test_data_inputs = {}
        for var in self.variables:
            input_field = QLineEdit()
            input_field.setPlaceholderText(f"Enter test value for {var}")
            input_field.textChanged.connect(self.update_preview)
            self.test_data_inputs[var] = input_field
            test_layout.addRow(f"{var}:", input_field)
        
        # Member selector if members available
        if self.members:
            self.member_combo = QComboBox()
            self.member_combo.addItem("Custom test data", None)
            for i, member in enumerate(self.members[:20]):  # Limit to first 20
                display = f"{member.get('first_name', '')} {member.get('last_name', '')} (@{member.get('username', 'N/A')})"
                self.member_combo.addItem(display.strip(), member)
            self.member_combo.currentIndexChanged.connect(self.on_member_selected)
            test_layout.addRow("Use real member:", self.member_combo)
        
        test_group.setLayout(test_layout)
        left_layout.addWidget(test_group)
        
        content_layout.addLayout(left_layout, 1)
        
        # Right side - Preview
        right_layout = QVBoxLayout()
        
        preview_group = QGroupBox("📱 Message Preview")
        preview_layout = QVBoxLayout()
        
        # Preview area (styled like a chat bubble)
        self.preview_area = QTextEdit()
        self.preview_area.setReadOnly(True)
        self.preview_area.setStyleSheet("""
            QTextEdit {
                background-color: #dcf8c6;
                border: 1px solid #34b7f1;
                border-radius: 8px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        preview_layout.addWidget(self.preview_area)
        
        # Character count
        self.char_count_label = QLabel()
        preview_layout.addWidget(self.char_count_label)
        
        preview_group.setLayout(preview_layout)
        right_layout.addWidget(preview_group)
        
        # Tips
        tips_group = QGroupBox("💡 Tips")
        tips_layout = QVBoxLayout()
        tips = QLabel(
            "• Keep messages under 300 characters for best delivery\n"
            "• Personalize with recipient's first name\n"
            "• Include a clear call-to-action\n"
            "• Test with multiple members to ensure it works for all\n"
            "• Avoid spam words: free, win, click here, etc."
        )
        tips.setWordWrap(True)
        tips_layout.addWidget(tips)
        tips_group.setLayout(tips_layout)
        right_layout.addWidget(tips_group)
        
        content_layout.addLayout(right_layout, 1)
        layout.addLayout(content_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.test_multiple_btn = QPushButton("🧪 Test with Multiple Members")
        self.test_multiple_btn.clicked.connect(self.test_with_multiple)
        self.test_multiple_btn.setEnabled(len(self.members) > 0)
        button_layout.addWidget(self.test_multiple_btn)
        
        button_layout.addStretch()
        
        use_btn = QPushButton("✅ Use This Template")
        use_btn.clicked.connect(self.accept)
        use_btn.setObjectName("success")
        button_layout.addWidget(use_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    @staticmethod
    def extract_variables(template: str) -> List[str]:
        """Extract variables from template."""
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, template)
        return list(set(matches))  # Unique variables
    
    def on_template_changed(self):
        """Handle template text change."""
        self.template = self.template_edit.toPlainText()
        self.variables = self.extract_variables(self.template)
        self.update_preview()
    
    def on_member_selected(self, index: int):
        """Handle member selection."""
        member = self.member_combo.currentData()
        
        if member:
            # Fill in test data from selected member
            for var in self.variables:
                if var in self.test_data_inputs:
                    value = member.get(var, f"[{var}]")
                    self.test_data_inputs[var].setText(str(value))
        
        self.update_preview()
    
    def update_preview(self):
        """Update the preview."""
        template = self.template_edit.toPlainText()
        
        # Get test data
        test_data = {}
        for var, input_field in self.test_data_inputs.items():
            test_data[var] = input_field.text() or f"[{var}]"
        
        # Replace variables
        preview_text = template
        for var, value in test_data.items():
            preview_text = preview_text.replace(f"{{{var}}}", value)
        
        # Update preview
        self.preview_area.setPlainText(preview_text)
        
        # Update character count
        char_count = len(preview_text)
        if char_count > 300:
            color = "red"
            warning = " ⚠️ Too long!"
        elif char_count > 200:
            color = "orange"
            warning = " ⚠️ Consider shortening"
        else:
            color = "green"
            warning = " ✅"
        
        self.char_count_label.setText(
            f"<span style='color: {color};'><b>Characters:</b> {char_count}{warning}</span>"
        )
        self.char_count_label.setTextFormat(Qt.TextFormat.RichText)
    
    def test_with_multiple(self):
        """Test template with multiple members."""
        if not self.members:
            QMessageBox.information(self, "No Members", "No members available for testing")
            return
        
        # Create dialog showing multiple previews
        dialog = MultiplePreviewDialog(self.template, self.members[:10], self)
        dialog.exec()
    
    def get_template(self) -> str:
        """Get the template text."""
        return self.template_edit.toPlainText()


class MultiplePreviewDialog(QDialog):
    """Dialog showing previews for multiple recipients."""
    
    def __init__(self, template: str, members: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("🧪 Multiple Member Preview")
        self.resize(700, 500)
        
        self.template = template
        self.members = members
        
        self.setup_ui()
        self.generate_previews()
    
    def setup_ui(self):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel(f"🧪 Testing with {len(self.members)} Members")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        desc = QLabel("Here's how your message will look for different recipients:")
        layout.addWidget(desc)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Recipient", "Message Preview"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True)
        layout.addWidget(self.table)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
    
    def generate_previews(self):
        """Generate previews for all members."""
        self.table.setRowCount(len(self.members))
        
        for row, member in enumerate(self.members):
            # Recipient info
            recipient = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip()
            if not recipient:
                recipient = f"@{member.get('username', 'Unknown')}"
            
            self.table.setItem(row, 0, QTableWidgetItem(recipient))
            
            # Generate message
            message = self.template
            for key, value in member.items():
                message = message.replace(f"{{{key}}}", str(value))
            
            # Check for unsubstituted variables
            remaining_vars = re.findall(r'\{([^}]+)\}', message)
            if remaining_vars:
                message += f"\n\n⚠️ Missing: {', '.join(remaining_vars)}"
            
            self.table.setItem(row, 1, QTableWidgetItem(message))
        
        # Auto-resize rows
        self.table.resizeRowsToContents()


def test_template(template: str, members: Optional[List[Dict]] = None, parent=None) -> Optional[str]:
    """Show template tester dialog and return template if accepted."""
    dialog = TemplateTestDialog(template, members, parent)
    
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_template()
    
    return None

