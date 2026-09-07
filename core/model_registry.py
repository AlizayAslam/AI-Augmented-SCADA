"""
core/model_registry.py — Runtime Model Registry
================================================
Provides read-only access to pre-trained models at runtime.
Training is NEVER done here. Models are loaded from disk only.

This enforces the correct SCADA architecture:
    [Offline Training Pipeline] → [Model Files + Registry JSON]
                                        ↓
                              [Runtime Inference (this module)]
"""

import json
import logging
import os
from typing import Optional

from config import MODELS_DIR
from core.ml_models import LoadForecaster

logger = logging.getLogger(__name__)

REGISTRY_PATH = os.path.join(MODELS_DIR, "model_registry.json")


class ModelRegistry:
    """
    Singleton-style registry for pre-trained models.
    Call load_all() once at application startup.
    Then call get_forecaster() at runtime to get an inference-ready model.
    """

    def __init__(self):
        self._cache: dict[str, LoadForecaster] = {}  # key: "MODEL_TYPE::FeederName"
        self._registry_meta: dict = {}

    # ------------------------------------------------------------------
    # Startup: load registry metadata
    # ------------------------------------------------------------------
    def load_registry_meta(self) -> dict:
        """Load model_registry.json for metadata (metrics, training dates)."""
        if not os.path.exists(REGISTRY_PATH):
            logger.warning("model_registry.json not found. Run train_models_offline.py first.")
            return {}
        with open(REGISTRY_PATH) as f:
            self._registry_meta = json.load(f)
        logger.info("Registry loaded: %d feeders", len(self._registry_meta))
        return self._registry_meta

    # ------------------------------------------------------------------
    # Runtime: get a ready-to-use forecaster (lazy load with cache)
    # ------------------------------------------------------------------
    def get_forecaster(self, model_type: str, feeder_name: str) -> Optional[LoadForecaster]:
        """
        Return an inference-ready LoadForecaster for the given model + feeder.
        Loads from disk on first access; subsequent calls use the in-memory cache.
        Returns None if model files are not found.
        """
        cache_key = f"{model_type}::{feeder_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        fc = LoadForecaster()
        if fc.load_model(model_type, feeder_name):
            self._cache[cache_key] = fc
            logger.info("Loaded %s model for '%s'", model_type, feeder_name)
            return fc

        logger.warning(
            "No pre-trained %s model found for '%s'. "
            "Run train_models_offline.py to train models.",
            model_type, feeder_name,
        )
        return None

    def model_available(self, model_type: str, feeder_name: str) -> bool:
        """Check if a pre-trained model exists on disk."""
        fc = LoadForecaster()
        return fc.model_exists(model_type, feeder_name)

    def get_model_metrics(self, feeder_name: str) -> dict:
        """Return stored metrics from registry for a feeder (no re-training)."""
        return self._registry_meta.get(feeder_name, {}).get("models", {})

    def invalidate(self, feeder_name: str):
        """Remove cached models for a feeder (e.g., after rename)."""
        keys_to_remove = [k for k in self._cache if feeder_name in k]
        for k in keys_to_remove:
            del self._cache[k]
        logger.info("Cache invalidated for feeder '%s'", feeder_name)

    def rename_model_files(self, old_name: str, new_name: str):
        """
        Rename model files on disk when a feeder is renamed.
        Must be called from feeder rename operation to maintain consistency.
        """
        import glob
        old_safe = old_name.replace(" ", "_").replace("/", "_")
        new_safe = new_name.replace(" ", "_").replace("/", "_")

        patterns = [
            f"*_{old_safe}.keras",
            f"*_{old_safe}_scaler.pkl",
            f"*_{old_safe}.pkl",
        ]
        renamed = []
        for pattern in patterns:
            for path in glob.glob(os.path.join(MODELS_DIR, pattern)):
                new_path = path.replace(old_safe, new_safe)
                os.rename(path, new_path)
                renamed.append((path, new_path))
                logger.info("Renamed model file: %s → %s", path, new_path)

        # Update registry JSON
        if os.path.exists(REGISTRY_PATH):
            with open(REGISTRY_PATH) as f:
                reg = json.load(f)
            if old_name in reg:
                reg[new_name] = reg.pop(old_name)
                reg[new_name]["feeder"] = new_name
                with open(REGISTRY_PATH, "w") as f:
                    json.dump(reg, f, indent=2, default=str)

        self.invalidate(old_name)
        return renamed


# Module-level singleton used by runtime UI
model_registry = ModelRegistry()
