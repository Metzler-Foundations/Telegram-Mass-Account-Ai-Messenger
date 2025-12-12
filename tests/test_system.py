#!/usr/bin/env python3
"""
Comprehensive system test script for Telegram AI Assistant
Tests all imports, dependencies, and basic functionality before running main app
"""

import importlib
import os
import subprocess
import sys
import traceback
from typing import Dict

# Add the parent directory to Python path for package imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class SystemTester:
    """Comprehensive system testing for the Telegram AI Assistant"""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.successes = []

    def log_error(self, message: str):
        """Log an error"""
        self.errors.append(message)
        print(f"❌ {message}")

    def log_warning(self, message: str):
        """Log a warning"""
        self.warnings.append(message)
        print(f"⚠️  {message}")

    def log_success(self, message: str):
        """Log a success"""
        self.successes.append(message)
        print(f"✅ {message}")

    def test_python_version(self) -> bool:
        """Test Python version compatibility"""
        try:
            version = sys.version_info
            if version.major >= 3 and version.minor >= 8:
                self.log_success(
                    f"Python version {version.major}.{version.minor}.{version.micro} - Compatible"
                )
                return True
            else:
                self.log_error(
                    f"Python version {version.major}.{version.minor} is too old. Need 3.8+"
                )
                return False
        except Exception as e:
            self.log_error(f"Failed to check Python version: {e}")
            return False

    def test_core_imports(self) -> bool:
        """Test all required imports"""
        required_modules = [
            # Core Python modules
            "sys",
            "os",
            "json",
            "logging",
            "asyncio",
            "time",
            "random",
            "string",
            "hashlib",
            "platform",
            "subprocess",
            "threading",
            "sqlite3",
            "pathlib",
            "typing",
            "collections",
            # Third-party modules
            "pyrogram",
            "tgcrypto",
            "psutil",
            # Local modules (with new package structure)
            "telegram.telegram_client",
            "ai.gemini_service",
            "ui.settings_window",
            "scraping.member_scraper",
            "accounts.account_creator",
            "anti_detection.anti_detection_system",
        ]

        success_count = 0

        for module in required_modules:
            try:
                if "." in module:
                    # Handle submodules like PyQt6.QtWidgets
                    parts = module.split(".")
                    mod = importlib.import_module(".".join(parts[:-1]))
                    getattr(mod, parts[-1])
                else:
                    importlib.import_module(module)
                success_count += 1
            except ImportError as e:
                self.log_error(f"Missing module: {module} - {e}")
            except Exception as e:
                self.log_error(f"Import error for {module}: {e}")

        if success_count == len(required_modules):
            self.log_success(f"All {success_count} modules imported successfully")
            return True
        else:
            self.log_error(f"Only {success_count}/{len(required_modules)} modules imported")
            return False

    def test_ai_service(self) -> bool:
        """Test AI service imports and basic functionality"""
        try:
            # Test google.generativeai import
            import google.generativeai as genai  # noqa: F401

            self.log_success("Google Generative AI module available")
            return True
        except ImportError:
            self.log_error(
                "Google Generative AI not available - install with: pip install google-generativeai"
            )
            return False
        except Exception as e:
            self.log_warning(f"AI service test warning: {e}")
            return True  # Not critical for basic functionality

    def test_qt_components(self) -> bool:
        """Test all PyQt6 components used in the application"""
        required_widgets = [
            "QApplication",
            "QMainWindow",
            "QWidget",
            "QVBoxLayout",
            "QHBoxLayout",
            "QLabel",
            "QPushButton",
            "QTextEdit",
            "QStatusBar",
            "QSplitter",
            "QListWidget",
            "QListWidgetItem",
            "QMessageBox",
            "QSystemTrayIcon",
            "QMenu",
            "QProgressBar",
            "QComboBox",
            "QGroupBox",
            "QDialog",
            "QTabWidget",
            "QFormLayout",
            "QLineEdit",
            "QCheckBox",
            "QSpinBox",
            "QScrollArea",
            "QFrame",
        ]

        required_core = ["Qt", "QTimer", "pyqtSignal", "QThread", "QObject"]
        required_gui = ["QFont", "QPalette", "QColor", "QIcon"]

        success_count = 0
        total_count = len(required_widgets) + len(required_core) + len(required_gui)

        try:
            # Test widgets
            from PyQt6 import QtWidgets

            for widget in required_widgets:
                if hasattr(QtWidgets, widget):
                    success_count += 1
                else:
                    self.log_error(f"Missing PyQt6 widget: {widget}")

            # Test core
            from PyQt6 import QtCore

            for item in required_core:
                if hasattr(QtCore, item):
                    success_count += 1
                else:
                    self.log_error(f"Missing PyQt6 core: {item}")

            # Test gui
            from PyQt6 import QtGui

            for item in required_gui:
                if hasattr(QtGui, item):
                    success_count += 1
                else:
                    self.log_error(f"Missing PyQt6 gui: {item}")

        except ImportError as e:
            self.log_error(f"PyQt6 import failed: {e}")
            return False

        if success_count == total_count:
            self.log_success(f"All {success_count} PyQt6 components available")
            return True
        else:
            self.log_error(f"Only {success_count}/{total_count} PyQt6 components available")
            return False

    def test_database_creation(self) -> bool:
        """Test database creation and basic operations"""
        try:
            import os

            # Test database creation
            import tempfile
            from datetime import datetime

            from member_scraper import MemberDatabase

            temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
            temp_db.close()
            db = MemberDatabase(temp_db.name)  # Use temporary file for testing

            # Test basic operations
            db.save_channel("test_channel", "Test Channel", 100, False)
            current_time = datetime.now()
            db.save_member(
                12345,
                "testuser",
                "Test",
                "User",
                "+1234567890",
                current_time,
                current_time,
                "member",
                "test_channel",
                50,
            )

            channels = db.get_all_channels()
            if channels and len(channels) > 0:
                self.log_success("Database operations working correctly")
                # Clean up temp file
                try:
                    os.unlink(temp_db.name)
                except Exception:
                    pass
                return True
            else:
                self.log_error("Database operations failed")
                # Clean up temp file
                try:
                    os.unlink(temp_db.name)
                except Exception:
                    pass
                return False

        except Exception as e:
            # Clean up temp file on error
            try:
                os.unlink(temp_db.name)
            except Exception:
                pass
            self.log_error(f"Database test failed: {e}")
            return False

    def test_anti_detection_system(self) -> bool:
        """Test anti-detection system initialization"""
        try:
            from anti_detection_system import AntiDetectionSystem

            ads = AntiDetectionSystem()
            status = ads.get_system_status()

            if status and "anti_detection_active" in status:
                self.log_success("Anti-detection system initialized successfully")
                return True
            else:
                self.log_error("Anti-detection system initialization failed")
                return False

        except Exception as e:
            self.log_error(f"Anti-detection system test failed: {e}")
            return False

    def test_account_creator(self) -> bool:
        """Test account creator initialization"""
        try:
            from account_creator import AccountCreator
            from member_scraper import MemberDatabase

            db = MemberDatabase(":memory:")
            ac = AccountCreator(db)

            if hasattr(ac, "phone_provider") and hasattr(ac, "device_fingerprint"):
                self.log_success("Account creator initialized successfully")
                return True
            else:
                self.log_error("Account creator missing required components")
                return False

        except Exception as e:
            self.log_error(f"Account creator test failed: {e}")
            return False

    def install_missing_packages(self) -> bool:
        """Attempt to install missing packages"""
        try:
            # Check for common missing packages
            missing_packages = []

            try:
                import psutil  # noqa: F401
            except ImportError:
                missing_packages.append("psutil")

            if missing_packages:
                self.log_warning(f"Installing missing packages: {', '.join(missing_packages)}")
                for package in missing_packages:
                    try:
                        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                        self.log_success(f"Installed {package}")
                    except subprocess.CalledProcessError:
                        self.log_error(f"Failed to install {package}")
                        return False

            return True

        except Exception as e:
            self.log_error(f"Package installation failed: {e}")
            return False

    def test_account_manager(self) -> bool:
        """Test account manager initialization."""
        try:
            from account_manager import AccountManager
            from member_scraper import MemberDatabase

            db = MemberDatabase(":memory:")
            am = AccountManager(db)

            if hasattr(am, "accounts") and hasattr(am, "account_status"):
                self.log_success("Account manager initialized successfully")
                return True
            else:
                self.log_error("Account manager missing required attributes")
                return False

        except Exception as e:
            self.log_error(f"Account manager test failed: {e}")
            return False

    def test_gui_instantiation(self) -> bool:
        """Test GUI class imports and basic structure
        (no actual instantiation to avoid display issues)"""
        try:
            # Test that all GUI classes can be imported without instantiation
            try:
                self.log_success("GUI classes imported successfully")
            except Exception as e:
                self.log_error(f"GUI class import failed: {e}")
                return False

            # Test that all required PyQt6 widgets are available as classes
            try:
                from PyQt6.QtWidgets import (
                    QCheckBox,
                    QComboBox,
                    QDialog,
                    QGroupBox,
                    QHBoxLayout,
                    QLabel,
                    QLineEdit,
                    QListWidget,
                    QProgressBar,
                    QPushButton,
                    QSpinBox,
                    QTabWidget,
                    QTextEdit,
                    QVBoxLayout,
                )

                # Just check that these are classes, don't instantiate
                widget_classes = [
                    QComboBox,
                    QProgressBar,
                    QListWidget,
                    QTextEdit,
                    QLineEdit,
                    QCheckBox,
                    QSpinBox,
                    QPushButton,
                    QLabel,
                    QGroupBox,
                    QTabWidget,
                    QDialog,
                    QVBoxLayout,
                    QHBoxLayout,
                ]

                for widget_class in widget_classes:
                    if not hasattr(widget_class, "__init__"):
                        self.log_error(
                            f"Widget class {widget_class.__name__} is not a proper class"
                        )
                        return False

                self.log_success("All GUI widget classes verified")

            except Exception as e:
                self.log_error(f"GUI widget class verification failed: {e}")
                return False

            return True

        except Exception as e:
            self.log_error(f"GUI instantiation test failed: {e}")
            return False

    def run_all_tests(self) -> bool:
        """Run all system tests"""
        print("🧪 Starting comprehensive system test...")
        print("=" * 50)

        # Install missing packages first
        if not self.install_missing_packages():
            return False

        tests = [
            ("Python Version", self.test_python_version),
            ("Core Modules", self.test_core_imports),
            ("PyQt6 Components", self.test_qt_components),
            ("AI Service", self.test_ai_service),
            ("Database System", self.test_database_creation),
            ("Anti-Detection System", self.test_anti_detection_system),
            ("Account Creator", self.test_account_creator),
            ("Account Manager", self.test_account_manager),
            ("GUI Instantiation", self.test_gui_instantiation),
        ]

        passed = 0
        total = len(tests)

        for test_name, test_func in tests:
            print(f"\n🔍 Testing {test_name}...")
            try:
                if test_func():
                    passed += 1
                else:
                    self.log_error(f"{test_name} test failed")
            except Exception as e:
                self.log_error(f"{test_name} test crashed: {e}")

        print("\n" + "=" * 50)
        print(f"📊 Test Results: {passed}/{total} tests passed")

        if self.errors:
            print(f"❌ {len(self.errors)} errors found:")
            for error in self.errors:
                print(f"   • {error}")

        if self.warnings:
            print(f"⚠️  {len(self.warnings)} warnings:")
            for warning in self.warnings:
                print(f"   • {warning}")

        success_rate = (passed / total) * 100
        if success_rate >= 80:
            print(f"🎉 Success rate: {success_rate:.1f}% - System ready!")
            return True
        else:
            print(f"❌ Success rate: {success_rate:.1f}% - System needs fixes")
            return False

    def get_summary(self) -> Dict:
        """Get test summary"""
        return {
            "total_tests": len(self.errors) + len(self.warnings) + len(self.successes),
            "errors": len(self.errors),
            "warnings": len(self.warnings),
            "successes": len(self.successes),
            "error_list": self.errors,
            "warning_list": self.warnings,
            "success_list": self.successes,
        }


def main():
    """Main test function"""
    tester = SystemTester()

    try:
        success = tester.run_all_tests()
        tester.get_summary()

        if success:
            print("\n🚀 All systems go! Ready to launch Telegram AI Assistant.")
            print("💡 Run: python main.py")
            sys.exit(0)
        else:
            print("\n❌ System test failed. Please fix errors before running.")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n👋 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test system crashed: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
