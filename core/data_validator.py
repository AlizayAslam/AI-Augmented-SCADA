"""
Data Validator for SCADA System
FIX Issue 7:  Replaced deprecated fillna(method=...) with .bfill() / .ffill()
FIX Issue 10: Duplicate-timestamp check now operates on (timestamp, feeder)
              pair, not timestamp alone — correct for multi-feeder CSVs.
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple

logger = logging.getLogger(__name__)


class DataValidator:
    """Validates and cleans incoming load data."""

    # ------------------------------------------------------------------
    # Column validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_columns(df: pd.DataFrame) -> Tuple[bool, str]:
        """Check all mandatory columns are present."""
        required = ['timestamp', 'feeder', 'load', 'loss']
        missing = [c for c in required if c not in df.columns]
        if missing:
            msg = f"Missing columns: {', '.join(missing)}"
            logger.warning("Column validation failed — %s", msg)
            return False, msg
        logger.debug("Column validation passed")
        return True, "OK"

    # ------------------------------------------------------------------
    # Timestamp validation  (Issue 10 fix)
    # ------------------------------------------------------------------
    @staticmethod
    def validate_timestamps(df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Validate timestamp format and per-feeder continuity.

        The multi-feeder CSV has the same timestamp repeated once per
        feeder, so we check duplicates on the (timestamp, feeder) pair —
        NOT on timestamp alone.
        """
        try:
            df = df.copy()
            df['timestamp'] = pd.to_datetime(df['timestamp'])

            if df.duplicated(subset=['timestamp', 'feeder']).any():
                msg = "Duplicate (timestamp, feeder) combinations found"
                logger.warning("Timestamp validation failed — %s", msg)
                return False, msg

            if 'feeder' in df.columns:
                for feeder, group in df.groupby('feeder'):
                    group_sorted = group.sort_values('timestamp')
                    if len(group_sorted) > 1:
                        gaps = group_sorted['timestamp'].diff().dropna()
                        if (gaps > pd.Timedelta(hours=2)).any():
                            msg = f"Large time gap detected in feeder '{feeder}'"
                            logger.warning("Timestamp validation failed — %s", msg)
                            return False, msg
            else:
                if len(df) > 1:
                    gaps = df['timestamp'].diff().dropna()
                    if (gaps > pd.Timedelta(hours=2)).any():
                        msg = "Large gaps in timestamps detected"
                        logger.warning("Timestamp validation failed — %s", msg)
                        return False, msg

            logger.debug("Timestamp validation passed")
            return True, "OK"
        except Exception as e:
            logger.error("Timestamp validation error: %s", e, exc_info=True)
            return False, f"Timestamp error: {str(e)}"

    # ------------------------------------------------------------------
    # Value validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_values(df: pd.DataFrame) -> Tuple[bool, str]:
        """Check for physically impossible values."""
        if (df['load'] < 0).any():
            return False, "Negative load values found"
        if (df['loss'] < 0).any():
            return False, "Negative loss values found"
        if (df['load'] > 1000).any():
            return False, "Load values exceed 1000 MW — check units"
        if (df['loss'] > df['load']).any():
            return False, "Loss cannot exceed load"

        if 'feeder' in df.columns:
            for _, group in df.groupby('feeder'):
                std = group['load'].std()
                if std > 0:
                    outliers = (group['load'] - group['load'].mean()).abs() > 3 * std
                    if outliers.any():
                        msg = f"Outliers detected: {outliers.sum()} point(s)"
                        logger.warning("Value validation — %s", msg)
                        return False, msg
        logger.debug("Value validation passed")
        return True, "OK"

    # ------------------------------------------------------------------
    # Data cleaning  (Issue 7 fix: .bfill() / .ffill() instead of fillna)
    # ------------------------------------------------------------------
    @staticmethod
    def clean_data(df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare data for ingestion."""
        before = len(df)
        df = df.drop_duplicates(subset=['timestamp', 'feeder'])
        dropped = before - len(df)
        if dropped:
            logger.info("clean_data: dropped %d duplicate rows", dropped)

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        df[numeric_cols] = (
            df[numeric_cols]
            .interpolate(method='linear', limit=3)
            .bfill(limit=3)
            .ffill(limit=3)
        )

        df = df.dropna()
        df['load'] = df['load'].clip(lower=0, upper=1000)
        df['loss'] = df['loss'].clip(lower=0)
        df['loss'] = df[['load', 'loss']].apply(
            lambda x: min(x['loss'], x['load']), axis=1
        )

        logger.info("clean_data: returning %d rows", len(df))
        return df
