"""
Theme Manager - Light (default) + Dark Industrial SCADA toggle
Dark theme looks like professional NTDC/NEPRA control-room software.
"""
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QApplication

# ── Shared sidebar palette ───────────────────────────────────────────────────
SB_BG     = "#1a2e1a"
SB_HOVER  = "#243524"
SB_ACTIVE = "#2d4a2d"
SB_ACCENT = "#4ade80"
SB_BORDER = "#2d4a2d"

# ── LIGHT theme ─────────────────────────────────────────────────────────────
LIGHT_QSS = f"""
QMainWindow, QDialog {{
    background-color: #f8fafc;
    color: #0f172a;
}}
QWidget {{
    background-color: #f8fafc;
    color: #0f172a;
    font-family: 'Segoe UI', 'Inter', 'Arial', sans-serif;
    font-size: 13px;
}}
QFrame#sidebar {{
    background-color: {SB_BG};
    border-right: 1px solid {SB_BORDER};
}}
QFrame#topbar {{
    background-color: #ffffff;
    border-bottom: 1px solid #e2e8f0;
}}
QLabel#sidebar_logo {{
    color: {SB_ACCENT};
    font-size: 13px;
    font-weight: bold;
    background: transparent;
}}
QLabel#sidebar_sub {{
    color: #6b9e6b;
    font-size: 10px;
    background: transparent;
}}
QLabel#sidebar_version {{
    color: #4a7a4a;
    font-size: 10px;
    background: transparent;
    padding: 2px 6px;
}}
QPushButton#sidebar_btn {{
    background-color: transparent;
    color: #c8e6c9;
    border: none;
    text-align: left;
    padding: 8px 16px;
    font-size: 13px;
    border-radius: 6px;
    margin: 1px 6px;
}}
QPushButton#sidebar_btn:hover {{
    background-color: {SB_HOVER};
    color: #ffffff;
}}
QPushButton#sidebar_btn_active {{
    background-color: {SB_ACTIVE};
    color: {SB_ACCENT};
    border: none;
    text-align: left;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
    border-radius: 6px;
    margin: 1px 6px;
    border-left: 3px solid {SB_ACCENT};
}}
QPushButton#sidebar_toggle {{
    background-color: transparent;
    color: {SB_ACCENT};
    border: 1px solid #2d4a2d;
    border-radius: 4px;
    font-size: 16px;
    padding: 0;
}}
QPushButton#sidebar_toggle:hover {{
    background-color: {SB_HOVER};
}}
QFrame#welcome_banner {{
    background-color: {SB_BG};
    border-radius: 10px;
    border: none;
}}
QFrame#card {{
    background-color: #ffffff;
    border-radius: 10px;
    border: 1px solid #e2e8f0;
}}
QGroupBox {{
    font-weight: bold;
    font-size: 13px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    background-color: #ffffff;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #374151;
    background-color: #ffffff;
}}
QPushButton {{
    background-color: #16a34a;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}}
QPushButton:hover {{ background-color: #15803d; }}
QPushButton:disabled {{ background-color: #94a3b8; color: #e2e8f0; }}
QTableWidget {{
    background-color: #ffffff;
    alternate-background-color: #f8fafc;
    gridline-color: #e2e8f0;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
}}
QTableWidget::item {{ padding: 6px; color: #0f172a; }}
QTableWidget::item:selected {{ background-color: #dcfce7; color: #14532d; }}
QHeaderView::section {{
    background-color: #f1f5f9;
    color: #374151;
    font-weight: bold;
    font-size: 12px;
    padding: 8px 6px;
    border: none;
    border-bottom: 2px solid #e2e8f0;
}}
QScrollArea {{ background-color: #f8fafc; border: none; }}
QScrollBar:vertical {{
    background: #f1f5f9; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: #cbd5e1; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: #94a3b8; }}
QScrollBar:horizontal {{
    background: #f1f5f9; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #cbd5e1; border-radius: 4px;
}}
QComboBox {{
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #ffffff;
    color: #0f172a;
    min-height: 32px;
}}
QComboBox:focus {{ border-color: #16a34a; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    selection-background-color: #dcfce7;
    color: #0f172a;
}}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #ffffff;
    color: #0f172a;
    min-height: 32px;
}}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: #16a34a;
    outline: none;
}}
QProgressBar {{
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    text-align: center;
    background-color: #f1f5f9;
    color: #0f172a;
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: #16a34a;
    border-radius: 5px;
}}
QMessageBox {{ background-color: #ffffff; }}
QMenu {{
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
}}
QMenu::item {{ padding: 8px 16px; color: #0f172a; }}
QMenu::item:selected {{ background-color: #dcfce7; }}
QTabWidget::pane {{
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    background: #ffffff;
}}
QTabBar::tab {{
    background: #f1f5f9;
    color: #374151;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: #ffffff;
    color: #16a34a;
    font-weight: bold;
    border-bottom: 2px solid #16a34a;
}}
"""

