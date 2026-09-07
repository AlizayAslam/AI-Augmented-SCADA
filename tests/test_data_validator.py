"""
Unit tests for DataValidator
"""
import pytest
import pandas as pd
import numpy as np
from core.data_validator import DataValidator


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def valid_df():
    """Minimal well-formed DataFrame for testing."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=5, freq="h"),
        "feeder":    ["F1"] * 5,
        "load":      [10.0, 11.0, 12.0, 11.5, 10.8],
        "loss":      [1.6,  1.7,  1.8,  1.7,  1.6],
    })


# ── validate_columns ────────────────────────────────────────────────────────
class TestValidateColumns:
    def test_all_required_columns_present(self, valid_df):
        ok, msg = DataValidator.validate_columns(valid_df)
        assert ok is True
        assert msg == "OK"

    def test_missing_single_column(self, valid_df):
        df = valid_df.drop(columns=["loss"])
        ok, msg = DataValidator.validate_columns(df)
        assert ok is False
        assert "loss" in msg

    def test_missing_multiple_columns(self):
        df = pd.DataFrame({"timestamp": [], "feeder": []})
        ok, msg = DataValidator.validate_columns(df)
        assert ok is False
        assert "load" in msg
        assert "loss" in msg

    def test_extra_columns_are_accepted(self, valid_df):
        valid_df["voltage"] = 11.0
        ok, msg = DataValidator.validate_columns(valid_df)
        assert ok is True

    def test_empty_dataframe_fails(self):
        ok, msg = DataValidator.validate_columns(pd.DataFrame())
        assert ok is False


# ── clean_data ───────────────────────────────────────────────────────────────
class TestCleanData:
    def test_removes_exact_duplicates(self, valid_df):
        df_dup = pd.concat([valid_df, valid_df.iloc[[0]]], ignore_index=True)
        cleaned = DataValidator.clean_data(df_dup)
        assert len(cleaned) == len(valid_df)

    def test_clips_negative_load_to_zero(self, valid_df):
        valid_df.loc[0, "load"] = -5.0
        cleaned = DataValidator.clean_data(valid_df)
        assert (cleaned["load"] >= 0).all()

    def test_clips_load_above_1000(self, valid_df):
        valid_df.loc[0, "load"] = 9999.0
        cleaned = DataValidator.clean_data(valid_df)
        assert cleaned["load"].max() <= 1000.0

    def test_loss_never_exceeds_load(self, valid_df):
        valid_df.loc[2, "loss"] = valid_df.loc[2, "load"] + 50.0
        cleaned = DataValidator.clean_data(valid_df)
        assert (cleaned["loss"] <= cleaned["load"]).all()

    def test_interpolates_missing_values(self, valid_df):
        valid_df.loc[2, "load"] = np.nan
        cleaned = DataValidator.clean_data(valid_df)
        assert cleaned["load"].isna().sum() == 0

    def test_returns_dataframe(self, valid_df):
        result = DataValidator.clean_data(valid_df)
        assert isinstance(result, pd.DataFrame)
