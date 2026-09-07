"""
Data Import Page for SCADA System
FIX: Column hints now include voltage, current, power_factor.
FIX: Feeder names match NEPRA dataset (Civil Hospital Feeder, etc.).
FIX: Batch executemany insert — fast even for large CSVs.
FIX: Timestamp duplicate check uses (timestamp, feeder) pair.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QProgressBar, QMessageBox, QTextEdit, QFrame,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime
import os


# ── Worker thread ─────────────────────────────────────────────────────────────
class ImportWorker(QThread):
    progress              = pyqtSignal(int)
    status                = pyqtSignal(str)
    finished              = pyqtSignal(bool, str, int)
    feeder_action_required = pyqtSignal(list, str)

    def __init__(self, filepath, db):
        super().__init__()
        self.filepath = filepath
        self.db       = db
        self._autocreate = False
        self._warn_text  = ""

    def allow_autocreate_feeders(self, v: bool):
        self._autocreate = bool(v)

    def run(self):
        try:
            self.status.emit("📂 Reading file…")
            # Try multiple encodings
            df = None
            for enc in ('utf-8', 'utf-8-sig', 'latin1', 'cp1252'):
                try:
                    df = pd.read_csv(self.filepath, encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            if df is None:
                self.finished.emit(False, "Cannot read file (encoding issue).", 0)
                return
            self.progress.emit(15)

            # Normalise column names
            df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

            # Required columns check
            required = ['timestamp', 'feeder', 'load', 'loss']
            missing  = [c for c in required if c not in df.columns]
            if missing:
                self.finished.emit(
                    False,
                    f"Missing required columns: {', '.join(missing)}\n\n"
                    f"Required: timestamp, feeder, load, loss\n"
                    f"Optional: voltage, current, power_factor, temperature, humidity",
                    0,
                )
                return
            self.progress.emit(25)

            # Parse timestamps
            self.status.emit("🕐 Parsing timestamps…")
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
            if df['timestamp'].isna().any():
                self.finished.emit(
                    False,
                    "Some timestamps could not be parsed.\n"
                    "Use format: YYYY-MM-DD HH:MM:SS",
                    0,
                )
                return
            self.progress.emit(35)

            # Parse numeric columns
            self.status.emit("🔢 Validating numeric data…")
            for col in ['load', 'loss']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            if df['load'].isna().any() or df['loss'].isna().any():
                self.finished.emit(
                    False, "Invalid numeric values in load or loss columns.", 0
                )
                return

            # Optional columns — default if absent
            optionals = {
                'voltage':      11.0,
                'current':       0.0,
                'power_factor':  0.9,
                'temperature':  25.0,
                'humidity':     60.0,
            }
            for col, default in optionals.items():
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(default)
                else:
                    df[col] = default
            self.progress.emit(45)

            # Clean & validate
            self.status.emit("🧹 Cleaning data…")
            df = df.dropna(subset=['load', 'loss'])
            df = df[df['load']  >= 0]
            df = df[df['loss']  >= 0]
            df = df[df['loss']  <= df['load']]
            df = df.drop_duplicates(subset=['timestamp', 'feeder'])   # correct dup check

            if len(df) == 0:
                self.finished.emit(False, "No valid rows after cleaning.", 0)
                return
            self.progress.emit(55)

            # Data-quality warnings
            warns = []
            for feeder, grp in df.groupby('feeder'):
                diffs = grp['timestamp'].sort_values().diff().dropna()
                gaps  = diffs[diffs > pd.Timedelta(hours=2)]
                if not gaps.empty:
                    warns.append(f"⚠ Gaps > 2h in feeder '{feeder}': {len(gaps)} occurrence(s)")
            self._warn_text = "\n".join(warns)

            # Feeder existence check
            csv_feeders = sorted({str(x).strip() for x in df['feeder'].dropna()})
            existing    = {f['name'] for f in self.db.fetch_all("SELECT name FROM feeders")}
            missing_fds = [f for f in csv_feeders if f not in existing]

            if missing_fds and not self._autocreate:
                self.feeder_action_required.emit(missing_fds, self._warn_text)
                return

            if missing_fds and self._autocreate:
                for fn in missing_fds:
                    try:
                        self.db.add_feeder(fn, priority="medium", status="active")
                    except Exception:
                        pass
            self.progress.emit(65)

            # Save dataset record
            self.status.emit("💾 Saving to database…")
            cur = self.db.execute_query(
                "INSERT INTO datasets (filename, row_count, columns, status) VALUES (?,?,?,?)",
                (os.path.basename(self.filepath), len(df), ','.join(df.columns), 'active'),
            )
            dataset_id = cur.lastrowid
            self.progress.emit(72)

            # FAST batch insert using executemany  (fixes slow import)
            rows = []
            for _, r in df.iterrows():
                rows.append((
                    str(r['timestamp']),
                    str(r['feeder']).strip(),
                    float(r['load']),
                    float(r['loss']),
                    float(r['voltage']),
                    float(r['current']),
                    float(r['power_factor']),
                    float(r['temperature']),
                    float(r['humidity']),
                    dataset_id,
                ))

            # Use the persistent connection directly for bulk insert
            with self.db._conn_lock:
                conn = self.db._get_conn()
                conn.executemany(
                    """INSERT INTO feeder_data
                       (timestamp,feeder,load,loss,voltage,current,power_factor,
                        temperature,humidity,dataset_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    rows,
                )
                conn.commit()

            self.progress.emit(100)
            msg = f"Import successful!\n\nRows imported: {len(df):,}"
            if self._warn_text:
                msg += f"\n\nData-quality warnings:\n{self._warn_text}"
            self.finished.emit(True, msg, len(df))

        except Exception as e:
            self.finished.emit(False, f"Import error: {e}", 0)


