"""Shared settings: folder paths, supported cities and API variables."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
APPLIANCE_CSV = DATA_RAW / "appliances.csv"
FIGURES_DIR = BASE_DIR / "outputs" / "figures"
RESULTS_DIR = BASE_DIR / "outputs" / "results"

# City -> (latitude, longitude). A tuple fits here: the pair never changes.
CITIES = {
    "Karachi": (24.86, 67.01),
    "Lahore": (31.55, 74.34),
    "Islamabad": (33.68, 73.05),
    "Quetta": (30.18, 66.99),
    "Peshawar": (34.01, 71.58),
}

# Hourly weather variables we ask Open-Meteo for.
HOURLY_VARIABLES = ["shortwave_radiation", "cloud_cover", "temperature_2m"]

# One full year of history used for the monthly estimates and the models.
DEFAULT_START = "2025-01-01"
DEFAULT_END = "2025-12-31"
