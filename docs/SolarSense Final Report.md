# SolarSense Final Report

**Course:** AL-2001 Programming for Artificial Intelligence (Laboratory)

**Project:** SolarSense: Home Solar System Planner

## 1. Summary

SolarSense is a console application for planning the approximate size of a
household photovoltaic system. It accepts appliances from a dataset or from
plain English, calculates daily electricity use, processes saved or live
Open-Meteo weather data, estimates monthly solar generation and compares two
machine-learning models.

The implementation is a planning aid only. It does not produce a professional
electrical design.

## 2. Implementation

- `appliances.py` contains abstract appliance behavior, constant-load and
  cycling-load subclasses, CSV loading and household totals.
- `text_match.py` cleans text, extracts quantities and hours, and uses TF-IDF
  cosine similarity to match appliance descriptions.
- `weather.py` fetches Open-Meteo data and falls back to JSON caches.
- `analysis.py` converts hourly JSON dictionaries into validated Pandas
  DataFrames and creates daily/monthly summaries.
- `solar_estimator.py` uses NumPy for irradiation and capacity calculations.
- `solar_predictor.py` compares Linear Regression and Random Forest using
  complete unseen calendar months and reports a naive mean baseline.
- `visualization.py` saves five Matplotlib PNG charts.
- `main.py` integrates all components and writes the recommendation.
- `report.py` writes TXT reports.

## 3. Solar formulas

For an appliance:

`constant kWh/day = watts × hours / 1000`

`cycling kWh/day = watts × hours × duty cycle / 1000`

Hourly energy for a 1 kWp system is estimated from short-wave irradiance:

`kWh/h/kWp = (W/m² / 1000) × performance ratio`

The default performance ratio is 0.82. The estimator uses the least productive
month from the available weather history and applies a 10% capacity margin.
Panel count is calculated using 550 W modules. Inverter recommendation uses
approximately 110% of the resulting DC capacity.

## 4. Machine-learning evaluation

The target is daily total short-wave radiation in kWh/m². Features are daily
mean cloud cover, daily mean temperature and annual sine/cosine seasonality.
Chronological splitting holds out the latest complete calendar months. A
training-mean naive baseline is evaluated on the same test data. Predictions
are clamped to non-negative radiation values.

The models are compared using MAE, RMSE and R². These results predict weather
radiation, not measured panel electricity output. Negative R² values indicate
that a simple model does not improve on the test target mean and must not be
interpreted as useful solar forecasting.

## 5. Validation

The unittest suite covers:

- constant and cycling appliance calculations
- negative and fractional quantities
- TF-IDF parsing examples
- 1.5-ton AC quantity extraction
- missing weather columns
- NumPy solar sizing
- insufficient ML data
- complete-month chronological model training and baseline comparison
- forecast prediction, invalid/partial forecast handling and negative-output clamp
- zero-radiation handling and NumPy daily reshaping
- manual appliance input and generic-AC clarification
- stale recommendation invalidation and report filename uniqueness
- calendar-length monthly demand and sunshine/cloud-cover chart
- cache fallback
- offline forecast failure, empty-radiation weather display, empty-household and
  TXT-report behavior

The final suite was executed with `python -m unittest discover -s tests -v`.
All 36 tests passed.

## 6. End-to-end verification

A complete CLI run was performed with network requests blocked and saved
weather caches enabled. A manually entered 1,100 W load used for 8 hours/day
resulted in 8.80 kWh/day; the application recommended 3.30 kWp, 6 × 550 W
panels and an approximately 3.7 kVA inverter.

The observed held-out-month metrics were:

| Model | MAE (kWh/m²) | RMSE (kWh/m²) | R² |
|---|---:|---:|---:|
| Naive mean baseline | 0.922 | 1.112 | -2.074 |
| Linear Regression | 0.472 | 0.558 | 0.227 |
| Random Forest | 0.316 | 0.445 | 0.508 |

These are actual results from this saved dataset and split, not a general
accuracy guarantee. Random Forest had lower test RMSE than the baseline in this
run. The cached forecast was used to estimate 2026-11-20 radiation at
4.56 kWh/m². Five PNG charts, including daily mean irradiance and sunshine
versus cloud cover, and a TXT report were generated.

## 7. Evidence-based quality score

Scores rate the checked implementation and its evidence, not a guarantee of
field performance.

| Category | Score / 10 | Evidence |
|---|---:|---|
| Requested functionality | 9 | Appliance entry, recommendations, forecast, reports and charts are integrated. |
| Architecture and maintainability | 8 | Existing modules retained; responsibilities remain separated. |
| CLI usability | 8 | Guided menu, generic-AC clarification and manual appliance entry are available. |
| Input validation | 9 | Zero/fractional quantities, invalid specifications and malformed weather data are covered. |
| Error handling | 8 | Empty, zero and unavailable-data paths report errors without crashing. |
| Weather/cache reliability | 8 | Cache payloads and freshness are checked; offline fallback is exercised. |
| Physical and numerical correctness | 8 | Units are documented and radiation inputs/predictions are guarded. |
| NumPy/Pandas application | 9 | Complete-day validation, reshape, masking, broadcasting and axis reductions are used. |
| ML evaluation methodology | 8 | Seasonal features, chronological complete-month holdout and a naive baseline are used. |
| ML claims and metrics | 9 | Actual MAE/RMSE/R² are reported; improvement is conditional on measured RMSE. |
| Automated testing | 9 | All 36 tests pass, including the requested edge cases. |
| Visualizations | 8 | Five charts include daily irradiance and cloud-cover comparison. |
| Reports and recommendation freshness | 8 | Reports include recommendations and forecast; input changes invalidate stale results. |
| Documentation and reproducibility | 7 | Setup, assumptions, tests and limitations are documented; Pylance is currently opened at the parent folder, outside the project config scope. |
| Data provenance and academic rigor | 5 | Weather source is named, but appliance wattage citations are still missing and the modeled historical period is limited. |

**Overall: 8.1/10 — good and substantially functional, with evidence-based
limitations.** The most important remaining academic improvement is citing
reliable sources for appliance wattages and duty cycles; extend and validate
the weather dataset before making broad forecasting claims.

## 8. Limitations

- Weather history is for 2025 and may not represent future weather.
- Roof angle, orientation, shading, local temperature losses and degradation
  are not modeled.
- Appliance wattages are typical values rather than measured data.
- Battery storage, inverter topology, wiring and net metering are excluded.
- Weather predictions are not a substitute for a professional system design.
