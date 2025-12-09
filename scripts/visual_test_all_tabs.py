#!/usr/bin/env python3
"""
Visual Test Script - Navigate through all tabs and capture screenshots.
This allows checking the visual appearance of each tab/page.

Usage:
    xvfb-run -s "-screen 0 1920x1080x24" python3 scripts/visual_test_all_tabs.py
"""

import sys
import time
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

# Ensure project imports work
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    """Test all tabs and capture screenshots."""
    app = QApplication(sys.argv)
    app.setApplicationName("Telegram Bot - Visual Tab Test")

    # Apply theme
    try:
        from ui.theme_manager import ThemeManager

        ThemeManager.apply_to_application(app)
        print("✓ Theme applied successfully")
    except Exception as e:
        print(f"⚠ Theme application failed: {e}")

    from main import MainWindow

    # Create output directory
    out_dir = Path("artifacts/visual/tabs")
    out_dir.mkdir(parents=True, exist_ok=True)

    window = MainWindow()
    window.resize(1920, 1080)
    window.show()
    app.processEvents()

    # Tab definitions: (index, name, delay_ms)
    tabs = [
        (0, "dashboard", 800),
        (1, "accounts", 800),
        (2, "members", 800),
        (3, "campaigns", 800),
        (4, "analytics", 800),
        (5, "proxy_pool", 800),
        (6, "health", 800),
        (7, "engagement", 800),
        (8, "warmup", 800),
        (9, "risk_monitor", 800),
        (10, "delivery", 800),
        (11, "messages", 800),
        (12, "settings", 1000),  # Settings might take longer to load
        (13, "logs", 800),
    ]

    current_tab_idx = 0

    def capture_tab():
        nonlocal current_tab_idx

        if current_tab_idx >= len(tabs):
            print("\n✅ All tabs captured! Exiting...")
            app.quit()
            return

        tab_index, tab_name, delay = tabs[current_tab_idx]

        try:
            # Navigate to tab
            print(
                f"📸 Capturing tab {current_tab_idx + 1}/{len(tabs)}: {tab_name} (index {tab_index})"
            )
            window.navigate_to_page(tab_index)
            app.processEvents()

            # Wait for UI to update
            time.sleep(delay / 1000.0)
            window.repaint()
            app.processEvents()

            # Capture screenshot
            screen = app.primaryScreen()
            if screen:
                pixmap = screen.grabWindow(window.winId())
                filename = out_dir / f"tab_{current_tab_idx:02d}_{tab_name}.png"
                pixmap.save(str(filename))
                print(f"   ✓ Saved: {filename}")
            else:
                print("   ✗ No screen available")

        except Exception as e:
            print(f"   ✗ Error capturing {tab_name}: {e}")

        current_tab_idx += 1

        # Schedule next capture
        QTimer.singleShot(200, capture_tab)

    # Start capturing after initial delay
    print("🚀 Starting visual tab test...")
    print(f"📁 Screenshots will be saved to: {out_dir.absolute()}\n")
    QTimer.singleShot(2000, capture_tab)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