# ── DARK INDUSTRIAL theme (control-room style) ───────────────────────────────
DARK_QSS = f"""
QMainWindow, QDialog {{
    background-color: #0d1117;
    color: #e2e8f0;
}}
QWidget {{
    background-color: #0d1117;
    color: #e2e8f0;
    font-family: 'Segoe UI', 'Inter', 'Arial', sans-serif;
    font-size: 13px;
}}
QFrame#sidebar {{
    background-color: #161b22;
    border-right: 1px solid #21262d;
}}
QFrame#topbar {{
    background-color: #161b22;
    border-bottom: 1px solid #21262d;
}}
QLabel#sidebar_logo {{
    color: #00d4aa;
    font-size: 13px;
    font-weight: bold;
    background: transparent;
}}
QLabel#sidebar_sub {{
    color: #8b949e;
    font-size: 10px;
    background: transparent;
}}
QLabel#sidebar_version {{
    color: #484f58;
    font-size: 10px;
    background: transparent;
    padding: 2px 6px;
}}
QPushButton#sidebar_btn {{
    background-color: transparent;
    color: #8b949e;
    border: none;
    text-align: left;
    padding: 8px 16px;
    font-size: 13px;
    border-radius: 6px;
    margin: 1px 6px;
}}
QPushButton#sidebar_btn:hover {{
    background-color: #21262d;
    color: #e2e8f0;
}}
QPushButton#sidebar_btn_active {{
    background-color: #1f2937;
    color: #00d4aa;
    border: none;
    text-align: left;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: bold;
    border-radius: 6px;
    margin: 1px 6px;
    border-left: 3px solid #00d4aa;
}}
QPushButton#sidebar_toggle {{
    background-color: transparent;
    color: #00d4aa;
    border: 1px solid #21262d;
    border-radius: 4px;
    font-size: 16px;
    padding: 0;
}}
QPushButton#sidebar_toggle:hover {{
    background-color: #21262d;
}}
QFrame#welcome_banner {{
    background-color: #161b22;
    border-radius: 10px;
    border: 1px solid #21262d;
}}
QFrame#card {{
    background-color: #161b22;
    border-radius: 10px;
    border: 1px solid #21262d;
}}
QGroupBox {{
    font-weight: bold;
    font-size: 13px;
    border: 1px solid #21262d;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 8px;
    background-color: #161b22;
    color: #e2e8f0;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #00d4aa;
    background-color: #161b22;
}}
QPushButton {{
    background-color: #00d4aa;
    color: #0d1117;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}}
QPushButton:hover {{ background-color: #00b894; }}
QPushButton:disabled {{ background-color: #30363d; color: #8b949e; }}
QTableWidget {{
    background-color: #161b22;
    alternate-background-color: #1c2128;
    gridline-color: #21262d;
    border: 1px solid #21262d;
    border-radius: 6px;
    color: #e2e8f0;
}}
QTableWidget::item {{ padding: 6px; color: #e2e8f0; }}
QTableWidget::item:selected {{ background-color: #1f3a2e; color: #00d4aa; }}
QHeaderView::section {{
    background-color: #21262d;
    color: #8b949e;
    font-weight: bold;
    font-size: 12px;
    padding: 8px 6px;
    border: none;
    border-bottom: 2px solid #30363d;
}}
QScrollArea {{ background-color: #0d1117; border: none; }}
QScrollBar:vertical {{
    background: #161b22; width: 8px; border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: #30363d; border-radius: 4px; min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: #484f58; }}
QScrollBar:horizontal {{
    background: #161b22; height: 8px; border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: #30363d; border-radius: 4px;
}}
QComboBox {{
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #21262d;
    color: #e2e8f0;
    min-height: 32px;
}}
QComboBox:focus {{ border-color: #00d4aa; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background-color: #21262d;
    border: 1px solid #30363d;
    selection-background-color: #1f3a2e;
    color: #e2e8f0;
}}
QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    border: 1px solid #30363d;
    border-radius: 6px;
    padding: 6px 10px;
    background-color: #21262d;
    color: #e2e8f0;
    min-height: 32px;
}}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: #00d4aa;
}}
QProgressBar {{
    border: 1px solid #30363d;
    border-radius: 6px;
    text-align: center;
    background-color: #21262d;
    color: #e2e8f0;
    height: 18px;
}}
QProgressBar::chunk {{
    background-color: #00d4aa;
    border-radius: 5px;
}}
QMessageBox {{ background-color: #161b22; color: #e2e8f0; }}
QMenu {{
    background-color: #161b22;
    border: 1px solid #30363d;
    border-radius: 6px;
    color: #e2e8f0;
}}
QMenu::item {{ padding: 8px 16px; color: #e2e8f0; }}
QMenu::item:selected {{ background-color: #1f3a2e; color: #00d4aa; }}
QTabWidget::pane {{
    border: 1px solid #21262d;
    border-radius: 6px;
    background: #161b22;
}}
QTabBar::tab {{
    background: #21262d;
    color: #8b949e;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: #161b22;
    color: #00d4aa;
    font-weight: bold;
    border-bottom: 2px solid #00d4aa;
}}
"""


