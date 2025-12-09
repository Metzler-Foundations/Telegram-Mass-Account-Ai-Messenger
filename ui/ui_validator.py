#!/usr/bin/env python3
"""UI input validation before backend submission."""

import logging
from typing import Optional, Callable
from PyQt6.QtWidgets import QPushButton, QLineEdit, QTextEdit

logger = logging.getLogger(__name__)


class UIValidator:
    """Validates UI inputs before backend processing."""

    @staticmethod
    def validate_button_click(
        button: QPushButton, validation_func: Callable, error_callback: Optional[Callable] = None
    ) -> bool:
        """Validate before executing button click."""
        try:
            # Disable button during validation
            button.setEnabled(False)

            # Run validation
            valid, error_msg = validation_func()

            if not valid:
                logger.warning(f"Validation failed: {error_msg}")
                if error_callback:
                    error_callback(error_msg)
                return False

            return True

        except Exception as e:
            logger.error(f"Validation error: {e}")
            if error_callback:
                error_callback(str(e))
            return False
        finally:
            button.setEnabled(True)

    @staticmethod
    def validate_text_input(widget, validator_func) -> tuple:
        """Validate text input widget."""
        text = widget.text() if isinstance(widget, QLineEdit) else widget.toPlainText()

        try:
            return validator_func(text)
        except Exception as e:
            return False, str(e)

    @staticmethod
    def set_input_error(widget, error_msg: str):
        """Mark input widget with error."""
        widget.setStyleSheet("border: 2px solid red;")
        widget.setToolTip(error_msg)

    @staticmethod
    def clear_input_error(widget):
        """Clear error from input widget."""
        widget.setStyleSheet("")
        widget.setToolTip("")


def validate_before_submit(validation_func):
    """Decorator for UI validation before submission."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            valid, msg = validation_func()
            if not valid:
                logger.warning(f"Pre-submit validation failed: {msg}")
                return None
            return func(*args, **kwargs)

        return wrapper

    return decorator
