#!/usr/bin/env python3
"""
Minimal headless-friendly UI smoke that boots MainWindow and captures a screenshot.

Usage (headless example):
  cd /home/metzlerdalton3/bot
  xvfb-run -s "-screen 0 1280x720x24" ./venv/bin/python scripts/ui_visual_smoke.py --width 1280 --height 720
"""

import argparse
import sys
import time
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

# Ensure project imports work when run directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch UI and capture a screenshot.")
    parser.add_argument(
        "--viewports",
        nargs="+",
        default=["1280x720"],
        help="Viewport sizes as WxH (space separated). Example: 1280x720 768x1024",
    )
    parser.add_argument("--delay-ms", type=int, default=1500, help="Delay before capture (ms)")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("artifacts/visual"),
        help="Output directory for screenshots",
    )
    return parser.parse_args()


def parse_viewports(raw: List[str]) -> List[Tuple[int, int]]:
    parsed = []
    for item in raw:
        try:
            w, h = item.lower().split("x")
            parsed.append((int(w), int(h)))
        except Exception:
            continue
    return parsed or [(1280, 720)]


def main() -> int:
    args = parse_args()
    viewports = parse_viewports(args.viewports)

    app = QApplication(sys.argv)
    app.setApplicationName("Telegram Auto-Reply Bot - Visual Smoke")

    try:
        from ui.theme_manager import ThemeManager

        ThemeManager.apply_to_application(app)
    except Exception:
        pass  # Fall back to default Qt theme if theme import fails

    from main import MainWindow

    args.out_dir.mkdir(parents=True, exist_ok=True)

    window = MainWindow()
    window.show()
    app.processEvents()

    def capture_sequence(idx: int = 0):
        if idx >= len(viewports):
            app.quit()
            return

        width, height = viewports[idx]
        window.resize(width, height)
        window.repaint()
        app.processEvents()

        screen = app.primaryScreen()
        if not screen:
            print("No primary screen available; cannot capture screenshot")
            app.quit()
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = args.out_dir / f"main-{width}x{height}-{timestamp}.png"
        pixmap = screen.grabWindow(window.winId())
        pixmap.save(str(filename))
        print(f"Screenshot saved to {filename}")

        # Schedule next viewport capture
        QTimer.singleShot(args.delay_ms, lambda: capture_sequence(idx + 1))

    QTimer.singleShot(args.delay_ms, lambda: capture_sequence(0))
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
