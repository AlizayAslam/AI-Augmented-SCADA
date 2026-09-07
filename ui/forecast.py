

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QSpinBox, QGroupBox,
    QRadioButton, QButtonGroup, QMessageBox,
    QTableWidget, QTableWidgetItem, QProgressBar,
    QFrame, QApplication, QHeaderView, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QCursor, QColor
import matplotlib
matplotlib.use("QtAgg")
import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

from core.model_registry import model_registry

logger = logging.getLogger(__name__)


# ── Inference-only worker ──────────────────────────────────────────────────────
class ForecastWorker(QThread):
    """
   
    """
    progress = pyqtSignal(int)
    status   = pyqtSignal(str)
    finished = pyqtSignal(dict)
    error    = pyqtSignal(str)

    def __init__(self, db, model_type, horizon, feeder):
        super().__init__()
        self.db         = db
        self.model_type = model_type
        self.horizon    = horizon
        self.feeder     = feeder

    def run(self):
        try:
            self.status.emit(" Loading pre-trained model from registry…")
            self.progress.emit(15)

            forecaster = model_registry.get_forecaster(self.model_type, self.feeder)
            if forecaster is None:
                self.error.emit(
                    f"No pre-trained {self.model_type} model found for '{self.feeder}'.\n\n"
                    f"Please run the offline training pipeline:\n"
                    f"    python train_models_offline.py\n\n"
                    f"This separates training from the runtime application."
                )
                return

            self.status.emit(" Fetching recent feeder data…")
            self.progress.emit(35)

            df = self.db.get_feeder_data(feeder=self.feeder)
            if df.empty or len(df) < 24:
                self.error.emit(f"Insufficient data for feeder '{self.feeder}' (need ≥ 24 rows).")
                return

            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.sort_values("timestamp").reset_index(drop=True)

            self.status.emit("📈 Running inference (forward pass only)…")
            self.progress.emit(60)

            if self.model_type in ("LSTM", "GRU"):
                forecast = forecaster.forecast(self.horizon, df)
            else:
                forecast = forecaster.forecast(self.horizon)

            if self.isInterruptionRequested():
                self.error.emit("Cancelled"); return

            # Retrieve stored metrics from registry (no re-computation)
            stored = model_registry.get_model_metrics(self.feeder)
            metrics = stored.get(self.model_type, {}).get("metrics", {})

            self.status.emit("Forecast complete (model loaded from registry)")
            self.progress.emit(100)

            # Log forecast run
            logger.info(
                "FORECAST | feeder=%s | model=%s | horizon=%d | first_val=%.3f",
                self.feeder, self.model_type, self.horizon,
                float(forecast[0]) if len(forecast) > 0 else 0.0,
            )

            self.finished.emit({
                "forecast": forecast,
                "feeder":   self.feeder,
                "horizon":  self.horizon,
                "metrics":  metrics,
                "model":    self.model_type,
            })

        except Exception as e:
            logger.exception("Forecast inference error: %s", e)
            self.error.emit(str(e))


