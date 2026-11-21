"""Physical estimates for a small home photovoltaic system."""
from __future__ import annotations

from datetime import datetime
import math
from typing import Mapping

import numpy as np


class SolarDataError(ValueError):
    """Raised when solar or household inputs are invalid or incomplete."""


class SolarEstimator:
    """Estimate DC-to-AC PV output from hourly short-wave irradiance."""

    def __init__(
        self,
        hourly: Mapping[str, list],
        panel_wattage=550,
        performance_ratio=0.82,
        capacity_margin=1.10,
    ):
        try:
            panel_wattage = float(panel_wattage)
            performance_ratio = float(performance_ratio)
            capacity_margin = float(capacity_margin)
        except (TypeError, ValueError) as error:
            raise SolarDataError("System assumptions must be numeric.") from error
        if not math.isfinite(panel_wattage) or panel_wattage <= 0:
            raise SolarDataError("Panel wattage must be greater than zero.")
        if not math.isfinite(performance_ratio) or not 0 < performance_ratio <= 1:
            raise SolarDataError("Performance ratio must be between 0 and 1.")
        if not math.isfinite(capacity_margin) or capacity_margin < 1:
            raise SolarDataError("Capacity margin must be at least 1.")

        if not isinstance(hourly, dict):
            raise SolarDataError("Hourly weather data must be a dictionary.")
        if "time" not in hourly or "shortwave_radiation" not in hourly:
            raise SolarDataError("Weather data needs 'time' and 'shortwave_radiation'.")

        times = np.asarray(hourly["time"], dtype=str)
        try:
            radiation = np.asarray(hourly["shortwave_radiation"], dtype=float)
        except (TypeError, ValueError) as error:
            raise SolarDataError("Solar-radiation values must be numeric or missing.") from error
        if radiation.size != times.size or radiation.size == 0:
            raise SolarDataError("Solar-radiation values do not match timestamp values.")

        try:
            timestamps = np.asarray(
                [np.datetime64(datetime.fromisoformat(value)) for value in times]
            )
        except (TypeError, ValueError) as error:
            raise SolarDataError("Weather timestamps must be valid ISO date-times.") from error
        if radiation.size % 24:
            raise SolarDataError("Weather data must contain complete 24-hour days.")
        if np.any(np.diff(timestamps) != np.timedelta64(1, "h")):
            raise SolarDataError("Weather timestamps must be continuous hourly data.")
        hours_of_day = timestamps.astype("datetime64[h]").astype(np.int64) % 24
        if not np.array_equal(hours_of_day, np.tile(np.arange(24), radiation.size // 24)):
            raise SolarDataError("Weather data must start at midnight and contain whole days.")

        valid = np.isfinite(radiation) & (radiation >= 0) & (radiation <= 1500)
        if not valid.any():
            raise SolarDataError("No usable solar-radiation values were found.")
        cleaned = np.where(valid, radiation, np.nan)
        indices = np.flatnonzero(~np.isnan(cleaned))
        cleaned = np.interp(np.arange(cleaned.size), indices, cleaned[indices])

        self.time = times
        self.radiation_w_m2 = cleaned
        self.valid_radiation = valid
        self.panel_wattage = float(panel_wattage)
        self.performance_ratio = float(performance_ratio)
        self.capacity_margin = float(capacity_margin)
        self._daily_radiation = cleaned.reshape(-1, 24)
        self._daily_valid_mask = valid.reshape(-1, 24)
        self.missing_radiation_hours = int((~valid).sum())

    def hourly_kwh_per_kw(self) -> np.ndarray:
        """Convert irradiance (W/m2) measured for one hour into kWh/kWp."""
        # One kWp is treated as 1 kW of nameplate DC capacity.
        hourly = self._daily_radiation / 1000
        hourly = hourly * np.broadcast_to(self.performance_ratio, hourly.shape)
        return hourly

    def daily_output_kwh(self, capacity_kwp: float) -> tuple[np.ndarray, np.ndarray]:
        try:
            capacity_kwp = float(capacity_kwp)
        except (TypeError, ValueError) as error:
            raise SolarDataError("System capacity must be numeric.") from error
        if not math.isfinite(capacity_kwp) or capacity_kwp <= 0:
            raise SolarDataError("System capacity must be greater than zero.")
        dates = self.time[::24].astype("U10")
        # A scalar capacity broadcasts over each day's 24 hourly yields.
        daily_hourly = self.hourly_kwh_per_kw() * capacity_kwp
        daily = np.where(
            self._daily_valid_mask, daily_hourly, 0.0
        ).sum(axis=1)
        return dates, daily

    def monthly_output_kwh(self, capacity_kwp: float) -> dict[str, float]:
        dates, daily = self.daily_output_kwh(capacity_kwp)
        months, inverse = np.unique(dates.astype("U7"), return_inverse=True)
        totals = np.bincount(inverse, weights=daily)
        return dict(zip(months.tolist(), totals.tolist()))

    def monthly_generation_per_kwp(self) -> dict[str, float]:
        """Monthly kWh output produced by a 1 kWp system."""
        return self.monthly_output_kwh(1.0)

    def recommend_size(self, daily_consumption_kwh: float) -> dict:
        """Size against the least productive month rather than the annual mean."""
        try:
            daily_consumption_kwh = float(daily_consumption_kwh)
        except (TypeError, ValueError) as error:
            raise SolarDataError("Daily household consumption must be numeric.") from error
        if not math.isfinite(daily_consumption_kwh) or daily_consumption_kwh <= 0:
            raise SolarDataError("Daily household consumption must be greater than zero.")

        generation = self.monthly_generation_per_kwp()
        if not generation:
            raise SolarDataError("No monthly generation data is available.")

        month_days = {}
        for date in np.unique([str(value)[:10] for value in self.time]):
            month = date[:7]
            month_days[month] = month_days.get(month, 0) + 1

        avg_daily_yield = {
            month: kwh / month_days[month]
            for month, kwh in generation.items()
        }
        worst_month = min(avg_daily_yield, key=lambda month: avg_daily_yield[month])
        if avg_daily_yield[worst_month] <= 0:
            raise SolarDataError(
                "Solar radiation is zero; a system size cannot be estimated."
            )
        capacity = (
            daily_consumption_kwh
            / avg_daily_yield[worst_month]
            * self.capacity_margin
        )

        panel_count = int(np.ceil(capacity * 1000 / self.panel_wattage))
        actual_capacity_kwp = panel_count * self.panel_wattage / 1000
        inverter_kw = np.ceil(actual_capacity_kwp * 1.1 * 10) / 10

        return {
            "capacity_kwp": actual_capacity_kwp,
            "raw_capacity_kwp": capacity,
            "panel_count": panel_count,
            "panel_wattage": self.panel_wattage,
            "inverter_kw": float(inverter_kw),
            "worst_month": worst_month,
            "worst_month_avg_daily_kwh": float(avg_daily_yield[worst_month]),
            "performance_ratio": self.performance_ratio,
            "capacity_margin": self.capacity_margin,
            "monthly_output_kwh": self.monthly_output_kwh(actual_capacity_kwp),
            "missing_radiation_hours": self.missing_radiation_hours,
        }
