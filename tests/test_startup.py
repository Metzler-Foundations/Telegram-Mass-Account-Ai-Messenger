#!/usr/bin/env python3
"""
Test script to check application startup and catch import errors
"""

import os
import sys
import traceback

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_startup(qapp):
    """Test application startup step by step"""
    print("🔍 Testing application startup...")

    try:
        print("1. Testing basic Python imports...")
        import asyncio  # noqa: F401
        import logging  # noqa: F401
        import random  # noqa: F401
        import time  # noqa: F401
        from collections import defaultdict  # noqa: F401
        from pathlib import Path  # noqa: F401
        from typing import Any, Dict, List, Optional  # noqa: F401

        print("✅ Basic Python imports OK")

        print("2. Testing PyQt6 imports...")
        from PyQt6.QtCore import QObject, Qt, QThread, QTimer, pyqtSignal  # noqa: F401
        from PyQt6.QtGui import QAction, QFont, QIcon, QTextCursor  # noqa: F401
        from PyQt6.QtWidgets import (  # noqa: F401
            QApplication,
            QComboBox,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QListWidget,
            QListWidgetItem,
            QMainWindow,
            QMenu,
            QMessageBox,
            QProgressBar,
            QPushButton,
            QSplitter,
            QStatusBar,
            QSystemTrayIcon,
            QTextEdit,
            QVBoxLayout,
            QWidget,
        )

        print("✅ PyQt6 imports OK")

        print("3. Testing application modules...")
        from accounts.account_creator import AccountCreator  # noqa: F401
        from ai.gemini_service import GeminiService  # noqa: F401
        from anti_detection.anti_detection_system import AntiDetectionSystem  # noqa: F401
        from scraping.member_scraper import MemberDatabase, MemberScraper  # noqa: F401
        from telegram.telegram_client import TelegramClient  # noqa: F401

        print("✅ Application modules OK")

        print("4. Testing main window creation...")
        from main import MainWindow

        # Try to create main window
        MainWindow()
        print("✅ Main window created successfully")

        # Try to create settings window
        from ui.settings_window import SettingsWindow

        SettingsWindow()
        print("✅ Settings window created successfully")

        print("\n🎉 All startup tests passed!")
        return True

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"❌ Startup Error: {e}")
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_startup()
    sys.exit(0 if success else 1)