# ── Page ──────────────────────────────────────────────────────────────────────
class ForecastPage(QWidget):

    def __init__(self, db):
        super().__init__()
        self.db      = db
        self.worker  = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)

        # Header
        hdr = QLabel("Sukkur Power Distribution — Short-Term Load Forecasting")
        hdr.setStyleSheet("font-size:20px;font-weight:bold;color:#0f172a;")
        layout.addWidget(hdr)

        # Architecture notice
        arch_notice = QLabel(
            "ℹ️  Runtime inference mode — models are loaded from pre-trained registry. "
            "To train new models run: python train_models_offline.py"
        )
        arch_notice.setStyleSheet(
            "background:#dbeafe;padding:8px 12px;border-radius:6px;"
            "color:#1e40af;font-size:11px;border:1px solid #93c5fd;"
        )
        arch_notice.setWordWrap(True)
        layout.addWidget(arch_notice)

        # Status bar
        self.status_label = QLabel("Ready — select a feeder and model, then click Run Forecast")
        self.status_label.setStyleSheet(
            "background:#1e293b;padding:8px 12px;border-radius:6px;"
            "color:#94a3b8;font-family:monospace;font-size:12px;"
        )
        layout.addWidget(self.status_label)

        # ── Controls row ──────────────────────────────────────────────────────
        controls = QHBoxLayout()
        controls.setSpacing(10)

        # Model selection
        model_grp = QGroupBox("AI Model (pre-trained)")
        model_grp.setMinimumWidth(220)
        ml = QVBoxLayout()
        ml.setSpacing(6)
        self.lstm_radio    = QRadioButton("LSTM — Long Short-Term Memory")
        self.gru_radio     = QRadioButton("GRU  — Gated Recurrent Unit")
        self.prophet_radio = QRadioButton("Prophet (Meta / Facebook)")
        self.lstm_radio.setChecked(True)
        for rb in [self.lstm_radio, self.gru_radio, self.prophet_radio]:
            rb.setMinimumHeight(28)
            ml.addWidget(rb)
        model_grp.setLayout(ml)
        controls.addWidget(model_grp)

        # Horizon
        hz_grp = QGroupBox("Forecast Horizon")
        hz_grp.setMinimumWidth(140)
        hl = QVBoxLayout()
        self.horizon_spin = QSpinBox()
        self.horizon_spin.setRange(1, 48)
        self.horizon_spin.setValue(24)
        self.horizon_spin.setSuffix(" hours")
        self.horizon_spin.setMinimumHeight(36)
        hl.addWidget(self.horizon_spin)
        hz_grp.setLayout(hl)
        controls.addWidget(hz_grp)

        # Feeder — loads NEPRA names from DB
        fd_grp = QGroupBox("Select Feeder")
        fd_grp.setMinimumWidth(220)
        fl = QVBoxLayout()
        self.feeder_combo = QComboBox()
        self.feeder_combo.setMinimumHeight(36)
        self._load_feeders()
        fl.addWidget(self.feeder_combo)
        fd_grp.setLayout(fl)
        controls.addWidget(fd_grp)

        # Model availability indicator
        avail_grp = QGroupBox("Model Status")
        avail_grp.setMinimumWidth(160)
        al = QVBoxLayout()
        self.avail_label = QLabel("—")
        self.avail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avail_label.setStyleSheet("font-size:12px;font-weight:bold;")
        al.addWidget(self.avail_label)
        avail_grp.setLayout(al)
        controls.addWidget(avail_grp)
        self.feeder_combo.currentTextChanged.connect(self._update_availability)
        self.lstm_radio.toggled.connect(lambda _: self._update_availability())
        self.gru_radio.toggled.connect(lambda _: self._update_availability())
        self.prophet_radio.toggled.connect(lambda _: self._update_availability())

        # Buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(8)
        self.run_btn = QPushButton("📈  RUN FORECAST")
        self.run_btn.setMinimumHeight(56)
        self.run_btn.setMinimumWidth(180)
        self.run_btn.setStyleSheet("QPushButton{font-size:13px;font-weight:bold;}")
        self.run_btn.clicked.connect(self.run_forecast)
        btn_col.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("⛔  CANCEL")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:#ef4444;color:white;font-weight:bold;"
            "border-radius:6px;}"
            "QPushButton:hover{background:#dc2626;}"
            "QPushButton:disabled{background:#94a3b8;}"
        )
        self.cancel_btn.clicked.connect(self._cancel)
        btn_col.addWidget(self.cancel_btn)
        controls.addLayout(btn_col)

        layout.addLayout(controls)

        # ── Progress ──────────────────────────────────────────────────────────
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(10)
        layout.addWidget(self.progress_bar)

        # ── Metrics panel (replaces training loss curve) ───────────────────
        metrics_grp = QGroupBox("Stored Model Metrics (from offline training registry)")
        ml2 = QHBoxLayout()
        self.mape_lbl = QLabel("MAPE: —")
        self.rmse_lbl = QLabel("RMSE: —")
        self.r2_lbl   = QLabel("R²: —")
        for lbl in [self.mape_lbl, self.rmse_lbl, self.r2_lbl]:
            lbl.setStyleSheet("font-size:14px;font-weight:bold;padding:8px;")
            ml2.addWidget(lbl)
        metrics_grp.setLayout(ml2)
        metrics_grp.setMinimumHeight(80)
        layout.addWidget(metrics_grp)

        # ── Forecast chart ───────────────────────────────────────────────────
        chart_grp = QGroupBox("Forecast Output")
        cl = QVBoxLayout()
        self.figure = Figure(figsize=(10, 4), dpi=90)
        self.figure.patch.set_facecolor("#ffffff")
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(300)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cl.addWidget(self.canvas)
        chart_grp.setLayout(cl)
        layout.addWidget(chart_grp)

        # ── Forecast table ───────────────────────────────────────────────────
        tbl_grp = QGroupBox("Forecast Values")
        tbl_layout = QVBoxLayout()
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Hour", "Timestamp", "Predicted Load (MW)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMaximumHeight(200)
        tbl_layout.addWidget(self.table)
        tbl_grp.setLayout(tbl_layout)
        layout.addWidget(tbl_grp)

        self.setLayout(layout)
        self._update_availability()

    def _load_feeders(self):
        self.feeder_combo.clear()
        rows = self.db.fetch_all("SELECT name FROM feeders WHERE status='active' ORDER BY name")
        for r in rows:
            self.feeder_combo.addItem(r["name"])

    def _get_selected_model(self) -> str:
        if self.gru_radio.isChecked():    return "GRU"
        if self.prophet_radio.isChecked(): return "Prophet"
        return "LSTM"

    def _update_availability(self):
        feeder     = self.feeder_combo.currentText()
        model_type = self._get_selected_model()
        if not feeder:
            self.avail_label.setText("—")
            return
        available = model_registry.model_available(model_type, feeder)
        if available:
            self.avail_label.setText("✅ Model Ready")
            self.avail_label.setStyleSheet("font-size:12px;font-weight:bold;color:#16a34a;")
        else:
            self.avail_label.setText("❌ Not Trained")
            self.avail_label.setStyleSheet("font-size:12px;font-weight:bold;color:#dc2626;")

    def _set_status(self, msg: str, bg: str = "#1e293b", fg: str = "#94a3b8"):
        self.status_label.setText(msg)
        self.status_label.setStyleSheet(
            f"background:{bg};padding:8px 12px;border-radius:6px;"
            f"color:{fg};font-family:monospace;font-size:12px;"
        )

    def run_forecast(self):
        feeder     = self.feeder_combo.currentText()
        model_type = self._get_selected_model()
        horizon    = self.horizon_spin.value()

        if not feeder:
            QMessageBox.warning(self, "No Feeder", "Please select a feeder.")
            return

        if not model_registry.model_available(model_type, feeder):
            QMessageBox.warning(
                self, "Model Not Found",
                f"No pre-trained {model_type} model found for '{feeder}'.\n\n"
                f"Run the offline training pipeline:\n"
                f"    python train_models_offline.py\n\n"
                f"Training must be done outside the runtime application."
            )
            return

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._set_status(f"📈 Running {model_type} inference…", "#1e3a5f", "#93c5fd")

        self.worker = ForecastWorker(self.db, model_type, horizon, feeder)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(lambda m: self._set_status(m, "#1e3a5f", "#93c5fd"))
        self.worker.finished.connect(self._on_forecast_done)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_forecast_done(self, result: dict):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._set_status("✅ Forecast complete", "#14532d", "#bbf7d0")

        forecast = result.get("forecast", [])
        metrics  = result.get("metrics", {})
        horizon  = result.get("horizon", len(forecast))
        feeder   = result.get("feeder", "")

        # Update metrics labels
        if metrics:
            mape = metrics.get("mape")
            rmse = metrics.get("rmse")
            r2   = metrics.get("r2")
            self.mape_lbl.setText(f"MAPE: {mape:.2f}%" if mape is not None else "MAPE: —")
            self.rmse_lbl.setText(f"RMSE: {rmse:.3f} MW" if rmse is not None else "RMSE: —")
            self.r2_lbl.setText(f"R²: {r2:.4f}" if r2 is not None else "R²: —")

        # Plot forecast
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        now   = datetime.now()
        times = [now + timedelta(hours=i) for i in range(len(forecast))]

        ax.plot(times, forecast, color="#3b82f6", lw=2, marker="o", markersize=3,
                label=f"{result.get('model','?')} Forecast")
        ax.set_title(f"{feeder} — {horizon}h Forecast (from {now.strftime('%d %b %Y %H:%M')})",
                     fontsize=11)
        ax.set_xlabel("Date / Time")
        ax.set_ylabel("Load (MW)")
        ax.legend()

        # Use date+time format when forecast spans >1 day, else time only
        if horizon > 24:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b\n%H:%M"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, horizon // 12)))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M\n%d %b"))
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=max(1, horizon // 8)))

        ax.grid(True, linestyle="--", alpha=0.4)
        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.canvas.update()

        # Populate table
        self.table.setRowCount(len(forecast))
        for i, (t, v) in enumerate(zip(times, forecast)):
            self.table.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.table.setItem(i, 1, QTableWidgetItem(t.strftime("%Y-%m-%d %H:%M")))
            self.table.setItem(i, 2, QTableWidgetItem(f"{v:.3f}"))

        self._update_availability()

    def _on_error(self, msg: str):
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self._set_status(f"❌ Error: {msg[:120]}", "#7f1d1d", "#fca5a5")
        QMessageBox.critical(self, "Forecast Error", msg)

    def _cancel(self):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            self.cancel_btn.setEnabled(False)
