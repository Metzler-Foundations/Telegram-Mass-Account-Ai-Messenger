#!/usr/bin/env python3
"""
Test script to check application startup and catch import errors
"""

import sys
import os
import traceback

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_startup(qapp):
    """Test application startup step by step"""
    print("🔍 Testing application startup...")

    try:
        print("1. Testing basic Python imports...")
        import asyncio
        import logging
        import time
        import random
        from typing import Optional, Dict, Any, List
        from pathlib import Path
        from collections import defaultdict

        print("✅ Basic Python imports OK")

        print("2. Testing PyQt6 imports...")
        from PyQt6.QtWidgets import (
            QApplication,
            QMainWindow,
            QWidget,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QPushButton,
            QTextEdit,
            QStatusBar,
            QSplitter,
            QListWidget,
            QListWidgetItem,
            QMessageBox,
            QSystemTrayIcon,
            QMenu,
            QProgressBar,
            QComboBox,
            QGroupBox,
        )
        from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread, QObject
        from PyQt6.QtGui import QTextCursor
        from PyQt6.QtGui import QIcon, QFont, QAction

        print("✅ PyQt6 imports OK")

        print("3. Testing application modules...")
        from telegram.telegram_client import TelegramClient
        from ai.gemini_service import GeminiService
        from scraping.member_scraper import MemberScraper, MemberDatabase
        from accounts.account_creator import AccountCreator
        from anti_detection.anti_detection_system import AntiDetectionSystem

        print("✅ Application modules OK")

        print("4. Testing main window creation...")
        from main import MainWindow

        # Try to create main window
        main_window = MainWindow()
        print("✅ Main window created successfully")

        # Try to create settings window
        from ui.settings_window import SettingsWindow

        settings_window = SettingsWindow()
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
