"""
Generate NEPRA-based synthetic feeder data for Sukkur grid station.
Uses patterns from NEPRA State of Industry Report 2024:
- Sukkur 132kV grid station, 8 feeders
- Seasonal variation: summer peak (June-Aug) ~40% higher
- Daily pattern: peak 18:00-22:00 (evening), trough 02:00-05:00
- Weekly: weekday 15% higher than weekend
- Yearly: ~5% growth rate
- Distribution losses 16-17% (technical + non-technical)
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os

np.random.seed(42)

FEEDERS = [
    {"name": "Civil Hospital Feeder",        "priority": "critical", "base_mw": 8.5,  "capacity": 12.0},
    {"name": "Airport Road Feeder",           "priority": "high",     "base_mw": 12.0, "capacity": 16.0},
    {"name": "Rohri Industrial Feeder",       "priority": "high",     "base_mw": 18.0, "capacity": 24.0},
    {"name": "SITE Area Feeder",              "priority": "medium",   "base_mw": 14.0, "capacity": 20.0},
    {"name": "Military Road Feeder",          "priority": "high",     "base_mw": 10.0, "capacity": 15.0},
    {"name": "Barrage Colony Feeder",         "priority": "medium",   "base_mw": 9.5,  "capacity": 14.0},
    {"name": "Shikarpur Road Feeder",         "priority": "low",      "base_mw": 7.0,  "capacity": 10.0},
    {"name": "Old Sukkur Residential Feeder", "priority": "low",      "base_mw": 6.0,  "capacity": 9.0},
]

start = datetime(2024, 1, 1, 0, 0)
end   = datetime(2024, 12, 31, 23, 0)
timestamps = pd.date_range(start=start, end=end, freq='h')

records = []
for ts in timestamps:
    month     = ts.month
    hour      = ts.hour
    weekday   = ts.weekday()

    # Seasonal factor: NEPRA shows summer peaks in Sukkur (hot weather = heavy AC load)
    if month in [6, 7, 8]:        seasonal = 1.42   # summer peak
    elif month in [5, 9]:         seasonal = 1.20
    elif month in [4, 10]:        seasonal = 1.05
    elif month in [11, 12, 1]:    seasonal = 0.82   # winter low
    else:                         seasonal = 0.90

    # Daily pattern (evening peak, night trough)
    if 18 <= hour <= 22:          daily = 1.35
    elif 15 <= hour <= 17:        daily = 1.15
    elif  9 <= hour <= 14:        daily = 1.05
    elif  6 <= hour <=  8:        daily = 0.95
    else:                         daily = 0.60   # 00-05

    # Weekly factor
    weekly = 1.15 if weekday < 5 else 0.85

    for f in FEEDERS:
        base = f["base_mw"]
        load = base * seasonal * daily * weekly
        load += np.random.normal(0, base * 0.05)   # 5% noise
        load = max(base * 0.3, min(f["capacity"] * 0.98, load))

        # Loss: 16-17% average; civil hospital lower (better maintained)
        loss_pct = np.random.uniform(0.08, 0.18)
        if "hospital" in f["name"].lower():
            loss_pct = np.random.uniform(0.04, 0.09)

        loss     = load * loss_pct
        voltage  = np.random.uniform(10.8, 11.2)   # 11 kV feeder
        current  = (load * 1000) / (np.sqrt(3) * voltage) if voltage > 0 else 0
        pf       = np.random.uniform(0.82, 0.95)
        temp     = 15 + 20 * np.sin(np.pi * (month - 1) / 11) + np.random.normal(0, 2)
        humidity = 55 + 20 * np.sin(np.pi * (month + 2) / 11) + np.random.normal(0, 4)
        humidity = max(30, min(95, humidity))

        records.append({
            "timestamp":    ts.strftime("%Y-%m-%d %H:%M:%S"),
            "feeder":       f["name"],
            "load":         round(load, 3),
            "loss":         round(loss, 3),
            "voltage":      round(voltage, 2),
            "current":      round(current, 2),
            "power_factor": round(pf, 3),
            "temperature":  round(temp, 1),
            "humidity":     round(humidity, 1),
        })

df = pd.DataFrame(records)
out = os.path.join(os.path.dirname(__file__), "sukkur_nepra_2024.csv")
df.to_csv(out, index=False)
print(f"Generated {len(df):,} rows → {out}")
