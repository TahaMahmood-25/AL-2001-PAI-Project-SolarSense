# SolarSense: Home Solar System Planner

AL-2001 Programming for Artificial Intelligence (Lab) · Fall 2026 · FAST-NUCES Karachi

SolarSense is a Python console app that helps a household work out what size of solar system it needs. The user describes their appliances and daily hours, the program calculates the home's daily electricity use, and it combines this with real sunshine data for the user's city (from the free Open-Meteo weather API) to recommend a system size and show expected monthly solar output. Two machine learning models are compared at predicting daily sunshine from weather. All results are estimates for planning, not engineering advice.

> **TODO before submission:** delete every line that starts with "TODO" and update the feature list so it only describes what really works.

## Group members

| Name | Roll number | What they built |
|---|---|---|
| Taha Mahmood (leader) | 25K-0124 | Project structure, `Appliance` / `Household` classes, appliance table, `WeatherClient` with caching and offline fallback, console menu and input validation, TXT report |
| Syed Shahamat Shakeel | 25K-0143 | TODO: confirm and write one line (planned: text cleaning and TF-IDF matching, NumPy solar estimator, Pandas analysis, charts, the two models) |

## Setup

You need Python 3.9 or newer and Git.

1. Download the project:
   ```
   git clone https://github.com/TahaMahmood-25/AL-2001-PAI-Project-SolarSense
   cd AL-2001-PAI-Project-SolarSense
   ```
2. (Recommended) create and activate a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate
   ```
   On macOS or Linux use `source venv/bin/activate` instead.
3. Install the libraries:
   ```
   pip install -r requirements.txt
   ```
4. (Optional, needs internet) refresh the saved weather data:
   ```
   python src/fetch_data.py
   ```
   The repository already contains saved weather data, so the program also works without internet.

## How to run

From the repository folder:

```
python src/main.py
```

## Features

- Choose a city (Karachi, Lahore, Islamabad, Quetta or Peshawar)
- Add appliances from a table of common household appliances, with quantity and daily hours
- Daily electricity use in kWh, using the right formula for each appliance type
- Real hourly sunshine data from Open-Meteo, saved locally and used when offline
- Save a TXT report of the results to `outputs/results/`
- TODO: type appliances in plain words (text cleaning and TF-IDF matching)
- TODO: recommended system size and expected monthly output
- TODO: two compared models and charts in `outputs/figures/`

## Known limitations

- All numbers are estimates. Appliance wattages are typical values and real appliances vary.
- Sunshine data is one year (2025) of history for five cities. It is not a forecast of future years.
- The program does not know about shading, roof angle, batteries, inverters, prices or net-metering rules.
- Weather data needs internet the first time. After that the saved copy is used.
- TODO: add anything else you discover while testing.

## Data source

- Weather and sunshine: [Open-Meteo](https://open-meteo.com) Historical Weather API and Forecast API. Free for non-commercial use, data under CC BY 4.0. Weather data by Open-Meteo.com.
- Appliance table (`data/raw/appliances.csv`): compiled by the group from typical published values. TODO: name the sources you checked the wattages against.

## Project layout

```
README.md          this file
requirements.txt   libraries
docs/              proposal and report (PDF and Markdown)
src/               source code (main.py, appliances.py, weather.py, report.py, config.py, fetch_data.py)
data/raw/          appliance table and saved weather data
data/processed/    cleaned data
outputs/           figures/ and results/
```

## AI assistance

An AI assistant (Claude) was used to brainstorm the project, to help draft the proposal, and to help write and explain parts of the code. TODO: list exactly which parts, and make sure each member can explain their own code.
