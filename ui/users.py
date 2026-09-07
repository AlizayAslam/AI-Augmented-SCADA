"""
User Management Page (Admin only)
FIX: Table rows taller (50px) so action buttons are never clipped.
FIX: Actions column fixed-width (310px) — enough room for Reset / Change Role / Delete.
FIX: Delete button added with confirmation dialog.
FIX: Count badge refreshes on every refresh() call.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGroupBox,
    QTableWidget, QTableWidgetItem, QMessageBox, QLineEdit,
    QHeaderView, QAbstractItemView, QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import bcrypt


class UserManagementPage(QWidget):
    """Admin-only user management page"""

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.init_ui()
        self.refresh()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        header = QLabel("User Management")
        header.setStyleSheet("font-size:24px;font-weight:bold;")
        layout.addWidget(header)

        # Count badge — updated on every refresh()
        self.count_lbl = QLabel("")
        self.count_lbl.setStyleSheet(
            "font-size:13px;color:#16a34a;font-weight:bold;"
            "background:#dcfce7;padding:8px 14px;border-radius:6px;"
            "border:1px solid #bbf7d0;"
        )
        layout.addWidget(self.count_lbl)

        # ── Create account form ───────────────────────────────────────────────
        add_group = QGroupBox("Create Operator Account")
        add_layout = QHBoxLayout()
        add_layout.setSpacing(10)

        self.new_username = QLineEdit()
        self.new_username.setPlaceholderText("Username")
        self.new_username.setMinimumHeight(38)
        add_layout.addWidget(self.new_username, 2)

        self.new_email = QLineEdit()
        self.new_email.setPlaceholderText("Email (optional)")
        self.new_email.setMinimumHeight(38)
        add_layout.addWidget(self.new_email, 2)

        self.new_password = QLineEdit()
        self.new_password.setPlaceholderText("Password (8+ chars, upper/lower/digit/symbol)")
        self.new_password.setMinimumHeight(38)
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        add_layout.addWidget(self.new_password, 3)

        self.create_btn = QPushButton("+ Create User")
        self.create_btn.setMinimumHeight(38)
        self.create_btn.setMinimumWidth(130)
        self.create_btn.setStyleSheet(
            "QPushButton{background:#3b82f6;color:white;border-radius:6px;"
            "font-weight:bold;font-size:13px;}"
            "QPushButton:hover{background:#2563eb;}"
        )
        self.create_btn.clicked.connect(self.create_user)
        add_layout.addWidget(self.create_btn)

        add_group.setLayout(add_layout)
        layout.addWidget(add_group)

        # ── Users table ───────────────────────────────────────────────────────
        table_group = QGroupBox("Existing Users")
        table_layout = QVBoxLayout()
        table_layout.setSpacing(8)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Username", "Email", "Role", "Actions"])

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 160)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(2, 100)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 310)   # wide enough for 3 buttons

        # Taller rows so buttons are never clipped
        self.table.verticalHeader().setDefaultSectionSize(50)
        self.table.verticalHeader().setVisible(False)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.setStyleSheet(
            "QTableWidget{font-size:13px;}"
            "QHeaderView::section{font-size:13px;font-weight:bold;padding:6px;}"
        )
        table_layout.addWidget(self.table, 1)

        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setMinimumHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()
        table_layout.addLayout(btn_row)

        table_group.setLayout(table_layout)
        layout.addWidget(table_group, 1)   # stretch so table fills space

        self.setLayout(layout)

    # ── Data ─────────────────────────────────────────────────────────────────
    def refresh(self):
        try:
            user_count  = self.db.fetch_all("SELECT COUNT(*) as c FROM users")[0]['c']
            admin_count = self.db.fetch_all("SELECT COUNT(*) as c FROM users WHERE role='admin'")[0]['c']
            op_count    = user_count - admin_count
            self.count_lbl.setText(
                f"Total: {user_count}   |   Admins: {admin_count}   |   Operators: {op_count}"
            )
        except Exception:
            pass

        users = self.db.fetch_all("SELECT username, email, role FROM users ORDER BY username")
        self.table.setRowCount(len(users))

        for r, u in enumerate(users):
            uname = u["username"]
            role  = u.get("role") or "operator"
            is_root = (uname == "admin")

            un_item = QTableWidgetItem(uname)
            un_item.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
            self.table.setItem(r, 0, un_item)

            self.table.setItem(r, 1, QTableWidgetItem(u.get("email") or "—"))

            role_item = QTableWidgetItem(role.capitalize())
            role_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            role_item.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
            if role == "admin":
                role_item.setForeground(Qt.GlobalColor.white)
                role_item.setBackground(Qt.GlobalColor.darkBlue)
            else:
                role_item.setForeground(Qt.GlobalColor.darkGreen)
            self.table.setItem(r, 2, role_item)

            # Actions
            act_w = QWidget()
            act_l = QHBoxLayout()
            act_l.setContentsMargins(4, 4, 4, 4)
            act_l.setSpacing(6)

            if not is_root:
                reset_btn = QPushButton("Reset")
                reset_btn.setFixedHeight(36)
                reset_btn.setMinimumWidth(66)
                reset_btn.setStyleSheet(
                    "QPushButton{background:#0ea5e9;color:white;border-radius:5px;"
                    "font-size:12px;font-weight:bold;}"
                    "QPushButton:hover{background:#0284c7;}"
                )
                reset_btn.setToolTip("Reset password to Temp@1234")
                reset_btn.clicked.connect(lambda _, user=uname: self.reset_password(user))
                act_l.addWidget(reset_btn)

                role_label = "Make Admin" if role != "admin" else "Make Operator"
                role_btn = QPushButton(role_label)
                role_btn.setFixedHeight(36)
                role_btn.setMinimumWidth(106)
                role_btn.setStyleSheet(
                    "QPushButton{background:#8b5cf6;color:white;border-radius:5px;"
                    "font-size:12px;font-weight:bold;}"
                    "QPushButton:hover{background:#7c3aed;}"
                )
                role_btn.setToolTip("Change this user's role")
                role_btn.clicked.connect(lambda _, user=uname, ro=role: self.toggle_role(user, ro))
                act_l.addWidget(role_btn)

                del_btn = QPushButton("Delete")
                del_btn.setFixedHeight(36)
                del_btn.setMinimumWidth(70)
                del_btn.setStyleSheet(
                    "QPushButton{background:#ef4444;color:white;border-radius:5px;"
                    "font-size:12px;font-weight:bold;}"
                    "QPushButton:hover{background:#dc2626;}"
                )
                del_btn.setToolTip("Permanently delete this user")
                del_btn.clicked.connect(lambda _, user=uname: self.delete_user(user))
                act_l.addWidget(del_btn)
            else:
                lbl = QLabel("Protected account")
                lbl.setStyleSheet("color:#94a3b8;font-size:11px;padding-left:6px;")
                act_l.addWidget(lbl)

            act_l.addStretch()
            act_w.setLayout(act_l)
            self.table.setCellWidget(r, 3, act_w)

    # ── Helpers ──────────────────────────────────────────────────────────────
    @staticmethod
    def is_strong_password(password: str) -> bool:
        p = password or ""
        return (
            len(p) >= 8 and
            any(c.isupper()     for c in p) and
            any(c.islower()     for c in p) and
            any(c.isdigit()     for c in p) and
            any(not c.isalnum() for c in p)
        )

    # ── Actions ──────────────────────────────────────────────────────────────
    def create_user(self):
        username = (self.new_username.text() or "").strip()
        email    = (self.new_email.text()    or "").strip() or None
        password = self.new_password.text() or ""

        if len(username) < 3:
            QMessageBox.warning(self, "Create User", "Username must be at least 3 characters.")
            return
        if not self.is_strong_password(password):
            QMessageBox.warning(
                self, "Create User",
                "Password must be strong:\n"
                "  - At least 8 characters\n"
                "  - Uppercase + lowercase letters\n"
                "  - At least one digit\n"
                "  - At least one symbol (e.g. @!#$)"
            )
            return
        if self.db.fetch_all("SELECT 1 FROM users WHERE username=? LIMIT 1", (username,)):
            QMessageBox.warning(self, "Create User", f"Username '{username}' already exists.")
            return
        if email and self.db.fetch_all(
            "SELECT 1 FROM users WHERE lower(email)=lower(?) LIMIT 1", (email,)
        ):
            QMessageBox.warning(self, "Create User", "That email is already registered.")
            return

        try:
            hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
            self.db.execute_query(
                "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                (username, hashed_pw, email, "operator"),
            )
            self.db.log_action("admin", "user_create", f"Created operator: {username}")
            self.new_username.clear()
            self.new_email.clear()
            self.new_password.clear()
            self.refresh()
            QMessageBox.information(self, "User Created", f"Operator '{username}' created successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Create User Failed", str(e))

    def reset_password(self, username: str):
        temp = "Temp@1234"
        reply = QMessageBox.question(
            self, "Reset Password",
            f"Reset password for '{username}'?\n\n"
            f"Temporary password will be set to:  {temp}\n\n"
            f"The user should change it after logging in.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            hashed_pw = bcrypt.hashpw(temp.encode("utf-8"), bcrypt.gensalt())
            self.db.execute_query("UPDATE users SET password=? WHERE username=?", (hashed_pw, username))
            self.db.log_action("admin", "password_reset", f"Reset password for {username}")
            QMessageBox.information(
                self, "Password Reset",
                f"Password for '{username}' reset to: {temp}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Reset Failed", str(e))

    def toggle_role(self, username: str, current_role: str):
        new_role = "admin" if current_role != "admin" else "operator"
        reply = QMessageBox.question(
            self, "Change Role",
            f"Change role for '{username}'?\n\n"
            f"  Current role: {current_role}\n"
            f"  New role:     {new_role}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.execute_query("UPDATE users SET role=? WHERE username=?", (new_role, username))
            self.db.log_action("admin", "role_change", f"{username}: {current_role} -> {new_role}")
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Role Change Failed", str(e))

    def delete_user(self, username: str):
        reply = QMessageBox.warning(
            self, "Delete User",
            f"Permanently delete user '{username}'?\n\n"
            f"This cannot be undone. Their activity log entries will be kept,\n"
            f"but the account will be removed and they cannot log in again.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.db.execute_query("DELETE FROM users WHERE username=?", (username,))
            self.db.log_action("admin", "user_delete", f"Deleted user: {username}")
            self.refresh()
            QMessageBox.information(self, "Deleted", f"User '{username}' has been deleted.")
        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", str(e))
