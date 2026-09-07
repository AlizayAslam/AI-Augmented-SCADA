# AI-Augmented SCADA System

## Intelligent Power Distribution Management for Sukkur

AI-Augmented SCADA is an offline desktop decision-support application for monitoring and managing power distribution networks. It combines load forecasting, priority-aware load-shedding optimisation, reinforcement-learning scheduling, anomaly detection, and operational reporting in a single PyQt6 application.

## Screenshots

Application screenshots are stored in [`docs/screenshots/`](docs/screenshots/):

| Screen | File |
| --- | --- |
| Sign in | [`SignIn.png`](docs/screenshots/SignIn.png) |
| Sign up | [`SignUp.png`](docs/screenshots/SignUp.png) |
| Dashboard | [`Dashboard.png`](docs/screenshots/Dashboard.png) |
| Data import | [`Import.png`](docs/screenshots/Import.png) |
| Optimization | [`OPtimzation.png`](docs/screenshots/OPtimzation.png) |
| Alerts | [`alert.png`](docs/screenshots/alert.png) |
| Feeders | [`feeder.png`](docs/screenshots/feeder.png) |
| Forecasting | [`forecasting.png`](docs/screenshots/forecasting.png) |

## Key Capabilities

- Short-term feeder load forecasting with LSTM, GRU, and Prophet models
- Priority-aware load-shedding optimisation using linear programming
- Reinforcement-learning scheduling with PPO and Gymnasium
- Feeder monitoring and overload, spike, and energy-loss alerts
- Data validation, cleaning, and import workflows
- Model comparison and forecast evaluation
- PDF reports for forecasts, schedules, and model results
- Local SQLite database with role-based application access
- Offline operation after dependencies and model files are installed

## Technology Stack

| Area | Technology |
| --- | --- |
| Desktop UI | PyQt6 |
| Forecasting | TensorFlow/Keras, Prophet, scikit-learn |
| Optimisation | PuLP with CBC solver |
| Reinforcement learning | Stable-Baselines3, Gymnasium |
| Database | SQLite3 |
| Reports | ReportLab |
| Security | bcrypt |

## Results Summary

### Short-Term Load Forecasting

| Model | MAPE (%) | RMSE (MW) | MAE (MW) | Training Time |
| --- | ---: | ---: | ---: | ---: |
| LSTM | 3.82 | 0.71 | 0.54 | 84.2 s |
| GRU | 4.01 | 0.74 | 0.57 | 61.8 s |
| Prophet | 4.47 | 0.83 | 0.63 | 12.3 s |
| Target | < 5.00 | < 2.0 | - | < 120 s |

RMSE values are measured in MW and are consistent with the feeder demand range of 5-18 MW.

### Load-Shedding Optimisation

| Metric | Fixed Rotation | LP Optimised |
| --- | ---: | ---: |
| Hospital outage (min/day) | 120 | 42 |
| Outage reduction | - | 65% |
| Jain's Fairness Index | 0.71 | 0.94 |
| Over-generation (%) | 12.3 | 4.1 |

### Reinforcement-Learning Scheduler

- Jain's Fairness Index: 0.91 after 100 training episodes
- Hospital outage reduction: 58%

## Dataset

The project includes synthetic feeder data calibrated against published NEPRA State of Industry Report 2024 statistics for HESCO Sukkur Circle. The dataset models feeder capacities from 5-18 MW, distribution losses of approximately 16-17%, seasonal demand patterns, and peak-demand periods.

Raw operational SCADA data from Pakistani distribution utilities is not publicly accessible. The included data is intended for research, demonstration, and model evaluation; it is not a replacement for live utility SCADA data.

## Project Structure

```text
.
├── main.py                     Application entry point
├── config.py                   Paths and application settings
├── requirements.txt            Python dependencies
├── core/                       Database, forecasting, optimisation, and alerts
├── ui/                         PyQt6 screens and workflows
├── data/                       Datasets and data-generation utilities
├── models/                     Saved LSTM and GRU model files
├── tests/                      Automated tests
├── assets/                     Application stylesheet and visual assets
└── docs/screenshots/           Application screenshots for this README
```

## Installation

### Requirements

- Windows, Linux, or macOS
- Python 3.10 or 3.11 recommended
- A working C/C++ runtime supported by TensorFlow on the target operating system

### Setup

From the project directory:

```bash
python -m venv venv
```

Activate the environment on Windows:

```powershell
venv\Scripts\Activate.ps1
```

Activate it on macOS or Linux:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Running the Application

```bash
python main.py
```

The application creates its local SQLite database and log files automatically on first launch.

Default administrator credentials:

```text
Username: admin
Password: admin123
```

Change the default password before using the application in a real operational environment.

## Testing

Run the test suite with:

```bash
pytest tests/ -v
```

Run tests with coverage:

```bash
pytest tests/ --cov=core --cov-report=term-missing
```

## Data and Models

The project includes synthetic feeder data calibrated against published NEPRA statistics. The dataset is intended for research, demonstration, and model evaluation; it is not a replacement for live utility SCADA data.

Pre-trained model files are stored in `models/`. To retrain forecasting models locally:

```bash
python train_models_offline.py
```

The reinforcement-learning policy can be trained with:

```bash
python train_rl_policy.py
```

## Architecture

```text
Presentation Layer    PyQt6 user interface (ui/)
          |
Application Layer     Forecasting, optimisation, alerts, and scheduling (core/)
          |
Data Layer            SQLite database, CSV datasets, and saved models
```

For more detail, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Important Notes

- The application is designed for offline use and does not connect to a live SCADA system by default.
- The bundled data is synthetic and should be clearly identified as such in reports and demonstrations.
- Local runtime files such as the SQLite database, logs, caches, and generated PDF reports are excluded from Git through `.gitignore`.

