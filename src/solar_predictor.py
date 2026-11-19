"""Chronological comparison of models for daily solar-radiation prediction."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor


class PredictionDataError(ValueError):
    """Raised when there is insufficient or invalid time-series data."""


class SolarPredictor:
    """Compare Linear Regression and Random Forest on chronological data."""

    FEATURES = [
        "cloud_cover", "temperature_2m", "day_sin", "day_cos",
    ]
    TIMEZONE = ZoneInfo("Asia/Karachi")

    @classmethod
    def tomorrow(cls):
        return datetime.now(cls.TIMEZONE).date() + timedelta(days=1)

    def __init__(self, hourly_frame: pd.DataFrame, random_state=42):
        required = {"cloud_cover", "temperature_2m", "shortwave_radiation"}
        missing = required.difference(hourly_frame.columns)
        if missing:
            raise PredictionDataError(
                "Prediction data is missing: " + ", ".join(sorted(missing))
            )

        frame = hourly_frame.copy()
        frame = frame.sort_index()
        daily = frame.resample("D").agg(
            shortwave_radiation=("shortwave_radiation", "sum"),
            cloud_cover=("cloud_cover", "mean"),
            temperature_2m=("temperature_2m", "mean"),
            shortwave_count=("shortwave_radiation", "count"),
            cloud_count=("cloud_cover", "count"),
            temperature_count=("temperature_2m", "count"),
        )
        daily["shortwave_radiation"] = daily["shortwave_radiation"] / 1000
        complete_days = (
            (daily["shortwave_count"] == 24)
            & (daily["cloud_count"] == 24)
            & (daily["temperature_count"] == 24)
        )
        daily = daily.loc[complete_days].drop(
            columns=["shortwave_count", "cloud_count", "temperature_count"]
        )
        day_of_year = daily.index.strftime("%j").astype(int).to_numpy()
        angle = 2 * np.pi * day_of_year / 365.25
        daily["day_sin"] = np.sin(angle)
        daily["day_cos"] = np.cos(angle)
        daily = daily.replace([np.inf, -np.inf], np.nan).dropna()
        month_counts = daily.groupby(daily.index.to_period("M")).size()
        complete_months = [
            month for month, count in month_counts.items()
            if count == month.days_in_month
        ]
        daily = daily.loc[daily.index.to_period("M").isin(complete_months)]
        if daily.index.to_period("M").nunique() < 4:
            raise PredictionDataError(
                "At least four complete calendar months of hourly data are required."
            )
        self.daily = daily
        self.random_state = random_state
        self.models = {}
        self.results = {}
        self.test_dates = None

    def train(self) -> dict:
        months = self.daily.index.to_period("M").unique()
        test_month_count = max(2, int(np.ceil(len(months) * 0.2)))
        if len(months) - test_month_count < 2:
            raise PredictionDataError(
                "Not enough earlier months remain after reserving unseen test months."
            )
        test_months = months[-test_month_count:]
        test_start = test_months[0].start_time
        train = self.daily.loc[self.daily.index < test_start]
        test = self.daily.loc[self.daily.index >= test_start]
        if train.empty or test.empty:
            raise PredictionDataError("Chronological month split produced an empty partition.")

        X_train = train[self.FEATURES]
        y_train = train["shortwave_radiation"]
        X_test = test[self.FEATURES]
        y_test = test["shortwave_radiation"]

        candidates = {
            "Linear Regression": make_pipeline(
                StandardScaler(), LinearRegression()
            ),
            "Random Forest": RandomForestRegressor(
                n_estimators=150,
                min_samples_leaf=3,
                random_state=self.random_state,
                n_jobs=-1,
            ),
        }

        baseline_prediction = np.full(len(test), y_train.mean(), dtype=float)
        self.results["Naive mean baseline"] = self._metrics(y_test, baseline_prediction)
        for name, model in candidates.items():
            model.fit(X_train, y_train)
            predictions = np.maximum(0.0, model.predict(X_test))
            self.results[name] = self._metrics(y_test, predictions)
            self.models[name] = model

        self.test_dates = test.index
        self.actual = y_test.to_numpy()
        self.training_mean = float(y_train.mean())
        self.test_months = [str(month) for month in test_months]
        return self.results

    @staticmethod
    def _metrics(actual, predictions):
        return {
            "MAE": float(mean_absolute_error(actual, predictions)),
            "RMSE": float(np.sqrt(mean_squared_error(actual, predictions))),
            "R2": float(r2_score(actual, predictions)),
            "predictions": np.asarray(predictions),
        }

    def _features_for_date(self, weather: dict, target_day: date) -> pd.DataFrame:
        cloud = weather.get("cloud_cover")
        temperature = weather.get("temperature_2m")
        if cloud is None or temperature is None or pd.isna(cloud) or pd.isna(temperature):
            raise PredictionDataError(
                "Forecast is missing cloud-cover or temperature."
            )
        angle = 2 * np.pi * target_day.timetuple().tm_yday / 365.25
        return pd.DataFrame([{
            "cloud_cover": float(cloud),
            "temperature_2m": float(temperature),
            "day_sin": float(np.sin(angle)),
            "day_cos": float(np.cos(angle)),
        }], columns=self.FEATURES)

    def predict(self, weather: dict, model_name="Linear Regression",
                target_day=None) -> float:
        if model_name == "Naive mean baseline":
            if not hasattr(self, "training_mean"):
                raise PredictionDataError("Train the predictor before making predictions.")
            return self.training_mean
        if model_name not in self.models:
            raise PredictionDataError("Train the predictor before making predictions.")
        if target_day is None:
            target_day = self.tomorrow()
        target_day = pd.Timestamp(target_day).date()
        row = self._features_for_date(weather, target_day)
        return max(0.0, float(self.models[model_name].predict(row)[0]))

    def predict_from_forecast(self, forecast_hourly: pd.DataFrame,
                              target_day=None) -> tuple[str, float]:
        if forecast_hourly.empty:
            raise PredictionDataError("No forecast rows are available.")
        if not self.results:
            raise PredictionDataError("Train the predictor before making predictions.")
        if target_day is None:
            target_day = self.tomorrow()
        target_day = pd.Timestamp(target_day).date()
        missing = {"cloud_cover", "temperature_2m"}.difference(forecast_hourly.columns)
        if missing:
            raise PredictionDataError(
                "Forecast is missing: " + ", ".join(sorted(missing))
            )
        forecast_daily = forecast_hourly.resample("D").agg(
            cloud_cover=("cloud_cover", "mean"),
            temperature_2m=("temperature_2m", "mean"),
            cloud_count=("cloud_cover", "count"),
            temperature_count=("temperature_2m", "count"),
        ).dropna()
        target_timestamp = pd.Timestamp(target_day)
        if (target_timestamp not in forecast_daily.index or
                int(forecast_daily.loc[target_timestamp, "cloud_count"]) < 24 or
                int(forecast_daily.loc[target_timestamp, "temperature_count"]) < 24):
            raise PredictionDataError(
                f"The forecast does not contain a complete usable day for {target_day}."
            )
        weather = forecast_daily.loc[target_timestamp].to_dict()
        winner = min(
            self.results,
            key=lambda name: self.results[name]["RMSE"],
        )
        return winner, self.predict(weather, winner, target_day)
