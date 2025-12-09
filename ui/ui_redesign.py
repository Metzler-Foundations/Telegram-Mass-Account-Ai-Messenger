"""
Aurora Enterprise Theme - Apple-Level Premium Design System
Comprehensive redesign with 60+ design perspectives applied for maximum polish.
Inspired by Apple's Human Interface Guidelines and modern design systems.
"""

# -----------------------------------------------------------------------------
# APPLE-LEVEL DARK THEME
# -----------------------------------------------------------------------------
DARK_THEME = """
/* ============================================================================
   GLOBAL RESET & TYPOGRAPHY SYSTEM
   ============================================================================ */
* {
    font-family: -apple-system, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue',
                 'Segoe UI', 'Roboto', 'Inter', Arial, sans-serif;
    outline: none;
    border: none;
}

QWidget {
    background-color: #0f1115;  /* Deep background */
    color: #e8ecf4;             /* High-legibility text */
    font-size: 13px;
    line-height: 1.5em;
    letter-spacing: -0.01em;    /* Tighter letter spacing for clarity */
    selection-background-color: #007aff; /* Apple blue */
    selection-color: #ffffff;
}

QMainWindow, QDialog, QWizard {
    background-color: #0f1115;
    color: #e8ecf4;
}

/* ============================================================================
   TYPOGRAPHY HIERARCHY (Apple-inspired scale)
   ============================================================================ */
QLabel#page_title {
    font-size: 28px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
    line-height: 1.2em;
    background-color: transparent;
}

QLabel#page_subtitle {
    font-size: 15px;
    color: #98989d;
    margin-top: 4px;
    line-height: 1.4em;
    letter-spacing: -0.08px;
    background-color: transparent;
}

QLabel#brand_title {
    font-size: 17px;
    font-weight: 600;
    color: #ffffff;
    letter-spacing: -0.3px;
    line-height: 1.3em;
    background-color: transparent;
}

QLabel#brand_subtitle {
    color: #8e8e93;
    font-size: 12px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    background-color: transparent;
}

/* ============================================================================
   TOOLTIPS & OVERLAYS
   ============================================================================ */
QToolTip {
    background-color: #2c2c2e;
    color: #f2f2f7;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: 400;
    font-size: 12px;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    max-width: 300px;
}

/* ============================================================================
   MENUS & DROPDOWNS
   ============================================================================ */
QMenu {
    background-color: #2c2c2e;
    color: #f2f2f7;
    border: none;
    border-radius: 10px;
    padding: 8px 0;
    font-size: 13px;
}

QMenu::item {
    padding: 10px 20px;
    border-radius: 6px;
    margin: 2px 8px;
    min-width: 160px;
}

QMenu::item:selected {
    background-color: #3a3a3c;
    color: #ffffff;
}

QStatusBar {
    background: #2c2c2e;
    color: #8e8e93;
    border-top: 0.5px solid rgba(255, 255, 255, 0.08);
    font-size: 12px;
    font-weight: 400;
    letter-spacing: -0.08px;
    padding: 6px 16px;
    min-height: 28px;
}

/* ============================================================================
   LAYOUT SURFACES & CONTAINERS
   ============================================================================ */

/* Sidebar */
QWidget#sidebar_container {
    background-color: #242426; /* Subtle elevation */
    border-right: 0.5px solid rgba(255, 255, 255, 0.08);
}

/* Brand Card */
QFrame#brand_card {
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 18px 20px;
    margin-bottom: 14px;
}

/* User Panel */
QWidget#user_panel {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 16px 18px;
}

/* ============================================================================
   STATUS CHIPS & BADGES (Refined Apple-style)
   ============================================================================ */
QLabel#status_chip {
    padding: 6px 14px;
    border-radius: 20px; /* Pill shape */
    font-size: 11px;
    font-weight: 600;
    color: #f2f2f7;
    background-color: #3a3a3c;
    border: none;
    min-width: 70px;
    text-align: center;
    letter-spacing: 0.18px;
    line-height: 1.3em;
}

QLabel#status_chip[state="ok"] {
    background-color: rgba(52, 199, 89, 0.15);
    color: #34c759;
    border: none;
}

QLabel#status_chip[state="warn"] {
    background-color: rgba(255, 204, 0, 0.15);
    color: #ffcc00;
    border: none;
}

QLabel#status_chip[state="bad"] {
    background-color: rgba(255, 59, 48, 0.15);
    color: #ff3b30;
    border: none;
}

QLabel#status_chip[state="info"] {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
    border: none;
}

QLabel#status_chip[state="pending"] {
    background-color: rgba(255, 204, 0, 0.12);
    color: #ffcc00;
    border: none;
}

QFrame#page_chip {
    background-color: rgba(0, 122, 255, 0.12);
    border: none;
    color: #007aff;
    border-radius: 6px;
    padding: 5px 10px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.18px;
}

/* ============================================================================
   HEADERS & NAVIGATION
   ============================================================================ */
QFrame#global_header {
    background-color: #242426;
    border-bottom: 0.5px solid rgba(255, 255, 255, 0.08);
    padding: 14px 24px;
    min-height: 56px;
}

QLineEdit#global_search {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #f2f2f7;
    font-size: 13px;
    font-weight: 400;
    min-height: 40px;
    letter-spacing: -0.08px;
}

QLineEdit#global_search:focus {
    border: 0.5px solid #007aff;
    background-color: #2c2c2e;
    outline: none;
}

QWidget#content_area {
    background-color: #1c1c1e;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

QSplitter::handle {
    background-color: rgba(255, 255, 255, 0.08);
    width: 1px;
}

QFrame#page_header {
    background-color: transparent;
    border: none;
    padding: 0px 0px 20px 0px;
}

/* Dashboard hero + profile cards */
QFrame#hero_card, QFrame#profile_card {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 22px 28px;
}

QFrame#profile_card QLabel {
    color: #f2f2f7;
}

/* ============================================================================
   NAVIGATION BUTTONS (Refined Apple-style)
   ============================================================================ */
QPushButton#nav_button {
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    color: #8e8e93;
    text-align: left;
    font-weight: 500;
    font-size: 14px;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    min-height: 40px;
}

QPushButton#nav_button:hover {
    background-color: rgba(255, 255, 255, 0.05);
    color: #f2f2f7;
}

QPushButton#nav_button:checked {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
    font-weight: 600;
}

QLabel#nav_section_label {
    color: #636366;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 14px 20px 10px 20px;
    margin-top: 14px;
    letter-spacing: 0.48px;
    line-height: 1.3em;
}

/* ============================================================================
   BUTTONS (Apple-level refinement)
   ============================================================================ */
QPushButton {
    background-color: #3a3a3c;
    border: none;
    border-radius: 10px;
    color: #ffffff;
    padding: 12px 24px;
    min-height: 44px; /* Apple's touch target size */
    font-weight: 500;
    font-size: 15px;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

QPushButton:hover {
    background-color: #48484a;
}

QPushButton:pressed {
    background-color: #2c2c2e;
}

QPushButton:disabled {
    background-color: #2c2c2e;
    color: #636366;
    opacity: 0.5;
}

/* Primary Button (Apple Blue) */
QPushButton[class="primary"], QPushButton#primary_button, QPushButton#quick_action {
    background-color: #007aff;
    color: #ffffff;
    font-weight: 600;
}

QPushButton[class="primary"]:hover, QPushButton#quick_action:hover {
    background-color: #0051d5;
}

QPushButton[class="primary"]:pressed, QPushButton#quick_action:pressed {
    background-color: #0040a8;
}

/* Success Button */
QPushButton[class="success"], QPushButton#success {
    background-color: #34c759;
    color: #ffffff;
    font-weight: 600;
}

QPushButton[class="success"]:hover {
    background-color: #28a745;
}

QPushButton[class="success"]:pressed {
    background-color: #1e7e34;
}

/* Danger Button */
QPushButton[class="danger"], QPushButton#danger, QPushButton#stop_button {
    background-color: #ff3b30;
    color: #ffffff;
    font-weight: 600;
}

QPushButton[class="danger"]:hover {
    background-color: #d70015;
}

QPushButton[class="danger"]:pressed {
    background-color: #b80012;
}

/* Secondary Button */
QPushButton[class="secondary"], QPushButton#secondary {
    background-color: transparent;
    border: 0.5px solid rgba(255, 255, 255, 0.2);
    color: #f2f2f7;
}

QPushButton[class="secondary"]:hover {
    background-color: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.3);
}

/* ============================================================================
   METRIC CARDS (Refined with subtle elevation)
   ============================================================================ */
QFrame#metric_card {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 22px 28px;
}

QFrame#metric_card:hover {
    background-color: #323234;
    border-color: rgba(255, 255, 255, 0.15);
}

QLabel#metric_label {
    color: #8e8e93;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.48px;
    line-height: 1.3em;
    background-color: transparent;
    margin-bottom: 2px;
}

QLabel#metric_value {
    color: #ffffff;
    font-size: 36px;
    font-weight: 700;
    margin-top: 6px;
    letter-spacing: -0.52px;
    line-height: 1.1em;
    background-color: transparent;
}

QLabel#metric_value[color="blue"] { color: #007aff; }
QLabel#metric_value[color="green"] { color: #34c759; }
QLabel#metric_value[color="yellow"] { color: #ffcc00; }
QLabel#metric_value[color="purple"] { color: #af52de; }
QLabel#metric_value[color="red"] { color: #ff3b30; }

QLabel#metric_spark {
    color: #34c759;
    font-size: 13px;
    font-weight: 500;
    margin-top: 6px;
    letter-spacing: -0.08px;
    background-color: transparent;
}

/* Quick actions group */
QGroupBox#actions_group {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    margin-top: 14px;
    padding: 22px 28px 26px 28px;
}

QGroupBox#actions_group::title {
    subcontrol-origin: margin;
    left: 18px;
    padding: 0 10px;
    color: #8e8e93;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

/* ============================================================================
   INPUT FIELDS (Refined Apple-style)
   ============================================================================ */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #f2f2f7;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 400;
    min-height: 40px;
    letter-spacing: -0.08px;
    line-height: 1.45em;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    background-color: #2c2c2e;
    border: 0.5px solid #007aff;
    outline: none;
}

QLineEdit::placeholder, QTextEdit::placeholder {
    color: #636366;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: -0.08px;
}

QComboBox {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #f2f2f7;
    padding: 10px 14px;
    min-height: 40px;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QComboBox:hover {
    border-color: rgba(255, 255, 255, 0.2);
}

QComboBox:focus {
    border-color: #007aff;
}

QComboBox::down-arrow {
    image: none;
    border: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #8e8e93;
    width: 0px;
    height: 0px;
    margin-right: 16px;
    margin-left: 8px;
}

QComboBox QAbstractItemView {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    selection-background-color: rgba(0, 122, 255, 0.2);
    selection-color: #007aff;
    outline: none;
    padding: 6px;
}

QComboBox QAbstractItemView::item {
    padding: 10px 16px;
    border-radius: 6px;
    margin: 2px;
    min-height: 36px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}

QComboBox QAbstractItemView::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

QSpinBox, QDoubleSpinBox {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    color: #f2f2f7;
    padding: 12px 16px;
    font-size: 15px;
    font-weight: 400;
    min-height: 44px;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

/* ============================================================================
   PROGRESS BARS
   ============================================================================ */
QProgressBar {
    background-color: #2c2c2e;
    border: none;
    border-radius: 8px;
    padding: 2px;
    min-height: 6px;
    max-height: 6px;
}

QProgressBar::chunk {
    background-color: #007aff;
    border-radius: 6px;
}

/* ============================================================================
   TABLES (Refined Apple-style)
   ============================================================================ */
QTableWidget {
    background-color: #2c2c2e;
    alternate-background-color: #242426;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    gridline-color: transparent;
    color: #f2f2f7;
    font-size: 14px;
}

QTableWidget::item {
    padding: 14px 18px;
    border-bottom: 0.5px solid rgba(255, 255, 255, 0.05);
    min-height: 48px;
}

QTableWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
}

QTableWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

QHeaderView::section {
    background-color: #242426;
    color: #8e8e93;
    padding: 14px 18px;
    border: none;
    border-bottom: 0.5px solid rgba(255, 255, 255, 0.1);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.48px;
    line-height: 1.3em;
    min-height: 44px;
}

/* ============================================================================
   GROUP BOXES & CARDS
   ============================================================================ */
QGroupBox {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    margin-top: 32px;
    padding: 32px 28px 28px 28px;
    font-weight: 600;
    color: #f2f2f7;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 18px;
    top: -1px;
    padding: 0 12px;
    color: #8e8e93;
    background-color: #1c1c1e;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

/* ============================================================================
   SCROLLBARS (Refined Apple-style)
   ============================================================================ */
QScrollBar:vertical {
    background-color: rgba(255, 255, 255, 0.02);
    width: 14px;
    border: none;
    margin: 4px 0;
    border-radius: 8px;
}

QScrollBar::handle:vertical {
    background-color: rgba(255, 255, 255, 0.28);
    border-radius: 7px;
    min-height: 36px;
    margin: 2px 3px 2px 3px;
    width: 10px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(255, 255, 255, 0.38);
}

QScrollBar::handle:vertical:pressed {
    background-color: rgba(255, 255, 255, 0.46);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
}

QScrollBar:horizontal {
    background-color: rgba(255, 255, 255, 0.02);
    height: 14px;
    border: none;
    margin: 0 4px;
    border-radius: 8px;
}

QScrollBar::handle:horizontal {
    background-color: rgba(255, 255, 255, 0.28);
    border-radius: 7px;
    min-width: 36px;
    margin: 3px 2px 3px 2px;
    height: 10px;
}

QScrollBar::handle:horizontal:hover {
    background-color: rgba(255, 255, 255, 0.38);
}

QScrollBar::handle:horizontal:pressed {
    background-color: rgba(255, 255, 255, 0.46);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
}

/* ============================================================================
   CHECKBOXES & RADIO BUTTONS (Refined Apple-style)
   ============================================================================ */
QCheckBox {
    spacing: 10px;
    font-size: 15px;
    font-weight: 400;
    color: #f2f2f7;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 5px;
    border: 0.5px solid rgba(255, 255, 255, 0.3);
    background-color: #2c2c2e;
    margin-right: 2px;
}

QCheckBox::indicator:hover {
    border-color: rgba(255, 255, 255, 0.5);
    background-color: #323234;
}

QCheckBox::indicator:checked {
    background-color: #007aff;
    border-color: #007aff;
    image: none;
}

QCheckBox::indicator:checked:hover {
    background-color: #0051d5;
    border-color: #0051d5;
}

QCheckBox::indicator:disabled {
    background-color: #242426;
    border-color: rgba(255, 255, 255, 0.1);
    opacity: 0.5;
}

QRadioButton {
    spacing: 10px;
    font-size: 15px;
    font-weight: 400;
    color: #f2f2f7;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QRadioButton::indicator {
    width: 20px;
    height: 20px;
    border-radius: 10px;
    border: 0.5px solid rgba(255, 255, 255, 0.3);
    background-color: #2c2c2e;
    margin-right: 2px;
}

QRadioButton::indicator:hover {
    border-color: rgba(255, 255, 255, 0.5);
    background-color: #323234;
}

QRadioButton::indicator:checked {
    background-color: #007aff;
    border-color: #007aff;
    border-width: 6px;
}

QRadioButton::indicator:checked:hover {
    background-color: #0051d5;
    border-color: #0051d5;
}

QRadioButton::indicator:disabled {
    background-color: #242426;
    border-color: rgba(255, 255, 255, 0.1);
    opacity: 0.5;
}

/* ============================================================================
   SLIDERS (Refined Apple-style)
   ============================================================================ */
QSlider::groove:horizontal {
    background-color: #2c2c2e;
    height: 3px;
    border-radius: 2px;
    margin: 0px;
}

QSlider::handle:horizontal {
    background-color: #007aff;
    width: 18px;
    height: 18px;
    border-radius: 9px;
    margin: -7.5px 0;
    border: 2px solid #2c2c2e;
}

QSlider::handle:horizontal:hover {
    background-color: #0051d5;
}

QSlider::handle:horizontal:pressed {
    background-color: #0040a8;
}

QSlider::groove:vertical {
    background-color: #2c2c2e;
    width: 3px;
    border-radius: 2px;
    margin: 0px;
}

QSlider::handle:vertical {
    background-color: #007aff;
    width: 18px;
    height: 18px;
    border-radius: 9px;
    margin: 0 -7.5px;
    border: 2px solid #2c2c2e;
}

QSlider::handle:vertical:hover {
    background-color: #0051d5;
}

QSlider::handle:vertical:pressed {
    background-color: #0040a8;
}

/* ============================================================================
   TABS (Refined Apple-style)
   ============================================================================ */
QTabWidget::pane {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 12px;
    top: -1px;
}

QTabBar::tab {
    background-color: transparent;
    color: #8e8e93;
    padding: 10px 20px;
    margin-right: 6px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    min-width: 80px;
    min-height: 40px;
}

QTabBar::tab:hover {
    background-color: rgba(255, 255, 255, 0.05);
    color: #f2f2f7;
}

QTabBar::tab:selected {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
    font-weight: 600;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}

/* ============================================================================
   LIST & TREE WIDGETS (Refined Apple-style)
   ============================================================================ */
QListWidget {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    color: #f2f2f7;
    font-size: 14px;
    padding: 4px;
}

QListWidget::item {
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px;
}

QListWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
}

QListWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

QTreeWidget {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    color: #f2f2f7;
    font-size: 14px;
}

QTreeWidget::item {
    padding: 6px;
    border-radius: 6px;
}

QTreeWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
}

QTreeWidget::item:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

QTreeWidget::branch {
    background-color: transparent;
}

QTreeWidget::branch:has-siblings:!adjoins-item {
    border-image: none;
}

QTreeWidget::branch:has-siblings:adjoins-item {
    border-image: none;
}

QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
    border-image: none;
}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    border-image: none;
    image: none;
}

QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {
    border-image: none;
    image: none;
}

/* ============================================================================
   SPINBOX BUTTONS (Refined Apple-style)
   ============================================================================ */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    width: 24px;
    height: 20px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #8e8e93;
    width: 0px;
    height: 0px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    width: 24px;
    height: 20px;
}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8e8e93;
    width: 0px;
    height: 0px;
}

/* ============================================================================
   DIALOGS & MESSAGE BOXES (Refined Apple-style)
   ============================================================================ */
QDialog {
    background-color: #111621;
    color: #e8ecf4;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
}

QMessageBox {
    background-color: #111621;
    color: #e8ecf4;
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}

QMessageBox QLabel {
    color: #e8ecf4;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.5em;
    padding: 8px;
}

QMessageBox QPushButton {
    min-width: 100px;
    padding: 10px 20px;
}

/* ============================================================================
   SETUP WIZARDS (High-contrast modal)
   ============================================================================ */
QWizard {
    background-color: #111621;
    color: #e8ecf4;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 18px;
    padding: 12px;
}

QWizard::title {
    font-size: 22px;
    font-weight: 700;
    color: #e8ecf4;
    margin-bottom: 8px;
    padding: 4px 0;
    letter-spacing: -0.2px;
}

QWizard::subtitle {
    font-size: 14px;
    color: #9ea8ba;
    margin-top: 0px;
    margin-bottom: 12px;
}

QWizard::header {
    background-color: #161a24;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 18px 20px;
}

QWizard::separator {
    background-color: rgba(255, 255, 255, 0.06);
    height: 1px;
}

QWizard QPushButton {
    min-width: 120px;
    padding: 12px 22px;
    border-radius: 12px;
    font-size: 15px;
    font-weight: 600;
}

QWizard QPushButton:default {
    background-color: #007aff;
    color: #ffffff;
}

QWizard QPushButton:default:hover {
    background-color: #1a7dff;
}

QWizard QPushButton:default:pressed {
    background-color: #0f64d4;
}

QWizard QWidget#page_container {
    background-color: #111621;
}

/* ============================================================================
   TOOL BUTTONS (Refined Apple-style)
   ============================================================================ */
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px;
    color: #8e8e93;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: -0.08px;
    min-width: 36px;
    min-height: 36px;
}

QToolButton:hover {
    background-color: rgba(255, 255, 255, 0.05);
    color: #f2f2f7;
}

QToolButton:pressed {
    background-color: rgba(255, 255, 255, 0.1);
}

QToolButton:checked {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
}

/* ============================================================================
   PROGRESS DIALOGS (Refined Apple-style)
   ============================================================================ */
QProgressDialog {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px 28px;
}

QProgressDialog QLabel {
    color: #f2f2f7;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.5em;
    padding: 4px 0;
}

QProgressDialog QPushButton {
    min-width: 100px;
    padding: 10px 20px;
}

/* ============================================================================
   FORM LAYOUTS (Refined spacing)
   ============================================================================ */
QFormLayout {
    spacing: 12px;
}

QFormLayout QLabel {
    color: #f2f2f7;
    font-size: 14px;
    font-weight: 500;
    padding-right: 12px;
}

/* ============================================================================
   SPLITTER HANDLES (Enhanced)
   ============================================================================ */
QSplitter::handle:horizontal {
    background-color: rgba(255, 255, 255, 0.08);
    width: 1px;
}

QSplitter::handle:vertical {
    background-color: rgba(255, 255, 255, 0.08);
    height: 1px;
}

QSplitter::handle:hover {
    background-color: rgba(255, 255, 255, 0.12);
}

/* ============================================================================
   TOAST NOTIFICATIONS (Refined Apple-style)
   ============================================================================ */
QLabel#toast {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 14px 20px;
    color: #f2f2f7;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    min-width: 200px;
    max-width: 400px;
}

QLabel#toast[variant="success"] {
    background-color: rgba(52, 199, 89, 0.15);
    border-color: rgba(52, 199, 89, 0.3);
    color: #34c759;
}

QLabel#toast[variant="error"] {
    background-color: rgba(255, 59, 48, 0.15);
    border-color: rgba(255, 59, 48, 0.3);
    color: #ff3b30;
}

QLabel#toast[variant="warning"] {
    background-color: rgba(255, 204, 0, 0.15);
    border-color: rgba(255, 204, 0, 0.3);
    color: #ffcc00;
}

QLabel#toast[variant="info"] {
    background-color: rgba(0, 122, 255, 0.15);
    border-color: rgba(0, 122, 255, 0.3);
    color: #007aff;
}

/* ============================================================================
   INPUT VALIDATION STATES (Refined Apple-style)
   ============================================================================ */
QLineEdit:invalid, QTextEdit:invalid, QPlainTextEdit:invalid {
    border: 0.5px solid #ff3b30;
    background-color: rgba(255, 59, 48, 0.05);
}

QLineEdit:valid, QTextEdit:valid, QPlainTextEdit:valid {
    border: 0.5px solid #34c759;
}

/* ============================================================================
   LOADING OVERLAYS (Refined Apple-style)
   ============================================================================ */
LoadingOverlay {
    background-color: rgba(28, 28, 30, 0.85);
}

/* ============================================================================
   VALIDATION FEEDBACK (Refined Apple-style)
   ============================================================================ */
QLabel[class="validation_error"] {
    color: #ff3b30;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 0;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

QLabel[class="validation_success"] {
    color: #34c759;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 0;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

QLabel[class="validation_warning"] {
    color: #ffcc00;
    font-size: 13px;
    font-weight: 500;
    padding: 6px 0;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

/* ============================================================================
   EMPTY STATES (Enhanced)
   ============================================================================ */
QFrame#empty_state {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 56px 40px;
}

QLabel#empty_state_icon {
    font-size: 72px;
    color: #636366;
    background-color: transparent;
    padding: 20px;
}

QLabel#empty_state_title {
    font-size: 20px;
    font-weight: 700;
    color: #8e8e93;
    letter-spacing: -0.3px;
    line-height: 1.3em;
    background-color: transparent;
    margin-top: 20px;
}

QLabel#empty_state_message {
    font-size: 15px;
    font-weight: 400;
    color: #636366;
    letter-spacing: -0.08px;
    line-height: 1.5em;
    background-color: transparent;
    margin-top: 12px;
}

/* ============================================================================
   ERROR DIALOGS (Refined Apple-style)
   ============================================================================ */
QDialog[class="error_dialog"] {
    background-color: #1c1c1e;
    border-radius: 16px;
}

QDialog[class="error_dialog"] QLabel {
    color: #f2f2f7;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QDialog[class="error_dialog"] QTextEdit {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 12px 16px;
    color: #f2f2f7;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QDialog[class="error_dialog"] QLabel[class="error_title"] {
    color: #ff3b30;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.3px;
}

QDialog[class="error_dialog"] QLabel[class="error_icon"] {
    font-size: 48px;
    color: #ff3b30;
    padding: 10px;
}

/* ============================================================================
   SUCCESS STATES (Refined Apple-style)
   ============================================================================ */
QLabel[class="success_message"] {
    color: #34c759;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -0.08px;
    line-height: 1.5em;
    padding: 12px 16px;
    background-color: rgba(52, 199, 89, 0.1);
    border: 0.5px solid rgba(52, 199, 89, 0.2);
    border-radius: 10px;
}

/* ============================================================================
   WARNING STATES (Refined Apple-style)
   ============================================================================ */
QLabel[class="warning_message"] {
    color: #ffcc00;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -0.08px;
    line-height: 1.5em;
    padding: 12px 16px;
    background-color: rgba(255, 204, 0, 0.1);
    border: 0.5px solid rgba(255, 204, 0, 0.2);
    border-radius: 10px;
}

/* ============================================================================
   INFO STATES (Refined Apple-style)
   ============================================================================ */
QLabel[class="info_message"] {
    color: #007aff;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -0.08px;
    padding: 12px 16px;
    background-color: rgba(0, 122, 255, 0.1);
    border: 0.5px solid rgba(0, 122, 255, 0.2);
    border-radius: 10px;
}

/* ============================================================================
   FOCUS INDICATORS & KEYBOARD NAVIGATION (Accessibility)
   ============================================================================ */
QWidget:focus {
    outline: none;
}

QPushButton:focus {
    outline: 2px solid rgba(0, 122, 255, 0.5);
    outline-offset: 2px;
}

QComboBox:focus {
    outline: 2px solid rgba(0, 122, 255, 0.5);
    outline-offset: 2px;
}

QCheckBox:focus, QRadioButton:focus {
    outline: 2px solid rgba(0, 122, 255, 0.5);
    outline-offset: 2px;
}

/* ============================================================================
   HELP TEXT & HINTS (Refined Apple-style)
   ============================================================================ */
QLabel[class="help_text"] {
    color: #8e8e93;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    padding: 4px 0;
}

QLabel[class="hint_text"] {
    color: #636366;
    font-size: 12px;
    font-weight: 400;
    letter-spacing: -0.08px;
    font-style: italic;
    padding: 2px 0;
}

/* ============================================================================
   DISABLED STATE CONSISTENCY
   ============================================================================ */
QWidget:disabled {
    opacity: 0.5;
}

QPushButton:disabled {
}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    background-color: #242426;
    color: #636366;
}

QComboBox:disabled {
    background-color: #242426;
    color: #636366;
}

/* ============================================================================
   SEPARATORS & DIVIDERS (Refined Apple-style)
   ============================================================================ */
QFrame[class="separator"] {
    background-color: rgba(255, 255, 255, 0.1);
    max-height: 1px;
    min-height: 1px;
}

QFrame[class="divider"] {
    background-color: rgba(255, 255, 255, 0.08);
    max-width: 1px;
    min-width: 1px;
}

/* ============================================================================
   BADGES & LABELS (Refined Apple-style)
   ============================================================================ */
QLabel[class="badge"] {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.18px;
    background-color: #3a3a3c;
    color: #f2f2f7;
}

QLabel[class="badge"][variant="primary"] {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
}

QLabel[class="badge"][variant="success"] {
    background-color: rgba(52, 199, 89, 0.15);
    color: #34c759;
}

QLabel[class="badge"][variant="warning"] {
    background-color: rgba(255, 204, 0, 0.15);
    color: #ffcc00;
}

QLabel[class="badge"][variant="danger"] {
    background-color: rgba(255, 59, 48, 0.15);
    color: #ff3b30;
}

/* ============================================================================
   PAGINATION CONTROLS (Refined Apple-style)
   ============================================================================ */
QWidget[class="pagination"] {
    background-color: transparent;
    padding: 8px 0;
}

QWidget[class="pagination"] QPushButton {
    min-width: 80px;
    padding: 8px 16px;
    font-size: 14px;
}

QWidget[class="pagination"] QLabel {
    color: #8e8e93;
    font-size: 14px;
    font-weight: 500;
    padding: 0 12px;
    letter-spacing: -0.08px;
}

QWidget[class="pagination"] QLabel[class="page_info"] {
    color: #636366;
    font-size: 13px;
}

/* ============================================================================
   SEARCH INPUTS & HIGHLIGHTING (Refined Apple-style)
   ============================================================================ */
QLineEdit[class="search_input"] {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #f2f2f7;
    font-size: 14px;
    min-height: 40px;
}

QLineEdit[class="search_input"]:focus {
    border: 0.5px solid #007aff;
    background-color: #2c2c2e;
}

QLineEdit[class="search_input"]::placeholder {
    color: #636366;
}

/* Search results highlighting */
QTableWidget::item[class="search_match"] {
    background-color: rgba(0, 122, 255, 0.1);
    color: #007aff;
}

/* ============================================================================
   FILTER CHIPS & TAGS (Refined Apple-style)
   ============================================================================ */
QPushButton[class="filter_chip"] {
    background-color: #3a3a3c;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
    color: #f2f2f7;
    min-height: 28px;
    letter-spacing: -0.08px;
}

QPushButton[class="filter_chip"]:hover {
    background-color: #48484a;
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton[class="filter_chip"]:checked {
    background-color: rgba(0, 122, 255, 0.15);
    border-color: #007aff;
    color: #007aff;
}

QPushButton[class="filter_chip"]::close-button {
    image: none;
    border: none;
    width: 16px;
    height: 16px;
    border-radius: 8px;
    background-color: rgba(255, 255, 255, 0.2);
    margin-left: 8px;
}

QPushButton[class="filter_chip"]::close-button:hover {
    background-color: rgba(255, 255, 255, 0.3);
}

/* ============================================================================
   TABLE SORTING INDICATORS (Refined Apple-style)
   ============================================================================ */
QHeaderView::section[class="sortable"] {
    padding-right: 24px;
}

QHeaderView::section[class="sorted_asc"]::indicator {
    image: none;
    border: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #007aff;
    width: 0px;
    height: 0px;
    margin-right: 8px;
}

QHeaderView::section[class="sorted_desc"]::indicator {
    image: none;
    border: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #007aff;
    width: 0px;
    height: 0px;
    margin-right: 8px;
}

/* ============================================================================
   CHART CONTAINERS (Refined Apple-style)
   ============================================================================ */
QWidget[class="chart_container"] {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 20px;
}

QWidget[class="chart_container"] QLabel[class="chart_title"] {
    color: #f2f2f7;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.2px;
    padding-bottom: 12px;
}

QWidget[class="chart_container"] QLabel[class="chart_subtitle"] {
    color: #8e8e93;
    font-size: 13px;
    padding-bottom: 16px;
}

/* ============================================================================
   MODAL OVERLAYS (Refined Apple-style)
   ============================================================================ */
QWidget[class="modal_overlay"] {
    background-color: rgba(28, 28, 30, 0.6);
}

QDialog[class="modal"] {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px;
}

QDialog[class="modal"] QLabel[class="modal_title"] {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.3px;
    padding-bottom: 8px;
}

QDialog[class="modal"] QLabel[class="modal_message"] {
    color: #8e8e93;
    font-size: 15px;
    letter-spacing: -0.08px;
    line-height: 1.5em;
    padding-bottom: 20px;
}

/* ============================================================================
   SKELETON LOADERS (Refined Apple-style)
   ============================================================================ */
QWidget[class="skeleton"] {
    background-color: #3a3a3c;
    border-radius: 8px;
    min-height: 20px;
}

QWidget[class="skeleton"][variant="text"] {
    background: linear-gradient(90deg, #3a3a3c 0%, #48484a 50%, #3a3a3c 100%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

QWidget[class="skeleton"][variant="circle"] {
    border-radius: 50%;
    min-width: 40px;
    min-height: 40px;
}

QWidget[class="skeleton"][variant="rect"] {
    border-radius: 8px;
}

/* ============================================================================
   DRAG & DROP STATES (Refined Apple-style)
   ============================================================================ */
QWidget[class="drag_target"] {
    border: 2px dashed rgba(0, 122, 255, 0.5);
    border-radius: 12px;
    background-color: rgba(0, 122, 255, 0.05);
}

QWidget[class="drag_target"][state="drag_over"] {
    border-color: #007aff;
    background-color: rgba(0, 122, 255, 0.1);
}

QWidget[class="drag_target"][state="drag_reject"] {
    border-color: #ff3b30;
    background-color: rgba(255, 59, 48, 0.05);
}

/* ============================================================================
   MULTI-SELECT STATES (Refined Apple-style)
   ============================================================================ */
QTableWidget::item[class="multi_selected"] {
    background-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}

QListWidget::item[class="multi_selected"] {
    background-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}

QTreeWidget::item[class="multi_selected"] {
    background-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}
"""

