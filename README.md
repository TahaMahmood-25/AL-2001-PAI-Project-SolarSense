# SolarSense: Home Solar System Planner

AL-2001 Programming for Artificial Intelligence (Lab), Fall 2026

SolarSense is a home solar-planning application with a React web interface and
a Python API. It estimates a household's daily electricity consumption and
recommends a suitable small photovoltaic system. The application uses a local
appliance dataset, five-city Open-Meteo weather caches, NumPy solar calculations,
Pandas analysis, TF-IDF appliance matching and two chronological machine-learning
comparisons.

All outputs are planning estimates, not engineering guarantees or professional
solar-system advice.

## Features

- Choose Karachi, Lahore, Islamabad, Quetta or Peshawar.
- Add appliances individually or describe them in plain text.
- Enter a custom appliance with user-provided wattage.
- Parse quantities, hours, singular/plural names and common AC/spelling variants.
- Calculate constant-load and cycling-load energy use.
- Read saved hourly weather or refresh from the Open-Meteo APIs.
- Estimate photovoltaic capacity, panel count and inverter size.
- Compare estimated monthly generation with household demand.
- Train Linear Regression and Random Forest models on chronological data.
- Evaluate against a naive baseline with MAE, RMSE and R² on complete unseen months.
- Estimate tomorrow's daily radiation from the weather forecast when available.
- Generate and save five informative charts, including daily irradiance and
  sunshine-versus-cloud-cover visualizations.
- Save a detailed TXT report.
- Run the same planning workflow from a responsive, six-screen editorial web
  interface backed by the Python application.
- Export a designed, two-page PDF field report.

## Requirements

- Python 3.9 or newer
- Node.js 18 or newer (web interface)
- Internet access is optional when valid saved weather files exist
- Windows commands below use the repository folder

## Installation

```powershell
cd "G:\Ai\Programing For Ai Lab\AL-2001-PAI-Project-SolarSense"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

For a system Python without a virtual environment:

```powershell
python -m pip install -r requirements.txt
```

## Run

Start the API and web application in separate PowerShell terminals from the
repository root:

```powershell
# Terminal 1: Python API
uvicorn api:app --app-dir src --reload
```

```powershell
# Terminal 2: React + Vite
cd frontend
npm install
npm run dev
```

Open the local address printed by Vite (normally `http://127.0.0.1:5173`).
The frontend proxies API requests to `http://127.0.0.1:8000`. The API serves
the existing appliance parser, weather cache, solar estimator and predictor.
The [frontend design system](frontend/DESIGN_SYSTEM.md) documents the visual
tokens, layouts and interaction conventions.
For a single-process production preview, build the frontend and then start the
API; FastAPI serves the generated `frontend/dist/` application:

```powershell
cd frontend
npm run build
cd ..
uvicorn api:app --app-dir src --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` for that production build.
Run the console interface separately, as before:

```powershell
python src/main.py
```

After adding appliances, choose menu option 6 for the complete recommendation.
Generic "AC" mentions ask for tonnage rather than assuming a model. Menu option
8 allows custom appliance wattage. Choose option 7 afterward to save the result
to `outputs/results/`.

To refresh all saved weather data where internet access is available:

```powershell
python src/fetch_data.py
```

## Tests

```powershell
python -m unittest discover -s tests -v
```

The tests use temporary directories and mocked network failures for cache
fallback. They do not require an internet connection.

## Main calculations

Constant-load appliance:

`kWh/day = watts × hours/day ÷ 1000`

Cycling-load appliance:

`kWh/day = watts × hours/day × duty cycle ÷ 1000`

Hourly system output:

`kWh = (hourly irradiance W/m² ÷ 1000) × system capacity kWp × performance ratio`

Default planning assumptions:

- 550 W nominal panel
- 82% system performance ratio
- 10% capacity margin
- Inverter capacity is approximately 110% of DC capacity
- Sizing is based on the least productive month in the available 2025 data

These assumptions are adjustable in `SolarEstimator`.

## Machine-learning methodology

The models predict daily total short-wave radiation in kWh/m² using daily mean
cloud cover, daily mean temperature and annual sine/cosine seasonality. The
data is sorted chronologically, trained on older months, and evaluated on the
latest complete unseen calendar months. A training-mean baseline is reported
alongside the models. The CLI reports improvement only when test RMSE beats
that baseline. No random shuffle is used.

The target is weather radiation, not measured panel electricity production.
Model results must therefore be interpreted as limited weather-model
evaluation only.

## Project layout

```text
src/
  api.py                   FastAPI integration for the web application
  main.py                  CLI integration
  appliances.py            OOP appliance classes and household totals
  text_match.py            text cleaning, quantities and TF-IDF matching
  weather.py               Open-Meteo access and cache fallback
  analysis.py              Pandas JSON/DataFrame analysis
  solar_estimator.py       NumPy photovoltaic estimates
  solar_predictor.py       chronological ML training and evaluation
  visualization.py         Matplotlib chart generation
  report.py                TXT report generation
  fetch_data.py            download/cache utility
frontend/
  src/App.jsx              React planning and analysis screens
  src/charts.jsx           Responsive, interactive SVG visualizations
  src/styles.css           SolarSense editorial design system
  vite.config.js           Development server and API proxy
data/raw/                  appliance CSV and saved weather JSON
docs/                      proposal and final report
outputs/figures/           generated PNG charts
outputs/results/           generated TXT reports
tests/                     unittest suite
```

## Data sources

- Hourly weather and short-wave radiation: Open-Meteo APIs.
- Five-city historical data and forecasts are cached as JSON in `data/raw/`.
- `data/raw/appliances.csv` contains typical planning wattages. It does not
  claim that every appliance's measured wattage or duty cycle matches these values.

The existing project proposal should be checked before submission for course
formatting requirements. No wattage publication sources are currently cited;
add them before presenting the table as sourced technical data.

## Known limitations

- 2025 is historical weather data, not a guarantee of future production.
- No roof tilt, azimuth, shading, panel temperature coefficient or degradation
  is included.
- The battery, inverter topology, wiring, protection and net-metering are not
  designed.
- Typical appliance wattages and duty cycles may differ from real usage.
- Forecast cache validity is three hours; historical-cache validity is seven
  days for this implementation.
- Negative R² or weak model scores are reported honestly and do not establish
  accurate solar forecasting.