class ThemeManager(QObject):
    theme_changed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.current_theme = "light"
        self._main_window = None

    def set_main_window(self, window):
        self._main_window = window

    def apply_theme(self, widget, theme: str = None):
        if theme:
            self.current_theme = theme
        qss = DARK_QSS if self.current_theme == "dark" else LIGHT_QSS
        widget.setStyleSheet(qss)
        self.theme_changed.emit(self.current_theme)

    def toggle_theme(self, window=None):
        # Guard: Qt's toggled(bool) signal passes a bool as first arg.
        # If called that way, window is a bool — ignore it and use _main_window.
        if isinstance(window, bool):
            window = None
        target = window or self._main_window
        new_theme = "dark" if self.current_theme == "light" else "light"
        self.current_theme = new_theme
        if target:
            self.apply_theme(target, new_theme)
        return new_theme

    def is_dark(self) -> bool:
        return self.current_theme == "dark"

    def card_bg(self)  -> str: return "#161b22" if self.is_dark() else "#ffffff"
    def text_pri(self) -> str: return "#e2e8f0" if self.is_dark() else "#0f172a"
    def text_sec(self) -> str: return "#8b949e" if self.is_dark() else "#64748b"
    def border(self)   -> str: return "#21262d" if self.is_dark() else "#e2e8f0"
    def accent(self)   -> str: return "#00d4aa" if self.is_dark() else "#16a34a"
    def bg(self)       -> str: return "#0d1117" if self.is_dark() else "#f8fafc"
    def plot_bg(self)  -> str: return "#161b22" if self.is_dark() else "#ffffff"
    def plot_grid(self)-> str: return "#21262d" if self.is_dark() else "#e2e8f0"
    def plot_text(self)-> str: return "#8b949e" if self.is_dark() else "#64748b"
