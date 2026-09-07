"""
AI-Augmented Intelligent SCADA System
Main Application Entry Point
"""

import sys
import os
import warnings
import logging
import logging.handlers

# Suppress TensorFlow / Plotly noise before any other import
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore')

from config import LOG_FILE, LOG_LEVEL, DB_PATH


# ── Logging setup ─────────────────────────────────────────────────────────────
def configure_logging():
    """Configure root logger: rotating file + console (WARNING only)."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Rotating file handler (10 MB × 5 backups)
    fh = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Console handler — only WARNING+ so terminal stays clean
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)

    root.addHandler(fh)
    root.addHandler(ch)

    # Silence third-party chatter
    for noisy in ("plotly", "matplotlib", "tensorflow", "PIL", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.ERROR)


configure_logging()
logger = logging.getLogger(__name__)

import logging as _log
_log.getLogger('plotly').setLevel(_log.ERROR)

from PyQt6.QtWidgets import QApplication, QSplashScreen, QLabel
from PyQt6.QtGui import QPixmap, QFont, QIcon, QColor
from PyQt6.QtCore import Qt, QTimer


def _load_stylesheet(app: QApplication):
    """Load global QSS stylesheet if present."""
    qss_path = os.path.join(os.path.dirname(__file__), "assets", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def _make_splash(app: QApplication) -> QSplashScreen:
    """Build a styled splash screen that shows immediately."""
    # Create a 480×260 dark-navy canvas
    pix = QPixmap(480, 260)
    pix.fill(QColor("#0f172a"))

    splash = QSplashScreen(pix, Qt.WindowType.WindowStaysOnTopHint)
    splash.showMessage(
        "  ⚡  AI-Augmented SCADA System\n\n"
        "  Sukkur IBA University\n"
        "  Power Distribution Management\n\n"
        "  Starting up…",
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        QColor("#94a3b8"),
    )
    splash.show()
    app.processEvents()   # paint immediately
    return splash


class SCADASystem:
    """Main SCADA System Application"""

    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("AI SCADA System - Sukkur IBA")
        self.app.setOrganizationName("Sukkur IBA University")
        self.app.setFont(QFont("Segoe UI", 9))

        # Load global stylesheet
        _load_stylesheet(self.app)

        # Show splash FIRST, before any heavy imports
        self.splash = _make_splash(self.app)
        self._splash_update("Loading database…")

        from core.db import DatabaseManager
        self.db = DatabaseManager(DB_PATH)

        try:
            self.db.ensure_database()
            logger.info("Database ready")
        except Exception as e:
            logger.critical("Database initialisation failed: %s", e, exc_info=True)
            sys.exit(1)

        self._splash_update("Loading AI model registry…")
        try:
            from core.model_registry import model_registry
            model_registry.load_registry_meta()
            logger.info("Model registry loaded")
        except Exception as e:
            logger.warning("Model registry load failed (run train_models_offline.py): %s", e)

        self._splash_update("Opening login screen…")
        from ui.login import LoginWindow
        self.login_window = LoginWindow(self.db)
        self.login_window.show()

        # Close splash after login window is visible
        QTimer.singleShot(800, self.splash.close)
        logger.info("SCADA application started")

        sys.exit(self.app.exec())

    def _splash_update(self, message: str):
        self.splash.showMessage(
            f"  ⚡  AI-Augmented SCADA System\n\n"
            f"  Sukkur IBA University\n"
            f"  Power Distribution Management\n\n"
            f"  {message}",
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            QColor("#94a3b8"),
        )
        self.app.processEvents()


if __name__ == "__main__":
    system = SCADASystem()
