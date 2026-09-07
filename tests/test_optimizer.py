"""
Unit tests for PowerOptimizer — calculate_metrics (via LoadForecaster)
and calculate_fairness_index.
"""
import pytest
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.optimizer import PowerOptimizer


# ── Fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def optimizer():
    return PowerOptimizer()


@pytest.fixture
def simple_feeders():
    return [
        {"name": "Hospital",    "priority": "critical", "demand": 10.0},
        {"name": "Industrial",  "priority": "high",     "demand": 20.0},
        {"name": "Residential", "priority": "low",      "demand": 30.0},
    ]


@pytest.fixture
def perfect_schedule(simple_feeders):
    """Each feeder receives exactly its demand."""
    sched = []
    for f in simple_feeders:
        sched.append({"feeder": f["name"], "hour": 0,
                      "allocated_power": f["demand"], "priority": f["priority"]})
    return sched


# ── calculate_fairness_index ─────────────────────────────────────────────────
class TestCalculateFairnessIndex:
    def test_perfect_allocation_returns_one(self, optimizer, simple_feeders, perfect_schedule):
        fi = optimizer.calculate_fairness_index(perfect_schedule, simple_feeders)
        assert abs(fi - 1.0) < 1e-6

    def test_fairness_in_zero_to_one_range(self, optimizer, simple_feeders):
        # give hospital 80%, give residential 10%
        sched = [
            {"feeder": "Hospital",    "hour": 0, "allocated_power": 8.0,  "priority": "critical"},
            {"feeder": "Industrial",  "hour": 0, "allocated_power": 10.0, "priority": "high"},
            {"feeder": "Residential", "hour": 0, "allocated_power": 3.0,  "priority": "low"},
        ]
        fi = optimizer.calculate_fairness_index(sched, simple_feeders)
        assert 0.0 <= fi <= 1.0

    def test_empty_feeders_returns_zero(self, optimizer):
        fi = optimizer.calculate_fairness_index([], [])
        assert fi == 0.0

    def test_zero_demand_feeder_skipped(self, optimizer):
        feeders = [{"name": "X", "priority": "low", "demand": 0.0}]
        sched   = [{"feeder": "X", "hour": 0, "allocated_power": 0.0, "priority": "low"}]
        fi = optimizer.calculate_fairness_index(sched, feeders)
        assert fi == 0.0

    def test_unequal_allocation_less_than_one(self, optimizer, simple_feeders):
        sched = [
            {"feeder": "Hospital",    "hour": 0, "allocated_power": 10.0, "priority": "critical"},
            {"feeder": "Industrial",  "hour": 0, "allocated_power": 1.0,  "priority": "high"},
            {"feeder": "Residential", "hour": 0, "allocated_power": 1.0,  "priority": "low"},
        ]
        fi = optimizer.calculate_fairness_index(sched, simple_feeders)
        assert fi < 1.0


# ── calculate_metrics (LoadForecaster) ──────────────────────────────────────
class TestCalculateMetrics:
    """
    LoadForecaster.calculate_metrics() is the function under test.
    We import it directly to avoid TensorFlow initialisation in CI.
    """

    @pytest.fixture
    def forecaster(self):
        # Lazy import so TF is only loaded when this fixture is used
        from core.ml_models import LoadForecaster
        return LoadForecaster()

    def test_perfect_prediction_mape_zero(self, forecaster):
        a = np.array([10.0, 20.0, 30.0])
        m = forecaster.calculate_metrics(a, a)
        assert m["mape"] == pytest.approx(0.0, abs=1e-6)
        assert m["r2"]   == pytest.approx(1.0, abs=1e-6)

    def test_returns_required_keys(self, forecaster):
        a = np.array([10.0, 20.0])
        p = np.array([11.0, 19.0])
        m = forecaster.calculate_metrics(a, p)
        assert {"mape", "rmse", "r2"} <= set(m.keys())

    def test_empty_arrays_returns_defaults(self, forecaster):
        m = forecaster.calculate_metrics(np.array([]), np.array([]))
        assert m["mape"] == 100.0

    def test_mape_ignores_zero_actuals(self, forecaster):
        """Zero actuals should not produce division-by-zero or inf."""
        a = np.array([0.0, 10.0, 20.0])
        p = np.array([1.0, 11.0, 21.0])
        m = forecaster.calculate_metrics(a, p)
        assert np.isfinite(m["mape"])

    def test_rmse_is_nonnegative(self, forecaster):
        a = np.array([5.0, 10.0, 15.0])
        p = np.array([6.0,  9.0, 14.0])
        m = forecaster.calculate_metrics(a, p)
        assert m["rmse"] >= 0.0
