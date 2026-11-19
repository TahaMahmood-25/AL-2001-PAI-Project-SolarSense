"""Download and save a year of history and a forecast for every city.

Run once with internet, from the repository root:  python src/fetch_data.py
After this the program works offline.
"""
from config import CITIES
from weather import WeatherClient, WeatherDataError


def main():
    """Fetch and cache data for every supported city."""
    for city in CITIES:
        client = WeatherClient(city)
        try:
            history = client.fetch_history()
            client.fetch_forecast()
            print(f"{city}: saved {len(history['time'])} hourly rows.")
        except WeatherDataError as error:
            print(f"{city}: FAILED - {error}")


if __name__ == "__main__":
    main()
