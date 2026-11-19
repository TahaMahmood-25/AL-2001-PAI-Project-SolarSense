"""Fetch hourly weather and sunshine from Open-Meteo, with an offline cache.

Weather data by Open-Meteo.com (https://open-meteo.com).
"""
import json
import time
from datetime import datetime
from math import isfinite

import requests

from config import (CITIES, DATA_RAW, DEFAULT_END, DEFAULT_START,
                    HOURLY_VARIABLES)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherDataError(Exception):
    """Raised when weather data is not available live or from the saved cache."""


class WeatherClient:
    """Gets weather for one city. Every good reply is saved as a JSON file, and
    the saved file is used when the internet or the API fails."""

    def __init__(self, city="Karachi", cache_dir=DATA_RAW, timeout=20):
        if city not in CITIES:
            raise ValueError(f"Unknown city: {city}")
        self.city = city
        self.latitude, self.longitude = CITIES[city]  # unpack the tuple
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.last_source = None

    def _cache_path(self, label):
        """Path of the cache file for this city and this label."""
        return self.cache_dir / f"{self.city.lower()}_{label}.json"

    def _read_cache(self, path):
        """Return the cached data, or None if there is no usable file."""
        try:
            with open(path, encoding="utf-8") as file:
                return self._validate_hourly(json.load(file))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            print(f"Warning: saved file {path.name} is invalid and was ignored ({error}).")
            return None

    @staticmethod
    def _validate_hourly(hourly):
        if not isinstance(hourly, dict):
            raise ValueError("hourly weather data must be an object")
        if "time" not in hourly or not isinstance(hourly["time"], list):
            raise ValueError("weather data must contain a time list")
        times = hourly["time"]
        if not times:
            raise ValueError("weather data contains no timestamps")
        for variable in HOURLY_VARIABLES:
            values = hourly.get(variable)
            if not isinstance(values, list) or len(values) != len(times):
                raise ValueError(f"weather variable '{variable}' is missing or has the wrong length")
        for value in times:
            if not isinstance(value, str):
                raise ValueError("weather timestamps must be strings")
            try:
                datetime.fromisoformat(value)
            except ValueError as error:
                raise ValueError(f"invalid weather timestamp: {value!r}") from error
        for variable in HOURLY_VARIABLES:
            for value in hourly[variable]:
                if value is None:
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        f"weather variable '{variable}' contains a non-numeric value"
                    ) from error
                if not isfinite(numeric):
                    raise ValueError(
                        f"weather variable '{variable}' contains a non-finite value"
                    )
                if variable == "shortwave_radiation" and numeric < 0:
                    raise ValueError("short-wave radiation cannot be negative")
                if variable == "cloud_cover" and not 0 <= numeric <= 100:
                    raise ValueError("cloud cover must be between 0 and 100 percent")
        return hourly

    def _write_cache(self, path, data):
        """Save data as JSON, creating the folder if needed."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file)

    def _cache_is_fresh(self, path, max_age_seconds):
        if not path.exists():
            return False
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return False
        return 0 <= age <= max_age_seconds

    @staticmethod
    def _cache_age(path):
        age_seconds = max(0, time.time() - path.stat().st_mtime)
        if age_seconds < 60:
            return f"{int(age_seconds)} seconds"
        if age_seconds < 3600:
            return f"{int(age_seconds // 60)} minutes"
        if age_seconds < 86400:
            return f"{age_seconds / 3600:.1f} hours"
        return f"{age_seconds / 86400:.1f} days"

    def _get_hourly(self, url, params, label):
        """Ask the API; on any failure fall back to the saved copy."""
        path = self._cache_path(label)
        reason = None

        max_age = 7 * 24 * 60 * 60 if label.startswith("history_") else 3 * 60 * 60
        if self._cache_is_fresh(path, max_age):
            cached = self._read_cache(path)
            if cached is not None:
                self.last_source = "fresh cache"
                print(f"Using cached data from {path.name} "
                      f"(updated {self._cache_age(path)} ago).")
                return cached

        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                payload = response.json()
                hourly = self._validate_hourly(payload["hourly"])
                self._write_cache(path, hourly)
                self.last_source = "live API"
                return hourly
            reason = f"the API returned status {response.status_code}"
        except requests.exceptions.ConnectionError:
            reason = "there is no internet connection"
        except requests.exceptions.Timeout:
            reason = "the request timed out"
        except requests.exceptions.RequestException as error:
            reason = f"the request failed ({error})"
        except (TypeError, ValueError, KeyError):
            reason = "the API reply was not in the expected format"

        cached = self._read_cache(path)
        if cached is not None:
            self.last_source = "cache fallback"
            print(f"Note: {reason}. Using saved data from {path.name} "
                  f"(updated {self._cache_age(path)} ago).")
            return cached
        raise WeatherDataError(
            f"Could not get weather data because {reason}, "
            f"and there is no saved copy ({path.name}).")

    def fetch_history(self, start=DEFAULT_START, end=DEFAULT_END):
        """Return past hourly data as a dict of lists (time + each variable)."""
        params = {"latitude": self.latitude, "longitude": self.longitude,
                  "start_date": start, "end_date": end,
                  "hourly": ",".join(HOURLY_VARIABLES),
                  "timezone": "Asia/Karachi"}
        return self._get_hourly(ARCHIVE_URL, params, f"history_{start}_{end}")

    def fetch_forecast(self, days=3):
        """Return the hourly forecast for the next few days."""
        params = {"latitude": self.latitude, "longitude": self.longitude,
                  "hourly": ",".join(HOURLY_VARIABLES),
                  "forecast_days": days, "timezone": "Asia/Karachi"}
        return self._get_hourly(FORECAST_URL, params, "forecast")
