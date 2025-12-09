"""Pytest configuration and fixtures for GUI tests."""

import os
import sys
from typing import Generator

import pytest

# Ensure Qt uses an offscreen platform by default to reduce GUI requirements.
# This must be set before any Qt imports.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Disable Qt plugin paths to avoid issues in CI
os.environ.setdefault("QT_PLUGIN_PATH", "")
# Prevent Qt from trying to connect to X server
os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", "")


# Create QApplication early to avoid issues during test collection
_qt_app = None


def _ensure_qapplication():
    """Ensure QApplication exists before tests run."""
    global _qt_app
    if _qt_app is None:
        try:
            from PyQt6.QtWidgets import QApplication

            # Get or create QApplication instance
            _qt_app = QApplication.instance()
            if _qt_app is None:
                # Create with minimal arguments for headless operation
                _qt_app = QApplication(sys.argv if sys.argv else ["pytest"])
                # Process events to complete initialization
                _qt_app.processEvents()
        except ImportError:
            pass  # PyQt6 not available
        except Exception:
            pass  # Ignore initialization errors
    return _qt_app


def pytest_configure(config):
    """Called after command line options have been parsed and all plugins initialized.

    This ensures QApplication is created very early, before any test collection or imports.
    """
    # Ensure QApplication exists before any test files are imported
    _ensure_qapplication()


@pytest.fixture(scope="session", autouse=True)
def qapplication() -> Generator:
    """Create a QApplication instance for the entire test session.

    This fixture ensures a single QApplication instance is created and properly
    cleaned up. It works in both headless (CI) and GUI environments.
    The autouse=True ensures it's created before any tests run.
    """
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        # If PyQt6 is not available, skip silently - some tests don't need it
        yield None
        return

    # Ensure QApplication exists
    app = _ensure_qapplication()
    if app is None:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv if sys.argv else ["pytest"])

    # Process any pending events to ensure initialization is complete
    app.processEvents()

    yield app

    # Cleanup: close all windows and process final events
    try:
        # Close all top-level widgets
        for widget in app.allWidgets():
            if widget.isWindow() and widget.isVisible():
                widget.close()
        app.processEvents()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture(scope="function")
def qapp(qapplication) -> Generator:
    """Provide QApplication instance for individual test functions.

    This is a function-scoped fixture that ensures the QApplication is
    available and processes events between tests.
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = qapplication
        if app is None:
            # Fallback: create if still None
            app = QApplication(sys.argv if sys.argv else ["pytest"])

    # Process any pending events
    app.processEvents()

    yield app

    # Process events after test to ensure cleanup
    app.processEvents()
