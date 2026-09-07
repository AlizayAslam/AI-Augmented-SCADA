"""
Signup Window - Minimal clean design
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
import bcrypt
from core.db import DatabaseManager


MINIMAL_STYLE = """
    QDialog { background-color: #f8fafc; }
    QWidget { background-color: #f8fafc; color: #1e293b; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }
    QLineEdit { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 12px; color: #1e293b; font-size: 13px; }
    QLineEdit:focus { border: 1.5px solid #3b82f6; }
    QPushButton#primary_btn { background-color: #3b82f6; color: white; border: none; border-radius: 6px; padding: 11px; font-size: 13px; font-weight: bold; }
    QPushButton#primary_btn:hover { background-color: #2563eb; }
    QPushButton#primary_btn:disabled { background-color: #bfdbfe; color: #93c5fd; }
    QPushButton#link_btn { background: none; border: none; color: #3b82f6; font-size: 12px; padding: 4px; }
    QPushButton#link_btn:hover { color: #1d4ed8; }
"""


class SignupWindow(QDialog):
    signup_successful = pyqtSignal()

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self.username_ok = False
        self.email_ok = False
        self.passwords_ok = False
        self._username_timer = QTimer(self)
        self._username_timer.setSingleShot(True)
        self._username_timer.timeout.connect(self._do_check_username)
        self._email_timer = QTimer(self)
        self._email_timer.setSingleShot(True)
        self._email_timer.timeout.connect(self._do_check_email)
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Create Account — Sukkur SCADA")
        self.setFixedSize(420, 590)
        self.setModal(True)
        self.setStyleSheet(MINIMAL_STYLE)

        root = QVBoxLayout()
        root.setContentsMargins(40, 36, 40, 32)
        root.setSpacing(0)

        title = QLabel("Create account")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet("color: #0f172a; background: transparent;")
        root.addWidget(title)

        sub = QLabel("Sukkur IBA — Power Distribution SCADA")
        sub.setStyleSheet("color: #64748b; font-size: 12px; background: transparent; margin-top: 2px;")
        root.addWidget(sub)
        root.addSpacing(26)

        # Username
        root.addWidget(self._lbl("Username"))
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Minimum 3 characters")
        self.username_input.setMinimumHeight(42)
        self.username_input.textChanged.connect(lambda: self._username_timer.start(400))
        root.addWidget(self.username_input)
        self.username_hint = self._hint()
        root.addWidget(self.username_hint)
        root.addSpacing(10)

        # Email
        root.addWidget(self._lbl("Email address"))
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("you@example.com")
        self.email_input.setMinimumHeight(42)
        self.email_input.textChanged.connect(lambda: self._email_timer.start(400))
        root.addWidget(self.email_input)
        self.email_hint = self._hint()
        root.addWidget(self.email_hint)
        root.addSpacing(10)

        # Password
        root.addWidget(self._lbl("Password"))
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("8+ chars, uppercase, number, symbol")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(42)
        self.password_input.textChanged.connect(self._check_passwords)
        root.addWidget(self.password_input)
        root.addSpacing(10)

        # Confirm password
        root.addWidget(self._lbl("Confirm password"))
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Re-enter your password")
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setMinimumHeight(42)
        self.confirm_input.textChanged.connect(self._check_passwords)
        self.confirm_input.returnPressed.connect(self._attempt_signup)
        root.addWidget(self.confirm_input)
        self.password_hint = self._hint()
        root.addWidget(self.password_hint)
        root.addSpacing(22)

        self.signup_btn = QPushButton("Create account")
        self.signup_btn.setObjectName("primary_btn")
        self.signup_btn.setMinimumHeight(44)
        self.signup_btn.setEnabled(False)
        self.signup_btn.clicked.connect(self._attempt_signup)
        root.addWidget(self.signup_btn)
        root.addSpacing(14)

        back_row = QHBoxLayout()
        back_row.addStretch()
        back_btn = QPushButton("← Back to login")
        back_btn.setObjectName("link_btn")
        back_btn.clicked.connect(self.reject)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        root.addLayout(back_row)
        root.addStretch()
        self.setLayout(root)

    def _lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet("color: #374151; font-size: 12px; font-weight: bold; background: transparent; margin-bottom: 4px;")
        return l

    def _hint(self):
        l = QLabel("")
        l.setStyleSheet("font-size: 11px; min-height: 16px; background: transparent; margin-top: 3px; color: #64748b;")
        return l

    def _set_hint(self, lbl, text, state):
        colors = {"ok": "#16a34a", "warn": "#d97706", "err": "#dc2626", "": "#64748b"}
        lbl.setText(text)
        lbl.setStyleSheet(f"font-size: 11px; min-height: 16px; background: transparent; margin-top: 3px; color: {colors.get(state, '#64748b')};")

    def _do_check_username(self):
        val = self.username_input.text().strip()
        if not val:
            self._set_hint(self.username_hint, "", ""); self.username_ok = False
        elif len(val) < 3:
            self._set_hint(self.username_hint, "Must be at least 3 characters", "warn"); self.username_ok = False
        elif self.db.fetch_all("SELECT 1 FROM users WHERE username = ?", (val,)):
            self._set_hint(self.username_hint, "Username already taken", "err"); self.username_ok = False
        else:
            self._set_hint(self.username_hint, "Username available", "ok"); self.username_ok = True
        self._refresh_btn()

    def _do_check_email(self):
        val = self.email_input.text().strip()
        if not val:
            self._set_hint(self.email_hint, "", ""); self.email_ok = False
        elif "@" not in val or "." not in val.split("@")[-1]:
            self._set_hint(self.email_hint, "Enter a valid email address", "warn"); self.email_ok = False
        elif self.db.fetch_all("SELECT 1 FROM users WHERE lower(email) = lower(?)", (val,)):
            self._set_hint(self.email_hint, "Email already registered", "err"); self.email_ok = False
        else:
            self._set_hint(self.email_hint, "Email available", "ok"); self.email_ok = True
        self._refresh_btn()

    def _check_passwords(self):
        pw = self.password_input.text()
        cf = self.confirm_input.text()
        if not pw:
            self._set_hint(self.password_hint, "", ""); self.passwords_ok = False
        elif not self._strong(pw):
            self._set_hint(self.password_hint, "Need uppercase, lowercase, number and symbol (8+ chars)", "warn"); self.passwords_ok = False
        elif cf and pw != cf:
            self._set_hint(self.password_hint, "Passwords do not match", "err"); self.passwords_ok = False
        elif cf and pw == cf:
            self._set_hint(self.password_hint, "Passwords match", "ok"); self.passwords_ok = True
        else:
            self._set_hint(self.password_hint, "Strong password — now confirm it", "ok"); self.passwords_ok = False
        self._refresh_btn()

    def _strong(self, pw):
        return (len(pw) >= 8 and any(c.isupper() for c in pw)
                and any(c.islower() for c in pw) and any(c.isdigit() for c in pw)
                and any(not c.isalnum() for c in pw))

    def _refresh_btn(self):
        self.signup_btn.setEnabled(self.username_ok and self.email_ok and self.passwords_ok)

    def _attempt_signup(self):
        if not self.signup_btn.isEnabled():
            return
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text()
        try:
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
            self.db.execute_query(
                "INSERT INTO users (username, password, email, role) VALUES (?, ?, ?, ?)",
                (username, hashed, email, "operator")
            )
            self.db.log_action(username, "signup", "New account created")
            QMessageBox.information(self, "Account created",
                f"Account for '{username}' created.\n\nYou can now log in.")
            self.signup_successful.emit()
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Signup failed", str(exc))
