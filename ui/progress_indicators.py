#!/usr/bin/env python3
"""UI progress indicators - Prevent freezing during long operations."""

import logging

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QProgressDialog

logger = logging.getLogger(__name__)


class ProgressWorker(QThread):
    """Worker thread for long-running operations."""

    progress = pyqtSignal(int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, func, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """Run operation in background thread."""
        try:
            result = self.func(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            logger.error(f"Background operation failed: {e}")
            self.error.emit(str(e))


class ProgressIndicator:
    """Shows progress for long operations."""

    @staticmethod
    def show_progress(parent, title: str, message: str, func, *args, **kwargs):
        """Execute function with progress dialog."""
        progress = QProgressDialog(message, "Cancel", 0, 0, parent)
        progress.setWindowTitle(title)
        progress.setModal(True)
        progress.show()

        worker = ProgressWorker(func, *args, **kwargs)
        worker.finished.connect(lambda: progress.close())
        worker.error.connect(lambda e: progress.close())
        worker.start()

        return worker


def run_with_progress(parent, title, message, func, *args, **kwargs):
    """Helper to run function with progress indicator."""
    return ProgressIndicator.show_progress(parent, title, message, func, *args, **kwargs)
