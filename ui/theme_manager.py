"""
Theme Manager - Centralized theme application for all widgets.
Now supports premium light/dark themes and runtime toggling.
"""

from pathlib import Path
from typing import Optional
from PyQt6.QtWidgets import QWidget, QApplication, QStyleFactory, QGraphicsDropShadowEffect
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

from ui.ui_redesign import DARK_THEME, LIGHT_THEME, HIGH_CONTRAST_THEME


class ThemeManager:
    """Manages application-wide theming with dual light/dark modes."""

    THEME_PREF_FILE = Path(".theme_pref")
    DEFAULT_THEME = "dark"
    THEME_MAP = {"dark": DARK_THEME, "light": LIGHT_THEME}
    PALETTES = {
        "dark": {
            "BG_PRIMARY": "#0f1115",  # Deep app background
            "BG_SECONDARY": "#161a24",  # Elevated surface
            "BG_TERTIARY": "#1f2430",  # Controls surface
            "BG_INPUT": "#121622",  # Input surface
            "TEXT_PRIMARY": "#e8ecf4",  # High legibility text
            "TEXT_SECONDARY": "#9ea8ba",  # Secondary text
            "TEXT_DISABLED": "#5f6775",  # Disabled text
            "TEXT_BRIGHT": "#ffffff",  # Bright text
            "ACCENT_PRIMARY": "#007aff",  # Brand blue
            "ACCENT_SUCCESS": "#3dd598",  # Modern green
            "ACCENT_WARNING": "#f5a524",  # Modern amber
            "ACCENT_DANGER": "#ff4d4f",  # Modern red
            "BORDER_DEFAULT": "rgba(255, 255, 255, 0.08)",  # Subtle border
            "BORDER_FOCUS": "#5aa2ff",  # Focus ring
            "SHADOW_ELEVATED": "0 18px 60px rgba(0, 0, 0, 0.45)",
        },
        "light": {
            "BG_PRIMARY": "#f5f7fb",
            "BG_SECONDARY": "#ffffff",
            "BG_TERTIARY": "#e6e9f0",
            "BG_INPUT": "#ffffff",
            "TEXT_PRIMARY": "#0f141f",
            "TEXT_SECONDARY": "#5c6675",
            "TEXT_DISABLED": "#9ba3b0",
            "TEXT_BRIGHT": "#ffffff",
            "ACCENT_PRIMARY": "#007aff",
            "ACCENT_SUCCESS": "#2f9e69",
            "ACCENT_WARNING": "#e7961c",
            "ACCENT_DANGER": "#e54848",
            "BORDER_DEFAULT": "rgba(0, 0, 0, 0.08)",
            "BORDER_FOCUS": "#1f7bff",
            "SHADOW_ELEVATED": "0 18px 60px rgba(15, 20, 31, 0.25)",
        },
    }

    current_theme = DEFAULT_THEME

    @classmethod
    def _get_palette(cls, theme: Optional[str] = None) -> dict:
        return cls.PALETTES.get(theme or cls.current_theme, cls.PALETTES[cls.DEFAULT_THEME])

    @classmethod
    def _load_saved_theme(cls) -> str:
        try:
            if cls.THEME_PREF_FILE.exists():
                saved = cls.THEME_PREF_FILE.read_text().strip()
                if saved in cls.THEME_MAP:
                    return saved
        except Exception:
            pass
        return cls.DEFAULT_THEME

    @classmethod
    def _save_theme(cls, theme: str):
        try:
            cls.THEME_PREF_FILE.write_text(theme)
        except Exception:
            # Non-critical if persisting fails
            pass

    @classmethod
    def apply_theme_to_app(cls, app: QApplication):
        """Compatibility wrapper for legacy imports."""
        cls.apply_to_application(app)

    @classmethod
    def apply_to_application(cls, app: QApplication, theme: Optional[str] = None):
        """Apply selected theme to entire application."""
        active_theme = theme or cls._load_saved_theme()
        cls.current_theme = active_theme if active_theme in cls.THEME_MAP else cls.DEFAULT_THEME

        # Use Fusion base style for consistent cross-platform rendering
        try:
            app.setStyle(QStyleFactory.create("Fusion"))
        except Exception:
            pass

        app.setStyleSheet(cls.THEME_MAP.get(cls.current_theme, HIGH_CONTRAST_THEME))
        cls._apply_palette(app, cls.current_theme)
        cls._save_theme(cls.current_theme)

    @classmethod
    def set_theme(cls, theme: str, app: Optional[QApplication] = None, persist: bool = True):
        """Switch theme at runtime."""
        if theme not in cls.THEME_MAP:
            theme = cls.DEFAULT_THEME
        cls.current_theme = theme
        target_app = app or QApplication.instance()
        if target_app:
            target_app.setStyleSheet(cls.THEME_MAP[cls.current_theme])
            cls._apply_palette(target_app, cls.current_theme)
        if persist:
            cls._save_theme(cls.current_theme)

    @classmethod
    def toggle_theme(cls, app: Optional[QApplication] = None):
        """Toggle between light and dark themes."""
        next_theme = "light" if cls.current_theme == "dark" else "dark"
        cls.set_theme(next_theme, app=app)
        return next_theme

    @classmethod
    def _apply_palette(cls, app: QApplication, theme: str):
        colors = cls._get_palette(theme)
        palette = QPalette()

        palette.setColor(QPalette.ColorRole.Window, QColor(colors["BG_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["TEXT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(colors["BG_INPUT"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["BG_SECONDARY"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(colors["TEXT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(colors["BG_TERTIARY"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["TEXT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(colors["TEXT_BRIGHT"]))

        palette.setColor(QPalette.ColorRole.Highlight, QColor(colors["ACCENT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(colors["TEXT_BRIGHT"]))

        palette.setColor(QPalette.ColorRole.Link, QColor(colors["ACCENT_PRIMARY"]))
        palette.setColor(QPalette.ColorRole.LinkVisited, QColor(colors["ACCENT_PRIMARY"]))

        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colors["TEXT_DISABLED"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(colors["TEXT_DISABLED"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(colors["TEXT_DISABLED"]))

        app.setPalette(palette)

    @classmethod
    def apply_to_widget(cls, widget: QWidget, style_type: str = "default"):
        """Apply theme to a specific widget."""
        c = cls._get_palette()
        if style_type == "card":
            widget.setStyleSheet(
                f"""
                QFrame {{
                    background-color: {c["BG_SECONDARY"]};
                    border: 0.5px solid {c["BORDER_DEFAULT"]};
                    border-radius: 14px;
                    padding: 20px 24px;
                }}
                QLabel {{
                    background-color: transparent;
                    color: {c["TEXT_PRIMARY"]};
                }}
            """
            )
        elif style_type == "panel":
            widget.setStyleSheet(
                f"""
                QWidget {{
                    background-color: {c["BG_TERTIARY"]};
                    border: 0.5px solid {c["BORDER_DEFAULT"]};
                    border-radius: 12px;
                }}
                QLabel {{
                    color: {c["TEXT_PRIMARY"]};
                    background-color: transparent;
                }}
            """
            )
        elif style_type == "input_group":
            widget.setStyleSheet(
                f"""
                QLabel {{
                    color: {c["TEXT_PRIMARY"]};
                    font-weight: 500;
                    background-color: transparent;
                }}
                QLineEdit, QTextEdit, QPlainTextEdit {{
                    background-color: {c["BG_INPUT"]};
                    color: {c["TEXT_PRIMARY"]};
                    border: 0.5px solid {c["BORDER_DEFAULT"]};
                    padding: 12px 16px;
                    border-radius: 10px;
                    min-height: 44px;
                    font-size: 15px;
                }}
                QLineEdit:focus, QTextEdit:focus {{
                    border: 0.5px solid {c["BORDER_FOCUS"]};
                }}
            """
            )
        else:
            widget.setStyleSheet(
                f"""
                QWidget {{
                    background-color: {c["BG_PRIMARY"]};
                    color: {c["TEXT_PRIMARY"]};
                }}
                QLabel {{
                    color: {c["TEXT_PRIMARY"]};
                    background-color: transparent;
                }}
            """
            )

    @classmethod
    def get_button_style(cls, button_type: str = "default") -> str:
        """Get button stylesheet."""
        c = cls._get_palette()
        common = f"""
            QPushButton {{
                border: none;
                padding: 12px 22px;
                border-radius: 12px;
                font-weight: 600;
                font-size: 15px;
                min-height: 44px;
                letter-spacing: -0.08px;
            }}
            QPushButton:focus {{
                outline: 2px solid {c["BORDER_FOCUS"]};
                outline-offset: 2px;
            }}
            QPushButton:disabled {{
                color: {c["TEXT_DISABLED"]};
                opacity: 0.55;
            }}
        """
        if button_type == "primary":
            return common + f"""
                QPushButton {{
                    background-color: {c["ACCENT_PRIMARY"]};
                    color: {c["TEXT_BRIGHT"]};
                }}
                QPushButton:hover {{
                    background-color: #1a7dff;
                }}
                QPushButton:pressed {{
                    background-color: #0f64d4;
                }}
                QPushButton:disabled {{
                    background-color: {c["BG_TERTIARY"]};
                }}
            """
        elif button_type == "danger":
            return common + f"""
                QPushButton {{
                    background-color: {c["ACCENT_DANGER"]};
                    color: {c["TEXT_BRIGHT"]};
                }}
                QPushButton:hover {{
                    background-color: #d73b3f;
                }}
                QPushButton:pressed {{
                    background-color: #b62f32;
                }}
            """
        elif button_type == "success":
            return common + f"""
                QPushButton {{
                    background-color: {c["ACCENT_SUCCESS"]};
                    color: {c["TEXT_BRIGHT"]};
                }}
                QPushButton:hover {{
                    background-color: #2fb57e;
                }}
                QPushButton:pressed {{
                    background-color: #27996b;
                }}
            """
        else:
            return common + f"""
                QPushButton {{
                    background-color: {c["BG_TERTIARY"]};
                    color: {c["TEXT_PRIMARY"]};
                }}
                QPushButton:hover {{
                    background-color: {c["BG_SECONDARY"]};
                }}
                QPushButton:pressed {{
                    background-color: {c["BG_PRIMARY"]};
                }}
                QPushButton:disabled {{
                    background-color: {c["BG_TERTIARY"]};
                }}
            """

    @classmethod
    def get_label_style(cls, label_type: str = "default") -> str:
        """Get label stylesheet."""
        c = cls._get_palette()
        if label_type == "header":
            return f"""
                QLabel {{
                    color: {c["TEXT_BRIGHT"]};
                    font-size: 22px;
                    font-weight: 700;
                    letter-spacing: -0.3px;
                    line-height: 1.3em;
                    background-color: transparent;
                }}
            """
        elif label_type == "subheader":
            return f"""
                QLabel {{
                    color: {c["TEXT_PRIMARY"]};
                    font-size: 17px;
                    font-weight: 600;
                    letter-spacing: -0.2px;
                    line-height: 1.4em;
                    background-color: transparent;
                }}
            """
        elif label_type == "title":
            return f"""
                QLabel {{
                    color: {c["TEXT_BRIGHT"]};
                    font-size: 28px;
                    font-weight: 700;
                    letter-spacing: -0.4px;
                    line-height: 1.25em;
                    background-color: transparent;
                }}
            """
        elif label_type == "description":
            return f"""
                QLabel {{
                    color: {c["TEXT_SECONDARY"]};
                    font-size: 15px;
                    letter-spacing: -0.05px;
                    line-height: 1.5em;
                    background-color: transparent;
                }}
            """
        else:
            return f"""
                QLabel {{
                    color: {c["TEXT_PRIMARY"]};
                    font-size: 15px;
                    letter-spacing: -0.1px;
                    line-height: 1.5em;
                    background-color: transparent;
                }}
            """

    @classmethod
    def get_color(cls, color_name: str, theme: Optional[str] = None) -> str:
        """Get a color value from the palette by name."""
        palette = cls._get_palette(theme)
        return palette.get(color_name, palette.get("TEXT_PRIMARY", "#000000"))

    @classmethod
    def apply_shadow(
        cls,
        widget: QWidget,
        blur_radius: int = 40,
        x_offset: int = 0,
        y_offset: int = 16,
        opacity: float = 0.6,
    ):
        """Apply a drop shadow to a widget using Qt effects (QSS cannot do shadows)."""
        try:
            effect = QGraphicsDropShadowEffect(widget)
            effect.setBlurRadius(blur_radius)
            effect.setOffset(x_offset, y_offset)
            # Use palette text color with reduced opacity for a subtle shadow
            shadow_color = QColor(0, 0, 0)
            shadow_color.setAlphaF(max(0.0, min(1.0, opacity)))
            effect.setColor(shadow_color)
            widget.setGraphicsEffect(effect)
        except Exception:
            # Non-fatal if shadow cannot be applied
            pass

    @classmethod
    def get_colors(cls, theme: Optional[str] = None) -> dict:
        """Get the full color palette for the current or specified theme."""
        return cls._get_palette(theme)

    @classmethod
    def get_empty_state_style(cls) -> str:
        """Get stylesheet for empty state widgets."""
        c = cls._get_palette()
        return f"""
            QFrame#empty_state {{
                background-color: {c["BG_SECONDARY"]};
                border: 0.5px solid {c["BORDER_DEFAULT"]};
                border-radius: 16px;
                padding: 56px 40px;
            }}
            QLabel#empty_state_icon {{
                font-size: 72px;
                color: {c["TEXT_DISABLED"]};
                background-color: transparent;
            }}
            QLabel#empty_state_title {{
                font-size: 20px;
                font-weight: 700;
                color: {c["TEXT_SECONDARY"]};
                letter-spacing: -0.3px;
                line-height: 1.3em;
                background-color: transparent;
                margin-top: 20px;
            }}
            QLabel#empty_state_message {{
                font-size: 15px;
                color: {c["TEXT_DISABLED"]};
                letter-spacing: -0.1px;
                line-height: 1.4em;
                background-color: transparent;
                margin-top: 10px;
            }}
        """

    @classmethod
    def get_dialog_style(cls) -> str:
        """Get stylesheet for dialogs."""
        c = cls._get_palette()
        return f"""
            QDialog {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {c["BG_SECONDARY"]},
                    stop:1 {c["BG_PRIMARY"]});
                color: {c["TEXT_PRIMARY"]};
                border: 1px solid {c["BORDER_DEFAULT"]};
                border-radius: 16px;
                padding: 8px;
            }}
            QLabel {{
                color: {c["TEXT_PRIMARY"]};
                background-color: transparent;
            }}
        """

    @classmethod
    def get_chart_colors(cls) -> dict:
        """Get color palette for charts."""
        c = cls._get_palette()
        is_dark = cls.current_theme == "dark"
        return {
            "background": c["BG_PRIMARY"],
            "surface": c["BG_SECONDARY"],
            "border": c["BORDER_DEFAULT"],
            "text": c["TEXT_PRIMARY"],
            "text_secondary": c["TEXT_SECONDARY"],
            "text_disabled": c["TEXT_DISABLED"],
            "accent": c["ACCENT_PRIMARY"],
            "success": c["ACCENT_SUCCESS"],
            "warning": c["ACCENT_WARNING"],
            "danger": c["ACCENT_DANGER"],
            "grid": c["BORDER_DEFAULT"] if is_dark else "#e4e4e7",
            "axis": c["TEXT_SECONDARY"],
        }


def apply_theme_to_widget(widget: QWidget):
    """Convenience function to apply theme to any widget."""
    ThemeManager.apply_to_widget(widget)


def apply_theme_to_app(app: QApplication):
    """Convenience function to apply theme to application."""
    ThemeManager.apply_to_application(app)

