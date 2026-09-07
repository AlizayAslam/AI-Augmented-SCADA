"""
train_models_offline.py — OFFLINE Training Pipeline
====================================================
Run this script ONCE (or on a schedule) to train and register all models.
This must NEVER be imported or called from the runtime UI.

Usage:
    python train_models_offline.py [--feeders all] [--model lstm,gru,prophet]

Output:
    models/<MODEL>_<Feeder_Name>.keras  + _scaler.pkl
    models/model_registry.json          (model metadata + metrics)
"""

import argparse
import json
import os
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("offline_trainer")

from config import DB_PATH, MODELS_DIR
from core.db import DatabaseManager
from core.ml_models import LoadForecaster

REGISTRY_PATH = os.path.join(MODELS_DIR, "model_registry.json")


def load_registry() -> dict:
    if os.path.exists(REGISTRY_PATH):
        with open(REGISTRY_PATH) as f:
            return json.load(f)
    return {}


def save_registry(registry: dict):
    with open(REGISTRY_PATH, "w") as f:
        json.dump(registry, f, indent=2, default=str)
    logger.info("Registry saved → %s", REGISTRY_PATH)


def train_feeder(db: DatabaseManager, feeder_name: str, model_types: list, horizon: int = 24) -> dict:
    """Train all requested model types for a single feeder. Returns registry entry."""
    df = db.get_feeder_data(feeder=feeder_name)
    if df.empty or len(df) < 200:
        logger.warning("[%s] Insufficient data (%d rows) — skip", feeder_name, len(df))
        return {}

    # Ensure timestamp + load columns
    df = df.rename(columns={"timestamp": "timestamp"})
    if "timestamp" not in df.columns or "load" not in df.columns:
        logger.error("[%s] Missing required columns", feeder_name)
        return {}

    df["timestamp"] = df["timestamp"].astype("datetime64[ns]")
    df = df.sort_values("timestamp").reset_index(drop=True)

    entry = {
        "feeder": feeder_name,
        "trained_at": datetime.utcnow().isoformat(),
        "data_rows": len(df),
        "models": {},
    }

    for mtype in model_types:
        logger.info("[%s] Training %s…", feeder_name, mtype)
        fc = LoadForecaster()
        try:
            if mtype == "LSTM":
                result = fc.train_lstm(df, horizon=horizon, epochs=100)
            elif mtype == "GRU":
                result = fc.train_gru(df, horizon=horizon, epochs=100)
            elif mtype == "Prophet":
                result = fc.train_prophet(df, periods=horizon)
            else:
                logger.warning("Unknown model type: %s", mtype)
                continue

            fc.save_model(feeder_name)
            metrics = result["metrics"]
            logger.info(
                "[%s][%s] MAPE=%.2f%%  RMSE=%.3f  R²=%.4f",
                feeder_name, mtype, metrics["mape"], metrics["rmse"], metrics["r2"],
            )
            entry["models"][mtype] = {
                "metrics": metrics,
                "epochs_trained": result.get("epochs_trained", "—"),
                "status": "ok",
            }

        except Exception as exc:
            logger.error("[%s][%s] Training failed: %s", feeder_name, mtype, exc)
            entry["models"][mtype] = {"status": "failed", "error": str(exc)}

    return entry


def main():
    parser = argparse.ArgumentParser(description="Offline SCADA Model Trainer")
    parser.add_argument("--feeders", default="all", help="Comma-separated feeder names or 'all'")
    parser.add_argument("--models", default="LSTM,GRU", help="Comma-separated model types")
    parser.add_argument("--horizon", type=int, default=24, help="Forecast horizon (hours)")
    args = parser.parse_args()

    db = DatabaseManager(DB_PATH)
    db.ensure_database()

    # Resolve feeders
    if args.feeders.lower() == "all":
        rows = db.fetch_all("SELECT name FROM feeders WHERE status='active' ORDER BY name")
        feeder_list = [r["name"] for r in rows]
    else:
        feeder_list = [f.strip() for f in args.feeders.split(",")]

    model_types = [m.strip() for m in args.models.split(",")]

    logger.info("=" * 60)
    logger.info("OFFLINE TRAINING PIPELINE")
    logger.info("Feeders : %s", feeder_list)
    logger.info("Models  : %s", model_types)
    logger.info("Horizon : %d hours", args.horizon)
    logger.info("=" * 60)

    registry = load_registry()

    for feeder in feeder_list:
        entry = train_feeder(db, feeder, model_types, args.horizon)
        if entry:
            registry[feeder] = entry

    save_registry(registry)
    logger.info("✅ Offline training complete. %d feeders processed.", len(feeder_list))


if __name__ == "__main__":
    main()
