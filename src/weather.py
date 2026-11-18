"""Fetch hourly weather and sunshine from Open-Meteo, with an offline cache.

Weather data by Open-Meteo.com (https://open-meteo.com).
"""
import json

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

    def _cache_path(self, label):
        """Path of the cache file for this city and this label."""
        return self.cache_dir / f"{self.city.lower()}_{label}.json"

    def _read_cache(self, path):
        """Return the cached data, or None if there is no usable file."""
        try:
            with open(path, encoding="utf-8") as file:
                return json.load(file)
        except FileNotFoundError:
            return None
        except json.JSONDecodeError:
            print(f"Warning: the saved file {path.name} is damaged and was ignored.")
            return None

    def _write_cache(self, path, data):
        """Save data as JSON, creating the folder if needed."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file)

    def _get_hourly(self, url, params, label):
        """Ask the API; on any failure fall back to the saved copy."""
        path = self._cache_path(label)
        reason = None
        try:
            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code == 200:
                hourly = response.json()["hourly"]
                self._write_cache(path, hourly)
                return hourly
            reason = f"the API returned status {response.status_code}"
        except requests.exceptions.ConnectionError:
            reason = "there is no internet connection"
        except requests.exceptions.Timeout:
            reason = "the request timed out"
        except requests.exceptions.RequestException as error:
            reason = f"the request failed ({error})"
        except (ValueError, KeyError):
            reason = "the API reply was not in the expected format"

        cached = self._read_cache(path)
        if cached is not None:
            print(f"Note: {reason}. Using saved data from {path.name}.")
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
