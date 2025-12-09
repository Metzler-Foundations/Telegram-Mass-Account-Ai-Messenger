"""Pytest configuration and fixtures for GUI tests."""

import os
from typing import Generator

import pytest

# Ensure Qt uses an offscreen platform by default to reduce GUI requirements.
# This must be set before any Qt imports.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# Disable Qt plugin paths to avoid issues in CI
os.environ.setdefault("QT_PLUGIN_PATH", "")
# Prevent Qt from trying to connect to X server
os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", "")

# Create QApplication at module level - this runs BEFORE any test files are imported
# This is critical to prevent hangs during test collection
_qt_app = None
try:
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QEventLoop

    # Get or create QApplication instance immediately
    _qt_app = QApplication.instance()
    if _qt_app is None:
        # Create with minimal arguments for headless operation
        # Use empty list to avoid issues with sys.argv in CI
        _qt_app = QApplication([])
        # DO NOT process events at module level - can cause hangs in CI
except ImportError:
    # PyQt6 not available - some tests don't need it
    pass
except Exception:
    # Ignore initialization errors - will be handled in fixtures
    pass


def _safe_process_events(app, max_events=5):
    """Safely process Qt events with a limit to prevent blocking.
    
    In headless/CI environments, processEvents() can block indefinitely.
    This function processes a limited number of events to avoid hangs.
    """
    if app is None:
        return
    try:
        from PyQt6.QtCore import QEventLoop
        # In headless/CI mode, minimize event processing to avoid hangs
        # Only process if there are actually pending events
        if not app.hasPendingEvents():
            return
        
        # Process only a very limited number of events to prevent blocking
        # Use AllEvents flag - in PyQt6, processEvents() without timeout
        # can block, so we limit iterations strictly
        iterations = 0
        while iterations < max_events and app.hasPendingEvents():
            # Process events with AllEvents flag
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents)
            iterations += 1
            # Double-check to break early if no more events
            if not app.hasPendingEvents():
                break
    except Exception:
        pass  # Ignore all errors during event processing - better to skip than hang


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
                _qt_app = QApplication([])
                # DO NOT process events here - can cause hangs
        except ImportError:
            pass  # PyQt6 not available
        except Exception:
            pass  # Ignore initialization errors
    return _qt_app


def pytest_load_initial_conftests(early_config, parser, args):
    """Called very early, before test collection starts.

    This is the earliest hook available - ensures QApplication exists
    before ANY test files are imported.
    """
    # Ensure QApplication exists before any test files are imported
    _ensure_qapplication()


def pytest_configure(config):
    """Called after command line options have been parsed and all plugins initialized.

    This ensures QApplication is created very early, before any test collection or imports.
    """
    # Ensure QApplication exists before any test files are imported
    _ensure_qapplication()


def pytest_sessionstart(session):
    """Called after test collection is complete but before tests run.

    This ensures QApplication is ready before any tests execute.
    """
    # Ensure QApplication exists and is ready
    app = _ensure_qapplication()
    if app is not None:
        # Minimize event processing to avoid blocking in CI
        _safe_process_events(app, max_events=2)


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
            app = QApplication([])

    # Minimize event processing in headless mode to avoid hangs
    # Only process if absolutely necessary
    _safe_process_events(app, max_events=2)

    yield app

    # Cleanup: close all windows and process final events
    try:
        # Close all top-level widgets
        for widget in app.allWidgets():
            if widget.isWindow() and widget.isVisible():
                widget.close()
        # Minimize cleanup event processing to avoid hangs
        _safe_process_events(app, max_events=2)
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
            app = QApplication([])

    # Minimize event processing before test to avoid hangs
    _safe_process_events(app, max_events=1)

    yield app

    # Minimize event processing after test to avoid hangs
    _safe_process_events(app, max_events=1)
