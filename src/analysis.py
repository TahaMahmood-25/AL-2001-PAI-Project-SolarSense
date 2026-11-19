"""Pandas-based loading, cleaning and aggregation of SolarSense weather data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

import pandas as pd


class AnalysisDataError(ValueError):
    """Raised when weather data cannot be converted into a valid DataFrame."""


WEATHER_COLUMNS = ("shortwave_radiation", "cloud_cover", "temperature_2m")
SOLAR_COLUMNS = ("shortwave_radiation",)


def hourly_dataframe(
    hourly: Mapping[str, list],
    required_columns=SOLAR_COLUMNS,
) -> pd.DataFrame:
    """Convert hourly JSON; solar radiation is required unless overridden."""
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise AnalysisDataError("Weather data must contain a 'time' list.")

    try:
        frame = pd.DataFrame(hourly)
    except ValueError as error:
        raise AnalysisDataError("Weather columns have inconsistent lengths.") from error
    for column in set(required_columns) | {"time"}:
        if column not in frame.columns:
            raise AnalysisDataError(f"Weather data is missing '{column}'.")

    frame["datetime"] = pd.to_datetime(frame["time"], errors="coerce")
    frame = frame.loc[frame["datetime"].notna()].copy()
    frame = frame.sort_values("datetime").drop_duplicates("datetime")
    frame = frame.set_index("datetime")

    for column in WEATHER_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")

    if "shortwave_radiation" in frame.columns:
        radiation = frame["shortwave_radiation"]
        frame.loc[(radiation < 0) | (radiation > 1500), "shortwave_radiation"] = float("nan")
        frame["shortwave_radiation"] = frame["shortwave_radiation"].interpolate(
            limit_direction="both"
        )

    if frame.empty:
        raise AnalysisDataError("Weather data contains no valid timestamps.")
    if frame["shortwave_radiation"].isna().all():
        raise AnalysisDataError("All solar-radiation values are missing.")
    frame["shortwave_radiation"] = frame["shortwave_radiation"].fillna(0)
    return frame


def load_hourly_json(path: str | Path) -> pd.DataFrame:
    """Load and validate an hourly Open-Meteo JSON cache file."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as file:
            hourly = json.load(file)
    except FileNotFoundError as error:
        raise AnalysisDataError(f"Weather file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise AnalysisDataError(f"Weather file is damaged: {path}") from error
    return hourly_dataframe(hourly)


def daily_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate hourly weather into daily totals and means."""
    if frame.empty:
        raise AnalysisDataError("Cannot aggregate an empty weather DataFrame.")
    missing = set(WEATHER_COLUMNS).difference(frame.columns)
    if missing:
        raise AnalysisDataError(
            "Daily analysis is missing: " + ", ".join(sorted(missing))
        )
    return frame.resample("D").agg({
        "shortwave_radiation": "sum",
        "cloud_cover": "mean",
        "temperature_2m": "mean",
    }).rename(columns={"shortwave_radiation": "radiation_wh_m2"})


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weather data by month."""
    daily = daily_summary(frame)
    daily["irradiation_kwh_m2"] = daily["radiation_wh_m2"] / 1000
    daily["month"] = daily.index.to_period("M").astype(str)
    return daily.groupby("month", sort=True).agg({
        "irradiation_kwh_m2": ["sum", "mean", "count"],
        "cloud_cover": "mean",
        "temperature_2m": "mean",
    })
