#!/usr/bin/env python3
"""
Crash Recovery - REAL crash detection and recovery system
Detects abnormal shutdowns and recovers state
"""

import atexit
import json
import logging
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)


class CrashRecovery:
    """REAL crash detection and recovery."""

    def __init__(self):
        self.state_file = Path(".app_state.json")
        self.crash_marker = Path(".app_running")
        self.crash_log = Path("logs/crash.log")

        # Setup crash detection
        self.setup_crash_detection()

    def setup_crash_detection(self):
        """Setup REAL crash detection markers."""
        # Register cleanup handlers
        atexit.register(self.on_normal_exit)

        # Handle signals
        signal.signal(signal.SIGTERM, self.on_signal_exit)
        signal.signal(signal.SIGINT, self.on_signal_exit)

        logger.info("✅ Crash detection initialized")

    def mark_startup(self):
        """Mark application startup with REAL file."""
        try:
            # Check if crash marker exists (means previous crash)
            if self.crash_marker.exists():
                logger.warning("⚠️ Detected previous abnormal shutdown")
                self.handle_crash_recovery()

            # Create new crash marker
            with open(self.crash_marker, "w") as f:
                json.dump({"started_at": datetime.now().isoformat(), "pid": os.getpid()}, f)

            logger.info("Application startup marked")

        except Exception as e:
            logger.error(f"Failed to mark startup: {e}")

    def mark_shutdown(self):
        """Mark normal shutdown by ACTUALLY removing marker."""
        try:
            if self.crash_marker.exists():
                self.crash_marker.unlink()
                logger.info("Normal shutdown marked")
        except Exception as e:
            logger.error(f"Failed to mark shutdown: {e}")

    def on_normal_exit(self):
        """Handle normal exit."""
        self.mark_shutdown()
        self.save_state()

    def on_signal_exit(self, signum, frame):
        """Handle signal-based exit."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.mark_shutdown()
        self.save_state()
        sys.exit(0)

    def save_state(self, state: Dict = None):
        """Save ACTUAL application state to file."""
        try:
            if state is None:
                state = {}

            state["last_save"] = datetime.now().isoformat()

            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)

            logger.debug("Application state saved")

        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_state(self) -> Dict:
        """Load REAL application state from file."""
        try:
            if self.state_file.exists():
                with open(self.state_file) as f:
                    state = json.load(f)
                logger.info("Application state loaded")
                return state
        except Exception as e:
            logger.error(f"Failed to load state: {e}")

        return {}

    def handle_crash_recovery(self):
        """Handle REAL crash recovery."""
        logger.warning("🔧 Initiating crash recovery...")

        try:
            # Load state from before crash
            state = self.load_state()

            # Log crash details
            self.log_crash_details(state)

            # Check for incomplete operations
            from resume_manager import check_for_incomplete_operations

            incomplete = check_for_incomplete_operations()

            if incomplete > 0:
                logger.info(f"Found {incomplete} incomplete operations to resume")

            # Create crash recovery backup
            from backup_restore import create_auto_backup

            backup_file = create_auto_backup(include_sessions=True)
            if backup_file:
                logger.info(f"Created crash recovery backup: {backup_file}")

            logger.info("✅ Crash recovery complete")

        except Exception as e:
            logger.error(f"Crash recovery failed: {e}", exc_info=True)

    def log_crash_details(self, state: Dict):
        """Log REAL crash details to file."""
        try:
            # Ensure logs directory exists
            Path("logs").mkdir(exist_ok=True)

            with open(self.crash_log, "a") as f:
                f.write("=" * 80 + "\n")
                f.write(f"Crash detected at: {datetime.now().isoformat()}\n")
                f.write(f"Last known state: {json.dumps(state, indent=2)}\n")
                f.write("=" * 80 + "\n\n")

            logger.info("Crash details logged")

        except Exception as e:
            logger.error(f"Failed to log crash details: {e}")


# Import os for getpid
import os  # noqa: E402

# Global instance
crash_recovery = CrashRecovery()


def initialize_crash_recovery():
    """Initialize REAL crash recovery on startup."""
    crash_recovery.mark_startup()


def save_application_state(state: Dict):
    """Save REAL application state."""
    crash_recovery.save_state(state)


def check_for_crash() -> bool:
    """Check if previous run crashed."""
    return crash_recovery.crash_marker.exists()
