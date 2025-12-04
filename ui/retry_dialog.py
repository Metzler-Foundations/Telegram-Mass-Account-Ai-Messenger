"""
Retry Dialog - Enhanced error dialogs with retry functionality.
"""

import logging
from typing import Callable, Optional, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QFrame, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

logger = logging.getLogger(__name__)


class RetryDialog(QDialog):
    """Dialog for displaying errors with retry functionality."""
    
    def __init__(
        self,
        parent=None,
        title: str = "Operation Failed",
        message: str = "An error occurred",
        error_details: str = "",
        retry_callback: Optional[Callable] = None,
        max_retries: int = 3
    ):
        super().__init__(parent)
        self.retry_callback = retry_callback
        self.max_retries = max_retries
        self.retry_count = 0
        self.error_details = error_details
        
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(500, 350)
        self.setup_ui(title, message)
    
    def setup_ui(self, title: str, message: str):
        """Setup the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        # Icon and title
        header_layout = QHBoxLayout()
        
        icon_label = QLabel("❌")
        icon_font = QFont()
        icon_font.setPointSize(32)
        icon_label.setFont(icon_font)
        header_layout.addWidget(icon_label)
        
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #f23f42;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Message
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("color: #e4e4e7; font-size: 13px;")
        layout.addWidget(message_label)
        
        # Error details (collapsible)
        if self.error_details:
            details_frame = QFrame()
            details_frame.setStyleSheet("""
                QFrame {
                    background-color: #1e1f22;
                    border: 1px solid #2b2d31;
                    border-radius: 4px;
                }
            """)
            details_layout = QVBoxLayout(details_frame)
            details_layout.setContentsMargins(12, 12, 12, 12)
            
            details_label = QLabel("Error Details:")
            details_label.setStyleSheet("color: #b5bac1; font-weight: 500; font-size: 12px;")
            details_layout.addWidget(details_label)
            
            self.details_text = QTextEdit()
            self.details_text.setPlainText(self.error_details)
            self.details_text.setReadOnly(True)
            self.details_text.setMaximumHeight(120)
            self.details_text.setStyleSheet("""
                QTextEdit {
                    background-color: #0d0e10;
                    color: #949ba4;
                    border: none;
                    font-family: monospace;
                    font-size: 11px;
                }
            """)
            details_layout.addWidget(self.details_text)
            
            layout.addWidget(details_frame)
        
        # Retry status
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #b5bac1; font-size: 12px;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)
        
        # Progress bar (for retry operations)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #2b2d31;
                border-radius: 4px;
                background-color: #1e1f22;
                text-align: center;
                color: #b5bac1;
            }
            QProgressBar::chunk {
                background-color: #5865f2;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        
        # Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        
        buttons_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedWidth(100)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b2d31;
                color: #b5bac1;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3f4147;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)
        
        if self.retry_callback:
            self.retry_btn = QPushButton(f"🔄 Retry")
            self.retry_btn.setFixedWidth(120)
            self.retry_btn.setStyleSheet("""
                QPushButton {
                    background-color: #5865f2;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #4752c4;
                }
                QPushButton:disabled {
                    background-color: #3f4147;
                    color: #949ba4;
                }
            """)
            self.retry_btn.clicked.connect(self.do_retry)
            buttons_layout.addWidget(self.retry_btn)
        else:
            ok_btn = QPushButton("OK")
            ok_btn.setFixedWidth(100)
            ok_btn.setStyleSheet("""
                QPushButton {
                    background-color: #5865f2;
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #4752c4;
                }
            """)
            ok_btn.clicked.connect(self.accept)
            buttons_layout.addWidget(ok_btn)
        
        layout.addLayout(buttons_layout)
    
    def do_retry(self):
        """Execute retry callback."""
        if not self.retry_callback:
            return
        
        self.retry_count += 1
        
        if self.retry_count > self.max_retries:
            self.status_label.setText(f"❌ Maximum retry attempts ({self.max_retries}) exceeded")
            self.status_label.setStyleSheet("color: #f23f42; font-size: 12px;")
            self.status_label.setVisible(True)
            self.retry_btn.setEnabled(False)
            return
        
        # Show progress
        self.status_label.setText(f"Retrying... (Attempt {self.retry_count}/{self.max_retries})")
        self.status_label.setStyleSheet("color: #f0b232; font-size: 12px;")
        self.status_label.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.retry_btn.setEnabled(False)
        
        try:
            # Execute callback
            result = self.retry_callback()
            
            # Check result
            if result:
                self.status_label.setText("✅ Operation succeeded!")
                self.status_label.setStyleSheet("color: #23a55a; font-size: 12px;")
                self.progress_bar.setVisible(False)
                
                # Close dialog after success
                QTimer.singleShot(1500, self.accept)
            else:
                self.status_label.setText(f"❌ Retry {self.retry_count} failed")
                self.status_label.setStyleSheet("color: #f23f42; font-size: 12px;")
                self.progress_bar.setVisible(False)
                self.retry_btn.setEnabled(True)
                
        except Exception as e:
            logger.error(f"Retry failed: {e}")
            self.status_label.setText(f"❌ Retry {self.retry_count} failed: {str(e)[:50]}")
            self.status_label.setStyleSheet("color: #f23f42; font-size: 12px;")
            self.progress_bar.setVisible(False)
            self.retry_btn.setEnabled(True)
            
            # Update error details
            if self.error_details and hasattr(self, 'details_text'):
                self.details_text.append(f"\n\n--- Retry {self.retry_count} Error ---\n{str(e)}")


def show_error_with_retry(
    parent,
    title: str,
    message: str,
    error_details: str = "",
    retry_callback: Optional[Callable] = None,
    max_retries: int = 3
) -> bool:
    """
    Show error dialog with retry option.
    
    Args:
        parent: Parent widget
        title: Dialog title
        message: Error message
        error_details: Detailed error information
        retry_callback: Function to call on retry (should return True on success)
        max_retries: Maximum retry attempts
        
    Returns:
        True if operation succeeded (via retry), False otherwise
    """
    dialog = RetryDialog(
        parent=parent,
        title=title,
        message=message,
        error_details=error_details,
        retry_callback=retry_callback,
        max_retries=max_retries
    )
    
    result = dialog.exec()
    return result == QDialog.DialogCode.Accepted






