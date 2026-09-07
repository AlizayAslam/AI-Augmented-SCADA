"""
Dashboard - Forest Green theme (matches screenshot), Power Grid Network SVG,
real nav icons, collapsible sidebar, scrollable pages, KPI colour borders.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QScrollArea, QStackedWidget,
    QMessageBox, QHeaderView, QSizePolicy, QDialog, QApplication, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QEvent, QSize
from PyQt6.QtGui import QFont, QColor
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
from datetime import datetime

from core.db import DatabaseManager
from core.theme_manager import ThemeManager
from core.alert_manager import AlertManager
from ui.data_import import DataImportPage
from ui.forecast import ForecastPage
from ui.optimization import OptimizationPage
from ui.alerts import AlertsPage
from ui.reports import ReportsPage
from ui.settings import SettingsPage
from ui.feeders import FeederManagementPage
from ui.users import UserManagementPage
from ui.model_comparison import ModelComparisonPage

# ── colour constants (match theme_manager) ──────────────────────────────────
SB_BG    = "#1a2e1a"
SB_ACCNT = "#4ade80"
CARD_BG  = "#ffffff"
CARD_BDR = "#e2e8f0"
TEXT_SEC = "#64748b"
ACCENT   = "#16a34a"
BG       = "#f8fafc"

# nav items: (label, MUI-style icon, method, page_index)
# Icons chosen to match Material UI icon set visually
NAV = [
    ("Dashboard",    "⧉",  "show_dashboard",    0),   # GridView (MUI)
    ("Data Import",  "↥",  "show_data_import",  1),   # Upload (MUI)
    ("Forecasting",  "⌇",  "show_forecast",     2),   # Timeline / ShowChart
    ("Optimization", "⧟",  "show_optimization", 3),   # Tune / Sliders
    ("Alerts",       "⍾",  "show_alerts",       4),   # NotificationsActive
    ("Reports",      "≡",  "show_reports",      5),   # Description / Article
    ("Model Compare","⧉⧉", "show_comparison",   9),   # Compare (two grids)
    ("Settings",     "✦",  "show_settings",     6),   # Settings gear star
    ("Feeders",      "⌁",  "show_feeders",      7),   # ElectricalServices
    ("Users",        "⚇",  "show_users",        8),   # People / Group
]

KPI_COLORS = {
    "demand":    "#3b82f6",
    "predicted": "#8b5cf6",
    "supply":    "#16a34a",
    "status":    "#f59e0b",
}


# ─────────────────────────────────────────────────────────────────────────────
# Zoom dialog
# ─────────────────────────────────────────────────────────────────────────────
class ZoomGraphDialog(QDialog):
    def __init__(self, title, plot_fn, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(1100, 620)
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        fig = Figure(figsize=(15, 6), dpi=100)
        canvas = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.set_facecolor("#f8fafc")
        fig.patch.set_facecolor("#f8fafc")
        plot_fn(ax)
        fig.tight_layout()
        layout.addWidget(canvas)
        btn = QPushButton("Close")
        btn.setMaximumWidth(100)
        btn.clicked.connect(self.accept)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        self.setLayout(layout)


# ─────────────────────────────────────────────────────────────────────────────
# Chart card with zoom
# ─────────────────────────────────────────────────────────────────────────────
class ChartCard(QFrame):
    def __init__(self, title, figsize=(6, 3), parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._title = title
        self._plot_fn = None

        layout = QVBoxLayout()
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(4)

        hdr = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet(f"font-size:12px;font-weight:bold;color:{TEXT_SEC};background:transparent;")
        hdr.addWidget(lbl)
        hdr.addStretch()
        zoom = QPushButton("⤢ Zoom")
        zoom.setStyleSheet(
            f"QPushButton{{font-size:11px;color:{ACCENT};background:none;border:none;"
            f"padding:2px 6px;min-height:24px;}}"
            f"QPushButton:hover{{color:#15803d;}}"
        )
        zoom.setToolTip("Open full view")
        zoom.clicked.connect(self._open_zoom)
        hdr.addWidget(zoom)
        layout.addLayout(hdr)

        self.fig = Figure(figsize=figsize, dpi=90)
        self.fig.patch.set_facecolor(CARD_BG)
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setStyleSheet(f"background:{CARD_BG};border:none;")
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(CARD_BG)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

    def set_plot_fn(self, fn): self._plot_fn = fn

    def refresh(self):
        self.fig.tight_layout(pad=0.8)
        self.canvas.draw()

    def _open_zoom(self):
        if self._plot_fn:
            ZoomGraphDialog(self._title, self._plot_fn, self.window()).exec()


# ─────────────────────────────────────────────────────────────────────────────
# KPI card (white card, coloured left border, icon top-right)
# ─────────────────────────────────────────────────────────────────────────────
class KpiCard(QFrame):
    def __init__(self, title, unit="", accent="#3b82f6", icon="📊", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.setMinimumHeight(110)

        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        bar = QFrame()
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background:{accent};border-radius:4px 0 0 4px;")
        outer.addWidget(bar)

        inner = QVBoxLayout()
        inner.setContentsMargins(14, 12, 14, 12)
        inner.setSpacing(4)

        # title row with icon
        tr = QHBoxLayout()
        self._title_lbl = QLabel(title)
        self._title_lbl.setStyleSheet(f"font-size:11px;color:{TEXT_SEC};background:transparent;")
        tr.addWidget(self._title_lbl)
        tr.addStretch()
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(f"font-size:18px;color:{accent};background:transparent;")
        tr.addWidget(icon_lbl)
        inner.addLayout(tr)

        self._value_lbl = QLabel("—")
        self._value_lbl.setStyleSheet(f"font-size:26px;font-weight:bold;background:transparent;color:#0f172a;")
        inner.addWidget(self._value_lbl)

        self._unit_lbl = QLabel(unit)
        self._unit_lbl.setStyleSheet(f"font-size:11px;color:{accent};background:transparent;font-weight:bold;")
        inner.addWidget(self._unit_lbl)

        content = QWidget()
        content.setLayout(inner)
        outer.addWidget(content)
        self.setLayout(outer)

    def set_value(self, value, unit=None):
        self._value_lbl.setText(str(value))
        if unit is not None:
            self._unit_lbl.setText(unit)


# ─────────────────────────────────────────────────────────────────────────────
# Power Grid Network SVG widget
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Animated Power Grid Network (Sukkur feeders, matplotlib + animation)
# ─────────────────────────────────────────────────────────────────────────────
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.animation import FuncAnimation
from matplotlib.patches import FancyArrowPatch

class AnimatedGridWidget(QWidget):
    """
    Professional Single-Line Diagram (SLD) style power grid.
    Horizontal bus-bar layout — looks like real SCADA / EPMS software.
    Animated flow dots travel along each feeder line.
    """
    # ── feeder data: (label, x_tap, y_tap, x_end, y_end, color, load_mw) ──
    FEEDERS = [
        ("Civil Hospital\nFeeder",        0.18, 0.55, 0.18, 0.12,  "#ef4444", 8.5),
        ("Airport Road\nFeeder",          0.30, 0.55, 0.30, 0.12,  "#3b82f6", 12.0),
        ("Rohri Industrial\nFeeder",      0.42, 0.55, 0.42, 0.12,  "#f59e0b", 18.0),
        ("SITE Area\nFeeder",             0.54, 0.55, 0.54, 0.12,  "#8b5cf6", 14.0),
        ("Military Road\nFeeder",         0.66, 0.55, 0.66, 0.12,  "#0891b2", 10.0),
        ("Barrage Colony\nFeeder",        0.76, 0.55, 0.76, 0.12,  "#16a34a",  9.5),
        ("Shikarpur Road\nFeeder",        0.86, 0.55, 0.86, 0.12,  "#64748b",  7.0),
        ("Old Sukkur\nRes. Feeder",       0.96, 0.55, 0.96, 0.12,  "#64748b",  6.0),
    ]
    # priority label colours
    PRI_COLORS = {"critical": "#ef4444", "high": "#3b82f6",
                  "medium":   "#f59e0b", "low":  "#64748b"}

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db   = db
        self._anim = None
        self._dots = []
        self._dot_pos = [0.0] * len(self.FEEDERS)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.fig = Figure(figsize=(10, 4.2), dpi=90)
        self.fig.patch.set_facecolor("#0f172a")
        self.canvas = FigureCanvas(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.canvas)
        self.setLayout(layout)
        self._draw_sld()
        self._start_animation()

    def _draw_sld(self):
        ax = self.fig.add_subplot(111)
        ax.set_facecolor("#0f172a")
        ax.set_xlim(0.06, 1.04)
        ax.set_ylim(0.0, 1.0)
        ax.axis("off")
        self.ax = ax
        self._flow_dots = []

        # ── title ──
        ax.text(0.5, 0.97, "Sukkur 132 kV Grid Station  —  Single-Line Diagram (SLD)",
                ha="center", va="top", fontsize=9, color="#94a3b8",
                fontfamily="monospace", transform=ax.transAxes)

        # ── 132 kV busbar (thick horizontal) ──
        BUS_Y   = 0.72
        BUS_X0  = 0.08
        BUS_X1  = 1.02
        ax.plot([BUS_X0, BUS_X1], [BUS_Y, BUS_Y],
                color="#fbbf24", lw=5, solid_capstyle="round", zorder=4)
        ax.text(BUS_X0 - 0.01, BUS_Y, "132 kV\nBus", ha="right", va="center",
                fontsize=7.5, color="#fbbf24", fontweight="bold")

        # ── grid transformer (left) ──
        TX = 0.10
        TY_TOP  = 0.95
        TY_MID  = BUS_Y
        ax.plot([TX, TX], [TY_TOP, TY_MID], color="#fbbf24", lw=2.5, zorder=3)
        # transformer symbol: two circles
        c1 = mpatches.Circle((TX, 0.88), 0.025, fill=False,
                              ec="#fbbf24", lw=2, zorder=5)
        c2 = mpatches.Circle((TX, 0.84), 0.025, fill=False,
                              ec="#fbbf24", lw=2, zorder=5)
        ax.add_patch(c1); ax.add_patch(c2)
        ax.text(TX + 0.03, 0.88, "132/11kV\nPTR", ha="left", va="center",
                fontsize=7, color="#94a3b8")
        ax.text(TX, 0.97, "Grid\nInfeed", ha="center", va="top",
                fontsize=7.5, color="#fbbf24", fontweight="bold")

        # ── per-feeder vertical lines with breakers & load boxes ──
        for i, (label, xt, yt, xe, ye, color, load_mw) in enumerate(self.FEEDERS):
            # tap line from busbar down
            ax.plot([xt, xt], [BUS_Y, yt - 0.03], color=color, lw=2, zorder=3)
            # circuit breaker symbol (small square)
            br_y = 0.64
            br = mpatches.FancyBboxPatch((xt - 0.014, br_y - 0.018),
                                          0.028, 0.036,
                                          boxstyle="square,pad=0.003",
                                          fc="#1e293b", ec=color, lw=1.5, zorder=5)
            ax.add_patch(br)
            ax.text(xt, br_y, "CB", ha="center", va="center",
                    fontsize=5.5, color=color, fontweight="bold", zorder=6)

            # feeder line below CB
            ax.plot([xt, xt], [br_y - 0.018, ye + 0.05], color=color, lw=1.8,
                    alpha=0.9, zorder=3)

            # animated dot placeholder (drawn by animation)
            dot, = ax.plot([], [], "o", color="#ffffff", ms=5, zorder=8)
            self._flow_dots.append(dot)

            # load box at bottom
            lb = mpatches.FancyBboxPatch((xt - 0.046, ye),
                                          0.092, 0.09,
                                          boxstyle="round,pad=0.005",
                                          fc="#1e293b", ec=color, lw=1.5, zorder=5)
            ax.add_patch(lb)
            # load MW value
            ax.text(xt, ye + 0.062, f"{load_mw} MW",
                    ha="center", va="center", fontsize=7,
                    color=color, fontweight="bold", zorder=6)
            # feeder label below box
            ax.text(xt, ye - 0.01, label,
                    ha="center", va="top", fontsize=6,
                    color="#94a3b8", multialignment="center", zorder=6)

            # load bar inside the box
            bar_w_full = 0.072
            bar_w = bar_w_full * min(1.0, load_mw / 20.0)
            bar = mpatches.Rectangle((xt - 0.036, ye + 0.004),
                                      bar_w, 0.022,
                                      fc=color, alpha=0.7, zorder=7)
            ax.add_patch(bar)

        # ── legend ──
        legend_items = [
            (mpatches.Patch(fc="#ef4444"), "Critical (hospital)"),
            (mpatches.Patch(fc="#3b82f6"), "High (airport/military)"),
            (mpatches.Patch(fc="#f59e0b"), "Medium (industrial)"),
            (mpatches.Patch(fc="#64748b"), "Low (residential)"),
        ]
        ax.legend([p for p, _ in legend_items],
                  [l for _, l in legend_items],
                  loc="upper right", fontsize=7,
                  facecolor="#1e293b", edgecolor="#334155",
                  labelcolor="#94a3b8", framealpha=0.9,
                  handlelength=1.2, handleheight=0.8)

        self.fig.tight_layout(pad=0.3)

    def _start_animation(self):
        n = len(self.FEEDERS)
        speeds = [0.018, 0.022, 0.015, 0.020, 0.019, 0.016, 0.021, 0.017]

        def animate(frame):
            artists = []
            for i, (label, xt, yt, xe, ye, color, _) in enumerate(self.FEEDERS):
                self._dot_pos[i] = (self._dot_pos[i] + speeds[i % len(speeds)]) % 1.0
                p = self._dot_pos[i]
                dy = yt - 0.048 - (ye + 0.14)
                y_dot = (yt - 0.048) - p * abs(dy)
                self._flow_dots[i].set_data([xt], [y_dot])
                self._flow_dots[i].set_color(color)
                artists.append(self._flow_dots[i])
            return artists

        self._anim = FuncAnimation(
            self.fig, animate, frames=300, interval=60,
            blit=True, cache_frame_data=False
        )
        self.canvas.draw()

    def closeEvent(self, event):
        if self._anim:
            self._anim.event_source.stop()
        super().closeEvent(event)



# ─────────────────────────────────────────────────────────────────────────────
# Theft detection
# ─────────────────────────────────────────────────────────────────────────────
def detect_theft(df, threshold_pct=15.0):
    if df.empty: return []
    results = []
    for feeder, grp in df.groupby("feeder"):
        total_input = grp["load"].sum()
        total_loss  = grp["loss"].sum() if "loss" in grp.columns else 0
        loss_pct    = (total_loss / total_input * 100) if total_input > 0 else 0
        results.append({
            "feeder": feeder, "input_mwh": round(total_input, 2),
            "loss_mwh": round(total_loss, 2),
            "delivered_mwh": round(total_input - total_loss, 2),
            "loss_pct": round(loss_pct, 2),
            "theft_flag": loss_pct > threshold_pct,
        })
    return sorted(results, key=lambda x: x["loss_pct"], reverse=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────
class DashboardWindow(QMainWindow):
    SIDEBAR_W  = 210
    SIDEBAR_C  = 54

    def __init__(self, db: DatabaseManager, username: str, role: str = "operator"):
        super().__init__()
        self.db       = db
        self.username = username
        self.role     = role or "operator"
        self.theme_manager   = ThemeManager()
        self.alert_manager   = AlertManager(db)
        self._feeder_colors  = {}
        self._sb_expanded    = True
        self._session_timeout_ms = 30 * 60 * 1000
        self._session_timer = QTimer(self)
        self._session_timer.setSingleShot(True)
        self._session_timer.timeout.connect(self._handle_session_timeout)

        self.init_ui()
        self.load_dashboard_data()
        self.start_auto_refresh()
        self._start_session_timeout()

    # ── UI skeleton ──────────────────────────────────────────────────────────

    def init_ui(self):
        self.setWindowTitle("AI-Augmented SCADA — Sukkur Power Grid")
        self.resize(1480, 900)
        self.setMinimumSize(900, 600)

        central = QWidget()
        self.setCentralWidget(central)
        self._main_layout = QHBoxLayout()
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        self._sb_frame = self._build_sidebar()
        self._main_layout.addWidget(self._sb_frame)

        right = QWidget()
        rl = QVBoxLayout()
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(0)
        rl.addWidget(self._build_topbar())
        self.content_stack = QStackedWidget()
        self._create_pages()
        rl.addWidget(self.content_stack)
        right.setLayout(rl)
        self._main_layout.addWidget(right)

        central.setLayout(self._main_layout)
        self.theme_manager.apply_theme(self)
        self.installEventFilter(self)

    # ── sidebar ──────────────────────────────────────────────────────────────

    def _build_sidebar(self):
        sb = QFrame()
        sb.setObjectName("sidebar")
        sb.setFixedWidth(self.SIDEBAR_W)

        # outer layout holds header + scrollable nav + footer
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 12)
        outer.setSpacing(0)

        # ── header ───────────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(70)
        hdr.setStyleSheet(f"background:{SB_BG};")
        hl = QHBoxLayout()
        hl.setContentsMargins(14, 0, 10, 0)

        self._logo_lbl = QLabel("SCADA Grid")
        self._logo_lbl.setObjectName("sidebar_logo")
        self._logo_lbl.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        self._sub_lbl = QLabel("AI-Augmented System")
        self._sub_lbl.setObjectName("sidebar_sub")
        self._sub_lbl.setStyleSheet("font-size:10px;color:#6b9e6b;background:transparent;")
        lv = QVBoxLayout()
        lv.setSpacing(1)
        lv.addWidget(self._logo_lbl)
        lv.addWidget(self._sub_lbl)
        hl.addLayout(lv)
        hl.addStretch()

        self._toggle_btn = QPushButton("☰")
        self._toggle_btn.setObjectName("sidebar_toggle")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.clicked.connect(self._toggle_sidebar)
        hl.addWidget(self._toggle_btn)
        hdr.setLayout(hl)
        outer.addWidget(hdr)

        # divider
        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background:#2d4a2d;")
        outer.addWidget(div)
        outer.addSpacing(6)

        # ── scrollable nav area ───────────────────────────────────────────────
        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        nav_scroll.setStyleSheet(
            f"QScrollArea{{background:{SB_BG};border:none;}}"
            f"QScrollBar:vertical{{background:{SB_BG};width:4px;}}"
            f"QScrollBar::handle:vertical{{background:#2d4a2d;border-radius:2px;}}"
        )

        nav_container = QWidget()
        nav_container.setStyleSheet(f"background:{SB_BG};")
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)

        ADMIN_ONLY = {"Settings", "Users"}
        self._nav_btns = {}
        for label, icon, method, idx in NAV:
            if label in ADMIN_ONLY and self.role != "admin":
                continue
            btn = QPushButton(f"  {icon}   {label}")
            btn.setObjectName("sidebar_btn")
            btn.setMinimumHeight(42)
            btn.setProperty("nav_label", label)
            btn.clicked.connect(lambda _, m=method: getattr(self, m)())
            nav_layout.addWidget(btn)
            self._nav_btns[label] = btn

        nav_layout.addStretch()
        nav_container.setLayout(nav_layout)
        nav_scroll.setWidget(nav_container)
        outer.addWidget(nav_scroll, 1)

        # ── footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(f"background:{SB_BG};")
        fl = QVBoxLayout()
        fl.setContentsMargins(8, 8, 8, 8)
        fl.setSpacing(4)

        # user count badge (admin only)
        if self.role == "admin":
            users = self.db.fetch_all("SELECT COUNT(*) as c FROM users")[0]['c']
            self._user_count_lbl = QLabel(f"  👥  {users} registered user{'s' if users != 1 else ''}")
            self._user_count_lbl.setStyleSheet("color:#6b9e6b;font-size:11px;background:transparent;")
            fl.addWidget(self._user_count_lbl)

        logout_btn = QPushButton("  ⎋   Logout")
        logout_btn.setObjectName("sidebar_btn")
        logout_btn.setMinimumHeight(40)
        logout_btn.clicked.connect(self.logout)
        fl.addWidget(logout_btn)

        exit_btn = QPushButton("  ⊠   Exit")
        exit_btn.setObjectName("sidebar_btn")
        exit_btn.setMinimumHeight(40)
        exit_btn.clicked.connect(self.exit_application)
        fl.addWidget(exit_btn)

        ver = QLabel(f"  Version 2.1.0 — Sukkur IBA")
        ver.setObjectName("sidebar_version")
        fl.addWidget(ver)

        footer.setLayout(fl)
        outer.addWidget(footer)

        sb.setLayout(outer)
        return sb

    def _toggle_sidebar(self):
        if self._sb_expanded:
            self._sb_frame.setFixedWidth(self.SIDEBAR_C)
            self._logo_lbl.hide(); self._sub_lbl.hide()
            for label, btn in self._nav_btns.items():
                icon = next((i for l, i, *_ in NAV if l == label), "•")
                btn.setText(f" {icon}")
                btn.setToolTip(label)
        else:
            self._sb_frame.setFixedWidth(self.SIDEBAR_W)
            self._logo_lbl.show(); self._sub_lbl.show()
            for label, btn in self._nav_btns.items():
                icon = next((i for l, i, *_ in NAV if l == label), "•")
                btn.setText(f"  {icon}   {label}")
                btn.setToolTip("")
        self._sb_expanded = not self._sb_expanded

    def _set_active_nav(self, label):
        for lbl, btn in self._nav_btns.items():
            obj = "sidebar_btn_active" if lbl == label else "sidebar_btn"
            btn.setObjectName(obj)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ── top bar ──────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(56)
        bar.setStyleSheet(f"QFrame#topbar{{background:#ffffff;border-bottom:1px solid #e2e8f0;}}")
        layout = QHBoxLayout()
        layout.setContentsMargins(24, 0, 24, 0)

        ttl = QLabel("SCADA Energy Management")
        ttl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        ttl.setStyleSheet("color:#0f172a;background:transparent;")
        sub = QLabel("  AI-Augmented Power Grid Control System")
        sub.setStyleSheet("color:#64748b;font-size:12px;background:transparent;")
        layout.addWidget(ttl)
        layout.addWidget(sub)
        layout.addStretch()

        online_dot = QLabel("●")
        online_dot.setStyleSheet("color:#16a34a;font-size:14px;background:transparent;")
        online_lbl = QLabel("Online")
        online_lbl.setStyleSheet("color:#16a34a;font-size:13px;font-weight:bold;background:transparent;")
        layout.addWidget(online_dot)
        layout.addWidget(online_lbl)
        layout.addSpacing(16)

        self._clock_lbl = QLabel()
        self._clock_lbl.setStyleSheet("color:#374151;font-size:12px;background:transparent;")
        self._clock_timer = QTimer()
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()
        layout.addWidget(self._clock_lbl)
        layout.addSpacing(16)

        user_lbl = QLabel(f"👤  {self.username.title()}")
        user_lbl.setStyleSheet("color:#374151;font-size:13px;font-weight:bold;background:transparent;")
        layout.addWidget(user_lbl)
        layout.addSpacing(12)

        # Theme toggle button
        self._theme_btn = QPushButton("🌙")
        self._theme_btn.setFixedSize(36, 36)
        self._theme_btn.setToolTip("Toggle Dark / Light theme")
        self._theme_btn.setStyleSheet(
            "QPushButton{background:#f1f5f9;border:1px solid #e2e8f0;border-radius:8px;"
            "font-size:16px;padding:0;}"
            "QPushButton:hover{background:#e2e8f0;}"
        )
        self._theme_btn.clicked.connect(self.toggle_theme)
        layout.addWidget(self._theme_btn)

        bar.setLayout(layout)
        return bar

    def _update_clock(self):
        now = datetime.now()
        self._clock_lbl.setText(now.strftime("%H:%M:%S\n%a, %b %d %Y"))

    # ── pages ────────────────────────────────────────────────────────────────

    def _create_pages(self):
        self._dash_page = self._build_dashboard_page()
        self._di_page   = DataImportPage(self.db)
        self._fc_page   = ForecastPage(self.db)
        self._opt_page  = OptimizationPage(self.db)
        self._al_page   = AlertsPage(self.db, self.alert_manager)
        self._rep_page  = ReportsPage(self.db)
        self._set_page  = SettingsPage(self.db, self.theme_manager)
        self._feed_page = FeederManagementPage(self.db)
        self._usr_page  = UserManagementPage(self.db)
        self._cmp_page  = ModelComparisonPage(self.db)

        for page in [self._dash_page, self._di_page, self._fc_page, self._opt_page,
                     self._al_page, self._rep_page, self._set_page,
                     self._feed_page, self._usr_page, self._cmp_page]:
            self.content_stack.addWidget(self._wrap(page))
        self.content_stack.setCurrentIndex(0)

    def _wrap(self, w):
        s = QScrollArea()
        s.setWidgetResizable(True)
        s.setFrameShape(QFrame.Shape.NoFrame)
        s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        s.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        s.setWidget(w)
        return s

    # ── dashboard page ────────────────────────────────────────────────────────

    def _build_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(24, 20, 24, 24)
        layout.setSpacing(16)

        # Welcome banner - text only, left aligned, no icon
        banner = QFrame()
        banner.setObjectName("welcome_banner")
        banner.setFixedHeight(90)
        bl = QHBoxLayout()
        bl.setContentsMargins(24, 14, 24, 14)
        txt_l = QVBoxLayout()
        txt_l.setSpacing(3)
        b1 = QLabel("Welcome to SCADA Energy Management")
        b1.setStyleSheet("font-size:15px;font-weight:bold;color:#ffffff;background:transparent;")
        b2 = QLabel("Real-time monitoring and AI-powered management of Sukkur power grid. "
                    "Load forecasting, demand optimization, and automated load shedding for Sukkur IBA University.")
        b2.setStyleSheet("font-size:11px;color:#a3c5a3;background:transparent;")
        b2.setWordWrap(True)
        txt_l.addWidget(b1)
        txt_l.addWidget(b2)
        bl.addLayout(txt_l)
        bl.addStretch()
        banner.setLayout(bl)
        layout.addWidget(banner)

        # KPI row
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)
        self._kpi_demand   = KpiCard("Total Load",        "MW",  KPI_COLORS["demand"],    "〜")
        self._kpi_pred     = KpiCard("Predicted Load",    "Next Hour", KPI_COLORS["predicted"], "↗")
        self._kpi_supply   = KpiCard("Available Supply",  "MW",  KPI_COLORS["supply"],    "▣")
        self._kpi_status   = KpiCard("Grid Status",       "",    KPI_COLORS["status"],    "△")
        for k in [self._kpi_demand, self._kpi_pred, self._kpi_supply, self._kpi_status]:
            kpi_row.addWidget(k)
        layout.addLayout(kpi_row)

        # Grid network + Forecast side by side
        grid_row = QHBoxLayout()
        grid_row.setSpacing(12)

        # Power grid network card
        net_card = QFrame()
        net_card.setObjectName("card")
        nl = QVBoxLayout()
        nl.setContentsMargins(14, 12, 14, 12)
        nl.setSpacing(6)
        net_lbl = QLabel("Power Grid Network")
        net_lbl.setStyleSheet(f"font-size:13px;font-weight:bold;color:#0f172a;background:transparent;")
        nl.addWidget(net_lbl)
        try:
            self._grid_anim_widget = AnimatedGridWidget(db=self.db)
            nl.addWidget(self._grid_anim_widget)
        except Exception as e:
            print(f'Grid widget error: {e}')
            fallback = QLabel('Sukkur Power Grid Network')
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setStyleSheet('color:#64748b;font-size:12px;')
            fallback.setFixedHeight(300)
            nl.addWidget(fallback)
        net_card.setLayout(nl)
        grid_row.addWidget(net_card, 6)

        # Forecast chart card
        self._chart_forecast = ChartCard("Load Forecast  (MW)", figsize=(5, 3))
        grid_row.addWidget(self._chart_forecast, 4)
        layout.addLayout(grid_row)

        # Theft detection table
        theft_lbl = QLabel("Cumulative Energy Loss Detection — Technical / Commercial Theft Monitor")
        theft_lbl.setStyleSheet(f"font-size:12px;font-weight:bold;color:{TEXT_SEC};margin-top:4px;")
        layout.addWidget(theft_lbl)

        self._theft_table = QTableWidget()
        self._theft_table.setColumnCount(6)
        self._theft_table.setHorizontalHeaderLabels([
            "Feeder", "Input (MWh)", "Loss (MWh)", "Delivered (MWh)", "Loss %", "Status"
        ])
        self._theft_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._theft_table.setMaximumHeight(200)
        self._theft_table.setAlternatingRowColors(True)
        self._theft_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._theft_table.verticalHeader().setVisible(False)
        layout.addWidget(self._theft_table)

        # Active alerts
        al_lbl = QLabel("Active Alerts")
        al_lbl.setStyleSheet(f"font-size:12px;font-weight:bold;color:{TEXT_SEC};margin-top:4px;")
        layout.addWidget(al_lbl)
        self._alerts_table = QTableWidget()
        self._alerts_table.setColumnCount(4)
        self._alerts_table.setHorizontalHeaderLabels(["Time", "Severity", "Feeder", "Message"])
        self._alerts_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._alerts_table.setMaximumHeight(160)
        self._alerts_table.setAlternatingRowColors(True)
        self._alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._alerts_table.verticalHeader().setVisible(False)
        layout.addWidget(self._alerts_table)

        # Footer
        footer_lbl = QLabel("AI-Augmented SCADA for Smarter Power Grids © 2026  |  Sukkur IBA University  |  FYP Project")
        footer_lbl.setStyleSheet("font-size:10px;color:#94a3b8;background:transparent;margin-top:8px;")
        footer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer_lbl)

        page.setLayout(layout)
        return page

    # ── data loading ──────────────────────────────────────────────────────────

    def load_dashboard_data(self):
        try:
            df = self.db.get_feeder_data()
            if not df.empty:
                total_demand  = df['load'].sum()
                total_loss    = df['loss'].sum() if 'loss' in df.columns else 0
                available     = total_demand * 0.92
                loss_pct      = (total_loss / total_demand * 100) if total_demand > 0 else 0

                # Compute trend vs previous period
                try:
                    prev_df = df.sort_values('timestamp').head(len(df)//2)
                    prev_demand = prev_df['load'].sum()
                    trend_pct = ((total_demand - prev_demand) / prev_demand * 100) if prev_demand > 0 else 0
                    trend_str = f"↑ +{trend_pct:.1f}%" if trend_pct >= 0 else f"↓ {trend_pct:.1f}%"
                    trend_col = "#16a34a" if trend_pct <= 0 else "#dc2626"
                except Exception:
                    trend_str = ""; trend_col = "#64748b"

                self._kpi_demand.set_value(f"{total_demand:,.1f}", f"MW — all feeders  {trend_str}")
                self._kpi_supply.set_value(f"{available:,.1f}",    "MW — grid input")

                # ── Real AI forecast KPI (reads from DB, not a formula) ──────
                try:
                    forecast_df = self.db.get_forecast_data()
                    if forecast_df is not None and not forecast_df.empty and 'predicted_load' in forecast_df.columns:
                        forecast_df['timestamp'] = pd.to_datetime(forecast_df['timestamp'])
                        next_val = forecast_df.sort_values('timestamp').iloc[-1]['predicted_load']
                        self._kpi_pred.set_value(f"{float(next_val):,.1f}", "MW — AI forecast (next hour)")
                    else:
                        self._kpi_pred.set_value("—", "Run Forecasting first")
                except Exception:
                    self._kpi_pred.set_value(f"{total_demand*1.056:,.1f}", "MW — est. (no forecast)")

                alert_count = len(self.db.get_active_alerts())
                if alert_count == 0:
                    self._kpi_status.set_value("Stable", "No Alerts")
                else:
                    self._kpi_status.set_value("⚠ Alerts", f"{alert_count} active alert(s)")

                # Theft table
                theft_data = detect_theft(df, threshold_pct=15.0)
                self._theft_table.setRowCount(len(theft_data))
                for i, row in enumerate(theft_data):
                    self._theft_table.setItem(i, 0, QTableWidgetItem(row["feeder"]))
                    self._theft_table.setItem(i, 1, QTableWidgetItem(f"{row['input_mwh']:,.1f} MWh"))
                    self._theft_table.setItem(i, 2, QTableWidgetItem(f"{row['loss_mwh']:,.1f} MWh"))
                    self._theft_table.setItem(i, 3, QTableWidgetItem(f"{row['delivered_mwh']:,.1f} MWh"))
                    self._theft_table.setItem(i, 4, QTableWidgetItem(f"{row['loss_pct']:.1f} %"))
                    flag = QTableWidgetItem("⚠  Suspected theft / high loss" if row["theft_flag"] else "✓  Normal")
                    flag.setForeground(QColor("#dc2626") if row["theft_flag"] else QColor("#16a34a"))
                    self._theft_table.setItem(i, 5, flag)
            else:
                for k in [self._kpi_demand, self._kpi_supply, self._kpi_pred, self._kpi_status]:
                    k.set_value("No data")

            self._load_forecast_chart()
            self._load_alerts()
        except Exception as e:
            print(f"Dashboard load error: {e}")

    def _load_forecast_chart(self):
        forecast_df = self.db.get_forecast_data()

        def _plot(ax):
            ax.set_facecolor(CARD_BG)
            if not forecast_df.empty:
                df = forecast_df.copy()
                df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
                df = df.dropna(subset=['timestamp']).sort_values('timestamp')
                now = pd.Timestamp.now()

                # Show ALL feeders as separate coloured lines
                feeders = df['feeder'].dropna().unique() if 'feeder' in df.columns else []
                palette = [ACCENT, "#3b82f6", "#f59e0b", "#ef4444", "#8b5cf6",
                           "#06b6d4", "#0891b2", "#f97316", "#ec4899", "#a78bfa"]

                if len(feeders) > 1:
                    for fi, feeder in enumerate(sorted(feeders)):
                        fdf = df[df['feeder'] == feeder]
                        upcoming = fdf[fdf['timestamp'] > now].head(24)
                        to_plot  = upcoming if not upcoming.empty else fdf.tail(24)
                        if to_plot.empty:
                            continue
                        color = palette[fi % len(palette)]
                        short_name = feeder.replace(" Feeder", "").replace("Feeder", "")[:16]
                        ax.plot(to_plot['timestamp'], to_plot['predicted_load'],
                                color=color, linewidth=1.8, marker='o', markersize=3,
                                label=short_name)
                    ax.legend(fontsize=7, loc="upper left",
                              facecolor=CARD_BG, framealpha=0.85,
                              ncol=2 if len(feeders) > 4 else 1)
                else:
                    # Single feeder fallback
                    upcoming = df[df['timestamp'] > now].head(24)
                    to_plot  = upcoming if not upcoming.empty else df.tail(24)
                    ax.plot(to_plot['timestamp'], to_plot['predicted_load'],
                            color=ACCENT, linewidth=2, marker='o', markersize=4,
                            label="Predicted Load")
                    hist_df = df[df['timestamp'] <= now].tail(6)
                    if not hist_df.empty:
                        ax.plot(hist_df['timestamp'], hist_df['predicted_load'],
                                color="#94a3b8", linewidth=1.5, linestyle='--', label="Historical")
                    ax.legend(fontsize=8, loc="lower right")

                ax.set_ylabel("Load (MW)", fontsize=9, color=TEXT_SEC)
                # Fix x-axis: show hours clearly every 2h, rotated so they don't overlap
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
                ax.tick_params(axis='x', colors=TEXT_SEC, labelsize=7, rotation=45)
                ax.tick_params(axis='y', colors=TEXT_SEC, labelsize=8)
                for sp in ax.spines.values(): sp.set_color(CARD_BDR)
                ax.grid(color=CARD_BDR, alpha=0.8)
            else:
                ax.text(0.5, 0.5, "Run Forecasting first\n(Forecasting page → Train & Forecast)",
                        ha='center', va='center', fontsize=9, color=TEXT_SEC,
                        multialignment='center')
                ax.set_axis_off()

        self._chart_forecast.set_plot_fn(_plot)
        self._chart_forecast.ax.clear()
        _plot(self._chart_forecast.ax)
        self._chart_forecast.refresh()

    def _load_alerts(self):
        alerts = self.db.get_active_alerts()[:8]
        self._alerts_table.setRowCount(len(alerts))
        for i, a in enumerate(alerts):
            self._alerts_table.setItem(i, 0, QTableWidgetItem(str(a['timestamp'])[:16]))
            sev = QTableWidgetItem(a['severity'].upper())
            if a['severity'] == 'critical':
                sev.setForeground(QColor("#dc2626"))
            elif a['severity'] == 'warning':
                sev.setForeground(QColor("#d97706"))
            else:
                sev.setForeground(QColor("#2563eb"))
            self._alerts_table.setItem(i, 1, sev)
            self._alerts_table.setItem(i, 2, QTableWidgetItem(a.get('feeder') or '—'))
            self._alerts_table.setItem(i, 3, QTableWidgetItem(a.get('title', '')))

    def _feeder_color(self, name):
        if name not in self._feeder_colors:
            palette = [ACCENT,"#3b82f6","#f59e0b","#ef4444","#8b5cf6",
                       "#06b6d4","#0891b2","#f97316","#ec4899","#a78bfa"]
            self._feeder_colors[name] = palette[abs(hash(name)) % len(palette)]
        return self._feeder_colors[name]

    # ── navigation ────────────────────────────────────────────────────────────

    def _go(self, idx, label):
        self.content_stack.setCurrentIndex(idx)
        self._set_active_nav(label)

    def show_dashboard(self):  self._go(0, "Dashboard"); self.load_dashboard_data()
    def show_data_import(self):self._go(1, "Data Import")
    def show_forecast(self):   self._go(2, "Forecasting")
    def show_optimization(self):self._go(3, "Optimization")
    def show_alerts(self):     self._go(4, "Alerts"); self._al_page.load_alerts()
    def show_reports(self):    self._go(5, "Reports")
    def show_settings(self):   self._go(6, "Settings"); self._set_page.load_settings()
    def show_feeders(self):    self._go(7, "Feeders"); self._feed_page.refresh()
    def show_users(self):      self._go(8, "Users"); self._usr_page.refresh()
    def show_comparison(self): self._go(9, "Model Compare")

    # ── session / misc ────────────────────────────────────────────────────────

    def _start_session_timeout(self):
        self._session_timer.start(self._session_timeout_ms)

    def _handle_session_timeout(self):
        QMessageBox.information(self, "Session expired", "Logged out due to inactivity.")
        self.close()
        from ui.login import LoginWindow
        self.login_window = LoginWindow(self.db)
        self.login_window.show()

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
                            QEvent.Type.KeyPress, QEvent.Type.Wheel):
            self._start_session_timeout()
        return super().eventFilter(obj, event)

    def toggle_theme(self):
        new_theme = self.theme_manager.toggle_theme(self)
        icon = "☀" if new_theme == "light" else "🌙"
        if hasattr(self, "_theme_btn"):
            self._theme_btn.setText(icon)
        self.db.update_setting("theme", new_theme)

    def start_auto_refresh(self):
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self.load_dashboard_data)
        if self.db.get_setting('auto_refresh') == 'true':
            self._refresh_timer.start(30000)

    def logout(self):
        if QMessageBox.question(self, 'Logout', 'Log out?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.db.log_action(self.username, "logout", "User logged out")
            self.close()
            from ui.login import LoginWindow
            self.login_window = LoginWindow(self.db)
            self.login_window.show()

    def exit_application(self):
        if QMessageBox.question(self, 'Exit', 'Exit the SCADA system?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self.db.log_action(self.username, "exit", "Application closed")
            QApplication.quit()

    def closeEvent(self, event):
        self.alert_manager.stop_monitoring()
        event.accept()
