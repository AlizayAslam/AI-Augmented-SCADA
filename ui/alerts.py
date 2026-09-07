"""
Alerts Page for SCADA System
FIX: Acknowledge removes alert from visible list immediately.
FIX: Renamed "Resolve All" → "Acknowledge All".
FIX: "Acknowledge All" clears all alerts from list.
FIX: No more AlertManager re-creation / log spam on every refresh.
FIX: Per-row Resolve button removed — Acknowledge is the only action.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTableWidget, QTableWidgetItem, QComboBox,
    QGroupBox, QTextEdit, QMessageBox, QHeaderView, QFrame,
    QSizePolicy, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont


class AlertsPage(QWidget):

    def __init__(self, db, alert_manager=None):
        super().__init__()
        self.db               = db
        self.alert_manager    = alert_manager   # shared instance from dashboard
        self.selected_alert_id = None
        self._all_alerts      = []
        self.init_ui()
        self.load_alerts()

        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_alerts)
        self.refresh_timer.start(30_000)   # refresh every 30 s (not 15)

    # ── UI ────────────────────────────────────────────────────────────────────
    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        hdr = QLabel("Alerts & Notifications")
        hdr.setStyleSheet("font-size:22px;font-weight:bold;color:#0f172a;")
        layout.addWidget(hdr)

        # Summary bar ─────────────────────────────────────────────────────────
        self._summary_bar = QFrame()
        self._summary_bar.setObjectName("card")
        sb_layout = QHBoxLayout()
        sb_layout.setContentsMargins(16, 10, 16, 10)
        sb_layout.setSpacing(24)
        self._lbl_total    = self._make_badge("Total",    "0", "#3b82f6")
        self._lbl_critical = self._make_badge("Critical", "0", "#ef4444")
        self._lbl_warning  = self._make_badge("Warning",  "0", "#f59e0b")
        self._lbl_info     = self._make_badge("Info",     "0", "#16a34a")
        for w in [self._lbl_total, self._lbl_critical,
                  self._lbl_warning, self._lbl_info]:
            sb_layout.addWidget(w)
        sb_layout.addStretch()
        self._summary_bar.setLayout(sb_layout)
        layout.addWidget(self._summary_bar)

        # Filter row ──────────────────────────────────────────────────────────
        fr = QHBoxLayout()
        fr.addWidget(QLabel("Filter by severity:"))
        self.severity_filter = QComboBox()
        self.severity_filter.addItems(["All", "Critical", "Warning", "Info"])
        self.severity_filter.setMinimumHeight(36)
        self.severity_filter.setMinimumWidth(160)
        self.severity_filter.currentTextChanged.connect(self._apply_filter)
        fr.addWidget(self.severity_filter)

        # Toggle: hide acknowledged
        self.hide_acked_chk = QCheckBox("Hide acknowledged")
        self.hide_acked_chk.setChecked(True)
        self.hide_acked_chk.setToolTip("When checked, acknowledged alerts are not shown")
        self.hide_acked_chk.stateChanged.connect(self._apply_filter)
        fr.addWidget(self.hide_acked_chk)

        fr.addStretch()

        self.refresh_btn = QPushButton("↻  Refresh")
        self.refresh_btn.setMinimumHeight(36)
        self.refresh_btn.setMinimumWidth(110)
        self.refresh_btn.clicked.connect(self.load_alerts)
        fr.addWidget(self.refresh_btn)

        # "Acknowledge All" button (was "Resolve All")
        ack_all_btn = QPushButton("✓  Acknowledge All")
        ack_all_btn.setMinimumHeight(36)
        ack_all_btn.setMinimumWidth(150)
        ack_all_btn.setStyleSheet(
            "QPushButton{background:#3b82f6;color:white;border-radius:6px;font-weight:bold;}"
            "QPushButton:hover{background:#2563eb;}"
        )
        ack_all_btn.clicked.connect(self._acknowledge_all)
        fr.addWidget(ack_all_btn)

        layout.addLayout(fr)

        # Main alerts table ───────────────────────────────────────────────────
        self.alerts_table = QTableWidget()
        self.alerts_table.setAlternatingRowColors(True)
        self.alerts_table.setColumnCount(7)
        self.alerts_table.setHorizontalHeaderLabels(
            ["ID", "Time", "Severity", "Type", "Title", "Feeder", "Action"]
        )
        hh = self.alerts_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed);   self.alerts_table.setColumnWidth(0, 48)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed);   self.alerts_table.setColumnWidth(1, 145)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed);   self.alerts_table.setColumnWidth(2, 90)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed);   self.alerts_table.setColumnWidth(3, 100)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed);   self.alerts_table.setColumnWidth(5, 190)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed);   self.alerts_table.setColumnWidth(6, 110)
        self.alerts_table.verticalHeader().setDefaultSectionSize(46)
        self.alerts_table.verticalHeader().setVisible(False)
        self.alerts_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.alerts_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.alerts_table.itemSelectionChanged.connect(self._on_alert_selected)
        self.alerts_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.alerts_table, 1)

        # Detail box ──────────────────────────────────────────────────────────
        detail_grp = QGroupBox("Alert Details")
        detail_grp.setStyleSheet("QGroupBox{font-weight:bold;font-size:13px;}")
        dl = QVBoxLayout()
        dl.setSpacing(8)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumHeight(110)
        self.details_text.setMaximumHeight(130)
        self.details_text.setPlaceholderText("Click an alert row to see full details here…")
        dl.addWidget(self.details_text)
        detail_grp.setLayout(dl)
        layout.addWidget(detail_grp)

        self.setLayout(layout)

    # ── helper ────────────────────────────────────────────────────────────────
    @staticmethod
    def _make_badge(title: str, value: str, color: str) -> QWidget:
        w = QWidget()
        l = QHBoxLayout()
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(6)
        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color};font-size:14px;background:transparent;")
        ttl = QLabel(f"{title}:")
        ttl.setStyleSheet("color:#64748b;font-size:12px;background:transparent;")
        val = QLabel(value)
        val.setObjectName(f"badge_{title.lower()}")
        val.setStyleSheet(
            f"color:{color};font-size:15px;font-weight:bold;background:transparent;"
        )
        l.addWidget(dot); l.addWidget(ttl); l.addWidget(val)
        w.setLayout(l)
        w._val_lbl = val
        return w

    def _update_summary(self, alerts):
        # Count only unacknowledged for summary badges
        unacked = [a for a in alerts if not a.get('acknowledged')]
        total    = len(unacked)
        critical = sum(1 for a in unacked if a['severity'] == 'critical')
        warning  = sum(1 for a in unacked if a['severity'] == 'warning')
        info     = sum(1 for a in unacked if a['severity'] == 'info')
        self._lbl_total._val_lbl.setText(str(total))
        self._lbl_critical._val_lbl.setText(str(critical))
        self._lbl_warning._val_lbl.setText(str(warning))
        self._lbl_info._val_lbl.setText(str(info))

    # ── data ─────────────────────────────────────────────────────────────────
    def load_alerts(self):
        """Fetch active alerts — use shared alert_manager, never create a new one."""
        # Use the shared instance if available; never instantiate a new AlertManager here
        if self.alert_manager is not None:
            try:
                self.alert_manager.check_all()
            except Exception:
                pass

        self._all_alerts = self.db.get_active_alerts()
        self._update_summary(self._all_alerts)
        self._apply_filter()

    def _apply_filter(self):
        sev = self.severity_filter.currentText()
        hide_acked = self.hide_acked_chk.isChecked()

        filtered = self._all_alerts
        if sev != "All":
            filtered = [a for a in filtered
                        if a['severity'].lower() == sev.lower()]
        if hide_acked:
            filtered = [a for a in filtered if not a.get('acknowledged')]

        self._populate_table(filtered)

    def _populate_table(self, alerts):
        self.alerts_table.setRowCount(len(alerts))

        SEV_STYLES = {
            'critical': ("#fef2f2", "#dc2626"),
            'warning':  ("#fffbeb", "#d97706"),
            'info':     ("#eff6ff", "#2563eb"),
        }

        for i, alert in enumerate(alerts):
            is_acked = bool(alert.get('acknowledged'))

            # ID
            id_item = QTableWidgetItem(str(alert['id']))
            id_item.setData(Qt.ItemDataRole.UserRole, alert['id'])
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.alerts_table.setItem(i, 0, id_item)

            # Time
            ts = str(alert.get('timestamp', ''))[:19]
            self.alerts_table.setItem(i, 1, QTableWidgetItem(ts))

            # Severity badge
            sev = (alert.get('severity') or 'info').lower()
            bg, fg = SEV_STYLES.get(sev, ("#f8fafc", "#374151"))
            sev_item = QTableWidgetItem(sev.upper())
            sev_item.setBackground(QColor(bg))
            sev_item.setForeground(QColor(fg))
            sev_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            sev_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.alerts_table.setItem(i, 2, sev_item)

            # Type
            self.alerts_table.setItem(i, 3, QTableWidgetItem(alert.get('type', '—')))

            # Title
            title_text = ("✓ " if is_acked else "") + alert.get('title', '—')
            title_item = QTableWidgetItem(title_text)
            title_item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            if is_acked:
                title_item.setForeground(QColor("#94a3b8"))
            self.alerts_table.setItem(i, 4, title_item)

            # Feeder
            feeder = alert.get('feeder') or 'System'
            self.alerts_table.setItem(i, 5, QTableWidgetItem(feeder))

            # Action — single Acknowledge button (only if not yet acked)
            act_w = QWidget()
            act_l = QHBoxLayout()
            act_l.setContentsMargins(4, 4, 4, 4)
            act_l.setSpacing(6)

            if not is_acked:
                ack_btn = QPushButton("✓ Acknowledge")
                ack_btn.setFixedHeight(32)
                ack_btn.setMinimumWidth(96)
                ack_btn.setStyleSheet(
                    "QPushButton{background:#3b82f6;color:white;border-radius:5px;"
                    "font-size:12px;font-weight:bold;}"
                    "QPushButton:hover{background:#2563eb;}"
                )
                ack_btn.setToolTip("Acknowledge and dismiss this alert")
                ack_btn.clicked.connect(
                    lambda _, aid=alert['id']: self._acknowledge_id(aid)
                )
                act_l.addWidget(ack_btn)
            else:
                done_lbl = QLabel("✓ Done")
                done_lbl.setStyleSheet("color:#94a3b8;font-size:12px;padding:4px;")
                act_l.addWidget(done_lbl)

            act_w.setLayout(act_l)
            self.alerts_table.setCellWidget(i, 6, act_w)

    # ── selection ─────────────────────────────────────────────────────────────
    def _on_alert_selected(self):
        rows = self.alerts_table.selectedItems()
        if not rows:
            return
        row = rows[0].row()
        id_item = self.alerts_table.item(row, 0)
        if not id_item:
            return
        aid = id_item.data(Qt.ItemDataRole.UserRole)
        self.selected_alert_id = aid
        for a in self._all_alerts:
            if a['id'] == aid:
                ack = "✓ Yes" if a.get('acknowledged') else "No"
                self.details_text.setPlainText(
                    f"ID:           {a['id']}\n"
                    f"Title:        {a.get('title','—')}\n"
                    f"Message:      {a.get('message','—')}\n"
                    f"Type:         {a.get('type','—')}\n"
                    f"Severity:     {a.get('severity','—').upper()}\n"
                    f"Feeder:       {a.get('feeder') or 'System'}\n"
                    f"Time:         {str(a.get('timestamp',''))[:19]}\n"
                    f"Acknowledged: {ack}"
                )
                break

    # ── actions ───────────────────────────────────────────────────────────────
    def _acknowledge_id(self, alert_id: int):
        """Acknowledge one alert — it disappears from the list immediately."""
        self.db.acknowledge_alert(alert_id, "operator")
        self.db.resolve_alert(alert_id)           # also mark resolved so it won't resurface
        self.db.log_action("operator", "acknowledge_alert", f"Acknowledged alert {alert_id}")
        self.load_alerts()

    def _acknowledge_all(self):
        """Acknowledge every currently visible active alert."""
        unacked = [a for a in self._all_alerts if not a.get('acknowledged')]
        if not unacked:
            QMessageBox.information(self, "No Active Alerts", "There are no active alerts to acknowledge.")
            return
        if QMessageBox.question(
            self, "Acknowledge All",
            f"Acknowledge and clear all {len(unacked)} active alerts?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        for a in unacked:
            self.db.acknowledge_alert(a['id'], "operator")
            self.db.resolve_alert(a['id'])
        self.db.log_action("operator", "acknowledge_all_alerts", f"Acknowledged {len(unacked)} alerts")
        self.load_alerts()

    def closeEvent(self, event):
        self.refresh_timer.stop()
        event.accept()


