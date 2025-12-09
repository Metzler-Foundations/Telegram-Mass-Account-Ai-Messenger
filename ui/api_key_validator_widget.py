"""
API Key Validator Widget - Inline validation for API keys in settings.

Features:
- Real-time API key validation
- Inline error/success messages
- Visual feedback (green checkmark, red X)
- Async validation without blocking UI
- Validation caching
"""

import logging
import asyncio
from typing import Optional
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)

# Try to import API key manager
try:
    from integrations.api_key_manager import APIKeyManager
    API_KEY_MANAGER_AVAILABLE = True
except ImportError:
    API_KEY_MANAGER_AVAILABLE = False
    logger.warning("APIKeyManager not available")


class ValidationThread(QThread):
    """Thread for async API key validation."""
    
    validation_complete = pyqtSignal(bool, str)  # (success, message)
    
    def __init__(self, api_key_manager, service: str, api_key: str, parent=None):
        super().__init__(parent)
        self.api_key_manager = api_key_manager
        self.service = service
        self.api_key = api_key
    
    def run(self):
        """Run validation in background."""
        try:
            # Run async validation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Save key first
            self.api_key_manager.add_api_key(self.service, self.api_key)
            
            # Validate
            is_valid, message = loop.run_until_complete(
                self.api_key_manager.validate_api_key(self.service, force=True)
            )
            
            loop.close()
            
            self.validation_complete.emit(is_valid, message)
            
        except Exception as e:
            logger.error(f"Validation thread error: {e}")
            self.validation_complete.emit(False, f"Validation error: {str(e)[:100]}")


class APIKeyValidatorWidget(QWidget):
    """Widget for API key input with inline validation."""
    
    validation_changed = pyqtSignal(bool)  # Emits True if valid, False if invalid
    
    def __init__(self, service_name: str, label_text: str, placeholder: str = "", parent=None):
        super().__init__(parent)
        self.service_name = service_name
        self.api_key_manager: Optional[APIKeyManager] = None
        self.validation_thread: Optional[ValidationThread] = None
        self._is_valid = False
        
        self.setup_ui(label_text, placeholder)
        
        # Initialize API key manager
        if API_KEY_MANAGER_AVAILABLE:
            try:
                self.api_key_manager = APIKeyManager()
                self._load_existing_key()
            except Exception as e:
                logger.error(f"Failed to initialize API key manager: {e}")
    
    def setup_ui(self, label_text: str, placeholder: str):
        """Setup the UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Label
        label = QLabel(label_text)
        label.setMinimumWidth(150)
        layout.addWidget(label)
        
        # Input field
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.setEchoMode(QLineEdit.EchoMode.Password)
        self.input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.input)
        
        # Show/hide button
        self.show_btn = QPushButton("👁")
        self.show_btn.setMaximumWidth(40)
        self.show_btn.setCheckable(True)
        self.show_btn.toggled.connect(self._toggle_visibility)
        layout.addWidget(self.show_btn)
        
        # Validate button
        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self.validate_key)
        layout.addWidget(self.validate_btn)
        
        # Status indicator
        self.status_label = QLabel("")
        self.status_label.setMinimumWidth(30)
        layout.addWidget(self.status_label)
        
        # Error message
        from ui.theme_manager import ThemeManager
        c = ThemeManager.get_colors()
        self.error_label = QLabel("")
        self.error_label.setStyleSheet(f"color: {c['ACCENT_DANGER']}; font-size: 10px;")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)
    
    def _load_existing_key(self):
        """Load existing API key if available."""
        if not self.api_key_manager:
            return
        
        try:
            key_data = self.api_key_manager.get_api_key(self.service_name)
            if key_data:
                self.input.setText(key_data.get('key', ''))
                # Check validation cache
                if self.api_key_manager.key_validation_cache.get(self.service_name, {}).get('valid'):
                    self._show_success("Previously validated")
        except Exception as e:
            logger.debug(f"Could not load existing key: {e}")
    
    def _on_text_changed(self, text: str):
        """Handle text changes."""
        # Clear validation state when text changes
        self._clear_validation_state()
    
    def _toggle_visibility(self, checked: bool):
        """Toggle key visibility."""
        if checked:
            self.input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_btn.setText("🙈")
        else:
            self.input.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_btn.setText("👁")
    
    def validate_key(self):
        """Validate the API key."""
        api_key = self.input.text().strip()
        
        if not api_key:
            self._show_error("API key is required")
            return
        
        if not self.api_key_manager:
            self._show_error("API key manager not available")
            return
        
        # Basic format validation
        if len(api_key) < 10:
            self._show_error("API key seems too short (minimum 10 characters)")
            return
        
        # Show validating state
        self.status_label.setText("Validating...")
        from ui.theme_manager import ThemeManager
        c = ThemeManager.get_colors()
        self.status_label.setStyleSheet(f"color: {c['ACCENT_WARNING']};")
        self.validate_btn.setEnabled(False)
        self.validate_btn.setText("Validating...")
        self.error_label.setVisible(False)
        
        # Start validation in background thread
        self.validation_thread = ValidationThread(
            self.api_key_manager,
            self.service_name,
            api_key,
            self
        )
        self.validation_thread.validation_complete.connect(self._on_validation_complete)
        self.validation_thread.start()
    
    def _on_validation_complete(self, is_valid: bool, message: str):
        """Handle validation result."""
        self.validate_btn.setEnabled(True)
        self.validate_btn.setText("Validate")
        
        if is_valid:
            self._show_success(message)
        else:
            self._show_error(message)
    
    def _show_success(self, message: str = "Valid"):
        """Show success state."""
        self._is_valid = True
        self.status_label.setText("✓")
        from ui.theme_manager import ThemeManager
        c = ThemeManager.get_colors()
        self.status_label.setStyleSheet(f"color: {c['ACCENT_SUCCESS']};")
        self.error_label.setText(f"✓ {message}")
        self.error_label.setStyleSheet(f"color: {c['ACCENT_SUCCESS']}; font-size: 10px;")
        self.error_label.setVisible(True)
        self.validation_changed.emit(True)
    
    def _show_error(self, message: str):
        """Show error state."""
        self._is_valid = False
        self.status_label.setText("✗")
        from ui.theme_manager import ThemeManager
        c = ThemeManager.get_colors()
        self.status_label.setStyleSheet(f"color: {c['ACCENT_DANGER']};")
        self.error_label.setText(f"✗ {message}")
        self.error_label.setStyleSheet(f"color: {c['ACCENT_DANGER']}; font-size: 10px;")
        self.error_label.setVisible(True)
        self.validation_changed.emit(False)
    
    def _clear_validation_state(self):
        """Clear validation indicators."""
        self._is_valid = False
        self.status_label.setText("")
        self.error_label.setVisible(False)
    
    def is_valid(self) -> bool:
        """Check if current API key is valid."""
        return self._is_valid
    
    def get_api_key(self) -> str:
        """Get the current API key value."""
        return self.input.text().strip()








