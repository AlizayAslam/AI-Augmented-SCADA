"""
Database Manager for SCADA System
FIX Issue 5: True Singleton pattern (__new__ + _instance class variable)
FIX Issue 6: Persistent connection with threading.RLock — no open-per-query
"""

import logging
import sqlite3
import threading
import bcrypt
from datetime import datetime
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Singleton DatabaseManager.
    Only ONE instance is ever created; every caller shares the same
    persistent SQLite connection, protected by a reentrant lock.
    """

    _instance = None
    _class_lock = threading.Lock()   # used only during first-time construction

    # ------------------------------------------------------------------
    # Singleton __new__  (Issue 5 fix)
    # ------------------------------------------------------------------
    def __new__(cls, db_path: str = "database.db"):
        with cls._class_lock:
            if cls._instance is None:
                instance = super().__new__(cls)
                instance._db_path = db_path
                instance._conn = None
                instance._conn_lock = threading.RLock()   # reentrant; same thread can re-acquire
                cls._instance = instance
        return cls._instance

    # __init__ is called every time DatabaseManager() is called,
    # but _instance already exists so we make it a no-op.
    def __init__(self, db_path: str = "database.db"):
        pass   # already set up in __new__

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @property
    def db_path(self):
        return self._db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Return (and lazily open) the persistent connection (Issue 6 fix)."""
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._db_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
            self._conn.execute("PRAGMA journal_mode = WAL")
        return self._conn

    def _prep_params(self, params: tuple) -> tuple:
        """Convert datetime objects to ISO strings for SQLite compatibility."""
        return tuple(p.isoformat() if isinstance(p, datetime) else p for p in params)

    # ------------------------------------------------------------------
    # Public query interface
    # ------------------------------------------------------------------
    def execute_query(self, query: str, params: tuple = ()):
        """Execute a write query (INSERT / UPDATE / DELETE / CREATE)."""
        with self._conn_lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(query, self._prep_params(params))
            conn.commit()
            return cursor

    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows as a list of plain dicts."""
        with self._conn_lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute(query, self._prep_params(params))
            return [dict(row) for row in cursor.fetchall()]

    def connect(self):
        """Legacy helper — returns the persistent connection."""
        return self._get_conn()

    def close(self):
        """Close the connection. Call only at application shutdown."""
        with self._conn_lock:
            if self._conn:
                try:
                    self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                except Exception:
                    pass
                self._conn.close()
                self._conn = None

    def table_exists(self, table_name: str) -> bool:
        result = self.fetch_all(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return len(result) > 0

    # ------------------------------------------------------------------
    # Schema bootstrap
    # ------------------------------------------------------------------
    def ensure_database(self):
        """
        Idempotent schema bootstrap.
        Creates any missing tables; never drops existing data.
        """
        with self._conn_lock:
            conn = self._get_conn()
            cur = conn.cursor()

            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    id      INTEGER PRIMARY KEY CHECK (id = 1),
                    version INTEGER NOT NULL
                )""")
            cur.execute("INSERT OR IGNORE INTO schema_version (id, version) VALUES (1, 1)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    username   TEXT UNIQUE NOT NULL,
                    password   TEXT NOT NULL,
                    email      TEXT UNIQUE,
                    role       TEXT DEFAULT 'operator',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS datasets (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename    TEXT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    row_count   INTEGER,
                    columns     TEXT,
                    status      TEXT DEFAULT 'active'
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS feeders (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    name     TEXT UNIQUE NOT NULL,
                    priority TEXT DEFAULT 'medium',
                    capacity REAL,
                    location TEXT,
                    status   TEXT DEFAULT 'active'
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS feeder_data (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp    TEXT,
                    feeder       TEXT,
                    load         REAL,
                    loss         REAL,
                    voltage      REAL,
                    current      REAL,
                    power_factor REAL,
                    temperature  REAL,
                    humidity     REAL,
                    dataset_id   INTEGER,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS forecasts (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp      TEXT,
                    feeder         TEXT,
                    predicted_load REAL,
                    predicted_loss REAL,
                    model_used     TEXT,
                    horizon        INTEGER,
                    run_at         TEXT,
                    model_params   TEXT,
                    train_start    TEXT,
                    train_end      TEXT,
                    mape           REAL,
                    rmse           REAL,
                    r2             REAL,
                    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS schedules (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    schedule_date   TEXT,
                    feeder          TEXT,
                    hour            INTEGER,
                    allocated_power REAL,
                    priority        TEXT,
                    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    type            TEXT,
                    severity        TEXT,
                    title           TEXT,
                    message         TEXT,
                    feeder          TEXT,
                    acknowledged    BOOLEAN DEFAULT 0,
                    resolved        BOOLEAN DEFAULT 0,
                    acknowledged_by TEXT
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user       TEXT,
                    action     TEXT,
                    details    TEXT,
                    ip_address TEXT
                )""")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id            INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key   TEXT UNIQUE,
                    setting_value TEXT,
                    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )""")

            conn.commit()

        # Seed data (all idempotent)
        self.create_default_admin()
        self.create_sukkur_feeders()
        self.init_default_settings()
        self._auto_import_nepra_csv()

    def initialize_database(self):
        """Drop-and-recreate all tables (development / reset only)."""
        with self._conn_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            for tbl in ['feeder_data', 'forecasts', 'schedules', 'alerts',
                        'logs', 'datasets', 'feeders', 'users', 'settings', 'schema_version']:
                cur.execute(f"DROP TABLE IF EXISTS {tbl}")
            conn.commit()
        self.ensure_database()

    # ------------------------------------------------------------------
    # Seed helpers
    # ------------------------------------------------------------------
    def _auto_import_nepra_csv(self):
        """Auto-import NEPRA 2024 CSV on first run if feeder_data is empty."""
        try:
            count = self.fetch_all("SELECT COUNT(*) as c FROM feeder_data")[0]['c']
            if count > 0:
                return
            import os
            csv_path = os.path.join(
                os.path.dirname(__file__), '..', 'data', 'sukkur_nepra_2024.csv'
            )
            if not os.path.exists(csv_path):
                return
            print("Auto-importing NEPRA 2024 data (first run)...")
            df = pd.read_csv(csv_path, parse_dates=['timestamp'])
            with self._conn_lock:
                conn = self._get_conn()
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO datasets (filename, row_count, columns, status) VALUES (?,?,?,?)",
                    ('sukkur_nepra_2024.csv', len(df), ','.join(df.columns), 'active'),
                )
                conn.commit()
                dataset_id = cur.lastrowid
                rows = [
                    (
                        str(r['timestamp']), r['feeder'],
                        float(r['load']), float(r['loss']),
                        float(r.get('voltage', 11.0)), float(r.get('current', 0.0)),
                        float(r.get('power_factor', 0.9)),
                        float(r.get('temperature', 25.0)), float(r.get('humidity', 60.0)),
                        dataset_id,
                    )
                    for _, r in df.iterrows()
                ]
                cur.executemany(
                    """INSERT INTO feeder_data
                       (timestamp,feeder,load,loss,voltage,current,power_factor,
                        temperature,humidity,dataset_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    rows,
                )
                conn.commit()
            print(f"Auto-import complete: {len(rows):,} rows loaded.")
        except Exception as e:
            print(f"Auto-import skipped: {e}")

    def create_default_admin(self):
        if not self.fetch_all("SELECT id FROM users WHERE username = 'admin'"):
            hashed_pw = bcrypt.hashpw(b'admin123', bcrypt.gensalt())
            self.execute_query(
                "INSERT INTO users (username, password, email, role) VALUES (?,?,?,?)",
                ('admin', hashed_pw, 'admin@local', 'admin'),
            )
            print("✅ Admin user created (admin / admin123)")

    def create_sukkur_feeders(self):
        feeders = [
            ('Civil Hospital Feeder',         'critical', 12.0,  'Civil Hospital Sukkur'),
            ('Airport Road Feeder',           'high',     16.0,  'Airport Road Sukkur'),
            ('Rohri Industrial Feeder',       'high',     24.0,  'Rohri'),
            ('SITE Area Feeder',              'medium',   20.0,  'Sukkur Industrial Area'),
            ('Military Road Feeder',          'high',     15.0,  'Military Road Sukkur'),
            ('Barrage Colony Feeder',         'medium',   14.0,  'Barrage Road Sukkur'),
            ('Shikarpur Road Feeder',         'low',      10.0,  'Shikarpur Road Sukkur'),
            ('Old Sukkur Residential Feeder', 'low',       9.0,  'Old Sukkur'),
        ]
        for f in feeders:
            if not self.fetch_all("SELECT id FROM feeders WHERE name=?", (f[0],)):
                self.execute_query(
                    "INSERT INTO feeders (name,priority,capacity,location) VALUES (?,?,?,?)", f
                )
        print(f"✅ {len(feeders)} Sukkur feeders ready")

    def init_default_settings(self):
        defaults = {
            'theme': 'dark', 'auto_refresh': 'true',
            'real_time_monitoring': 'true', 'auto_optimize': 'false',
            'loss_threshold': '5.0', 'overload_threshold': '80.0',
            'spike_threshold': '20.0', 'mape_threshold': '10.0',
            'retention_days': '30',
        }
        for k, v in defaults.items():
            if not self.fetch_all("SELECT id FROM settings WHERE setting_key=?", (k,)):
                self.execute_query(
                    "INSERT INTO settings (setting_key, setting_value) VALUES (?,?)", (k, v)
                )
        print("✅ Default settings ready")

    def create_sample_data(self, dataset_id: int):
        """Fallback: generate 30-day synthetic hourly data when no CSV is present."""
        print("Creating sample load data...")
        dates = pd.date_range(
            start=datetime.now() - pd.Timedelta(days=30),
            end=datetime.now(), freq='h',
        )
        feeders = self.fetch_all("SELECT name, priority FROM feeders")
        base_map = {
            'critical': (8.5, 1.5), 'high': (12.0, 2.5),
            'medium': (10.0, 2.0),  'low':  (6.5,  1.5),
        }
        total = 0
        with self._conn_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            for feeder in feeders:
                base, amp = base_map.get(feeder['priority'], (8.0, 2.0))
                rows = []
                for dt in dates:
                    h = dt.hour
                    peak = max(0.0, np.sin(np.pi * (h - 18) / 6)) if 15 <= h <= 21 else 0.0
                    wf = 1.15 if dt.weekday() < 5 else 0.85
                    load = max(base * 0.3, base + amp * peak * wf + np.random.normal(0, base * 0.05))
                    loss = load * np.random.uniform(0.08, 0.17)
                    temp = 25 + 10 * np.sin(np.pi * (h - 14) / 12) + np.random.normal(0, 2)
                    hum  = max(30.0, min(95.0, 60 + np.random.normal(0, 5)))
                    rows.append((
                        str(dt), feeder['name'], round(load, 3), round(loss, 3),
                        11.0, 0.0, 0.9, round(temp, 1), round(hum, 1), dataset_id,
                    ))
                cur.executemany(
                    """INSERT INTO feeder_data
                       (timestamp,feeder,load,loss,voltage,current,power_factor,
                        temperature,humidity,dataset_id)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""",
                    rows,
                )
                total += len(rows)
            conn.commit()
        self.execute_query("UPDATE datasets SET row_count=? WHERE id=?", (total, dataset_id))
        print(f"✅ Sample data: {total:,} rows")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def get_user_by_login(self, login: str) -> Optional[Dict[str, Any]]:
        login = (login or "").strip()
        if not login:
            return None
        rows = self.fetch_all("SELECT * FROM users WHERE username=?", (login,))
        if rows:
            return rows[0]
        rows = self.fetch_all("SELECT * FROM users WHERE lower(email)=lower(?)", (login,))
        return rows[0] if rows else None

    def authenticate_user(self, login: str, password: str) -> bool:
        user = self.get_user_by_login(login)
        if not user:
            return False
        return bcrypt.checkpw(password.encode('utf-8'), user['password'])

    def authenticate_user_with_info(self, login: str, password: str) -> Optional[Dict[str, Any]]:
        user = self.get_user_by_login(login)
        if not user:
            return None
        if bcrypt.checkpw(password.encode('utf-8'), user['password']):
            return user
        return None

    # ------------------------------------------------------------------
    # Data I/O
    # ------------------------------------------------------------------
    def save_dataset(self, filename: str, df: pd.DataFrame) -> int:
        cur = self.execute_query(
            "INSERT INTO datasets (filename, row_count, columns) VALUES (?,?,?)",
            (filename, len(df), ','.join(df.columns)),
        )
        dataset_id = cur.lastrowid
        with self._conn_lock:
            conn = self._get_conn()
            c = conn.cursor()
            rows = []
            for _, row in df.iterrows():
                ts = row['timestamp'].isoformat() if isinstance(row['timestamp'], datetime) else str(row['timestamp'])
                rows.append((
                    ts, row['feeder'], row['load'], row['loss'],
                    row.get('temperature', 25), row.get('humidity', 50), dataset_id,
                ))
            c.executemany(
                "INSERT INTO feeder_data (timestamp,feeder,load,loss,temperature,humidity,dataset_id) VALUES (?,?,?,?,?,?,?)",
                rows,
            )
            conn.commit()
        return dataset_id

    def save_forecast(self, forecasts: List[Dict], model: str, metrics: Dict,
                      meta: Optional[Dict[str, Any]] = None):
        meta = meta or {}
        with self._conn_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            rows = [
                (
                    f['timestamp'].isoformat() if isinstance(f['timestamp'], datetime) else str(f['timestamp']),
                    f['feeder'], f['predicted_load'], f['predicted_loss'], model,
                    meta.get('horizon'), meta.get('run_at'), meta.get('model_params'),
                    meta.get('train_start'), meta.get('train_end'),
                    metrics['mape'], metrics['rmse'], metrics['r2'],
                )
                for f in forecasts
            ]
            cur.executemany(
                """INSERT INTO forecasts
                   (timestamp,feeder,predicted_load,predicted_loss,model_used,horizon,
                    run_at,model_params,train_start,train_end,mape,rmse,r2)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            conn.commit()

    def save_schedule(self, schedule: List[Dict], date: str):
        self.execute_query("DELETE FROM schedules WHERE schedule_date=?", (date,))
        with self._conn_lock:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.executemany(
                "INSERT INTO schedules (schedule_date,feeder,hour,allocated_power,priority) VALUES (?,?,?,?,?)",
                [(date, i['feeder'], i['hour'], i['allocated_power'], i['priority']) for i in schedule],
            )
            conn.commit()

    def add_alert(self, alert_type: str, severity: str, title: str,
                  message: str, feeder: str = None):
        self.execute_query(
            "INSERT INTO alerts (type,severity,title,message,feeder) VALUES (?,?,?,?,?)",
            (alert_type, severity, title, message, feeder),
        )

    def get_active_alerts(self) -> List[Dict]:
        return self.fetch_all("SELECT * FROM alerts WHERE resolved=0 ORDER BY timestamp DESC")

    def acknowledge_alert(self, alert_id: int, user: str):
        self.execute_query(
            "UPDATE alerts SET acknowledged=1, acknowledged_by=? WHERE id=?", (user, alert_id)
        )

    def resolve_alert(self, alert_id: int):
        self.execute_query("UPDATE alerts SET resolved=1 WHERE id=?", (alert_id,))

    def log_forecast_run(self, username: str, feeder: str, model: str,
                         horizon: int, mape: float = None):
        """SEC FIX: Log every forecast run for SCADA audit trail."""
        detail = (
            f"model={model} feeder='{feeder}' horizon={horizon}h"
            + (f" mape={mape:.2f}%" if mape is not None else "")
        )
        self.log_action(username or "system", "forecast_run", detail)

    def log_action(self, user: str, action: str, details: str):
        self.execute_query(
            "INSERT INTO logs (user,action,details) VALUES (?,?,?)", (user, action, details)
        )

    def get_setting(self, key: str) -> Optional[str]:
        r = self.fetch_all("SELECT setting_value FROM settings WHERE setting_key=?", (key,))
        return r[0]['setting_value'] if r else None

    def update_setting(self, key: str, value: str):
        self.execute_query(
            """INSERT INTO settings (setting_key, setting_value)
               VALUES (?,?)
               ON CONFLICT(setting_key)
               DO UPDATE SET setting_value=?, updated_at=CURRENT_TIMESTAMP""",
            (key, value, value),
        )

    def get_feeder_data(self, start_date=None, end_date=None, feeder=None) -> pd.DataFrame:
        query, params, conds = "SELECT * FROM feeder_data", [], []
        if feeder:
            conds.append("feeder=?"); params.append(feeder)
        if start_date:
            conds.append("timestamp>=?"); params.append(start_date)
        if end_date:
            conds.append("timestamp<=?"); params.append(end_date)
        if conds:
            query += " WHERE " + " AND ".join(conds)
        query += " ORDER BY timestamp"
        with self._conn_lock:
            return pd.read_sql_query(query, self._get_conn(),
                                     params=params, parse_dates=['timestamp'])

    def get_forecast_data(self, feeder=None) -> pd.DataFrame:
        query, params = "SELECT * FROM forecasts", []
        if feeder:
            query += " WHERE feeder=?"; params = [feeder]
        query += " ORDER BY timestamp DESC"
        with self._conn_lock:
            return pd.read_sql_query(query, self._get_conn(),
                                     params=params, parse_dates=['timestamp'])

    # ------------------------------------------------------------------
    # Feeder management
    # ------------------------------------------------------------------
    def list_feeders(self, include_inactive: bool = True) -> List[Dict[str, Any]]:
        q, p = "SELECT id,name,priority,capacity,location,status FROM feeders", ()
        if not include_inactive:
            q += " WHERE status=?"; p = ("active",)
        return self.fetch_all(q + " ORDER BY name", p)

    def feeder_exists(self, name: str) -> bool:
        return bool(self.fetch_all(
            "SELECT 1 FROM feeders WHERE name=? LIMIT 1", ((name or "").strip(),)
        ))

    def add_feeder(self, name: str, priority: str = "medium",
                   capacity: Optional[float] = None, location: Optional[str] = None,
                   status: str = "active"):
        self.execute_query(
            "INSERT INTO feeders (name,priority,capacity,location,status) VALUES (?,?,?,?,?)",
            ((name or "").strip(), priority, capacity, location, status),
        )

    def rename_feeder(self, old_name: str, new_name: str):
        old_name, new_name = (old_name or "").strip(), (new_name or "").strip()
        if not old_name or not new_name:
            raise ValueError("Feeder names cannot be empty")
        for tbl, col in [('feeders', 'name'), ('feeder_data', 'feeder'),
                         ('forecasts', 'feeder'), ('schedules', 'feeder'), ('alerts', 'feeder')]:
            self.execute_query(f"UPDATE {tbl} SET {col}=? WHERE {col}=?", (new_name, old_name))

    def set_feeder_status(self, name: str, status: str):
        if status not in ("active", "inactive"):
            raise ValueError("Invalid status")
        self.execute_query(
            "UPDATE feeders SET status=? WHERE name=?", (status, (name or "").strip())
        )

    def update_feeder_priority(self, name: str, priority: str):
        if priority not in ("critical", "high", "medium", "low"):
            raise ValueError("Invalid priority")
        self.execute_query(
            "UPDATE feeders SET priority=? WHERE name=?", (priority, (name or "").strip())
        )
