"""Matplotlib charts for SolarSense estimates."""
from __future__ import annotations

from pathlib import Path
import calendar

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import FIGURES_DIR


def monthly_demand_kwh(daily_kwh: float, month: str) -> float:
    """Return household demand for a YYYY-MM month using its actual length."""
    year, month_number = (int(value) for value in month.split("-"))
    return daily_kwh * calendar.monthrange(year, month_number)[1]


def _save(fig, output_dir: Path, filename: str) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_daily_radiation(hourly: pd.DataFrame, output_dir=FIGURES_DIR) -> Path:
    if hourly.empty or "shortwave_radiation" not in hourly:
        raise ValueError("Solar-radiation data is unavailable.")
    daily = hourly["shortwave_radiation"].resample("D").mean().dropna()
    if daily.empty:
        raise ValueError("No valid solar-radiation values are available.")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(daily.index, daily, color="#f4a261", linewidth=1)
    ax.set_title("Daily Mean Short-Wave Solar Irradiance")
    ax.set_xlabel("Date")
    ax.set_ylabel("Mean irradiance (W/m²)")
    ax.grid(True, alpha=0.3)
    return _save(fig, output_dir, "daily_mean_solar_irradiance.png")


def plot_sunshine_vs_cloud_cover(hourly: pd.DataFrame,
                                 output_dir=FIGURES_DIR) -> Path:
    required = {"shortwave_radiation", "cloud_cover"}
    if hourly.empty or not required.issubset(hourly.columns):
        raise ValueError("Sunshine and cloud-cover data are unavailable.")
    daily = hourly.resample("D").agg({
        "shortwave_radiation": "mean",
        "cloud_cover": "mean",
    }).dropna()
    if daily.empty:
        raise ValueError("No complete sunshine/cloud-cover data is available.")
    fig, axis_radiation = plt.subplots(figsize=(10, 4.5))
    axis_cloud = axis_radiation.twinx()
    axis_radiation.plot(
        daily.index, daily["shortwave_radiation"],
        color="#f4a261", label="Mean solar irradiance",
    )
    axis_cloud.plot(
        daily.index, daily["cloud_cover"],
        color="#457b9d", alpha=0.8, label="Mean cloud cover",
    )
    axis_radiation.set_title("Daily Sunshine and Cloud Cover")
    axis_radiation.set_xlabel("Date")
    axis_radiation.set_ylabel("Mean solar irradiance (W/m²)", color="#f4a261")
    axis_cloud.set_ylabel("Mean cloud cover (%)", color="#457b9d")
    lines = axis_radiation.get_lines() + axis_cloud.get_lines()
    axis_radiation.legend(lines, [line.get_label() for line in lines], loc="upper right")
    axis_radiation.grid(True, alpha=0.3)
    return _save(fig, output_dir, "sunshine_vs_cloud_cover.png")


def plot_monthly_generation(monthly_output: dict, daily_kwh: float,
                            output_dir=FIGURES_DIR) -> Path:
    if not monthly_output:
        raise ValueError("Monthly generation data is unavailable.")
    months = list(monthly_output)
    values = [monthly_output[m] for m in months]
    demand = [monthly_demand_kwh(daily_kwh, month) for month in months]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(months, values, label="Estimated solar generation", color="#2a9d8f")
    ax.plot(months, demand, color="#e76f51", marker="o", label="Estimated monthly demand")
    ax.set_title("Estimated Solar Generation vs Household Demand")
    ax.set_xlabel("Month")
    ax.set_ylabel("Energy (kWh/month)")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, output_dir, "monthly_generation_vs_demand.png")


def plot_actual_vs_predicted(dates, actual, predictions, title,
                             output_dir=FIGURES_DIR) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, actual, label="Actual", marker="o", markersize=2)
    ax.plot(dates, predictions, label="Predicted", marker="o", markersize=2)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Daily solar radiation (kWh/m²)")
    ax.tick_params(axis="x", rotation=45)
    ax.legend()
    ax.grid(True, alpha=0.3)
    return _save(fig, output_dir, "actual_vs_predicted_solar.png")


def plot_consumption_breakdown(household, output_dir=FIGURES_DIR) -> Path:
    items = {}
    for appliance, quantity in household._items:
        items[appliance.name] = items.get(appliance.name, 0) + quantity * appliance.daily_kwh()
    if not items:
        raise ValueError("No appliances are available for a breakdown chart.")
    fig, ax = plt.subplots(figsize=(8, 5))
    names = list(items)
    ax.bar(names, list(items.values()), color="#264653")
    ax.set_title("Estimated Daily Consumption by Appliance")
    ax.set_xlabel("Appliance")
    ax.set_ylabel("Energy use (kWh/day)")
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    ax.grid(axis="y", alpha=0.3)
    return _save(fig, output_dir, "consumption_breakdown.png")
