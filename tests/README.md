# Test Suite

Run all tests from the project root:

```bash
pip install pytest pytest-cov
pytest tests/ -v
```

With coverage report:

```bash
pytest tests/ --cov=core --cov-report=term-missing
```

## Test files

| File | Covers |
|------|--------|
| `test_data_validator.py` | `DataValidator.validate_columns()`, `clean_data()` |
| `test_optimizer.py` | `PowerOptimizer.calculate_fairness_index()`, `LoadForecaster.calculate_metrics()` |
