"""
Feeder Management Page
FIX: Action column width increased to 280px — buttons no longer overlap border.
FIX: Row height 58px — all text fits without clipping.
FIX: Priority change also updates DB immediately.
FIX: Added critical-feeder popup when priority set to 'critical'.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QMessageBox, QLineEdit, QComboBox,
    QHeaderView, QAbstractItemView, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont


class FeederManagementPage(QWidget):

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        hdr = QLabel("Feeder Management")
        hdr.setStyleSheet("font-size:22px;font-weight:bold;color:#0f172a;")
        layout.addWidget(hdr)

        # ── Add new feeder ────────────────────────────────────────────────────
        add_grp = QGroupBox("Add New Feeder")
        add_grp.setStyleSheet("QGroupBox{font-weight:bold;font-size:13px;}")
        al = QHBoxLayout()
        al.setSpacing(10)

        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("Enter feeder name…")
        self.new_name.setMinimumHeight(42)
        al.addWidget(self.new_name, 3)

        self.new_priority = QComboBox()
        self.new_priority.addItems(["critical", "high", "medium", "low"])
        self.new_priority.setCurrentText("medium")
        self.new_priority.setMinimumHeight(42)
        self.new_priority.setMinimumWidth(140)
        al.addWidget(self.new_priority, 1)

        self.add_btn = QPushButton("⊕  Add Feeder")
        self.add_btn.setMinimumHeight(42)
        self.add_btn.setMinimumWidth(140)
        self.add_btn.setStyleSheet(
            "QPushButton{background:#16a34a;color:white;font-size:13px;"
            "font-weight:bold;border-radius:6px;}"
            "QPushButton:hover{background:#15803d;}"
        )
        self.add_btn.clicked.connect(self.add_feeder)
        al.addWidget(self.add_btn)

        add_grp.setLayout(al)
        layout.addWidget(add_grp)

        # ── Manage table ──────────────────────────────────────────────────────
        tbl_grp = QGroupBox("Manage Feeders")
        tbl_grp.setStyleSheet("QGroupBox{font-weight:bold;font-size:13px;}")
        tbl_grp.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        tbl_layout = QVBoxLayout()
        tbl_layout.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["Feeder Name", "Priority", "Status", "Rename To", "Actions"]
        )
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(1, 140)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 96)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(4, 280)   # FIX: was 240 — caused overlap

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(58)   # FIX: was 54
        self.table.setShowGrid(True)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        tbl_layout.addWidget(self.table)

        ref_row = QHBoxLayout()
        ref_btn = QPushButton("↻  Refresh")
        ref_btn.setMinimumHeight(36)
        ref_btn.setMinimumWidth(110)
        ref_btn.clicked.connect(self.refresh)
        ref_row.addWidget(ref_btn)
        ref_row.addStretch()
        tbl_layout.addLayout(ref_row)

        tbl_grp.setLayout(tbl_layout)
        layout.addWidget(tbl_grp, 1)
        self.setLayout(layout)

    # ── populate ──────────────────────────────────────────────────────────────
    def refresh(self):
        feeders = self.db.list_feeders(include_inactive=True)
        self.table.setRowCount(len(feeders))

        for r, f in enumerate(feeders):
            # Col 0: Name
            nm = QTableWidgetItem(f['name'])
            nm.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            self.table.setItem(r, 0, nm)

            # Col 1: Priority combo
            pc = QComboBox()
            pc.addItems(["critical", "high", "medium", "low"])
            pc.setCurrentText(f.get("priority") or "medium")
            pc.setMinimumHeight(42)
            pc.setStyleSheet(
                "QComboBox{font-size:12px;font-weight:bold;padding:4px 8px;"
                "border-radius:6px;border:1px solid #e2e8f0;}"
                "QComboBox:focus{border-color:#16a34a;}"
            )
            pc.currentTextChanged.connect(
                lambda val, fn=f['name']: self._change_priority(fn, val)
            )
            self.table.setCellWidget(r, 1, pc)

            # Col 2: Status
            status = (f.get("status") or "active").lower()
            st = QTableWidgetItem("● Active" if status == "active" else "○ Inactive")
            st.setForeground(
                QColor("#16a34a") if status == "active" else QColor("#ef4444")
            )
            st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            st.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            self.table.setItem(r, 2, st)

            # Col 3: Rename input
            ri = QLineEdit()
            ri.setPlaceholderText("Type new name…")
            ri.setMinimumHeight(42)
            ri.setStyleSheet(
                "font-size:12px;padding:4px 8px;border-radius:4px;"
                "border:1px solid #e2e8f0;"
            )
            self.table.setCellWidget(r, 3, ri)

            # Col 4: Action buttons — FIX: wider column, no text overflow
            act_w = QWidget()
            act_l = QHBoxLayout()
            act_l.setContentsMargins(4, 4, 4, 4)
            act_l.setSpacing(8)

            ren_btn = QPushButton("✏  Rename")
            ren_btn.setMinimumHeight(42)
            ren_btn.setMinimumWidth(108)
            ren_btn.setStyleSheet(
                "QPushButton{background:#2563eb;color:white;border-radius:6px;"
                "font-size:12px;font-weight:bold;padding:4px 8px;}"
                "QPushButton:hover{background:#1d4ed8;}"
            )
            ren_btn.clicked.connect(
                lambda _, row=r, old=f['name']: self.rename_feeder(row, old)
            )
            act_l.addWidget(ren_btn)

            is_active = status == "active"
            tog_btn = QPushButton(
                "🔴  Disable" if is_active else "🟢  Enable"
            )
            tog_btn.setMinimumHeight(42)
            tog_btn.setMinimumWidth(108)
            if is_active:
                tog_btn.setStyleSheet(
                    "QPushButton{background:#dc2626;color:white;border-radius:6px;"
                    "font-size:12px;font-weight:bold;padding:4px 8px;}"
                    "QPushButton:hover{background:#b91c1c;}"
                )
            else:
                tog_btn.setStyleSheet(
                    "QPushButton{background:#16a34a;color:white;border-radius:6px;"
                    "font-size:12px;font-weight:bold;padding:4px 8px;}"
                    "QPushButton:hover{background:#15803d;}"
                )
            tog_btn.clicked.connect(
                lambda _, fn=f['name'], cs=status: self.toggle_status(fn, cs)
            )
            act_l.addWidget(tog_btn)
            act_w.setLayout(act_l)
            self.table.setCellWidget(r, 4, act_w)

    # ── actions ───────────────────────────────────────────────────────────────
    def add_feeder(self):
        name = (self.new_name.text() or "").strip()
        if not name:
            QMessageBox.warning(self, "Add Feeder", "Enter a feeder name."); return
        if self.db.feeder_exists(name):
            QMessageBox.warning(self, "Add Feeder", "Feeder already exists."); return
        try:
            self.db.add_feeder(
                name=name, priority=self.new_priority.currentText()
            )
            self.db.log_action("system", "feeder_add", f"Added: {name}")
            self.new_name.setText("")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Add Feeder Failed", str(e))

    def rename_feeder(self, row: int, old_name: str):
        widget   = self.table.cellWidget(row, 3)
        new_name = (widget.text() if widget else "").strip()
        if not new_name:
            QMessageBox.warning(self, "Rename", "Type the new name first."); return
        if new_name == old_name:
            QMessageBox.information(self, "Rename", "Name unchanged."); return
        if self.db.feeder_exists(new_name):
            QMessageBox.warning(self, "Rename", "Name already taken."); return
        if QMessageBox.question(
            self, "Confirm Rename",
            f"Rename:\n  {old_name}\n→  {new_name}\n\n"
            f"This updates all historical data references.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.rename_feeder(old_name, new_name)
            self.db.log_action("system", "feeder_rename", f"{old_name} → {new_name}")
            # FIX: Rename model files and update registry to maintain consistency
            try:
                from core.model_registry import model_registry
                renamed = model_registry.rename_model_files(old_name, new_name)
                if renamed:
                    import logging
                    logging.getLogger(__name__).info(
                        "Renamed %d model file(s) for feeder rename: %s → %s",
                        len(renamed), old_name, new_name
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Could not rename model files: %s", e)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Rename Failed", str(e))

    def toggle_status(self, feeder_name: str, current_status: str):
        new_status = "inactive" if current_status == "active" else "active"
        try:
            self.db.set_feeder_status(feeder_name, new_status)
            self.db.log_action(
                "system", "feeder_status", f"{feeder_name} → {new_status}"
            )
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Status Change Failed", str(e))

    def _change_priority(self, feeder_name: str, priority: str):
        try:
            self.db.update_feeder_priority(feeder_name, priority)
        except Exception:
            pass

        if priority == "critical":
            mb = QMessageBox(self)
            mb.setWindowTitle("⚠  Critical Priority — Safety Notice")
            mb.setIcon(QMessageBox.Icon.Warning)
            mb.setText(f"<b>{feeder_name}</b> → <b>CRITICAL</b> priority")
            mb.setInformativeText(
                "This feeder will receive guaranteed 95% minimum supply "
                "(α = 0.95 per Equation 4.4) at all times.\n\n"
                "Assign CRITICAL only to:\n"
                "  • Hospitals / medical facilities\n"
                "  • Airport / military installations\n"
                "  • Water treatment / emergency services\n\n"
                "The LP optimizer enforces this constraint automatically."
            )
            mb.setStandardButtons(QMessageBox.StandardButton.Ok)
            mb.exec()
