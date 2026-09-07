"""
Machine Learning Models for Load Forecasting
FIX Issue 8:  LSTM/GRU now use Dense(n) direct multi-step output — not
              autoregressive loop.  Architecture matches thesis Chapter 4.3.2.
FIX Issue 11: run_cross_validation() provides 3-seed mean ± std metrics
              for statistical confidence in results.
"""

import logging
import numpy as np
logger = logging.getLogger(__name__)
import pandas as pd
import warnings
import os
import joblib
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_squared_error, r2_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, GRU, Dense, Dropout
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from prophet import Prophet

warnings.filterwarnings('ignore')

from config import MODELS_DIR, LOOKBACK_HOURS
os.makedirs(MODELS_DIR, exist_ok=True)

LOOKBACK = LOOKBACK_HOURS   # sliding-window size (thesis: 24-hour input)


class LoadForecaster:
    """Short-term load forecaster supporting LSTM, GRU, and Prophet."""

    def __init__(self):
        self.scaler           = MinMaxScaler()
        self.model            = None
        self.model_type       = None
        self.training_history = None

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------
    def prepare_data(
        self,
        df: pd.DataFrame,
        horizon: int = 1,
        lookback: int = LOOKBACK,
        test_size: float = 0.2,
    ):
        """
        Build sliding-window arrays for direct multi-step forecasting.

        X shape: (samples, lookback, 1)
        y shape: (samples, horizon)           <-- Issue 8 fix (multi-output)
        """
        data   = df['load'].values.reshape(-1, 1)
        scaled = self.scaler.fit_transform(data).flatten()

        X, y = [], []
        for i in range(lookback, len(scaled) - horizon + 1):
            X.append(scaled[i - lookback: i])
            y.append(scaled[i: i + horizon])   # horizon-length target vector

        X = np.array(X).reshape(-1, lookback, 1)
        y = np.array(y)   # shape (samples, horizon)

        split = int((1 - test_size) * len(X))
        return X[:split], X[split:], y[:split], y[split:], self.scaler

    # ------------------------------------------------------------------
    # Model builders  (Issue 8 fix: Dense(horizon) output)
    # ------------------------------------------------------------------
    def build_lstm(self, input_shape, horizon: int = 1) -> Sequential:
        """
        LSTM architecture from thesis Chapter 4.3.2.
        Output layer: Dense(horizon) — direct multi-step prediction.
        """
        model = Sequential([
            LSTM(64, return_sequences=True, input_shape=input_shape,
                 dropout=0.2, recurrent_dropout=0.2),
            LSTM(32, return_sequences=False,
                 dropout=0.2, recurrent_dropout=0.2),
            Dense(horizon),   # Issue 8 fix: n outputs, not 1
        ])
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        return model

    def build_gru(self, input_shape, horizon: int = 1) -> Sequential:
        """GRU architecture — mirrors LSTM but with GRU cells."""
        model = Sequential([
            GRU(64, return_sequences=True, input_shape=input_shape,
                dropout=0.2, recurrent_dropout=0.2),
            GRU(32, return_sequences=False,
                dropout=0.2, recurrent_dropout=0.2),
            Dense(horizon),   # Issue 8 fix
        ])
        model.compile(optimizer='adam', loss='mse', metrics=['mae'])
        return model

    # ------------------------------------------------------------------
    # Training methods
    # ------------------------------------------------------------------
    def _fit_deep_learning(
        self,
        model_type: str,
        df: pd.DataFrame,
        horizon: int = 24,
        epochs: int = 100,
        verbose: int = 0,
        seed: int = 42,
    ) -> dict:
        """Internal trainer used by both public train_lstm / train_gru."""
        import tensorflow as tf
        np.random.seed(seed)
        tf.random.set_seed(seed)

        if len(df) < LOOKBACK + horizon + 10:
            raise ValueError(
                f"Need at least {LOOKBACK + horizon + 10} rows; got {len(df)}"
            )

        X_tr, X_te, y_tr, y_te, scaler = self.prepare_data(df, horizon=horizon)

        if model_type == 'LSTM':
            self.model = self.build_lstm((LOOKBACK, 1), horizon)
        else:
            self.model = self.build_gru((LOOKBACK, 1), horizon)

        self.model_type = model_type

        callbacks = [
            EarlyStopping(monitor='val_loss', patience=10,
                          restore_best_weights=True),
            ReduceLROnPlateau(monitor='val_loss', factor=0.5,
                              patience=5, min_lr=1e-5),
        ]
        self.training_history = self.model.fit(
            X_tr, y_tr,
            epochs=epochs,
            batch_size=32,
            validation_split=0.1,
            callbacks=callbacks,
            verbose=verbose,
        )

        # Evaluate on held-out test set
        preds_scaled = self.model.predict(X_te, verbose=0)  # (samples, horizon)
        # Inverse-transform: reshape to (-1,1), invert, reshape back
        preds = scaler.inverse_transform(preds_scaled.reshape(-1, 1)).reshape(preds_scaled.shape)
        actual = scaler.inverse_transform(y_te.reshape(-1, 1)).reshape(y_te.shape)

        metrics = self.calculate_metrics(actual.flatten(), preds.flatten())
        return {
            'model':         self.model,
            'metrics':       metrics,
            'history':       self.training_history.history,
            'epochs_trained': len(self.training_history.history['loss']),
        }

    def train_lstm(self, df: pd.DataFrame, horizon: int = 24,
                   epochs: int = 100, verbose: int = 0) -> dict:
        """Train LSTM model (direct multi-step, thesis Chapter 4.3.2)."""
        return self._fit_deep_learning('LSTM', df, horizon, epochs, verbose)

    def train_gru(self, df: pd.DataFrame, horizon: int = 24,
                  epochs: int = 100, verbose: int = 0) -> dict:
        """Train GRU model (direct multi-step, thesis Chapter 4.3.3)."""
        return self._fit_deep_learning('GRU', df, horizon, epochs, verbose)

    def train_prophet(self, df: pd.DataFrame, periods: int = 24,
                      test_size: float = 0.2) -> dict:
        """
        Train Prophet model with proper chronological held-out evaluation.
        (thesis Chapter 4.3.4)
        """
        self.model_type = 'Prophet'

        if len(df) < 48:
            raise ValueError(f"Need at least 48 rows; got {len(df)}")

        df = df.sort_values('timestamp')
        split = int((1 - test_size) * len(df))
        train_df = df.iloc[:split].copy()
        test_df  = df.iloc[split:].copy()

        prophet_df = train_df[['timestamp', 'load']].rename(
            columns={'timestamp': 'ds', 'load': 'y'}
        )

        self.model = Prophet(
            yearly_seasonality=False,   # disabled: dataset covers sub-annual period (thesis §4.3.4)
            weekly_seasonality=True,
            daily_seasonality=True,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
        )
        if 'temperature' in df.columns:
            self.model.add_regressor('temperature')
            prophet_df['temperature'] = train_df['temperature'].values

        self.model.fit(prophet_df)

        test_len = min(len(test_df), max(1, periods))
        future = self.model.make_future_dataframe(
            periods=test_len, freq='h', include_history=False
        )
        if 'temperature' in df.columns:
            if 'temperature' in test_df.columns and not test_df['temperature'].isna().all():
                future['temperature'] = test_df['temperature'].iloc[:test_len].values
            else:
                future['temperature'] = train_df['temperature'].mean()

        forecast = self.model.predict(future)
        preds  = forecast['yhat'].values[:test_len]
        actual = test_df['load'].values[:test_len]

        return {
            'model':    self.model,
            'metrics':  self.calculate_metrics(actual, preds),
            'forecast': forecast,
        }

    # ------------------------------------------------------------------
    # Issue 11: 3-seed cross-validation for statistical confidence
    # ------------------------------------------------------------------
    def run_cross_validation(
        self,
        model_type: str,
        df: pd.DataFrame,
        horizon: int = 24,
        seeds: list = None,
        epochs: int = 50,
    ) -> dict:
        """
        Train the model with multiple random seeds and report mean ± std.

        Returns
        -------
        dict with keys:
            mape_mean, mape_std, rmse_mean, rmse_std,
            r2_mean,   r2_std,   seed_results (list of per-seed metrics)
        """
        if seeds is None:
            seeds = [42, 7, 123]   # 3 seeds as required by thesis reviewer

        seed_results = []
        for seed in seeds:
            forecaster = LoadForecaster()
            if model_type == 'LSTM':
                result = forecaster._fit_deep_learning(
                    'LSTM', df, horizon=horizon, epochs=epochs, seed=seed
                )
            elif model_type == 'GRU':
                result = forecaster._fit_deep_learning(
                    'GRU', df, horizon=horizon, epochs=epochs, seed=seed
                )
            else:
                result = forecaster.train_prophet(df, periods=horizon)
            seed_results.append(result['metrics'])

        mapes = [r['mape'] for r in seed_results]
        rmses = [r['rmse'] for r in seed_results]
        r2s   = [r['r2']   for r in seed_results]

        return {
            'mape_mean':    float(np.mean(mapes)),
            'mape_std':     float(np.std(mapes)),
            'rmse_mean':    float(np.mean(rmses)),
            'rmse_std':     float(np.std(rmses)),
            'r2_mean':      float(np.mean(r2s)),
            'r2_std':       float(np.std(r2s)),
            'seed_results': seed_results,
        }

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------
    def forecast(self, steps: int, recent_data: pd.DataFrame = None) -> np.ndarray:
        if self.model_type in ('LSTM', 'GRU'):
            if recent_data is None:
                raise ValueError("recent_data required for LSTM/GRU inference")
            return self._forecast_deep_learning(steps, recent_data)
        elif self.model_type == 'Prophet':
            return self._forecast_prophet(steps)
        raise ValueError("No model trained yet")

    def _forecast_deep_learning(self, steps: int, recent_data: pd.DataFrame) -> np.ndarray:
        """
        Direct multi-step inference (Issue 8 fix — no autoregressive loop).
        Model outputs 'steps' values in one forward pass.
        """
        recent_vals = recent_data['load'].values[-LOOKBACK:]
        if len(recent_vals) < LOOKBACK:
            pad = np.full(LOOKBACK - len(recent_vals), recent_vals[0])
            recent_vals = np.concatenate([pad, recent_vals])

        scaled = self.scaler.transform(recent_vals.reshape(-1, 1)).flatten()
        x = scaled.reshape(1, LOOKBACK, 1)

        # One forward pass -> (1, steps)
        preds_scaled = self.model.predict(x, verbose=0)[0]   # shape (steps,)
        preds_scaled = preds_scaled[:steps].reshape(-1, 1)
        return self.scaler.inverse_transform(preds_scaled).flatten()

    def _forecast_prophet(self, steps: int) -> np.ndarray:
        future   = self.model.make_future_dataframe(periods=steps, freq='h')
        forecast = self.model.predict(future)
        return forecast['yhat'].values[-steps:]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_model(self, feeder_name: str):
        safe = feeder_name.replace(' ', '_').replace('/', '_')
        if self.model_type in ('LSTM', 'GRU'):
            path = os.path.join(MODELS_DIR, f'{self.model_type}_{safe}.keras')
            self.model.save(path)
            joblib.dump(self.scaler, os.path.join(MODELS_DIR, f'{self.model_type}_{safe}_scaler.pkl'))
            print(f'Model saved: {path}')
        elif self.model_type == 'Prophet':
            path = os.path.join(MODELS_DIR, f'Prophet_{safe}.pkl')
            joblib.dump(self.model, path)
            print(f'Prophet saved: {path}')

    def load_model(self, model_type: str, feeder_name: str) -> bool:
        safe = feeder_name.replace(' ', '_').replace('/', '_')
        try:
            if model_type in ('LSTM', 'GRU'):
                from tensorflow.keras.models import load_model as keras_load
                path        = os.path.join(MODELS_DIR, f'{model_type}_{safe}.keras')
                scaler_path = os.path.join(MODELS_DIR, f'{model_type}_{safe}_scaler.pkl')
                if not os.path.exists(path):
                    return False
                self.model      = keras_load(path)
                self.scaler     = joblib.load(scaler_path)
                self.model_type = model_type
                return True
            elif model_type == 'Prophet':
                path = os.path.join(MODELS_DIR, f'Prophet_{safe}.pkl')
                if not os.path.exists(path):
                    return False
                self.model      = joblib.load(path)
                self.model_type = 'Prophet'
                return True
        except Exception as e:
            print(f'Model load failed: {e}')
        return False

    def model_exists(self, model_type: str, feeder_name: str) -> bool:
        safe = feeder_name.replace(' ', '_').replace('/', '_')
        if model_type in ('LSTM', 'GRU'):
            path = os.path.join(MODELS_DIR, f'{model_type}_{safe}.keras')
        else:
            path = os.path.join(MODELS_DIR, f'Prophet_{safe}.pkl')
        return os.path.exists(path)

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------
    def calculate_metrics(self, actual: np.ndarray, predicted: np.ndarray) -> dict:
        """
        Compute all SRS-required metrics:
            MAPE  — Mean Absolute Percentage Error
            sMAPE — Symmetric MAPE (stable near zero load)
            MAE   — Mean Absolute Error (MW)
            MSE   — Mean Squared Error (MW²)
            RMSE  — Root Mean Squared Error (MW)
            R²    — Coefficient of Determination
        """
        actual    = np.array(actual).flatten()
        predicted = np.array(predicted).flatten()

        if len(actual) == 0 or len(predicted) == 0:
            return {'mape': 100.0, 'smape': 100.0, 'mae': 0.0,
                    'mse': 0.0, 'rmse': 0.0, 'r2': 0.0}

        # MAPE — guard against zero actuals
        nz    = np.where(np.abs(actual) < 1e-9, 1e-9, actual)
        mape  = float(np.mean(np.abs((actual - predicted) / nz)) * 100)

        # sMAPE — symmetric, stable when actual ≈ 0
        smape = float(np.mean(
            2 * np.abs(actual - predicted) /
            (np.abs(actual) + np.abs(predicted) + 1e-9)
        ) * 100)

        mae  = float(np.mean(np.abs(actual - predicted)))
        mse  = float(mean_squared_error(actual, predicted))
        rmse = float(np.sqrt(mse))
        r2   = float(r2_score(actual, predicted))

        return {
            'mape':  round(mape,  4),
            'smape': round(smape, 4),
            'mae':   round(mae,   4),
            'mse':   round(mse,   4),
            'rmse':  round(rmse,  4),
            'r2':    round(r2,    4),
        }

    def get_training_info(self):
        if self.training_history:
            h = self.training_history.history
            return {
                'final_loss':     h['loss'][-1],
                'final_val_loss': h['val_loss'][-1],
                'epochs':         len(h['loss']),
            }
        return None