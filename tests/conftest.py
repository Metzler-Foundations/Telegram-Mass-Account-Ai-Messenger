"""Pytest configuration to guard GUI tests when system dependencies are missing."""

import ctypes.util
import os
from pathlib import Path

import pytest

# Tests that exercise the PyQt-based UI; these import Qt modules and will fail
# when the system lacks OpenGL libraries (e.g., libGL.so.1 in headless CI).
GUI_TEST_FILES = {
    "test_app.py",
    "test_wizard.py",
    "test_proxy_performance.py",
    "test_system.py",
}


def _has_libgl() -> bool:
    """Return True if libGL is available on the system."""
    return ctypes.util.find_library("GL") is not None


# Ensure Qt uses an offscreen platform by default to reduce GUI requirements.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def pytest_ignore_collect(collection_path: Path, config):
    """Prevent importing GUI-heavy test modules when libGL is unavailable."""
    if _has_libgl():
        return False

    filename = Path(collection_path).name
    return filename in GUI_TEST_FILES


def pytest_collection_modifyitems(config, items):
    """Skip GUI-heavy tests when libGL is missing so the suite can run headless."""
    if _has_libgl():
        return

    skip_gui = pytest.mark.skip(reason="libGL.so.1 not available; skipping GUI-dependent tests")
    for item in items:
        filename = Path(str(item.fspath)).name
        if filename in GUI_TEST_FILES:
            item.add_marker(skip_gui)
