"""
config.py — Central configuration for AI SCADA System
All tuneable constants live here; import them wherever needed.
"""

import os

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, "database.db")
MODELS_DIR  = os.path.join(BASE_DIR, "models")
DATA_DIR    = os.path.join(BASE_DIR, "data")
LOGS_DIR    = os.path.join(BASE_DIR, "logs")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR,   exist_ok=True)

# ── Authentication ─────────────────────────────────────────────────────────
DEFAULT_ADMIN_USER     = "admin"
DEFAULT_ADMIN_PASSWORD = "admin123"   # hashed with bcrypt on first run

# ── Monitoring thresholds ──────────────────────────────────────────────────
OVERLOAD_THRESHOLD_PCT   = 80.0   # % of capacity before overload alert
SPIKE_THRESHOLD_PCT      = 20.0   # % change per reading = demand spike
MAPE_THRESHOLD           = 10.0   # forecast MAPE (%) above which alert fires
LOSS_ANOMALY_SIGMA       = 2.0    # Z-score threshold for energy-loss anomaly
LOSS_ROLLING_WINDOW      = 24     # rolling window size (readings) for loss stats

# ── Forecasting ────────────────────────────────────────────────────────────
LOOKBACK_HOURS    = 24    # LSTM/GRU input window
FORECAST_HORIZON  = 24    # prediction horizon (hours)

# ── RL Training ────────────────────────────────────────────────────────────
RL_POLICY_PATH         = os.path.join(MODELS_DIR, "rl_policy.zip")
RL_TOTAL_TIMESTEPS     = 50_000   # pre-training timesteps (bundled model)

# ── Logging ────────────────────────────────────────────────────────────────
LOG_FILE   = os.path.join(LOGS_DIR, "scada.log")
LOG_LEVEL  = "INFO"          # DEBUG | INFO | WARNING | ERROR
