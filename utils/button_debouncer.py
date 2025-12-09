#!/usr/bin/env python3
"""Button debouncer to prevent double-clicks and duplicate submissions."""

import time
import logging
from typing import Dict, Callable, Any
from functools import wraps
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import QTimer

logger = logging.getLogger(__name__)


class ButtonDebouncer:
    """Prevents double-clicks on buttons."""

    def __init__(self, debounce_ms: int = 1000):
        """
        Initialize button debouncer.

        Args:
            debounce_ms: Minimum time between clicks in milliseconds
        """
        self.debounce_ms = debounce_ms
        self.last_click_times: Dict[int, float] = {}

    def debounce_click(self, button: QPushButton, callback: Callable, *args, **kwargs):
        """
        Execute callback only if enough time has passed since last click.

        Args:
            button: QPushButton instance
            callback: Function to call
            *args, **kwargs: Arguments for callback
        """
        button_id = id(button)
        current_time = time.time() * 1000  # Convert to ms

        # Check if button was recently clicked
        if button_id in self.last_click_times:
            time_since_last = current_time - self.last_click_times[button_id]
            if time_since_last < self.debounce_ms:
                logger.debug(
                    f"Button click ignored (debounced): {time_since_last:.0f}ms since last click"
                )
                return

        # Update last click time
        self.last_click_times[button_id] = current_time

        # Disable button temporarily
        button.setEnabled(False)

        # Execute callback
        try:
            result = callback(*args, **kwargs)
        finally:
            # Re-enable button after debounce period
            QTimer.singleShot(self.debounce_ms, lambda: button.setEnabled(True))

        return result

    def create_debounced_handler(self, button: QPushButton, callback: Callable) -> Callable:
        """
        Create a debounced click handler for a button.

        Args:
            button: QPushButton instance
            callback: Original callback function

        Returns:
            Debounced callback function
        """

        @wraps(callback)
        def debounced_callback(*args, **kwargs):
            return self.debounce_click(button, callback, *args, **kwargs)

        return debounced_callback


def debounce_button(debounce_ms: int = 1000):
    """
    Decorator to debounce button click handlers.

    Usage:
        @debounce_button(1000)
        def on_create_clicked(self):
            # This will only execute once per second max
            self.create_accounts()
    """

    def decorator(func: Callable) -> Callable:
        last_call_time = [0]  # Use list for mutability in closure

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            current_time = time.time() * 1000

            if current_time - last_call_time[0] < debounce_ms:
                logger.debug(f"Function {func.__name__} debounced")
                return None

            last_call_time[0] = current_time
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


# Global button debouncer instance
_button_debouncer = ButtonDebouncer(debounce_ms=1000)


def get_button_debouncer(debounce_ms: int = 1000) -> ButtonDebouncer:
    """Get the global button debouncer."""
    global _button_debouncer
    if _button_debouncer.debounce_ms != debounce_ms:
        _button_debouncer = ButtonDebouncer(debounce_ms=debounce_ms)
    return _button_debouncer


def protect_button(button: QPushButton, callback: Callable, debounce_ms: int = 1000):
    """
    Protect a button from double-clicks.

    Usage:
        from utils.button_debouncer import protect_button

        create_btn = QPushButton("Create")
        protect_button(create_btn, self.create_accounts, debounce_ms=2000)
    """
    debouncer = get_button_debouncer(debounce_ms)
    protected_callback = debouncer.create_debounced_handler(button, callback)
    button.clicked.connect(protected_callback)
