#!/usr/bin/env python3
"""
Application Launcher - Handles startup, welcome wizard, and initialization
"""

import sys
import logging
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QTimer

# Import and configure centralized logging with rotation
from core.setup_logging import setup_logging

# Set up logging with rotation (10MB per file, 5 backups)
setup_logging(log_level=logging.INFO)

logger = logging.getLogger(__name__)


def check_first_run() -> bool:
    """Check if this is the first time running the app."""
    from ui.welcome_wizard import should_show_wizard

    return should_show_wizard()


def show_welcome_wizard(app):
    """Show the welcome wizard for first-time users."""
    try:
        from ui.welcome_wizard import WelcomeWizard

        wizard = WelcomeWizard()

        # Fixed: Don't show message box in signal handler - wizard already shows completion message
        # The signal is emitted before wizard closes, so showing another dialog here is redundant
        def on_wizard_completed(config):
            logger.info("Welcome wizard completed successfully")
            # Wizard already shows completion message, so we just log here

        wizard.config_completed.connect(on_wizard_completed)
        result = wizard.exec()

        return result == wizard.DialogCode.Accepted
    except Exception as e:
        logger.error(f"Error showing welcome wizard: {e}", exc_info=True)
        QMessageBox.critical(
            None,
            "Wizard Error",
            f"Failed to show welcome wizard: {e}\n\nYou can configure the app in Settings.",
        )
        return True  # Continue anyway


def show_quick_start_tip(main_window):
    """Show quick start tip after wizard."""
    try:
        from ui.ui_enhancements import show_quick_start

        # Show quick start guide
        show_again = show_quick_start(main_window)

        # Save preference
        if not show_again:
            Path(".no_quick_start").touch()

    except Exception as e:
        logger.error(f"Error showing quick start: {e}")


def launch_application():
    """Launch the main application."""
    try:
        # Create logs directory
        Path("logs").mkdir(exist_ok=True)

        logger.info("=" * 60)
        logger.info("Starting Telegram Auto-Reply Bot")
        logger.info("=" * 60)

        # Create QApplication
        app = QApplication(sys.argv)
        app.setApplicationName("Telegram Auto-Reply Bot")
        app.setOrganizationName("TelegramBot")

        # Apply Aurora theme immediately so the welcome wizard is themed
        try:
            from ui.theme_manager import ThemeManager

            ThemeManager.apply_to_application(app)
            logger.info("Applied Aurora theme via ThemeManager (pre-wizard)")
        except Exception as theme_exc:
            logger.warning(f"Theme application fallback before wizard: {theme_exc}")
            try:
                from ui.ui_redesign import HIGH_CONTRAST_THEME

                app.setStyleSheet(HIGH_CONTRAST_THEME)
                logger.info("Applied Aurora stylesheet fallback (pre-wizard)")
            except Exception:
                logger.warning("Could not import theme before wizard - using default Qt styling")

        # Check if this is first run
        is_first_run = check_first_run()

        if is_first_run:
            logger.info("First run detected - showing welcome wizard")
            wizard_completed = show_welcome_wizard(app)

            if not wizard_completed:
                logger.info("User cancelled welcome wizard")
                return 0

        # Import main window (do this after wizard to ensure config exists)
        try:
            from main import MainWindow
        except ImportError as e:
            logger.error(f"Failed to import MainWindow: {e}")
            QMessageBox.critical(
                None,
                "Import Error",
                f"Failed to import main application:\n\n{e}\n\n"
                f"Make sure all dependencies are installed:\n"
                f"pip install -r requirements.txt",
            )
            return 1

        # Create and show main window
        logger.info("Creating main window")
        main_window = MainWindow()

        # Re-apply theme after main window creation (keeps current selection)
        try:
            from ui.theme_manager import ThemeManager

            ThemeManager.apply_to_application(app)
            logger.info("Re-applied Aurora theme post-main window")
        except Exception as theme_exc:
            logger.warning(f"Theme application fallback post-main window: {theme_exc}")
            try:
                from ui.ui_redesign import HIGH_CONTRAST_THEME

                app.setStyleSheet(HIGH_CONTRAST_THEME)
                logger.info("Applied Aurora stylesheet fallback post-main window")
            except Exception:
                logger.warning("Could not import theme post-main window - using default Qt styling")

        # Show main window
        main_window.show()
        logger.info("Main window shown")

        # Show quick start tip for first-time users (after a delay)
        if is_first_run:
            should_show_quick_start = not Path(".no_quick_start").exists()
            if should_show_quick_start:
                QTimer.singleShot(1000, lambda: show_quick_start_tip(main_window))

        # Run event loop
        logger.info("Entering main event loop")
        exit_code = app.exec()

        # Memory cleanup before exit
        try:
            import gc

            logger.info("Performing final memory cleanup...")

            # Force garbage collection
            collected = gc.collect()
            logger.info(f"Final garbage collection: {collected} objects collected")

            # Clear any cached references
            gc.collect(2)  # Full collection

        except Exception as cleanup_error:
            logger.warning(f"Memory cleanup failed: {cleanup_error}")

        logger.info(f"Application exited with code {exit_code}")
        return exit_code

    except Exception as e:
        logger.critical(f"Fatal error during application launch: {e}", exc_info=True)
        try:
            QMessageBox.critical(
                None,
                "Fatal Error",
                f"A fatal error occurred:\n\n{e}\n\n" f"Check logs/app.log for details.",
            )
        except Exception:
            pass  # GUI may not be available
        return 1


def main():
    """Main entry point."""
    try:
        exit_code = launch_application()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
