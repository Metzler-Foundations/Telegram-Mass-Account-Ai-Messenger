"""
Error Handler - User-friendly error messages with actionable guidance.
"""
import logging
from typing import Dict, Any, Optional
from PyQt6.QtWidgets import (
    QMessageBox, QWidget, QDialog, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QApplication
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Handles user-friendly error messages with actionable guidance."""

    # Error message templates with user-friendly explanations and solutions
    ERROR_MESSAGES = {
        # API and Authentication Errors
        "telegram_api_invalid": {
            "title": "Telegram API Configuration Error",
            "message": "Your Telegram API credentials are invalid or incomplete.",
            "solutions": [
                "1. Visit https://my.telegram.org/apps to get your API credentials",
                "2. Create a new application if you haven't already",
                "3. Copy the API ID and API Hash exactly as shown",
                "4. Make sure your phone number includes the country code (+1, +44, etc.)"
            ]
        },

        "telegram_connection_failed": {
            "title": "Telegram Connection Failed",
            "message": "Unable to connect to Telegram servers.",
            "solutions": [
                "1. Check your internet connection",
                "2. Verify your API credentials are correct",
                "3. Try using a VPN if you're in a restricted region",
                "4. Wait a few minutes and try again - Telegram may be having issues",
                "5. Check if your account is banned or restricted"
            ]
        },

        "gemini_api_error": {
            "title": "AI Service Error",
            "message": "The AI service (Gemini) is not responding properly.",
            "solutions": [
                "1. Check your Gemini API key in Settings → API & Auth",
                "2. Visit https://makersuite.google.com/app/apikey to verify your key",
                "3. Ensure your API key has sufficient credits/quota",
                "4. Try again later - the service may be temporarily unavailable",
                "5. Consider using a different AI model if available"
            ]
        },

        # Database Errors
        "database_connection_failed": {
            "title": "Database Connection Error",
            "message": "Cannot connect to the application database.",
            "solutions": [
                "1. Ensure the database file isn't corrupted",
                "2. Check if another instance of the application is running",
                "3. Try restarting the application",
                "4. If the problem persists, restore from a backup",
                "5. Contact support if you see this error repeatedly"
            ]
        },

        "database_corruption": {
            "title": "Database Corruption Detected",
            "message": "The application database appears to be corrupted.",
            "solutions": [
                "1. The application will automatically create backups before migrations",
                "2. Check the 'backups' folder for recent database backups",
                "3. Restore from the most recent backup file",
                "4. If no backups exist, you may need to start fresh",
                "5. Contact support for help recovering your data"
            ]
        },

        # Campaign Errors
        "campaign_target_limit": {
            "title": "Campaign Size Limit Exceeded",
            "message": "Your campaign is too large to process efficiently.",
            "solutions": [
                "1. Split large campaigns into smaller ones (max 10,000 targets each)",
                "2. Focus on high-quality targets rather than quantity",
                "3. Use member filtering to target specific user segments",
                "4. Consider running campaigns during off-peak hours",
                "5. Monitor campaign performance and adjust targeting"
            ]
        },

        "campaign_rate_limit": {
            "title": "Rate Limit Exceeded",
            "message": "You're sending messages too quickly and hitting rate limits.",
            "solutions": [
                "1. Increase delays between messages in Settings → Anti-Detection",
                "2. Reduce the number of concurrent accounts",
                "3. Use more accounts to distribute the load",
                "4. Enable random delays and human-like behavior",
                "5. Wait before resuming - rate limits usually reset within minutes"
            ]
        },

        # Member Scraping Errors
        "channel_access_denied": {
            "title": "Channel Access Denied",
            "message": "Cannot access the specified Telegram channel or group.",
            "solutions": [
                "1. Verify the channel/group exists and is public",
                "2. Check if your account is banned from the channel",
                "3. Join the channel manually first, then try scraping",
                "4. Use a different account that has access",
                "5. Some channels require special permissions or invitations"
            ]
        },

        "scraping_rate_limit": {
            "title": "Scraping Rate Limited",
            "message": "Member scraping is being rate limited by Telegram.",
            "solutions": [
                "1. Increase delays between scraping operations",
                "2. Use multiple accounts to distribute requests",
                "3. Scrape during off-peak hours (night time in target region)",
                "4. Enable anti-detection features in settings",
                "5. Consider purchasing premium accounts for better limits"
            ]
        },

        # System Errors
        "memory_limit_exceeded": {
            "title": "Memory Limit Exceeded",
            "message": "The application is using too much memory.",
            "solutions": [
                "1. Close other applications to free up memory",
                "2. Reduce campaign sizes or member scraping scope",
                "3. Restart the application to clear memory",
                "4. Consider using a machine with more RAM",
                "5. Monitor memory usage in the Health tab"
            ]
        },

        "disk_space_low": {
            "title": "Low Disk Space",
            "message": "Your disk is running low on space.",
            "solutions": [
                "1. Free up disk space by deleting unnecessary files",
                "2. Move the application to a drive with more space",
                "3. Clear temporary files and caches",
                "4. Consider archiving old data or logs",
                "5. Monitor disk usage regularly"
            ]
        },

        # Configuration Errors
        "invalid_proxy": {
            "title": "Invalid Proxy Configuration",
            "message": "The proxy settings are incorrect or the proxy is not working.",
            "solutions": [
                "1. Verify proxy IP address and port are correct",
                "2. Check proxy username/password if authentication is required",
                "3. Test the proxy in the Proxy Pool tab",
                "4. Try a different proxy from the pool",
                "5. Ensure the proxy supports SOCKS5 protocol"
            ]
        },

        "network_connectivity": {
            "title": "Network Connectivity Issues",
            "message": "Cannot establish network connections.",
            "solutions": [
                "1. Check your internet connection",
                "2. Try disabling VPN or proxy temporarily",
                "3. Restart your router/modem",
                "4. Check if Telegram is blocked in your region",
                "5. Try using a different network (mobile hotspot, etc.)"
            ]
        },

        "general_error": {
            "title": "Unexpected Error",
            "message": "An unexpected error occurred during operation.",
            "solutions": [
                "1. Try the operation again in a few moments",
                "2. Check the application logs for more details",
                "3. Restart the application if the error persists",
                "4. Make sure all required services are running",
                "5. Contact support if the problem continues"
            ]
        }
    }

    @staticmethod
    def show_error(parent: Optional[QWidget], error_type: str, details: str = ""):
        """Show a user-friendly error dialog with actionable guidance and copyable text."""
        if error_type not in ErrorHandler.ERROR_MESSAGES:
            error_info = {
                "title": "Error",
                "message": f"An unexpected error occurred: {details}",
                "solutions": ["Please check the logs for more details or contact support."]
            }
        else:
            error_info = ErrorHandler.ERROR_MESSAGES[error_type]

        # Create custom dialog with copyable text
        dialog = QDialog(parent)
        dialog.setWindowTitle(error_info["title"])
        dialog.setMinimumWidth(500)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(12)
        
        # Error icon and title
        title_label = QLabel(f"❌ {error_info['title']}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ed4245;")
        layout.addWidget(title_label)
        
        # Message (copyable text area)
        message = error_info["message"]
        if details:
            message += f"\n\nTechnical details:\n{details}"
        
        message += "\n\n💡 Suggested solutions:"
        for solution in error_info["solutions"]:
            message += f"\n• {solution}"
        
        text_area = QTextEdit()
        text_area.setPlainText(message)
        text_area.setReadOnly(True)
        text_area.setMinimumHeight(200)
        text_area.setStyleSheet("""
            QTextEdit {
                background-color: #2b2d31;
                border: 1px solid #3f4147;
                border-radius: 6px;
                padding: 10px;
                color: #dbdee1;
            }
        """)
        layout.addWidget(text_area)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        copy_btn = QPushButton("📋 Copy to Clipboard")
        copy_btn.clicked.connect(lambda: ErrorHandler._copy_to_clipboard(message))
        button_layout.addWidget(copy_btn)
        
        button_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        
        dialog.exec()
    
    @staticmethod
    def _copy_to_clipboard(text: str):
        """Copy text to clipboard."""
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(text)
            # Brief visual feedback would be nice but keeping it simple

    @staticmethod
    def show_success(parent: Optional[QWidget], title: str, message: str):
        """Show a success message with positive reinforcement."""
        ErrorHandler.safe_message_box(parent, QMessageBox.Icon.Information, title, message)

    @staticmethod
    def show_confirmation(parent: Optional[QWidget], title: str, message: str) -> bool:
        """Show a confirmation dialog and return user's choice."""
        # Create message box without auto-parent binding that can cause app closure
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        # Don't set parent to avoid dialog chain closure issues
        result = msg_box.exec()
        return result == QMessageBox.StandardButton.Yes
    
    @staticmethod
    def safe_message_box(parent: Optional[QWidget], icon: QMessageBox.Icon, title: str, message: str, 
                         buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok) -> QMessageBox.StandardButton:
        """
        Show a message box safely without causing parent dialogs to close.
        
        This method creates a standalone message box that won't trigger
        the closure of parent dialogs when dismissed.
        """
        msg_box = QMessageBox()
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(buttons)
        
        # Set proper window modality to ensure clean event handling
        msg_box.setWindowModality(Qt.WindowModality.ApplicationModal)
        
        # Apply theme styling
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #313338;
                color: #dbdee1;
            }
            QMessageBox QLabel {
                color: #dbdee1;
                font-size: 14px;
            }
            QPushButton {
                background-color: #5865f2;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: 500;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #4752c4;
            }
            QPushButton:pressed {
                background-color: #3c45a5;
            }
        """)
        
        return QMessageBox.StandardButton(msg_box.exec())
    
    @staticmethod
    def safe_warning(parent: Optional[QWidget], title: str, message: str):
        """Show a warning message safely."""
        ErrorHandler.safe_message_box(parent, QMessageBox.Icon.Warning, title, message)
    
    @staticmethod
    def safe_critical(parent: Optional[QWidget], title: str, message: str):
        """Show a critical error message safely."""
        ErrorHandler.safe_message_box(parent, QMessageBox.Icon.Critical, title, message)
    
    @staticmethod
    def safe_information(parent: Optional[QWidget], title: str, message: str):
        """Show an information message safely."""
        ErrorHandler.safe_message_box(parent, QMessageBox.Icon.Information, title, message)
    
    @staticmethod
    def safe_question(parent: Optional[QWidget], title: str, message: str) -> bool:
        """Show a question dialog safely and return user's choice."""
        result = ErrorHandler.safe_message_box(
            parent, 
            QMessageBox.Icon.Question, 
            title, 
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return result == QMessageBox.StandardButton.Yes

    @staticmethod
    def map_exception_to_error_type(exception: Exception) -> str:
        """Map common exceptions to user-friendly error types."""
        exception_str = str(exception).lower()

        # API and authentication errors
        if "api" in exception_str and ("invalid" in exception_str or "wrong" in exception_str):
            return "telegram_api_invalid"
        if "auth" in exception_str or "unauthorized" in exception_str:
            return "telegram_api_invalid"
        if "connection" in exception_str or "network" in exception_str:
            return "network_connectivity"
        if "rate" in exception_str or "flood" in exception_str:
            return "campaign_rate_limit"
        if "channel" in exception_str and ("not found" in exception_str or "access" in exception_str):
            return "channel_access_denied"

        # Database errors
        if "database" in exception_str or "sqlite" in exception_str:
            return "database_connection_failed"

        # Memory/disk errors
        if "memory" in exception_str or "out of memory" in exception_str:
            return "memory_limit_exceeded"
        if "disk" in exception_str or "space" in exception_str:
            return "disk_space_low"

        # Default fallback
        return "general_error"