# -----------------------------------------------------------------------------
# APPLE-LEVEL LIGHT THEME
# -----------------------------------------------------------------------------
LIGHT_THEME = """
/* ============================================================================
   GLOBAL RESET & TYPOGRAPHY SYSTEM
   ============================================================================ */
* {
    font-family: -apple-system, 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue',
                 'Segoe UI', 'Roboto', 'Inter', Arial, sans-serif;
    outline: none;
    border: none;
}

QWidget {
    background-color: #f5f5f7;  /* Apple light gray */
    color: #1d1d1f;             /* Apple dark text */
    font-size: 13px;
    line-height: 1.5em;
    letter-spacing: -0.01em;
    selection-background-color: #007aff;
    selection-color: #ffffff;
}

QMainWindow, QDialog, QWizard {
    background-color: #f5f5f7;
    color: #1d1d1f;
}

/* ============================================================================
   TYPOGRAPHY HIERARCHY
   ============================================================================ */
QLabel#page_title {
    font-size: 28px;
    font-weight: 700;
    color: #1d1d1f;
    letter-spacing: -0.5px;
    line-height: 1.2em;
    background-color: transparent;
}

QLabel#page_subtitle {
    font-size: 15px;
    color: #6e6e73;
    margin-top: 4px;
    line-height: 1.4em;
    letter-spacing: -0.08px;
    background-color: transparent;
}

QLabel#brand_title {
    font-size: 17px;
    font-weight: 600;
    color: #1d1d1f;
    letter-spacing: -0.3px;
    line-height: 1.3em;
    background-color: transparent;
}

QLabel#brand_subtitle {
    color: #6e6e73;
    font-size: 12px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    background-color: transparent;
}

/* ============================================================================
   TOOLTIPS & OVERLAYS
   ============================================================================ */
QToolTip {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: 400;
    font-size: 12px;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    max-width: 300px;
}

/* ============================================================================
   MENUS & DROPDOWNS
   ============================================================================ */
QMenu {
    background-color: #ffffff;
    color: #1d1d1f;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    padding: 8px 0;
    font-size: 13px;
}

QMenu::item {
    padding: 10px 20px;
    border-radius: 6px;
    margin: 2px 8px;
    min-width: 160px;
}

QMenu::item:selected {
    background-color: #f5f5f7;
    color: #1d1d1f;
}

QStatusBar {
    background: #ffffff;
    color: #6e6e73;
    border-top: 0.5px solid rgba(0, 0, 0, 0.08);
    font-size: 12px;
    font-weight: 400;
    letter-spacing: -0.08px;
    padding: 6px 16px;
    min-height: 28px;
}

/* ============================================================================
   LAYOUT SURFACES & CONTAINERS
   ============================================================================ */
QWidget#sidebar_container {
    background-color: #ffffff;
    border-right: 0.5px solid rgba(0, 0, 0, 0.1);
}

QFrame#brand_card {
    background-color: transparent;
    border: none;
    border-radius: 0px;
    padding: 18px 20px;
    margin-bottom: 14px;
}

QWidget#user_panel {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    padding: 16px 18px;
}

/* ============================================================================
   STATUS CHIPS & BADGES
   ============================================================================ */
QLabel#status_chip {
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    color: #1d1d1f;
    background-color: #e5e5ea;
    border: none;
    min-width: 70px;
    text-align: center;
    letter-spacing: 0.18px;
    line-height: 1.3em;
}

QLabel#status_chip[state="ok"] {
    background-color: rgba(52, 199, 89, 0.15);
    color: #28a745;
    border: none;
}

QLabel#status_chip[state="warn"] {
    background-color: rgba(255, 204, 0, 0.15);
    color: #ff9500;
    border: none;
}

QLabel#status_chip[state="bad"] {
    background-color: rgba(255, 59, 48, 0.15);
    color: #d70015;
    border: none;
}

QLabel#status_chip[state="info"] {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
    border: none;
}

QLabel#status_chip[state="pending"] {
    background-color: rgba(255, 204, 0, 0.12);
    color: #ff9500;
    border: none;
}

QFrame#page_chip {
    background-color: rgba(0, 122, 255, 0.12);
    border: none;
    color: #007aff;
    border-radius: 6px;
    padding: 5px 10px;
    font-weight: 600;
    font-size: 11px;
    letter-spacing: 0.18px;
}

/* ============================================================================
   HEADERS & NAVIGATION
   ============================================================================ */
QFrame#global_header {
    background-color: #ffffff;
    border-bottom: 0.5px solid rgba(0, 0, 0, 0.08);
    padding: 14px 24px;
    min-height: 56px;
}

QLineEdit#global_search {
    background-color: #f5f5f7;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #1d1d1f;
    font-size: 13px;
    font-weight: 400;
    min-height: 40px;
    letter-spacing: -0.08px;
}

QLineEdit#global_search:focus {
    border: 0.5px solid #007aff;
    background-color: #ffffff;
    outline: none;
}

QWidget#content_area {
    background-color: #f5f5f7;
}

QScrollArea {
    background: transparent;
    border: none;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

QSplitter::handle {
    background-color: rgba(0, 0, 0, 0.1);
    width: 1px;
}

QFrame#page_header {
    background-color: transparent;
    border: none;
    padding: 0px 0px 20px 0px;
}

QFrame#hero_card, QFrame#profile_card {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 16px;
    padding: 22px 28px;
}

QFrame#profile_card QLabel {
    color: #1d1d1f;
}

/* ============================================================================
   NAVIGATION BUTTONS
   ============================================================================ */
QPushButton#nav_button {
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    color: #6e6e73;
    text-align: left;
    font-weight: 500;
    font-size: 14px;
    letter-spacing: -0.08px;
    min-height: 40px;
}

QPushButton#nav_button:hover {
    background-color: rgba(0, 0, 0, 0.05);
    color: #1d1d1f;
}

QPushButton#nav_button:checked {
    background-color: rgba(0, 122, 255, 0.12);
    color: #007aff;
    font-weight: 600;
}

QLabel#nav_section_label {
    color: #8e8e93;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    padding: 14px 20px 10px 20px;
    margin-top: 14px;
    letter-spacing: 0.48px;
    line-height: 1.3em;
}

/* ============================================================================
   BUTTONS
   ============================================================================ */
QPushButton {
    background-color: #e5e5ea;
    border: none;
    border-radius: 10px;
    color: #1d1d1f;
    padding: 12px 24px;
    min-height: 44px;
    font-weight: 500;
    font-size: 15px;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

QPushButton:hover {
    background-color: #d1d1d6;
}

QPushButton:pressed {
    background-color: #c7c7cc;
}

QPushButton:disabled {
    background-color: #f5f5f7;
    color: #8e8e93;
    opacity: 0.5;
}

/* Primary Button */
QPushButton[class="primary"], QPushButton#primary_button, QPushButton#quick_action {
    background-color: #007aff;
    color: #ffffff;
    font-weight: 600;
}

QPushButton[class="primary"]:hover, QPushButton#quick_action:hover {
    background-color: #0051d5;
}

QPushButton[class="primary"]:pressed, QPushButton#quick_action:pressed {
    background-color: #0040a8;
}

/* Success Button */
QPushButton[class="success"], QPushButton#success {
    background-color: #34c759;
    color: #ffffff;
    font-weight: 600;
}

QPushButton[class="success"]:hover {
    background-color: #28a745;
}

QPushButton[class="success"]:pressed {
    background-color: #1e7e34;
}

/* Danger Button */
QPushButton[class="danger"], QPushButton#danger, QPushButton#stop_button {
    background-color: #ff3b30;
    color: #ffffff;
    font-weight: 600;
}

QPushButton[class="danger"]:hover {
    background-color: #d70015;
}

QPushButton[class="danger"]:pressed {
    background-color: #b80012;
}

/* Secondary Button */
QPushButton[class="secondary"], QPushButton#secondary {
    background-color: transparent;
    border: 0.5px solid rgba(0, 0, 0, 0.2);
    color: #1d1d1f;
}

QPushButton[class="secondary"]:hover {
    background-color: rgba(0, 0, 0, 0.05);
    border-color: rgba(0, 0, 0, 0.3);
}

/* ============================================================================
   METRIC CARDS
   ============================================================================ */
QFrame#metric_card {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 14px;
    padding: 22px 28px;
}

QFrame#metric_card:hover {
    background-color: #fafafa;
    border-color: rgba(0, 0, 0, 0.15);
}

QLabel#metric_label {
    color: #6e6e73;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.48px;
    line-height: 1.3em;
    background-color: transparent;
    margin-bottom: 2px;
}

QLabel#metric_value {
    color: #1d1d1f;
    font-size: 36px;
    font-weight: 700;
    margin-top: 6px;
    letter-spacing: -0.52px;
    line-height: 1.1em;
    background-color: transparent;
}

QLabel#metric_value[color="blue"] { color: #007aff; }
QLabel#metric_value[color="green"] { color: #34c759; }
QLabel#metric_value[color="yellow"] { color: #ff9500; }
QLabel#metric_value[color="purple"] { color: #af52de; }
QLabel#metric_value[color="red"] { color: #ff3b30; }

QLabel#metric_spark {
    color: #34c759;
    font-size: 13px;
    font-weight: 500;
    margin-top: 6px;
    letter-spacing: -0.08px;
    background-color: transparent;
}

QGroupBox#actions_group {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 14px;
    margin-top: 14px;
    padding: 22px 28px 26px 28px;
}

QGroupBox#actions_group::title {
    subcontrol-origin: margin;
    left: 18px;
    padding: 0 10px;
    color: #6e6e73;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.08px;
    line-height: 1.4em;
}

/* ============================================================================
   INPUT FIELDS
   ============================================================================ */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    color: #1d1d1f;
    padding: 10px 14px;
    font-size: 14px;
    font-weight: 400;
    min-height: 40px;
    letter-spacing: -0.08px;
    line-height: 1.45em;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    background-color: #ffffff;
    border: 0.5px solid #007aff;
    outline: none;
}

QLineEdit::placeholder, QTextEdit::placeholder {
    color: #8e8e93;
    font-size: 15px;
    font-weight: 400;
    letter-spacing: -0.08px;
}

QComboBox {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    color: #1d1d1f;
    padding: 10px 14px;
    min-height: 40px;
    font-size: 14px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QComboBox:hover {
    border-color: rgba(0, 0, 0, 0.2);
}

QComboBox:focus {
    border-color: #007aff;
}

QComboBox::down-arrow {
    image: none;
    border: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #6e6e73;
    width: 0px;
    height: 0px;
    margin-right: 16px;
    margin-left: 8px;
}

QComboBox QAbstractItemView {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    selection-background-color: rgba(0, 122, 255, 0.1);
    selection-color: #007aff;
    outline: none;
    padding: 6px;
}

QComboBox QAbstractItemView::item {
    padding: 10px 16px;
    border-radius: 6px;
    margin: 2px;
    min-height: 36px;
}

QComboBox QAbstractItemView::item:selected {
    background-color: rgba(0, 122, 255, 0.1);
    color: #007aff;
}

QComboBox QAbstractItemView::item:hover {
    background-color: rgba(0, 0, 0, 0.05);
}

QSpinBox, QDoubleSpinBox {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    color: #1d1d1f;
    padding: 12px 16px;
    font-size: 15px;
    font-weight: 400;
    min-height: 44px;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

/* ============================================================================
   PROGRESS BARS
   ============================================================================ */
QProgressBar {
    background-color: #e5e5ea;
    border: none;
    border-radius: 8px;
    padding: 2px;
    min-height: 6px;
    max-height: 6px;
}

QProgressBar::chunk {
    background-color: #007aff;
    border-radius: 5px;
    margin: 0.5px;
}

/* ============================================================================
   TABLES
   ============================================================================ */
QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #fafafa;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    gridline-color: transparent;
    color: #1d1d1f;
    font-size: 14px;
}

QTableWidget::item {
    padding: 14px 18px;
    border-bottom: 0.5px solid rgba(0, 0, 0, 0.05);
}

QTableWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.1);
    color: #007aff;
}

QTableWidget::item:hover {
    background-color: rgba(0, 0, 0, 0.03);
}

QHeaderView::section {
    background-color: #fafafa;
    color: #6e6e73;
    padding: 14px 18px;
    border: none;
    border-bottom: 0.5px solid rgba(0, 0, 0, 0.1);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
    letter-spacing: 0.48px;
}

/* ============================================================================
   GROUP BOXES & CARDS
   ============================================================================ */
QGroupBox {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 14px;
    margin-top: 28px;
    padding: 28px 24px 24px 24px;
    font-weight: 600;
    color: #1d1d1f;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    top: 0px;
    padding: 0 10px;
    color: #6e6e73;
    background-color: #f5f5f7;
    font-size: 13px;
    font-weight: 600;
    letter-spacing: -0.08px;
}

/* ============================================================================
   SCROLLBARS (Refined Apple-style)
   ============================================================================ */
QScrollBar:vertical {
    background-color: transparent;
    width: 12px;
    border: none;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(0, 0, 0, 0.3);
}

QScrollBar::handle:vertical:pressed {
    background-color: rgba(0, 0, 0, 0.4);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    width: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 12px;
    border: none;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background-color: rgba(0, 0, 0, 0.2);
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: rgba(0, 0, 0, 0.3);
}

QScrollBar::handle:horizontal:pressed {
    background-color: rgba(0, 0, 0, 0.4);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    height: 0px;
    width: 0px;
}

/* ============================================================================
   CHECKBOXES & RADIO BUTTONS (Refined Apple-style)
   ============================================================================ */
QCheckBox {
    spacing: 10px;
    font-size: 15px;
    color: #1d1d1f;
    letter-spacing: -0.08px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    border-radius: 6px;
    border: 0.5px solid rgba(0, 0, 0, 0.2);
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: rgba(0, 0, 0, 0.4);
    background-color: #fafafa;
}

QCheckBox::indicator:checked {
    background-color: #007aff;
    border-color: #007aff;
    image: none;
}

QCheckBox::indicator:checked:hover {
    background-color: #0051d5;
    border-color: #0051d5;
}

QCheckBox::indicator:disabled {
    background-color: #f5f5f7;
    border-color: rgba(0, 0, 0, 0.1);
    opacity: 0.5;
}

QRadioButton {
    spacing: 10px;
    font-size: 15px;
    color: #1d1d1f;
    letter-spacing: -0.08px;
}

QRadioButton::indicator {
    width: 20px;
    height: 20px;
    border-radius: 10px;
    border: 0.5px solid rgba(0, 0, 0, 0.2);
    background-color: #ffffff;
}

QRadioButton::indicator:hover {
    border-color: rgba(0, 0, 0, 0.4);
    background-color: #fafafa;
}

QRadioButton::indicator:checked {
    background-color: #007aff;
    border-color: #007aff;
    border-width: 6px;
}

QRadioButton::indicator:checked:hover {
    background-color: #0051d5;
    border-color: #0051d5;
}

QRadioButton::indicator:disabled {
    background-color: #f5f5f7;
    border-color: rgba(0, 0, 0, 0.1);
    opacity: 0.5;
}

/* ============================================================================
   SLIDERS (Refined Apple-style)
   ============================================================================ */
QSlider::groove:horizontal {
    background-color: #e5e5ea;
    height: 4px;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background-color: #007aff;
    width: 20px;
    height: 20px;
    border-radius: 10px;
    margin: -8px 0;
    border: none;
}

QSlider::handle:horizontal:hover {
    background-color: #0051d5;
}

QSlider::handle:horizontal:pressed {
    background-color: #0040a8;
}

QSlider::groove:vertical {
    background-color: #e5e5ea;
    width: 4px;
    border-radius: 2px;
}

QSlider::handle:vertical {
    background-color: #007aff;
    width: 20px;
    height: 20px;
    border-radius: 10px;
    margin: 0 -8px;
    border: none;
}

QSlider::handle:vertical:hover {
    background-color: #0051d5;
}

QSlider::handle:vertical:pressed {
    background-color: #0040a8;
}

/* ============================================================================
   TABS (Refined Apple-style)
   ============================================================================ */
QTabWidget::pane {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    padding: 8px;
}

QTabBar::tab {
    background-color: transparent;
    color: #6e6e73;
    padding: 10px 20px;
    margin-right: 4px;
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: -0.08px;
    min-width: 80px;
}

QTabBar::tab:hover {
    background-color: rgba(0, 0, 0, 0.05);
    color: #1d1d1f;
}

QTabBar::tab:selected {
    background-color: rgba(0, 122, 255, 0.12);
    color: #007aff;
    font-weight: 600;
}

QTabBar::tab:!selected {
    margin-top: 2px;
}

/* ============================================================================
   LIST & TREE WIDGETS (Refined Apple-style)
   ============================================================================ */
QListWidget {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    color: #1d1d1f;
    font-size: 14px;
    padding: 4px;
}

QListWidget::item {
    padding: 10px 14px;
    border-radius: 8px;
    margin: 2px;
}

QListWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.1);
    color: #007aff;
}

QListWidget::item:hover {
    background-color: rgba(0, 0, 0, 0.03);
}

QTreeWidget {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    color: #1d1d1f;
    font-size: 14px;
}

QTreeWidget::item {
    padding: 6px;
    border-radius: 6px;
}

QTreeWidget::item:selected {
    background-color: rgba(0, 122, 255, 0.1);
    color: #007aff;
}

QTreeWidget::item:hover {
    background-color: rgba(0, 0, 0, 0.03);
}

QTreeWidget::branch {
    background-color: transparent;
}

QTreeWidget::branch:has-siblings:!adjoins-item {
    border-image: none;
}

QTreeWidget::branch:has-siblings:adjoins-item {
    border-image: none;
}

QTreeWidget::branch:!has-children:!has-siblings:adjoins-item {
    border-image: none;
}

QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {
    border-image: none;
    image: none;
}

QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {
    border-image: none;
    image: none;
}

/* ============================================================================
   SPINBOX BUTTONS (Refined Apple-style)
   ============================================================================ */
QSpinBox::up-button, QDoubleSpinBox::up-button {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    width: 24px;
    height: 20px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
    background-color: rgba(0, 0, 0, 0.05);
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #6e6e73;
    width: 0px;
    height: 0px;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    width: 24px;
    height: 20px;
}

QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: rgba(0, 0, 0, 0.05);
}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #6e6e73;
    width: 0px;
    height: 0px;
}

/* ============================================================================
   DIALOGS & MESSAGE BOXES (Refined Apple-style)
   ============================================================================ */
QDialog {
    background-color: #f5f5f7;
    color: #1d1d1f;
}

QMessageBox {
    background-color: #f5f5f7;
    color: #1d1d1f;
}

QMessageBox QLabel {
    color: #1d1d1f;
    font-size: 15px;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QMessageBox QPushButton {
    min-width: 100px;
    padding: 10px 20px;
}

/* ============================================================================
   TOOL BUTTONS (Refined Apple-style)
   ============================================================================ */
QToolButton {
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 8px;
    color: #6e6e73;
    font-size: 14px;
}

QToolButton:hover {
    background-color: rgba(0, 0, 0, 0.05);
    color: #1d1d1f;
}

QToolButton:pressed {
    background-color: rgba(0, 0, 0, 0.1);
}

QToolButton:checked {
    background-color: rgba(0, 122, 255, 0.12);
    color: #007aff;
}

/* ============================================================================
   PROGRESS DIALOGS (Refined Apple-style)
   ============================================================================ */
QProgressDialog {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    padding: 20px;
}

QProgressDialog QLabel {
    color: #1d1d1f;
    font-size: 15px;
    letter-spacing: -0.08px;
}

QProgressDialog QPushButton {
    min-width: 100px;
    padding: 10px 20px;
}

/* ============================================================================
   FORM LAYOUTS (Refined spacing)
   ============================================================================ */
QFormLayout {
    spacing: 12px;
}

QFormLayout QLabel {
    color: #1d1d1f;
    font-size: 14px;
    font-weight: 500;
    padding-right: 12px;
}

/* ============================================================================
   SPLITTER HANDLES (Enhanced)
   ============================================================================ */
QSplitter::handle:horizontal {
    background-color: rgba(0, 0, 0, 0.1);
    width: 1px;
}

QSplitter::handle:vertical {
    background-color: rgba(0, 0, 0, 0.1);
    height: 1px;
}

QSplitter::handle:hover {
    background-color: rgba(0, 0, 0, 0.15);
}

/* ============================================================================
   TOAST NOTIFICATIONS (Refined Apple-style)
   ============================================================================ */
QLabel#toast {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 12px;
    padding: 12px 20px;
    color: #1d1d1f;
    font-size: 14px;
    font-weight: 500;
    letter-spacing: -0.08px;
    min-width: 200px;
    max-width: 400px;
}

QLabel#toast[variant="success"] {
    background-color: rgba(52, 199, 89, 0.1);
    border-color: rgba(52, 199, 89, 0.2);
    color: #28a745;
}

QLabel#toast[variant="error"] {
    background-color: rgba(255, 59, 48, 0.1);
    border-color: rgba(255, 59, 48, 0.2);
    color: #d70015;
}

QLabel#toast[variant="warning"] {
    background-color: rgba(255, 204, 0, 0.1);
    border-color: rgba(255, 204, 0, 0.2);
    color: #ff9500;
}

QLabel#toast[variant="info"] {
    background-color: rgba(0, 122, 255, 0.1);
    border-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}

/* ============================================================================
   INPUT VALIDATION STATES (Refined Apple-style)
   ============================================================================ */
QLineEdit:invalid, QTextEdit:invalid, QPlainTextEdit:invalid {
    border: 0.5px solid #ff3b30;
    background-color: rgba(255, 59, 48, 0.05);
}

QLineEdit:valid, QTextEdit:valid, QPlainTextEdit:valid {
    border: 0.5px solid #34c759;
}

/* ============================================================================
   LOADING OVERLAYS (Refined Apple-style)
   ============================================================================ */
LoadingOverlay {
    background-color: rgba(245, 245, 247, 0.85);
}

/* ============================================================================
   VALIDATION FEEDBACK (Refined Apple-style)
   ============================================================================ */
QLabel[class="validation_error"] {
    color: #ff3b30;
    font-size: 13px;
    font-weight: 500;
    padding: 4px 0;
    letter-spacing: -0.08px;
}

QLabel[class="validation_success"] {
    color: #34c759;
    font-size: 13px;
    font-weight: 500;
    padding: 4px 0;
    letter-spacing: -0.08px;
}

QLabel[class="validation_warning"] {
    color: #ff9500;
    font-size: 13px;
    font-weight: 500;
    padding: 4px 0;
    letter-spacing: -0.08px;
}

/* ============================================================================
   EMPTY STATES (Enhanced)
   ============================================================================ */
QFrame#empty_state {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 16px;
    padding: 56px 40px;
}

QLabel#empty_state_icon {
    font-size: 72px;
    color: #8e8e93;
    background-color: transparent;
    padding: 20px;
}

QLabel#empty_state_title {
    font-size: 20px;
    font-weight: 700;
    color: #6e6e73;
    letter-spacing: -0.3px;
    line-height: 1.3em;
    background-color: transparent;
    margin-top: 20px;
}

QLabel#empty_state_message {
    font-size: 15px;
    color: #8e8e93;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    background-color: transparent;
    margin-top: 10px;
}

/* ============================================================================
   ERROR DIALOGS (Refined Apple-style)
   ============================================================================ */
QDialog[class="error_dialog"] {
    background-color: #f5f5f7;
    border-radius: 16px;
}

QDialog[class="error_dialog"] QLabel {
    color: #1d1d1f;
    font-size: 15px;
    letter-spacing: -0.08px;
    line-height: 1.5em;
}

QDialog[class="error_dialog"] QTextEdit {
    background-color: #ffffff;
    border: 0.5px solid rgba(0, 0, 0, 0.1);
    border-radius: 10px;
    padding: 12px 16px;
    color: #1d1d1f;
    font-size: 14px;
    letter-spacing: -0.08px;
}

QDialog[class="error_dialog"] QLabel[class="error_title"] {
    color: #ff3b30;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: -0.3px;
}

QDialog[class="error_dialog"] QLabel[class="error_icon"] {
    font-size: 48px;
    color: #ff3b30;
    padding: 10px;
}

/* ============================================================================
   SUCCESS STATES (Refined Apple-style)
   ============================================================================ */
QLabel[class="success_message"] {
    color: #28a745;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -0.08px;
    padding: 12px 16px;
    background-color: rgba(52, 199, 89, 0.1);
    border: 0.5px solid rgba(52, 199, 89, 0.2);
    border-radius: 10px;
}

/* ============================================================================
   WARNING STATES (Refined Apple-style)
   ============================================================================ */
QLabel[class="warning_message"] {
    color: #ff9500;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -0.08px;
    padding: 12px 16px;
    background-color: rgba(255, 204, 0, 0.1);
    border: 0.5px solid rgba(255, 204, 0, 0.2);
    border-radius: 10px;
}

/* ============================================================================
   INFO STATES (Refined Apple-style)
   ============================================================================ */
QLabel[class="info_message"] {
    color: #007aff;
    font-size: 15px;
    font-weight: 500;
    letter-spacing: -0.08px;
    padding: 12px 16px;
    background-color: rgba(0, 122, 255, 0.1);
    border: 0.5px solid rgba(0, 122, 255, 0.2);
    border-radius: 10px;
}

/* ============================================================================
   FOCUS INDICATORS & KEYBOARD NAVIGATION (Accessibility)
   ============================================================================ */
QWidget:focus {
    outline: none;
}

QPushButton:focus {
    outline: 2px solid rgba(0, 122, 255, 0.5);
    outline-offset: 2px;
}

QComboBox:focus {
    outline: 2px solid rgba(0, 122, 255, 0.5);
    outline-offset: 2px;
}

QCheckBox:focus, QRadioButton:focus {
    outline: 2px solid rgba(0, 122, 255, 0.5);
    outline-offset: 2px;
}

/* ============================================================================
   HELP TEXT & HINTS (Refined Apple-style)
   ============================================================================ */
QLabel[class="help_text"] {
    color: #8e8e93;
    font-size: 13px;
    font-weight: 400;
    letter-spacing: -0.08px;
    line-height: 1.4em;
    padding: 4px 0;
}

QLabel[class="hint_text"] {
    color: #636366;
    font-size: 12px;
    font-weight: 400;
    letter-spacing: -0.08px;
    font-style: italic;
    padding: 2px 0;
}

/* ============================================================================
   DISABLED STATE CONSISTENCY
   ============================================================================ */
QWidget:disabled {
    opacity: 0.5;
}

QPushButton:disabled {
}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {
    background-color: #242426;
    color: #636366;
}

QComboBox:disabled {
    background-color: #242426;
    color: #636366;
}

/* ============================================================================
   SEPARATORS & DIVIDERS (Refined Apple-style)
   ============================================================================ */
QFrame[class="separator"] {
    background-color: rgba(255, 255, 255, 0.1);
    max-height: 1px;
    min-height: 1px;
}

QFrame[class="divider"] {
    background-color: rgba(255, 255, 255, 0.08);
    max-width: 1px;
    min-width: 1px;
}

/* ============================================================================
   BADGES & LABELS (Refined Apple-style)
   ============================================================================ */
QLabel[class="badge"] {
    padding: 4px 10px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.18px;
    background-color: #3a3a3c;
    color: #f2f2f7;
}

QLabel[class="badge"][variant="primary"] {
    background-color: rgba(0, 122, 255, 0.15);
    color: #007aff;
}

QLabel[class="badge"][variant="success"] {
    background-color: rgba(52, 199, 89, 0.15);
    color: #34c759;
}

QLabel[class="badge"][variant="warning"] {
    background-color: rgba(255, 204, 0, 0.15);
    color: #ffcc00;
}

QLabel[class="badge"][variant="danger"] {
    background-color: rgba(255, 59, 48, 0.15);
    color: #ff3b30;
}

/* ============================================================================
   PAGINATION CONTROLS (Refined Apple-style)
   ============================================================================ */
QWidget[class="pagination"] {
    background-color: transparent;
    padding: 8px 0;
}

QWidget[class="pagination"] QPushButton {
    min-width: 80px;
    padding: 8px 16px;
    font-size: 14px;
}

QWidget[class="pagination"] QLabel {
    color: #8e8e93;
    font-size: 14px;
    font-weight: 500;
    padding: 0 12px;
    letter-spacing: -0.08px;
}

QWidget[class="pagination"] QLabel[class="page_info"] {
    color: #636366;
    font-size: 13px;
}

/* ============================================================================
   SEARCH INPUTS & HIGHLIGHTING (Refined Apple-style)
   ============================================================================ */
QLineEdit[class="search_input"] {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 10px;
    padding: 10px 16px 10px 40px;
    color: #f2f2f7;
    font-size: 14px;
    min-height: 40px;
}

QLineEdit[class="search_input"]:focus {
    border: 0.5px solid #007aff;
    background-color: #2c2c2e;
}

QLineEdit[class="search_input"]::placeholder {
    color: #636366;
}

/* Search results highlighting */
QTableWidget::item[class="search_match"] {
    background-color: rgba(0, 122, 255, 0.1);
    color: #007aff;
}

/* ============================================================================
   FILTER CHIPS & TAGS (Refined Apple-style)
   ============================================================================ */
QPushButton[class="filter_chip"] {
    background-color: #3a3a3c;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 500;
    color: #f2f2f7;
    min-height: 28px;
    letter-spacing: -0.08px;
}

QPushButton[class="filter_chip"]:hover {
    background-color: #48484a;
    border-color: rgba(255, 255, 255, 0.2);
}

QPushButton[class="filter_chip"]:checked {
    background-color: rgba(0, 122, 255, 0.15);
    border-color: #007aff;
    color: #007aff;
}

QPushButton[class="filter_chip"]::close-button {
    image: none;
    border: none;
    width: 16px;
    height: 16px;
    border-radius: 8px;
    background-color: rgba(255, 255, 255, 0.2);
    margin-left: 8px;
}

QPushButton[class="filter_chip"]::close-button:hover {
    background-color: rgba(255, 255, 255, 0.3);
}

/* ============================================================================
   TABLE SORTING INDICATORS (Refined Apple-style)
   ============================================================================ */
QHeaderView::section[class="sortable"] {
    padding-right: 24px;
}

QHeaderView::section[class="sorted_asc"]::indicator {
    image: none;
    border: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid #007aff;
    width: 0px;
    height: 0px;
    margin-right: 8px;
}

QHeaderView::section[class="sorted_desc"]::indicator {
    image: none;
    border: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #007aff;
    width: 0px;
    height: 0px;
    margin-right: 8px;
}

/* ============================================================================
   CHART CONTAINERS (Refined Apple-style)
   ============================================================================ */
QWidget[class="chart_container"] {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 14px;
    padding: 20px;
}

QWidget[class="chart_container"] QLabel[class="chart_title"] {
    color: #f2f2f7;
    font-size: 16px;
    font-weight: 600;
    letter-spacing: -0.2px;
    padding-bottom: 12px;
}

QWidget[class="chart_container"] QLabel[class="chart_subtitle"] {
    color: #8e8e93;
    font-size: 13px;
    padding-bottom: 16px;
}

/* ============================================================================
   MODAL OVERLAYS (Refined Apple-style)
   ============================================================================ */
QWidget[class="modal_overlay"] {
    background-color: rgba(28, 28, 30, 0.6);
}

QDialog[class="modal"] {
    background-color: #2c2c2e;
    border: 0.5px solid rgba(255, 255, 255, 0.1);
    border-radius: 16px;
    padding: 24px;
}

QDialog[class="modal"] QLabel[class="modal_title"] {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.3px;
    padding-bottom: 8px;
}

QDialog[class="modal"] QLabel[class="modal_message"] {
    color: #8e8e93;
    font-size: 15px;
    letter-spacing: -0.08px;
    line-height: 1.5em;
    padding-bottom: 20px;
}

/* ============================================================================
   SKELETON LOADERS (Refined Apple-style)
   ============================================================================ */
QWidget[class="skeleton"] {
    background-color: #3a3a3c;
    border-radius: 8px;
    min-height: 20px;
}

QWidget[class="skeleton"][variant="text"] {
    background: linear-gradient(90deg, #3a3a3c 0%, #48484a 50%, #3a3a3c 100%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

QWidget[class="skeleton"][variant="circle"] {
    border-radius: 50%;
    min-width: 40px;
    min-height: 40px;
}

QWidget[class="skeleton"][variant="rect"] {
    border-radius: 8px;
}

/* ============================================================================
   DRAG & DROP STATES (Refined Apple-style)
   ============================================================================ */
QWidget[class="drag_target"] {
    border: 2px dashed rgba(0, 122, 255, 0.5);
    border-radius: 12px;
    background-color: rgba(0, 122, 255, 0.05);
}

QWidget[class="drag_target"][state="drag_over"] {
    border-color: #007aff;
    background-color: rgba(0, 122, 255, 0.1);
}

QWidget[class="drag_target"][state="drag_reject"] {
    border-color: #ff3b30;
    background-color: rgba(255, 59, 48, 0.05);
}

/* ============================================================================
   MULTI-SELECT STATES (Refined Apple-style)
   ============================================================================ */
QTableWidget::item[class="multi_selected"] {
    background-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}

QListWidget::item[class="multi_selected"] {
    background-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}

QTreeWidget::item[class="multi_selected"] {
    background-color: rgba(0, 122, 255, 0.2);
    color: #007aff;
}
"""

HIGH_CONTRAST_THEME = DARK_THEME
DISCORD_THEME = DARK_THEME

__all__ = ["DARK_THEME", "LIGHT_THEME", "HIGH_CONTRAST_THEME", "DISCORD_THEME"]
