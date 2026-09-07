# AI-Augmented SCADA — Corrected Architecture

## 🔴 Key Architectural Rule

**Training NEVER happens inside the runtime application.**

## System Components

### 1. Offline Training Pipeline (run by engineers, not operators)
```
python train_models_offline.py [--feeders all] [--models LSTM,GRU]
```
- Reads historical data from SQLite
- Trains LSTM, GRU, Prophet models per feeder
- Saves model files to `models/` directory
- Writes metrics + metadata to `models/model_registry.json`

### 2. Runtime Application (operators, always running)
```
python main.py
```
- Loads `model_registry.json` at startup (read-only)
- `ForecastPage` calls `model_registry.get_forecaster()` → inference only
- `OptimizePage` reads forecasted demand from `forecasts` DB table
- Training buttons / re-training are NOT present in runtime UI

### 3. Database Backup (scheduled)
```
python backup_db.py --keep 14
```
- Safe online backup using SQLite backup API
- Retains N most recent backups in `backups/` directory

## Data Flow

```
NEPRA CSV Data
     │
     ▼
[Database: feeder_data]
     │
     ▼  (offline, engineers only)
[train_models_offline.py]
     │
     ├──► models/LSTM_*.keras + _scaler.pkl
     ├──► models/GRU_*.keras  + _scaler.pkl
     └──► models/model_registry.json
                    │
                    │  (loaded read-only at startup)
                    ▼
         [Runtime: ModelRegistry singleton]
                    │
          ┌─────────┴─────────┐
          │                   │
          ▼                   ▼
   [ForecastPage]      [ModelComparisonPage]
   inference only      shows stored metrics only
          │
          │ saves forecasts to DB
          ▼
   [Database: forecasts]
          │
          │ per-feeder forecasted demand
          ▼
   [OptimizePage → LP Optimizer]
```

## Feeder Rename Consistency

When a feeder is renamed:
1. ✅ `db.rename_feeder()` — updates 5 DB tables
2. ✅ `model_registry.rename_model_files()` — renames .keras + .pkl files
3. ✅ Registry JSON updated with new feeder name
4. ✅ In-memory model cache invalidated

## Security Checklist
- [ ] Change DEFAULT_ADMIN_PASSWORD in config.py before deployment
- [ ] Move credentials to environment variables
- [ ] Enable regular backup_db.py via scheduler
- [ ] All forecast/optimization runs are logged via db.log_forecast_run()