# ── Page widget ───────────────────────────────────────────────────────────────
class DataImportPage(QWidget):

    def __init__(self, db):
        super().__init__()
        self.db           = db
        self.current_file = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        hdr = QLabel("Data Import — Sukkur Distribution Network")
        hdr.setStyleSheet("font-size:22px;font-weight:bold;color:#0f172a;")
        layout.addWidget(hdr)

        # Status bar
        self.status_lbl = QLabel("Ready — select a CSV file to begin")
        self.status_lbl.setStyleSheet(
            "background:#1e293b;color:#94a3b8;font-family:monospace;"
            "padding:8px 12px;border-radius:6px;font-size:12px;"
        )
        layout.addWidget(self.status_lbl)

        # Format info card
        info_card = QFrame()
        info_card.setObjectName("card")
        ic_layout = QVBoxLayout()
        ic_layout.setContentsMargins(16, 12, 16, 12)
        ic_layout.setSpacing(6)
        ic_layout.addWidget(
            self._bold_label("📋  CSV Format Requirements")
        )
        fmt = QTextEdit()
        fmt.setReadOnly(True)
        fmt.setMaximumHeight(230)
        fmt.setStyleSheet(
            "color:#374151;font-family:monospace;font-size:11px;"
            "background:#f8fafc;border:none;"
        )
        fmt.setPlainText(
            "REQUIRED COLUMNS\n"
            "─────────────────────────────────────────────────────────\n"
            "  timestamp     — YYYY-MM-DD HH:MM:SS  (hourly)\n"
            "  feeder        — Feeder name (must match system feeders below)\n"
            "  load          — Load in MW  (positive number)\n"
            "  loss          — Loss in MW  (positive, cannot exceed load)\n\n"
            "OPTIONAL COLUMNS  (defaults used if absent)\n"
            "─────────────────────────────────────────────────────────\n"
            "  voltage       — Line voltage in kV    (default 11.0)\n"
            "  current       — Line current in Amps  (default 0.0)\n"
            "  power_factor  — Power factor 0–1      (default 0.9)\n"
            "  temperature   — Ambient °C            (default 25.0)\n"
            "  humidity      — Humidity %            (default 60.0)\n\n"
            "EXAMPLE ROW\n"
            "─────────────────────────────────────────────────────────\n"
            "timestamp,feeder,load,loss,voltage,current,power_factor,temperature,humidity\n"
            "2024-01-15 08:00:00,Civil Hospital Feeder,8.45,1.35,11.0,440,0.92,28.5,62\n\n"
            "NEPRA SUKKUR FEEDERS (exact names required)\n"
            "─────────────────────────────────────────────────────────\n"
            "  • Civil Hospital Feeder       [CRITICAL]\n"
            "  • Airport Road Feeder         [HIGH]\n"
            "  • Rohri Industrial Feeder     [HIGH]\n"
            "  • Military Road Feeder        [HIGH]\n"
            "  • SITE Area Feeder            [MEDIUM]\n"
            "  • Barrage Colony Feeder       [MEDIUM]\n"
            "  • Shikarpur Road Feeder       [LOW]\n"
            "  • Old Sukkur Residential Feeder [LOW]"
        )
        ic_layout.addWidget(fmt)
        info_card.setLayout(ic_layout)
        layout.addWidget(info_card)

        # Upload area
        up_card = QFrame()
        up_card.setObjectName("card")
        up_layout = QVBoxLayout()
        up_layout.setContentsMargins(16, 16, 16, 16)
        up_layout.setSpacing(10)

        self.upload_btn = QPushButton("📁  SELECT CSV FILE")
        self.upload_btn.setMinimumHeight(80)
        self.upload_btn.setStyleSheet(
            "QPushButton{font-size:15px;font-weight:bold;border:2px dashed #16a34a;"
            "border-radius:8px;background:#f0fdf4;color:#16a34a;}"
            "QPushButton:hover{background:#dcfce7;}"
        )
        self.upload_btn.clicked.connect(self.select_file)
        up_layout.addWidget(self.upload_btn)

        self.file_label = QLabel("No file selected")
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.file_label.setStyleSheet(
            "color:#64748b;font-size:12px;padding:4px;"
        )
        up_layout.addWidget(self.file_label)
        up_card.setLayout(up_layout)
        layout.addWidget(up_card)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimumHeight(28)
        layout.addWidget(self.progress_bar)

        # Preview
        prev_lbl = self._bold_label("Data Preview (first 10 rows)")
        layout.addWidget(prev_lbl)
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(200)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.preview_table)

        # Import button
        self.import_btn = QPushButton("⬆  IMPORT DATA TO DATABASE")
        self.import_btn.setEnabled(False)
        self.import_btn.setMinimumHeight(52)
        self.import_btn.setStyleSheet(
            "QPushButton{font-size:14px;font-weight:bold;}"
            "QPushButton:disabled{background:#94a3b8;color:#e2e8f0;}"
        )
        self.import_btn.clicked.connect(self.import_data)
        layout.addWidget(self.import_btn)

        self.setLayout(layout)

    @staticmethod
    def _bold_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size:13px;font-weight:bold;color:#0f172a;")
        return lbl

    # ── file handling ─────────────────────────────────────────────────────────
    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv);;All Files (*)"
        )
        if path:
            self.current_file = path
            self.file_label.setText(f"✓  {os.path.basename(path)}  "
                                    f"({os.path.getsize(path) / 1024:.1f} KB)")
            self.import_btn.setEnabled(True)
            self._preview(path)
            self._set_status(f"File loaded: {os.path.basename(path)}", "#16a34a")

    def _preview(self, path: str):
        try:
            df = pd.read_csv(path, nrows=10)
            self.preview_table.setRowCount(len(df))
            self.preview_table.setColumnCount(len(df.columns))
            self.preview_table.setHorizontalHeaderLabels(list(df.columns))
            for i, row in df.iterrows():
                for j, val in enumerate(row):
                    self.preview_table.setItem(i, j, QTableWidgetItem(str(val)))
            self.preview_table.resizeColumnsToContents()
        except Exception as e:
            QMessageBox.warning(self, "Preview Error", str(e))

    def import_data(self):
        if not self.current_file:
            return
        self.import_btn.setEnabled(False)
        self.upload_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._set_status("Importing…", "#3b82f6")

        self.worker = ImportWorker(self.current_file, self.db)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.status.connect(lambda m: self._set_status(m, "#3b82f6"))
        self.worker.finished.connect(self._import_finished)
        self.worker.feeder_action_required.connect(self._handle_missing_feeders)
        self.worker.start()

    def _handle_missing_feeders(self, missing: list, warn_text: str):
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        lst = "\n".join(f"  • {f}" for f in missing[:20])
        if len(missing) > 20:
            lst += f"\n  … and {len(missing)-20} more"
        msg = (
            f"The CSV contains {len(missing)} feeder name(s) "
            f"not in the system:\n\n{lst}\n\n"
            f"Auto-create them as Medium priority and continue?"
        )
        if warn_text:
            msg += f"\n\nData-quality warnings:\n{warn_text}"
        if QMessageBox.question(
            self, "Missing Feeders", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) == QMessageBox.StandardButton.Yes:
            self.import_btn.setEnabled(False)
            self.upload_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.worker = ImportWorker(self.current_file, self.db)
            self.worker.allow_autocreate_feeders(True)
            self.worker.progress.connect(self.progress_bar.setValue)
            self.worker.status.connect(lambda m: self._set_status(m, "#3b82f6"))
            self.worker.finished.connect(self._import_finished)
            self.worker.feeder_action_required.connect(self._handle_missing_feeders)
            self.worker.start()
        else:
            self.import_btn.setEnabled(True)

    def _import_finished(self, success: bool, message: str, row_count: int):
        self.progress_bar.setVisible(False)
        self.upload_btn.setEnabled(True)
        if success:
            self._set_status(
                f"✅  Import complete — {row_count:,} rows saved", "#16a34a"
            )
            QMessageBox.information(
                self, "✅ Import Successful",
                f"{message}\n\nData is now available for Forecasting & Optimization."
            )
            self.db.log_action("system", "data_import", f"Imported {row_count} records")
            self.file_label.setText("No file selected")
            self.preview_table.setRowCount(0)
            self.import_btn.setEnabled(False)
            self.current_file = None
        else:
            self._set_status(f"❌  Import failed", "#ef4444")
            QMessageBox.critical(self, "❌ Import Failed", message)
            self.import_btn.setEnabled(True)

    def _set_status(self, msg: str, color: str = "#94a3b8"):
        self.status_lbl.setText(msg)
        self.status_lbl.setStyleSheet(
            f"background:#1e293b;color:{color};font-family:monospace;"
            f"padding:8px 12px;border-radius:6px;font-size:12px;font-weight:bold;"
        )
