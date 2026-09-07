"""
Optimization Page for SCADA System
FIX: Gantt chart now shows exactly which feeder is ON/OFF at which hour.
FIX: Detailed schedule table setMaximumHeight removed — fills available space.
FIX: NEPRA feeder names loaded from DB (no more old names).
FIX: Priority popup shown for ANY feeder set to critical (not just keywords).
FIX: Table columns show Hour, Feeder, Allocated MW, Demand MW, ON/OFF status.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSpinBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QMessageBox,
    QDoubleSpinBox, QFrame, QScrollArea, QHeaderView,
    QSplitter, QSizePolicy, QProgressBar,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.patches as mpatches
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

from core.optimizer import PowerOptimizer


# ── Worker ────────────────────────────────────────────────────────────────────
class OptimizationWorker(QThread):
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, optimizer, available_power, total_demand, feeders, hours):
        super().__init__()
        self.optimizer       = optimizer
        self.available_power = available_power
        self.total_demand    = total_demand
        self.feeders         = feeders
        self.hours           = hours

    def run(self):
        try:
            if self.isInterruptionRequested():
                self.error.emit("Cancelled"); return
            self.progress.emit(10)
            result = self.optimizer.optimize_schedule(
                self.available_power, self.total_demand,
                self.feeders, self.hours
            )
            if self.isInterruptionRequested():
                self.error.emit("Cancelled"); return
            self.progress.emit(100)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


# ── Page ──────────────────────────────────────────────────────────────────────
PRIORITY_COLORS = {
    "critical": "#ef4444",
    "high":     "#f59e0b",
    "medium":   "#3b82f6",
    "low":      "#94a3b8",
}


class OptimizationPage(QWidget):

    def __init__(self, db):
        super().__init__()
        self.db        = db
        self.optimizer = PowerOptimizer()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        hdr = QLabel("Power Optimization — Sukkur Distribution Network")
        hdr.setStyleSheet("font-size:20px;font-weight:bold;color:#0f172a;")
        layout.addWidget(hdr)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(24)
        layout.addWidget(self.progress_bar)

        # ── Main splitter: left controls | right results ──────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: controls ────────────────────────────────────────────────────
        left = QWidget()
        left.setMaximumWidth(360)
        left.setMinimumWidth(280)
        ll = QVBoxLayout()
        ll.setSpacing(10)

        # Power / demand inputs
        pw_grp = QGroupBox("Supply & Demand (MW)")
        pl = QVBoxLayout()
        pl.setSpacing(6)
        pl.addWidget(QLabel("Available Supply (MW):"))
        self.available_power = QDoubleSpinBox()
        self.available_power.setRange(0, 5000)
        self.available_power.setValue(450)
        self.available_power.setSuffix(" MW")
        self.available_power.setMinimumHeight(36)
        pl.addWidget(self.available_power)
        pl.addWidget(QLabel("Total Demand (MW):"))
        self.total_demand = QDoubleSpinBox()
        self.total_demand.setRange(0, 5000)
        self.total_demand.setValue(550)
        self.total_demand.setSuffix(" MW")
        self.total_demand.setMinimumHeight(36)
        pl.addWidget(self.total_demand)

        load_db_btn = QPushButton("⬇  Auto-Load from Database")
        load_db_btn.setMinimumHeight(36)
        load_db_btn.setStyleSheet(
            "QPushButton{background:#3b82f6;color:white;font-weight:bold;"
            "border-radius:6px;}"
            "QPushButton:hover{background:#2563eb;}"
        )
        load_db_btn.clicked.connect(self._load_from_db)
        pl.addWidget(load_db_btn)
        pw_grp.setLayout(pl)
        ll.addWidget(pw_grp)

        # Schedule hours
        hr_grp = QGroupBox("Schedule Duration")
        hl = QVBoxLayout()
        self.hours_spin = QSpinBox()
        self.hours_spin.setRange(1, 24)
        self.hours_spin.setValue(24)
        self.hours_spin.setSuffix(" hours")
        self.hours_spin.setMinimumHeight(36)
        hl.addWidget(self.hours_spin)
        hr_grp.setLayout(hl)
        ll.addWidget(hr_grp)

        # Feeder priorities list — loads NEPRA names from DB
        pri_grp = QGroupBox("Feeder Priorities")
        pri_grp.setMinimumHeight(280)
        prl = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(240)
        fd_widget = QWidget()
        fd_layout = QVBoxLayout()
        fd_layout.setSpacing(4)
        self.priority_widgets = []
        feeders = self.db.fetch_all(
            "SELECT name, priority FROM feeders WHERE status='active' ORDER BY priority DESC, name"
        )
        for f in feeders:
            row_w  = QWidget()
            row_l  = QHBoxLayout()
            row_l.setContentsMargins(4, 2, 4, 2)
            row_l.setSpacing(8)
            lbl = QLabel(f['name'])
            lbl.setMinimumWidth(150)
            lbl.setStyleSheet("font-size:11px;")
            row_l.addWidget(lbl, 3)
            cb = QComboBox()
            cb.addItems(['critical', 'high', 'medium', 'low'])
            cb.setCurrentText(f['priority'])
            cb.setMinimumHeight(30)
            cb.setMinimumWidth(110)
            cb.currentTextChanged.connect(
                lambda val, fn=f['name']: self._on_priority_changed(fn, val)
            )
            row_l.addWidget(cb, 2)
            row_w.setLayout(row_l)
            fd_layout.addWidget(row_w)
            self.priority_widgets.append({'name': f['name'], 'combo': cb})
        fd_layout.addStretch()
        fd_widget.setLayout(fd_layout)
        scroll.setWidget(fd_widget)
        prl.addWidget(scroll)
        pri_grp.setLayout(prl)
        ll.addWidget(pri_grp)

        # Buttons
        self.optimize_btn = QPushButton("⚡  GENERATE OPTIMAL SCHEDULE")
        self.optimize_btn.setMinimumHeight(52)
        self.optimize_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.optimize_btn.clicked.connect(self.optimize)
        ll.addWidget(self.optimize_btn)

        self.cancel_btn = QPushButton("⛔  CANCEL")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:#ef4444;color:white;font-weight:bold;border-radius:6px;}"
            "QPushButton:hover{background:#dc2626;}"
            "QPushButton:disabled{background:#94a3b8;}"
        )
        self.cancel_btn.clicked.connect(self._cancel)
        ll.addWidget(self.cancel_btn)
        ll.addStretch()
        left.setLayout(ll)
        splitter.addWidget(left)

        # ── RIGHT: results ────────────────────────────────────────────────────
        right = QWidget()
        rl = QVBoxLayout()
        rl.setSpacing(10)

        # Metrics cards row
        met_grp = QGroupBox("Optimization Metrics")
        ml = QHBoxLayout()
        ml.setSpacing(12)
        self.deficit_label    = self._metric_card("Deficit",        "— MW",  "#ef4444")
        self.fairness_label   = self._metric_card("Jain Fairness",  "—",     "#16a34a")
        self.protected_label  = self._metric_card("Protected Load", "— %",   "#3b82f6")
        self.status_label_opt = self._metric_card("LP Status",      "—",     "#f59e0b")
        for w in [self.deficit_label, self.fairness_label,
                  self.protected_label, self.status_label_opt]:
            ml.addWidget(w)
        met_grp.setLayout(ml)
        rl.addWidget(met_grp)

        # Gantt chart — LARGE
        gantt_grp = QGroupBox("24-Hour Power Allocation Gantt Chart — ON/OFF per Feeder")
        gl = QVBoxLayout()
        self.canvas = FigureCanvas(Figure(figsize=(11, 5.5), dpi=90))
        self.canvas.setMinimumHeight(380)
        self.ax = self.canvas.figure.add_subplot(111)
        self.ax.set_facecolor("#f8fafc")
        self.canvas.figure.patch.set_facecolor("#f8fafc")
        self.ax.text(0.5, 0.5, "Run optimization to see the Gantt chart",
                     ha='center', va='center', color='#94a3b8', fontsize=12,
                     transform=self.ax.transAxes)
        self.ax.set_axis_off()
        gl.addWidget(self.canvas)
        gantt_grp.setLayout(gl)
        rl.addWidget(gantt_grp)

        # Detailed schedule table — NO max height cap (fills space)
        sched_grp = QGroupBox("Detailed Schedule — Hour-by-Hour Feeder Status")
        sl = QVBoxLayout()
        self.schedule_table = QTableWidget()
        self.schedule_table.setColumnCount(5)
        self.schedule_table.setHorizontalHeaderLabels(
            ["Hour", "Feeder", "Demand (MW)", "Allocated (MW)", "Status"]
        )
        hh = self.schedule_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed);  self.schedule_table.setColumnWidth(0, 70)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed);  self.schedule_table.setColumnWidth(2, 110)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed);  self.schedule_table.setColumnWidth(3, 120)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed);  self.schedule_table.setColumnWidth(4, 100)
        self.schedule_table.verticalHeader().setVisible(False)
        self.schedule_table.verticalHeader().setDefaultSectionSize(36)
        self.schedule_table.setAlternatingRowColors(True)
        self.schedule_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.schedule_table.setMinimumHeight(260)   # FIX: was maxHeight 200 cap
        self.schedule_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        sl.addWidget(self.schedule_table)
        sched_grp.setLayout(sl)
        rl.addWidget(sched_grp, 1)   # stretch = 1 fills all remaining space
        right.setLayout(rl)
        splitter.addWidget(right)
        splitter.setSizes([340, 1060])
        layout.addWidget(splitter)
        self.setLayout(layout)

    # ── helpers ───────────────────────────────────────────────────────────────
    @staticmethod
    def _metric_card(title: str, value: str, color: str) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout()
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet(f"font-size:11px;color:#64748b;background:transparent;")
        v = QLabel(value)
        v.setObjectName("metric_val")
        v.setStyleSheet(
            f"font-size:18px;font-weight:bold;color:{color};background:transparent;"
        )
        cl.addWidget(t); cl.addWidget(v)
        card.setLayout(cl)
        card._val_lbl = v
        return card

    def _load_from_db(self):
        try:
            df = self.db.get_feeder_data()
            if df.empty:
                QMessageBox.warning(
                    self, "No Data", "No feeder data in database.\nImport CSV first."
                ); return
            total_demand    = float(df.groupby('feeder')['load'].mean().sum())
            total_available = total_demand * 0.92
            self.total_demand.setValue(round(total_demand, 1))
            self.available_power.setValue(round(total_available, 1))
            QMessageBox.information(
                self, "Loaded from Database",
                f"Demand:  {total_demand:.1f} MW\n"
                f"Supply:  {total_available:.1f} MW  (92% of demand)"
            )
        except Exception as e:
            QMessageBox.critical(self, "Load Failed", str(e))

    def _on_priority_changed(self, feeder_name: str, new_priority: str):
        """
        FIX: Show popup for ANY feeder set to critical, not just keyword-matched ones.
        Also save the updated priority back to DB.
        """
        try:
            self.db.update_feeder_priority(feeder_name, new_priority)
        except Exception:
            pass

        if new_priority != "critical":
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("⚠  Critical Priority — Safety Notice")
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setText(f"<b>{feeder_name}</b> has been set to <b>CRITICAL</b> priority.")
        msg.setInformativeText(
            "CRITICAL feeders receive guaranteed minimum supply (95% of demand) "
            "at all times, regardless of available power.\n\n"
            "Typical critical facilities:\n"
            "  • Hospitals and medical centres\n"
            "  • Airport and military installations\n"
            "  • Water treatment and pump stations\n"
            "  • Emergency services\n\n"
            "The LP optimizer will enforce the α = 0.95 minimum service-ratio "
            "constraint (Equation 4.4) for this feeder."
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()

    def _cancel(self):
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.cancel_btn.setEnabled(False)

    def _get_forecasted_demand_per_feeder(self) -> dict:
        """
        FIX: Retrieve latest forecasted demand per feeder from DB forecasts table.
        Returns dict mapping feeder_name -> forecasted_load (MW, averaged over horizon).
        Falls back to recent actual load if no forecast exists.
        """
        result = {}
        try:
            # Try latest forecasts first (preferred: use AI forecast, not historical mean)
            rows = self.db.fetch_all(
                """SELECT feeder, AVG(predicted_load) as avg_load
                   FROM forecasts
                   WHERE horizon <= 24
                   GROUP BY feeder"""
            )
            for r in rows:
                if r["feeder"] and r["avg_load"]:
                    result[r["feeder"]] = float(r["avg_load"])

            # For feeders without forecasts, use recent actual mean
            rows2 = self.db.fetch_all(
                """SELECT feeder, AVG(load) as avg_load
                   FROM feeder_data
                   WHERE timestamp >= datetime('now', '-7 days')
                   GROUP BY feeder"""
            )
            for r in rows2:
                if r["feeder"] and r["feeder"] not in result and r["avg_load"]:
                    result[r["feeder"]] = float(r["avg_load"])
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Could not fetch forecasted demand: %s", e)
        return result

        # ── optimization ──────────────────────────────────────────────────────────
    def optimize(self):
        available = self.available_power.value()
        demand    = self.total_demand.value()
        hours     = list(range(self.hours_spin.value()))

        # FIX: Use forecasted demand per feeder from DB rather than uniform split.
        # Uniform split (demand/n) ignores per-feeder load profiles and makes
        # the LP meaningless. Forecasted values give realistic per-feeder demands.
        forecast_demand = self._get_forecasted_demand_per_feeder()
        n_feeders = max(len(self.priority_widgets), 1)

        feeders = []
        for pw in self.priority_widgets:
            feeder_name = pw['name']
            # Use forecasted demand if available, else fall back to proportional share
            if feeder_name in forecast_demand and forecast_demand[feeder_name] > 0:
                d = forecast_demand[feeder_name]
            else:
                d = demand / n_feeders
            feeders.append({
                'name':     feeder_name,
                'priority': pw['combo'].currentText(),
                'demand':   d,
            })

        if not feeders:
            QMessageBox.warning(
                self, "No Feeders",
                "No feeders configured.\nGo to Feeder Management to add feeders."
            ); return

        self.optimize_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.worker = OptimizationWorker(
            self.optimizer, available, demand, feeders, hours
        )
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(
            lambda r, f=feeders: self._optimization_done(r, f, hours)
        )
        self.worker.error.connect(self._optimization_error)
        self.worker.start()

    def _optimization_done(self, result, feeders, hours):
        self.optimize_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)

        # Update metric cards
        self.deficit_label._val_lbl.setText(f"{result['deficit']:.1f} MW")
        self.fairness_label._val_lbl.setText(f"{result['fairness_index']:.3f}")
        self.protected_label._val_lbl.setText(f"{result['protected_pct']:.1f}%")
        self.status_label_opt._val_lbl.setText(result.get('status', 'Optimal'))

        schedule = result['schedule']
        self._draw_gantt(schedule, feeders, hours)
        self._populate_table(schedule, feeders)

        # Save to DB
        try:
            self.db.save_schedule(schedule, datetime.now().strftime('%Y-%m-%d'))
        except Exception as e:
            print(f"Schedule save warning: {e}")

        QMessageBox.information(
            self, "✅ Optimization Complete",
            f"LP Optimization finished successfully.\n\n"
            f"Jain's Fairness Index:  {result['fairness_index']:.3f}  "
            f"(target ≥ 0.90)\n"
            f"Protected Load:         {result['protected_pct']:.1f}%\n"
            f"Deficit:                {result['deficit']:.1f} MW\n"
            f"LP Status:              {result.get('status','Optimal')}"
        )

    def _optimization_error(self, error_msg: str):
        self.optimize_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        QMessageBox.critical(self, "Optimization Error", error_msg)

    # ── Gantt chart ───────────────────────────────────────────────────────────
    def _draw_gantt(self, schedule, feeders, hours):
        ax = self.ax
        ax.clear()
        ax.set_facecolor("#f8fafc")
        self.canvas.figure.patch.set_facecolor("#f8fafc")

        feeder_names = [f['name'] for f in feeders]
        n = len(feeder_names)
        if n == 0:
            return

        # Build allocation matrix  [feeder_idx][hour] = allocated_mw
        alloc = {fn: {h: 0.0 for h in hours} for fn in feeder_names}
        demand_map = {f['name']: f['demand'] for f in feeders}
        for item in schedule:
            alloc[item['feeder']][item['hour']] = item['allocated_power']

        bar_h = 0.65
        yticks, ylabels = [], []

        for i, fname in enumerate(feeder_names):
            y     = n - i - 1
            pri   = next((f['priority'] for f in feeders if f['name'] == fname), 'low')
            color = PRIORITY_COLORS.get(pri, "#94a3b8")
            d     = demand_map.get(fname, 1.0)

            yticks.append(y)
            ylabels.append(fname)

            for h in hours:
                a = alloc[fname].get(h, 0.0)
                on = a > (d / max(len(hours), 1)) * 0.05   # on if >5% allocated
                fc = color if on else "#f1f5f9"
                ec = color
                rect = mpatches.FancyBboxPatch(
                    (h, y - bar_h / 2), 0.9, bar_h,
                    boxstyle="round,pad=0.03",
                    fc=fc, ec=ec, lw=1, alpha=0.92, zorder=2
                )
                ax.add_patch(rect)
                # MW label inside bar if ON
                if on:
                    ax.text(
                        h + 0.45, y, f"{a:.1f}",
                        ha='center', va='center', fontsize=6.5,
                        color='white' if on else color,
                        fontweight='bold', zorder=3
                    )

        ax.set_xlim(-0.2, max(hours) + 1.2 if hours else 24.2)
        ax.set_ylim(-0.7, n - 0.3)
        ax.set_yticks(yticks)
        ax.set_yticklabels(ylabels, fontsize=9)
        ax.set_xlabel("Hour of Day", fontsize=10, color='#374151')
        ax.set_xticks(hours)
        ax.set_xticklabels([f"{h:02d}:00" for h in hours], fontsize=8, rotation=45)
        ax.set_title("Feeder Allocation Schedule — Values in MW  |  Coloured = ON,  Grey = OFF",
                     fontsize=10, color='#0f172a', fontweight='bold')
        ax.grid(axis='x', color='#e2e8f0', alpha=0.6, zorder=1)
        for sp in ['top', 'right']:
            ax.spines[sp].set_visible(False)

        # Legend
        legend_patches = [
            mpatches.Patch(fc=PRIORITY_COLORS['critical'], label='Critical'),
            mpatches.Patch(fc=PRIORITY_COLORS['high'],     label='High'),
            mpatches.Patch(fc=PRIORITY_COLORS['medium'],   label='Medium'),
            mpatches.Patch(fc=PRIORITY_COLORS['low'],      label='Low'),
            mpatches.Patch(fc='#f1f5f9', ec='#94a3b8',    label='OFF (outage)'),
        ]
        ax.legend(handles=legend_patches, loc='lower right', fontsize=8,
                  fancybox=True, framealpha=0.9)

        self.canvas.figure.tight_layout(pad=0.5)
        self.canvas.draw()

    # ── table ─────────────────────────────────────────────────────────────────
    def _populate_table(self, schedule, feeders):
        demand_map = {f['name']: f['demand'] for f in feeders}
        n_hours    = len({item['hour'] for item in schedule}) or 1

        self.schedule_table.setRowCount(len(schedule))
        for i, item in enumerate(schedule):
            h    = item['hour']
            fn   = item['feeder']
            alloc= item['allocated_power']
            d    = demand_map.get(fn, 1.0) / n_hours
            pri  = item.get('priority', 'low')
            on   = alloc > d * 0.05
            color = PRIORITY_COLORS.get(pri, "#94a3b8")

            self.schedule_table.setItem(i, 0, self._centered(f"{h:02d}:00"))
            self.schedule_table.setItem(i, 1, QTableWidgetItem(fn))
            self.schedule_table.setItem(i, 2, self._centered(f"{d:.2f} MW"))
            alloc_item = self._centered(f"{alloc:.3f} MW")
            alloc_item.setForeground(QColor(color))
            alloc_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.schedule_table.setItem(i, 3, alloc_item)

            status_item = QTableWidgetItem("✅  ON" if on else "⛔  OFF")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            status_item.setForeground(
                QColor("#16a34a") if on else QColor("#ef4444")
            )
            status_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.schedule_table.setItem(i, 4, status_item)

        self.schedule_table.resizeRowsToContents()

    @staticmethod
    def _centered(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item
