"""
Login Window - Minimal clean design with signup link
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from core.db import DatabaseManager

MINIMAL_STYLE = """
    QDialog { background-color: #f8fafc; }
    QWidget { background-color: #f8fafc; color: #1e293b; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }
    QLineEdit { background-color: #ffffff; border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px 12px; color: #1e293b; font-size: 13px; }
    QLineEdit:focus { border: 1.5px solid #3b82f6; }
    QPushButton#primary_btn { background-color: #3b82f6; color: white; border: none; border-radius: 6px; padding: 11px; font-size: 13px; font-weight: bold; }
    QPushButton#primary_btn:hover { background-color: #2563eb; }
    QPushButton#link_btn { background: none; border: none; color: #3b82f6; font-size: 12px; padding: 4px; }
    QPushButton#link_btn:hover { color: #1d4ed8; }
"""


class LoginWindow(QDialog):
    login_successful = pyqtSignal()

    def __init__(self, db: DatabaseManager):
        super().__init__()
        self.db = db
        self._failed_attempts = 0
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Sign in — Sukkur SCADA")
        self.setFixedSize(400, 420)
        self.setModal(True)
        self.setStyleSheet(MINIMAL_STYLE)

        root = QVBoxLayout()
        root.setContentsMargins(40, 44, 40, 36)
        root.setSpacing(0)

        title = QLabel("Sign in")
        title.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        title.setStyleSheet("color: #0f172a; background: transparent;")
        root.addWidget(title)

        sub = QLabel("Sukkur IBA — Power Distribution SCADA")
        sub.setStyleSheet("color: #64748b; font-size: 12px; background: transparent; margin-top: 3px;")
        root.addWidget(sub)

        root.addSpacing(30)

        # Username / email
        lbl1 = QLabel("Username or email")
        lbl1.setStyleSheet("color: #374151; font-size: 12px; font-weight: bold; background: transparent; margin-bottom: 4px;")
        root.addWidget(lbl1)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter username or email")
        self.username_input.setMinimumHeight(42)
        self.username_input.returnPressed.connect(self.attempt_login)
        root.addWidget(self.username_input)
        root.addSpacing(14)

        # Password
        lbl2 = QLabel("Password")
        lbl2.setStyleSheet("color: #374151; font-size: 12px; font-weight: bold; background: transparent; margin-bottom: 4px;")
        root.addWidget(lbl2)
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Enter password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setMinimumHeight(42)
        self.password_input.returnPressed.connect(self.attempt_login)
        root.addWidget(self.password_input)

        # Error label (hidden until needed)
        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #dc2626; font-size: 12px; background: transparent; margin-top: 6px;")
        root.addWidget(self.error_label)
        root.addSpacing(22)

        self.login_btn = QPushButton("Sign in")
        self.login_btn.setObjectName("primary_btn")
        self.login_btn.setMinimumHeight(44)
        self.login_btn.clicked.connect(self.attempt_login)
        root.addWidget(self.login_btn)

        root.addSpacing(16)

        signup_row = QHBoxLayout()
        signup_row.addStretch()
        no_acc = QLabel("Don't have an account?")
        no_acc.setStyleSheet("color: #64748b; font-size: 12px; background: transparent;")
        signup_row.addWidget(no_acc)
        signup_btn = QPushButton("Sign up")
        signup_btn.setObjectName("link_btn")
        signup_btn.clicked.connect(self.open_signup)
        signup_row.addWidget(signup_btn)
        signup_row.addStretch()
        root.addLayout(signup_row)

        root.addStretch()
        self.setLayout(root)

    def attempt_login(self):
        # Lockout check
        if not self.login_btn.isEnabled():
            return

        login = self.username_input.text().strip()
        password = self.password_input.text()
        if not login or not password:
            self.error_label.setText("Please enter your username and password.")
            return
        user = self.db.authenticate_user_with_info(login, password)
        if user:
            self.error_label.setText("")
            self._failed_attempts = 0
            self.db.log_action(user['username'], "login", "User logged in")
            self.login_successful.emit()
            self.accept()
            from ui.dashboard import DashboardWindow
            self.dashboard = DashboardWindow(self.db, user['username'], user.get('role', 'operator'))
            self.dashboard.show()
        else:
            self._failed_attempts += 1
            remaining = 5 - self._failed_attempts
            if self._failed_attempts >= 5:
                self.login_btn.setEnabled(False)
                self.username_input.setEnabled(False)
                self.password_input.setEnabled(False)
                self.error_label.setText(
                    "Too many failed attempts. Login disabled for 30 seconds."
                )
                self.error_label.setStyleSheet(
                    "color:#b91c1c;font-size:12px;background:#fee2e2;"
                    "padding:6px 10px;border-radius:5px;margin-top:6px;"
                )
                self._failed_attempts = 0
                QTimer.singleShot(30_000, self._unlock_login)
            elif remaining <= 2:
                self.error_label.setText(
                    f"Incorrect username or password. {remaining} attempt(s) remaining."
                )
                self.password_input.clear()
            else:
                self.error_label.setText("Incorrect username or password.")
                self.password_input.clear()

    def _unlock_login(self):
        self.login_btn.setEnabled(True)
        self.username_input.setEnabled(True)
        self.password_input.setEnabled(True)
        self.error_label.setText("You may try again.")
        self.error_label.setStyleSheet(
            "color:#15803d;font-size:12px;background:transparent;margin-top:6px;"
        )

    def open_signup(self):
        from ui.signup import SignupWindow
        dlg = SignupWindow(self.db)
        dlg.exec()
