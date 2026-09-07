"""
backup_db.py — Database Backup Utility
=======================================
Run on a schedule (e.g., daily via cron/Task Scheduler) to create
timestamped SQLite backups.

Usage:
    python backup_db.py [--keep 7]

Options:
    --keep N    Number of backups to retain (default: 7)

Cron example (daily at 2 AM):
    0 2 * * * cd /path/to/scada && python backup_db.py --keep 14
"""

import argparse
import logging
import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
logger = logging.getLogger("db_backup")

from config import DB_PATH, BASE_DIR

BACKUP_DIR = os.path.join(BASE_DIR, "backups")


def backup(keep: int = 7):
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"database_{timestamp}.db")

    # Use SQLite online backup API (safe even with active WAL)
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
        dst.close()
        src.close()
        size_kb = os.path.getsize(backup_path) / 1024
        logger.info("Backup created: %s  (%.1f KB)", backup_path, size_kb)
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return

    # Verify backup integrity
    try:
        conn = sqlite3.connect(backup_path)
        conn.execute("PRAGMA integrity_check")
        conn.close()
        logger.info("Integrity check passed")
    except Exception as e:
        logger.warning("Integrity check failed: %s", e)

    # Prune old backups
    backups = sorted(Path(BACKUP_DIR).glob("database_*.db"))
    if len(backups) > keep:
        for old in backups[:-keep]:
            old.unlink()
            logger.info("Removed old backup: %s", old.name)

    logger.info("Backup complete. %d backup(s) retained.", min(len(backups), keep))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SCADA Database Backup")
    parser.add_argument("--keep", type=int, default=7, help="Backups to retain")
    args = parser.parse_args()
    backup(args.keep)
