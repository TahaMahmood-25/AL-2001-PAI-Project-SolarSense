# SolarSense: Home Solar System Planner

AL-2001 Programming for Artificial Intelligence (Lab) · Fall 2026 · FAST-NUCES Karachi

SolarSense is a Python console app that helps a household work out what size of solar system it needs. The user adds their appliances (from a list, by typing a sentence such as "2 ACs 8 hours, 4 fans 12 hours, fridge", or with a custom wattage), and the program calculates the home's daily electricity use. It combines this with real hourly sunshine data for the chosen city from the free Open-Meteo weather API (saved locally, so the program also works offline) to recommend a system size, a number of panels and an inverter size, and to show the expected solar generation for each month. Two machine learning models, Linear Regression and Random Forest, are compared with a naive baseline at predicting daily solar radiation on months they were not trained on, and the better one gives an estimate for the coming day. All results are estimates for planning, not engineering advice.

## Group members

| Name | Roll number | What they built |
|---|---|---|
| Taha Mahmood (leader) | 25K-0124 | Project structure, appliance classes and appliance table, weather client with offline cache, text matching, console menu and input validation, TXT report |
| Syed Shahamat Shakeel | 25K-0143 | Pandas analysis, NumPy solar estimator, the two-model comparison, charts, automated tests [confirm and correct this line] |

## Setup

The project was developed and tested on Python 3.14 and the library versions in `requirements.txt`.

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
   The repository already contains saved weather data for all five cities, so the program also works without internet.

## How to run

From the repository folder:

```
python src/main.py
```

To run the automated tests:

```
python -m unittest discover -s tests
```

## How to use it

The menu has these options:

1. Choose city
2. Add an appliance from the list
3. Type appliances in plain words
4. Show my appliances and daily use
5. Check weather data
6. Recommend a solar system
7. Save a report (TXT)
8. Add an appliance with custom wattage
0. Exit

A quick example: choose **3**, type `2 ACs 8 hours, 4 fans 12 hours, fridge`, choose **4** to see the daily use, then choose **6** for the recommendation, the monthly generation table, the model comparison and the charts.

## Features

- Five cities: Karachi, Lahore, Islamabad, Quetta and Peshawar
- Appliances from a table of common household appliances, from plain-text sentences (cleaned and matched with TF-IDF), or with a custom wattage
- Daily electricity use in kWh, using the right formula for each appliance type
- Real hourly sunshine data from Open-Meteo, saved as JSON and used when the internet or the API fails
- Recommended system size, number of panels and inverter size, with expected monthly generation compared with the home's demand
- Linear Regression and Random Forest compared with a naive baseline on held-out months, using MAE, RMSE and R²
- Five charts saved to `outputs/figures/`
- A TXT report saved to `outputs/results/`
- Automated tests in `tests/`

## Project layout

```
README.md          this file
requirements.txt   libraries (pinned)
docs/              proposal and report (PDF and Markdown)
src/
  main.py            console menu
  appliances.py      Appliance classes, appliance table, Household
  text_match.py      text cleaning and TF-IDF matching
  weather.py         Open-Meteo client with offline cache
  analysis.py        Pandas cleaning and summaries
  solar_estimator.py NumPy solar sizing
  solar_predictor.py model comparison
  visualization.py   Matplotlib charts
  report.py          TXT report
  config.py          paths, cities and settings
  fetch_data.py      downloads and saves the weather data
tests/             automated tests
data/raw/          appliance table and saved weather data
data/processed/    cleaned data
outputs/           figures/ and results/
```

## Known limitations

- All numbers are estimates. Appliance wattages are typical values, not measured ones, and real appliances vary.
- The weather history covers 2025 only, so it may not represent other years.
- Roof angle, orientation, shading, temperature losses, panel ageing, batteries, inverter design, wiring, prices and net-metering rules are not modelled.
- The models predict daily solar radiation from weather, not the measured output of a real panel, and the Random Forest fit on the held-out months is only moderate.
- The first weather download needs internet. After that the saved copies are used.

## Data source

- Weather and sunshine: [Open-Meteo](https://open-meteo.com) Historical Weather API and Forecast API. Free for non-commercial use, data under CC BY 4.0. Weather data by Open-Meteo.com.
- Appliance table (`data/raw/appliances.csv`): compiled by the group from typical values, which were first suggested with AI assistance and then checked against [add the sources you checked, with links].

## AI assistance

An AI assistant (Claude, by Anthropic) was used to brainstorm the project, to help draft the proposal and report, and to help write and explain parts of the code. [Shahamat: add which AI tools you used and for what.] Each member can explain the modules listed under their name.
