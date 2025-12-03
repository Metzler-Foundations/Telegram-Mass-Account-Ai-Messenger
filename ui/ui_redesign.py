"""
Modern Enterprise UI Theme
Clean, professional, and organized design similar to VS Code or Linear.
"""

DISCORD_THEME = """
/* ===== GLOBAL RESET & TYPOGRAPHY ===== */
* {
    font-family: 'Segoe UI', 'Inter', 'San Francisco', 'Helvetica Neue', Arial, sans-serif;
    outline: none;
}

QWidget {
    color: #e4e4e7;
    selection-background-color: #264f78;
    selection-color: #ffffff;
    font-size: 13px;
}

QMainWindow, QDialog, QWizard {
    background-color: #18181b; /* Zinc-950 - Deep Matte Dark */
    color: #e4e4e7;
}

/* ===== STANDARD WIDGETS ===== */
QFrame, QWidget#content_area {
    background-color: #18181b;
    border: none;
}

/* Separators */
QFrame[frameShape="4"], QFrame[frameShape="5"] { /* HLine & VLine */
    color: #27272a;
    background-color: #27272a;
}

/* Group Boxes - Clean & Structured */
QGroupBox {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 24px;
    padding-bottom: 12px;
    padding-left: 12px;
    padding-right: 12px;
    font-weight: 600;
    font-size: 13px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    color: #a1a1aa;
    background-color: #18181b;
    font-weight: 600;
    font-size: 13px;
}

/* ===== BUTTONS - Clean & Solid ===== */
QPushButton {
    background-color: #27272a;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    color: #e4e4e7;
    padding: 8px 16px;
    min-height: 28px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3f3f46;
    border-color: #52525b;
}

QPushButton:pressed {
    background-color: #18181b;
}

QPushButton:disabled {
    background-color: #18181b;
    border-color: #27272a;
    color: #52525b;
}

/* Primary Action Buttons */
QPushButton[class="primary"], QPushButton#success {
    background-color: #2563eb; /* Professional Blue */
    border: 1px solid #2563eb;
    color: #ffffff;
}

QPushButton[class="primary"]:hover, QPushButton#success:hover {
    background-color: #1d4ed8;
    border-color: #1d4ed8;
}

QPushButton[class="danger"], QPushButton#danger {
    background-color: #dc2626;
    border-color: #dc2626;
    color: #ffffff;
}

/* ===== INPUTS - Clean & Readable ===== */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #09090b; /* Almost black */
    border: 1px solid #3f3f46;
    border-radius: 4px;
    color: #e4e4e7;
    padding: 8px;
    min-height: 24px;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #2563eb; /* Blue focus ring */
    background-color: #000000;
}

QLineEdit::placeholder {
    color: #71717a;
}

/* ===== LISTS & TABLES ===== */
QListWidget, QTableWidget, QTreeWidget {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    alternate-background-color: #18181b;
}

QListWidget::item, QTreeWidget::item, QTableWidget::item {
    padding: 8px;
    border-bottom: 1px solid #27272a;
    color: #e4e4e7;
}

QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {
    background-color: #264f78; /* VS Code Blue selection */
    color: #ffffff;
    border: none;
}

QListWidget::item:hover, QTreeWidget::item:hover, QTableWidget::item:hover {
    background-color: #27272a;
}

QHeaderView::section {
    background-color: #27272a;
    color: #a1a1aa;
    padding: 8px;
    border: none;
    border-right: 1px solid #3f3f46;
    border-bottom: 1px solid #3f3f46;
    font-weight: 600;
}

/* ===== SIDEBAR (Main.py specific) ===== */
QWidget#sidebar_container {
    background-color: #27272a; /* Sidebar background */
    border-right: 1px solid #3f3f46;
}

QWidget#sidebar {
    background-color: #27272a;
}

QWidget#nav_section {
    background-color: #27272a;
}

/* Sidebar Buttons */
QPushButton#nav_button {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    text-align: left;
    padding: 10px 12px;
    color: #a1a1aa;
    font-size: 14px;
}

QPushButton#nav_button:hover {
    background-color: #3f3f46;
    color: #e4e4e7;
}

QPushButton#nav_button:checked {
    background-color: #2563eb;
    color: #ffffff;
}

/* Server/Top Icons */
QPushButton#server_button {
    background-color: #3f3f46;
    border-radius: 4px; /* Square with slight radius */
    border: none;
    color: #e4e4e7;
}

QPushButton#server_button:checked {
    background-color: #2563eb;
    border-radius: 4px;
}

/* User Panel */
QWidget#user_panel {
    background-color: #18181b;
    border-top: 1px solid #3f3f46;
}

/* ===== SCROLL AREAS ===== */
QScrollArea {
    background-color: #18181b;
    border: none;
}

QScrollArea QWidget {
    background-color: #18181b;
}

QScrollArea#settings_scroll_area {
    background-color: #18181b;
    border: none;
}

QScrollArea#settings_scroll_area QWidget {
    background-color: #18181b;
}

/* ===== SCROLLBARS ===== */
QScrollBar:vertical {
    background: #18181b;
    width: 12px;
    margin: 0px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #3f3f46;
    min-height: 24px;
    border-radius: 6px;
    border: none;
}

QScrollBar::handle:vertical:hover {
    background: #52525b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar::groove:vertical {
    background: #18181b;
    border: none;
}

/* ===== CHECKBOXES ===== */
QCheckBox {
    spacing: 8px;
    color: #e4e4e7;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    background: #09090b;
    border: 1px solid #3f3f46;
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    background-color: #2563eb;
    border-color: #2563eb;
}

/* ===== WIZARD SPECIFIC ===== */
QWizard {
    background-color: #18181b;
}

QWizard .QWidget {
    background-color: #18181b;
}

/* ===== METRIC CARDS ===== */
QFrame#metric_card {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 6px;
}

/* ===== TAB WIDGETS - Readable Contrast ===== */
QTabWidget::pane {
    background-color: #18181b;
    border: 1px solid #3f3f46;
    border-radius: 4px;
    padding: 8px;
}

QTabBar::tab {
    background-color: #27272a;
    color: #a1a1aa;
    border: 1px solid #3f3f46;
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    padding: 8px 16px;
    margin-right: 2px;
    min-width: 80px;
}

QTabBar::tab:hover {
    background-color: #3f3f46;
    color: #e4e4e7;
}

QTabBar::tab:selected {
    background-color: #18181b;
    color: #e4e4e7;
    border-bottom: 2px solid #2563eb;
    font-weight: 600;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}

/* Ensure tab content area has dark background */
QTabWidget > QWidget {
    background-color: #18181b;
    color: #e4e4e7;
}
"""