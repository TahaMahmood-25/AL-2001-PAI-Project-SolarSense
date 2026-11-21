# Project Report

**SolarSense: Home Solar System Planner**

**AL-2001 Programming for Artificial Intelligence (Laboratory) · Fall 2026 · Semester Lab Project (2 marks)**

FAST — National University of Computer and Emerging Sciences, Karachi Campus · Department of Artificial Intelligence & Data Science

| | Student Name | Roll Number | Section |
|---|---|---|---|
| **Leader** | Taha Mahmood | 25K-0124 | BAI-3A |
| Member 2 | Syed Shahamat Shakeel | 25K-0143 | BAI-3A |

| | |
|---|---|
| **Course** | AL-2001 — Programming for Artificial Intelligence (Laboratory) |
| **Programme / Semester** | BS Artificial Intelligence · 3rd Semester |
| **Session** | Fall 2026 |
| **Lab Instructor** | Khadeejah Ashraf |
| **Specialisation Track** | Track A — Text / NLP ☑     Track B — Images / CV ☐ |
| **GitHub Repository** | https://github.com/TahaMahmood-25/AL-2001-PAI-Project-SolarSense |
| **Date of Submission** | [date] |

## Declaration and Contribution Statement

We declare that the work presented in this report is our own, that all external sources — code, datasets, APIs, tutorials and AI assistance — have been acknowledged, and that each of us is able to explain the portion of the work attributed to us below.

| Member | Roll Number | Principal contribution (one line) | Share | Signature |
|---|---|---|---|---|
| Taha Mahmood | 25K-0124 | Project structure, appliance classes and table, weather client with offline cache, text matching, console menu, TXT report | [__%] | |
| Syed Shahamat Shakeel | 25K-0143 | Pandas analysis, NumPy solar estimator, two-model comparison, charts, automated tests, solar recommendation workflow in the menu [confirm] | [__%] | |

**AI assistance acknowledged:** An AI assistant (Claude, by Anthropic) was used to brainstorm the project idea, to draft the proposal, the README and this report, to write and explain parts of the code (the appliance classes, weather client, text matching, report function and menu), and to suggest the first version of the appliance wattage table. [Shahamat: add which AI tools you used and for which files.] We reviewed and tested this work and each of us is able to explain the files listed under our name. [keep this sentence only if it is true]

## 1. Introduction

### 1.1 Overview

SolarSense is a Python console application that helps a household work out what size of solar system it needs. The user chooses a city and adds appliances by picking them from a list, by typing a sentence such as "2 ACs 8 hours, 4 fans 12 hours, fridge", or by entering a custom wattage. The program cleans the text, matches each phrase to an appliance in its wattage table using TF-IDF and cosine similarity, and calculates the home's daily electricity use in kWh. It then loads a year of hourly sunshine data for the chosen city from the free Open-Meteo weather API, or from its saved copy when there is no internet, and uses NumPy to work out how much energy each kilowatt of panels would produce in every month. From this it recommends a system size, a number of panels and an inverter size. Linear Regression and Random Forest are compared with a naive baseline at predicting daily solar radiation on months they were not trained on. The app is aimed at ordinary households in Pakistan who want a clear estimate before talking to an installer. All results are estimates for planning, not engineering advice.

### 1.2 Objectives and Scope

| # | Objective | Achieved? |
|---|---|---|
| 1 | Accept appliances typed in plain words and match them to a wattage table | ☑ |
| 2 | Calculate a household's daily electricity use in kWh | ☑ |
| 3 | Fetch real sunshine data from the Open-Meteo API, save it, and keep working offline | ☑ |
| 4 | Recommend a solar system size with monthly output, and compare two models that predict sunshine on unseen months | ☑ |

**Out of scope and known limitations:** There is no graphical or web interface, no cost or payback analysis, no battery, inverter design, shading or roof-angle modelling, and no net-metering rules. Appliance wattages are typical values, not measured ones. The weather history covers 2025 only, for five cities. The models predict daily solar radiation, not the measured output of a real panel. All results are estimates for planning, not engineering advice.

## 2. Problem Statement and Requirements

In Pakistan, high electricity bills and frequent load-shedding have led many households to consider solar power. The first question they face is simple but hard to answer: how big should the system be? A family with two air conditioners, several fans and a fridge usually decides by asking an installer, copying a neighbour's system, or guessing from last month's bill. None of these methods uses the home's own appliances or the actual sunshine in its city, and sunshine changes a great deal between summer and winter, and between a clear and a cloudy month. A system that is too small leaves the household paying the grid, while one that is too large wastes money. Ordinary homeowners have no easy tool for working this out themselves. A free tool that turns a list of appliances and real local sunshine data into a clear size estimate would help households ask better questions before they spend money.

| Type | Requirement |
|---|---|
| Functional | F1: The system shall accept appliances typed in plain words, with quantity and hours, and tell the user what it understood. |
| Functional | F2: The system shall calculate the daily electricity use and recommend a solar system size using real sunshine data for the chosen city. |
| Non-functional | N1: The system shall keep working without internet by using saved data, and shall say clearly that it is doing so. |
| Non-functional | N2: The system shall not crash on a missing file, a malformed data row or invalid user input, and shall show a clear message instead. |

## 3. System Design and Architecture

### 3.1 Overall Architecture

The program is made of small modules that main.py connects. The user's typed sentence goes to text_match.py, which cleans it and matches each phrase to a row of the appliance table that appliances.py loads from data/raw/appliances.csv. The matched rows become Appliance objects held in a Household, which calculates the daily kWh. In parallel, weather.py (WeatherClient) requests hourly data from Open-Meteo, saves every good reply as a JSON file in data/raw/, and reads that file when the network fails. analysis.py turns the hourly data into a validated Pandas DataFrame. solar_estimator.py uses NumPy to turn the hourly sunshine and the household's daily use into a recommended capacity and monthly generation, while solar_predictor.py trains and compares the models on that DataFrame. visualization.py draws five charts into outputs/figures/, and report.py saves a TXT report into outputs/results/.

```
typed sentence --> text_match.py --> appliances.py --> Household (daily kWh) --+
                        ^                   ^                                   |
                 appliances.csv      Appliance classes                          v
                                                                       solar_estimator.py --> recommendation
Open-Meteo API --> weather.py --> JSON cache (data/raw) --> analysis.py (Pandas) --+--> solar_predictor.py --> model comparison
                                                                                   +--> visualization.py --> outputs/figures
main.py (menu) connects all of these --> report.py --> outputs/results (TXT)
```

*Figure 3.1 System architecture (text version; replace with a drawn diagram if time allows)*

### 3.2 Class Design

![SolarSense class diagram](class_diagram.png)

*Figure 3.2 Class diagram*

| Class | Responsibility | Inherits from | Key methods |
|---|---|---|---|
| Appliance | Abstract base class; holds name, watts and hours with validation | ABC | daily_kwh() (abstract), describe() |
| ConstantLoadAppliance | Items that draw full power while on (fans, lights) | Appliance | daily_kwh() |
| CyclingAppliance | Items whose compressor or heater cycles (fridge, AC); adds a duty cycle | Appliance | daily_kwh() |
| Household | A city plus a list of (appliance, quantity) | none | add_appliance(), total_daily_kwh(), summary() |
| ApplianceMatcher | Matches a cleaned phrase to a table row using exact names and TF-IDF | none | best_match() |
| WeatherClient | Fetches weather from the API, saves and reads the cache | none | fetch_history(), fetch_forecast() |
| SolarEstimator | Turns hourly irradiance into monthly output and a recommended system size | none | hourly_kwh_per_kw(), daily_output_kwh(), monthly_output_kwh(), recommend_size() |
| SolarPredictor | Trains and compares the models on daily radiation | none | train(), predict(), predict_from_forecast() |
| WeatherDataError | No live or saved weather data | Exception | none |
| AnalysisDataError, SolarDataError, PredictionDataError | Invalid weather, solar or time-series data | ValueError | none |

| Principle | Where it is demonstrated in your code |
|---|---|
| Encapsulation | Appliance keeps _watts and _hours_per_day private and exposes them through properties whose setters validate the value (appliances.py) |
| Inheritance | ConstantLoadAppliance and CyclingAppliance extend Appliance (appliances.py) |
| Method overriding | Both subclasses override daily_kwh() with their own formula |
| Polymorphism | Household.total_daily_kwh() calls daily_kwh() on every appliance, whatever its type |
| Abstraction (ABC) | Appliance inherits from ABC and declares daily_kwh() with @abstractmethod, so it cannot be created directly |

### 3.3 Choice of Data Structures

| What it holds | Structure chosen | Why this one |
|---|---|---|
| Appliance table (key to row) | dict | We always look an appliance up by its key, which a dict does directly |
| A household's appliances | list of (appliance, quantity) tuples | Order is kept, items can repeat, and the tuple keeps each pair fixed |
| City coordinates | dict of (latitude, longitude) tuples | The pair never changes, so a tuple fits |
| Stop words and short plurals | set | We only ask whether a word is in it, and duplicates are not needed |
| Number words (one, two...) | dict | Maps a word straight to its number |
| Hourly weather | dict of lists (from JSON), then a Pandas DataFrame and NumPy arrays | JSON gives lists; the DataFrame gives dates and grouping; arrays give fast vectorised maths |
| Monthly generation | dict (month to kWh) | Months are looked up and printed by name |

## 4. Implementation

### 4.1 Module Overview

| File | Responsibility | Author |
|---|---|---|
| src/main.py | Console menu, input validation, and the solar recommendation workflow | Taha (menu); Shahamat (recommendation workflow) [confirm] |
| src/appliances.py | Appliance classes, table loader, Household | Taha (original); stricter input validation added later [confirm who] |
| src/weather.py | WeatherClient, offline cache, custom exception | Taha (original); cache validation and freshness rules added later [confirm who] |
| src/text_match.py | Text cleaning, TF-IDF matching and sentence parsing | Taha (original); extra spelling variants and AC tonnage handling added later [confirm who] |
| src/config.py | Paths, cities and settings shared by all modules | Taha |
| src/fetch_data.py | Downloads and saves weather data for all cities | Taha |
| src/report.py | Saves the TXT report | Taha [confirm any later changes by Shahamat] |
| src/analysis.py | Pandas cleaning, daily and monthly summaries | Shahamat |
| src/solar_estimator.py | NumPy solar sizing and monthly generation | Shahamat |
| src/solar_predictor.py | Chronological model comparison and forecast | Shahamat |
| src/visualization.py | Five Matplotlib charts | Shahamat |
| tests/test_solarsense.py | 36 automated unit tests | Shahamat [confirm] |

### 4.2 Lab Coverage — Where Each Concept Is Used

| Lab | Concept | File and function where it appears |
|---|---|---|
| 01–02 | Core Python, control flow, comprehensions | main.py: read_number() (validated input, loop); text_match.py: clean_text() (list comprehension) |
| 03 | Lists, tuples, dictionaries, sets | appliances.py: load_appliance_table() (dict), Household._items (list of tuples); config.py: CITIES (dict of tuples); text_match.py: STOP_WORDS (set) |
| 04 | Functions, default arguments, lambda / map / filter | appliances.py: create_appliance(row, hours=None); main.py: add_appliance_from_list() (sorted with lambda); text_match.py: split_parts() (filter and map); solar_estimator.py: recommend_size() (min with key) |
| 05 | Classes, inheritance, encapsulation, polymorphism, ABC | appliances.py: Appliance, ConstantLoadAppliance, CyclingAppliance, Household |
| 06 | File I/O (TXT / CSV / JSON), custom exception, try / except | appliances.py: load_appliance_table() (CSV); weather.py: _read_cache(), _write_cache() and _validate_hourly() (JSON); report.py: save_report() (TXT); WeatherDataError, AnalysisDataError, SolarDataError and PredictionDataError |
| 06 | Web API with requests, status check, local cache | weather.py: WeatherClient (status-code check, cache, fallback) |
| 07 | NumPy array, slicing / masking, broadcasting, axis aggregation | solar_estimator.py: SolarEstimator.__init__() (boolean mask, reshape to days × 24), hourly_kwh_per_kw() and daily_output_kwh() (broadcasting, sum along axis 1) |
| 08 | Pandas DataFrame — cleaning, filtering, groupby | analysis.py: hourly_dataframe() (cleaning), daily_summary() (resample), monthly_summary() (groupby) |
| 09 | Matplotlib / Seaborn visualisations | visualization.py: plot_daily_radiation(), plot_sunshine_vs_cloud_cover(), plot_monthly_generation(), plot_actual_vs_predicted(), plot_consumption_breakdown() |
| 10–11 | Train / test split, model fitting, evaluation, model comparison | solar_predictor.py: SolarPredictor.train() (chronological split, fit, MAE / RMSE / R²) |
| 12 | Text features (Track A) | text_match.py: clean_text(), singular(), ApplianceMatcher (TfidfVectorizer and cosine similarity) |
| 14 | Modularity, docstrings, README, ethical discussion | All modules have docstrings; README.md; config.py; Section 7.3 of this report |

### 4.3 Key Implementation Details

**1. Vectorised solar calculation (solar_estimator.py).** The year of hourly irradiance (8,760 values) is cleaned with a boolean mask and reshaped into a 365 × 24 array, one row per day. Converting irradiance to energy uses broadcasting, so a single number (the performance ratio, and later the system size) is applied to every hour at once, and `sum(axis=1)` adds the 24 hours of each day. No Python loop touches the individual hourly values. The recommended size uses the least productive month, so the system still covers the household in winter.

```python
valid = np.isfinite(radiation) & (radiation >= 0) & (radiation <= 1500)   # boolean mask
self._daily_radiation = cleaned.reshape(-1, 24)        # 365 days x 24 hours
self._daily_valid_mask = valid.reshape(-1, 24)

def hourly_kwh_per_kw(self):
    hourly = self._daily_radiation / 1000
    return hourly * np.broadcast_to(self.performance_ratio, hourly.shape)

# in daily_output_kwh():
daily_hourly = self.hourly_kwh_per_kw() * capacity_kwp          # scalar broadcasts
daily = np.where(self._daily_valid_mask, daily_hourly, 0.0).sum(axis=1)
```

**2. Offline-first weather data (weather.py).** The program must keep running when the network or the API fails. A saved copy that is recent (7 days for the history, 3 hours for the forecast) is used straight away. Otherwise the client asks the API and checks the status code, and a good reply is validated (required keys, matching lengths, valid timestamps, value ranges) and saved as JSON. If the request fails for any reason, the client remembers why, falls back to the saved copy whatever its age, and tells the user why. Only if there is no usable saved copy does it raise our own WeatherDataError, which the menu catches. The `last_source` attribute records whether the data came from a fresh cache, the live API or a cache fallback.

```python
max_age = 7 * 24 * 60 * 60 if label.startswith("history_") else 3 * 60 * 60
if self._cache_is_fresh(path, max_age):            # recent saved copy: no request needed
    cached = self._read_cache(path)
    if cached is not None:
        self.last_source = "fresh cache"
        return cached
try:
    response = requests.get(url, params=params, timeout=self.timeout)
    if response.status_code == 200:                 # status check
        hourly = self._validate_hourly(response.json()["hourly"])
        self._write_cache(path, hourly)             # save for offline use
        self.last_source = "live API"
        return hourly
    reason = f"the API returned status {response.status_code}"
except requests.exceptions.ConnectionError:
    reason = "there is no internet connection"
```

**Formulas.** Appliance use is `watts × hours / 1000` kWh per day for a constant load, and `watts × hours × duty cycle / 1000` for a cycling load. Solar yield for 1 kWp is `(irradiance / 1000) × performance ratio` per hour, with a performance ratio of 0.82. The recommended capacity is the household's daily use divided by the average daily yield of the worst month, multiplied by a 10% margin, then rounded up to whole 550 W panels. The suggested inverter is about 110% of that capacity, rounded up to 0.1 kVA.

## 5. Dataset

| | |
|---|---|
| **Dataset name** | Open-Meteo Historical Weather and Forecast APIs; appliance wattage table (our own CSV) |
| **Link** | https://open-meteo.com (archive: https://archive-api.open-meteo.com/v1/archive, forecast: https://api.open-meteo.com/v1/forecast) |
| **Type** | Public dataset ☐     Web API ☑     Self-collected ☑ (appliance table)     Generated ☐ |
| **Size** | Records: 8,760 hourly rows per city for 2025, five cities. Appliance table: 24 rows. Files / size on disk: [measure data/raw] |
| **Fields used** | time, shortwave_radiation (W/m2), cloud_cover (%), temperature_2m (C) |
| **Licence / terms of use** | Free for non-commercial use; data under CC BY 4.0; credit given as "Weather data by Open-Meteo.com" |
| **Cleaning applied** | hourly_dataframe() converts the hourly JSON into a DataFrame, parses the timestamps and drops invalid ones, sorts by time and removes duplicates, converts values to numbers, treats irradiance below 0 or above 1,500 W/m2 as missing and fills it by interpolation, and raises AnalysisDataError if required columns are missing or all values are missing. The solar estimator separately checks for complete 24-hour days and continuous hourly timestamps. |
| **Offline caching** | Every API reply is saved as JSON in data/raw/ and used when the request fails; a saved copy newer than 7 days (history) or 3 hours (forecast) is used directly without a request, and an older copy is used whenever the request fails; every API reply and every saved file is validated (required keys, matching lengths, timestamps and value ranges); one year of history and a forecast for each city are saved in the repository |

**Appliance table.** The table in data/raw/appliances.csv has 24 common household appliances with watts, type, duty cycle, typical hours and alternative spellings. The first version of the values was suggested by an AI assistant from typical figures, and was then checked by the group against published sources: Virginia Cooperative Extension, "ENERGY SERIES: Estimating Appliance and Home Electronic Energy Use" (https://www.pubs.ext.vt.edu/2901/2901-9014/2901-9014.html) for fans, irons, microwave ovens, washing machines, computers, televisions and water pumps; the Haier Pakistan specification sheet for a 1.5-ton DC inverter air conditioner (https://www.haier.com/pk/air-conditioners/hsu-20hjuv023wdc-g--t3plus.shtml, cooling power input 0.52 to 1.85 kW) for the inverter AC; and the South Australian Government page on electronics (https://www.sa.gov.au/topics/energy-and-environment/using-saving-energy/using-and-buying-appliances/electronics) for computers. After checking, three values were changed: the microwave oven from 1200 W to 1100 W, the laptop from 60 W to 50 W and the desktop computer from 200 W to 270 W (CPU and monitor). The ceiling fan, clothes iron, washing machine, LED TV, water pump and inverter air conditioner values were found to lie inside the published ranges and were kept. The remaining appliances (the fixed-speed air conditioners, refrigerator, deep freezer, electric geyser, other fans, lights, router, charger, water dispenser and air cooler) were not checked against a source and remain typical planning values suggested with AI assistance, so the estimates for homes that use them are less certain. The sources are ranges for typical appliances, mostly from outside Pakistan, so the table is a planning estimate and not a measurement. No permission was needed, and no personal data is stored.

## 6. Results and Analysis

### 6.1 Program Output

[Insert a screenshot of your program running: add an appliance, then option 6]

*Figure 6.1 The application in use*

### 6.2 Visualisations

![Daily mean solar irradiance](../outputs/figures/daily_mean_solar_irradiance.png)

*Figure 6.2 Daily mean short-wave solar irradiance, Karachi, 2025*

[Draft, check against the chart: The chart shows the daily mean irradiance through 2025, with the strongest hourly value of the year at 991 W/m2. We concluded that sunshine is strongest in spring and weakest in winter, and that this is why the system is sized on the worst month, December.]

![Sunshine and cloud cover](../outputs/figures/sunshine_vs_cloud_cover.png)

*Figure 6.3 Daily sunshine and cloud cover, Karachi, 2025*

[Draft, check against the chart: The chart plots daily mean irradiance and daily mean cloud cover on the same dates, with an average cloud cover of 31.5% over the year. We concluded that cloudier days tend to receive less sunshine, which is why cloud cover is a feature of the prediction models.]

![Generation vs demand](../outputs/figures/monthly_generation_vs_demand.png)

*Figure 6.4 Estimated solar generation against household demand per month*

[Draft, check against the chart and your example: The bars show the generation of the recommended system in each month and the line shows the household's demand for that month. We concluded that [use your own example, for example: generation is highest in spring and lowest in December, so the system covers the household in every month].]

![Actual vs predicted](../outputs/figures/actual_vs_predicted_solar.png)

*Figure 6.5 Actual and predicted daily solar radiation on the held-out months*

[Draft, check against the chart: The chart compares the real daily radiation with the best model's prediction on months it was not trained on. We concluded that [describe how closely the lines follow each other and where they differ].]

### 6.3 Model Results

Target: daily total solar radiation (kWh/m2). Features: daily mean cloud cover, daily mean temperature, and sine and cosine of the day of the year. The split is chronological: the last complete calendar months of 2025 (about 20% of the months, at least two) are held out, and everything earlier is used for training. Random splits would let the models see days next to the test days. All models use the same split, and a baseline that always predicts the training-period mean is evaluated on the same test months, so a trained model is only called useful if it beats that baseline. Predictions are clamped so that radiation cannot be negative. Test scores below are from our run.

| Model / configuration | Metric | Training score | Test score | Notes |
|---|---|---|---|---|
| Naive mean baseline | RMSE / R2 | 1.197 / 0.000 | 1.112 / -2.074 | Predicts the training mean every day; test MAE 0.922 |
| Linear Regression (with scaling) | RMSE / R2 | 0.569 / 0.774 | 0.558 / 0.227 | Test MAE 0.472 |
| Random Forest (150 trees, min leaf 3) | RMSE / R2 | 0.327 / 0.925 | 0.445 / 0.508 | Lowest test error; test MAE 0.316 |

Random Forest was chosen because it had the lowest test RMSE and clearly beat the baseline. However, its R2 fell from 0.925 on the training months to 0.508 on the held-out months, and Linear Regression fell from 0.774 to 0.227, so both models fit the training months much better than unseen ones. This gap is a sign of overfitting, and it is made larger because the held-out months (the last of the year) differ in weather and season from the training months. The baseline's negative test R2 probably happens for the same reason: the training-period mean is not a good guess for the less sunny held-out months. An R2 of 0.508 is only a moderate fit, so the predictions should be treated as rough. Because the same test months are used both to compare and to select the model, its test score is also slightly optimistic.

## 7. Testing, Error Handling and Ethics

### 7.1 Test Cases

| # | Test case | Expected | Actual | Pass |
|---|---|---|---|---|
| 1 | Normal input: choose option 3 and type "2 ACs 8 hours, 4 fans 12 hours, fridge", answer the tonnage question with 1.5, then option 4 | The program asks for the AC tonnage, then recognises the ACs, four ceiling fans and the fridge; total about 20.40 kWh per day with the current table | The program asked "AC tonnage (available: 1, 1.5, 2)"; after answering 1.5 it printed "Understood '2 acs 8 hours' as 2 x AC (1.5 ton) (8 h/day)", the four ceiling fans and the refrigerator, and option 4 showed Total: 20.40 kWh per day (when the tonnage question was skipped, only the fans and fridge were added: 5.04 kWh per day) | ☑ |
| 2 | Data file missing: rename data/raw/appliances.csv and start the program | A clear message that the table cannot be found, then the program exits without crashing | The program printed "Cannot find the appliance table at ...\data\raw\appliances.csv." and exited without crashing | ☑ |
| 3 | Malformed row in the data file: put text instead of a number in one watts cell | That row is skipped with a message and the other rows still load | The program printed "Skipping a bad row in ...appliances.csv: ValueError(could not convert string to float: 'abc')" and started normally | ☑ |
| 4 | Network unavailable during API call: (a) saved file older than the freshness limit and no internet; (b) no saved file and no internet | (a) A note that saved data is being used, and the data loads; (b) a clear weather-data message, with no crash | (a) With internet off and the saved file made 30 days old, option 5 printed "Note: there is no internet connection. Using saved data from karachi_history_2025-01-01_2025-12-31.json (updated 30.0 days ago)." and then "Got 8760 hourly rows for Karachi." (b) With the saved file renamed, option 5 printed "Weather data problem: Could not get weather data because there is no internet connection, and there is no saved copy (karachi_history_2025-01-01_2025-12-31.json)." The program did not crash in either case. | ☑ |
| 5 | Invalid input typed by the user: type letters at the menu, and "iron 30 hours" in option 3 | "Please type a number" at the menu; the 30-hour item is skipped with a message | "Please type a number." was printed for abc; "Skipped 'iron 30 hours': hours per day must be between 0 and 24." was printed for the iron | ☑ |
| 6 | Automated unit tests: python -m unittest discover -s tests | All tests pass | Ran 36 tests: OK | ☑ |

### 7.2 Exception Handling

| Exception | Where it is caught | What the user sees |
|---|---|---|
| FileNotFoundError | main.py: main() | A message that the appliance table cannot be found, then the program exits |
| ValueError | main.py: read_number(), add_appliances_from_text(), save_report_from_menu(); the appliance setters raise it | "Please type a number", or the item is skipped with the reason |
| json.JSONDecodeError, ValueError (damaged or invalid saved file) | weather.py: _read_cache() | A warning that the saved file is invalid and was ignored |
| requests.exceptions (connection, timeout and others) | weather.py: WeatherClient | A note that saved data is being used, and why |
| OSError | main.py: save_report_from_menu(); visualization charts in recommend_solar_system() | "Could not save the report" or "Could not create some charts", with the reason |
| WeatherDataError (custom) | Raised in weather.py; caught in main.py: check_weather() and recommend_solar_system() | "Weather data problem" with the reason, and the menu continues |
| AnalysisDataError (custom) | Raised in analysis.py; caught in main.py: recommend_solar_system() | "Weather data problem" with the reason |
| SolarDataError (custom) | Raised in solar_estimator.py; caught in main.py: recommend_solar_system() | "Could not estimate a solar system" with the reason |
| PredictionDataError (custom) | Raised in solar_predictor.py; caught in main.py: recommend_solar_system() | "Machine-learning comparison unavailable" or "Tomorrow's estimate unavailable", with the reason |

### 7.3 Ethical Considerations

SolarSense uses open weather data, which contains no personal information, and the appliances a user types are used only during the session and are not stored, so no consent is needed. The output could still be biased: wattages are typical values, so households with older or less efficient appliances may be underestimated, and the sunshine data describes the chosen city in 2025 rather than every year. A wrong estimate could lead a household to buy a system that is too small or too large and lose money. We therefore tell users clearly, in the program and here, that results are estimates for planning, not engineering advice, and that they should confirm the size with a qualified installer. We credit Open-Meteo for the data and acknowledge the AI assistance used in building the project.

## 8. Individual Contributions and Conclusion

| Member | Modules / files owned | Specific work done | Commits | Share |
|---|---|---|---|---|
| Taha Mahmood | main.py (menu), appliances.py, weather.py, text_match.py, report.py, config.py, fetch_data.py, README | Repository setup, appliance classes and table, weather client with caching and custom exception, text matching, menu, TXT report | 11 on 20 Nov [recount at the end with git shortlog -sn] | [__%] |
| Syed Shahamat Shakeel | analysis.py, solar_estimator.py, solar_predictor.py, visualization.py, tests, recommendation workflow in main.py | Pandas cleaning and summaries, NumPy solar sizing, two-model comparison with a baseline, five charts, automated tests | 5 on 20 Nov [recount at the end] | [__%] |

### 8.1 Challenges Faced

**Ambiguous text matches.** In testing, a plain "fan" was matched to the pedestal fan by TF-IDF alone, because that appliance's short description was dominated by the word "fan". We fixed it by checking for an exact name or alias first and using TF-IDF only for everything else, and by choosing the aliases in the table carefully.

**Combining two separate Git histories.** The two of us ended up with repository histories that did not share a starting point, so a normal pull failed with "refusing to merge unrelated histories". We cancelled the broken merge, backed up our work, merged the two histories on purpose so that every commit of both members was kept, and pushed normally without forcing anything. It taught us to pull before every push and never to create a new repository history. [Add one difficulty from your own modules, for example from the NumPy or model work.]

### 8.2 Conclusion and Future Work

[In 100–150 words, state what was achieved against the four objectives in Section 1.2, using only what really works. For example: appliances can be entered by list, by sentence or by custom wattage; daily use is calculated; weather is fetched and cached; and a system size and monthly output are recommended and compared with demand. The best model, Random Forest, beat the baseline on unseen months, but its fit is only moderate. Then name two or three improvements, for example: cite and verify the appliance wattages against reliable sources, use several years of weather data, and add cost and payback analysis.]

## Appendix A — Setup and Execution

```
git clone https://github.com/TahaMahmood-25/AL-2001-PAI-Project-SolarSense   # 1. clone
cd AL-2001-PAI-Project-SolarSense
pip install -r requirements.txt                                              # 2. install
python src/main.py                                                           # 3. run
```

No key or configuration file is needed. Saved weather data is included in data/raw/, so the program also works without internet. To refresh it, run `python src/fetch_data.py` once with internet. To run the tests: `python -m unittest discover -s tests`. Developed against Python 3.14 [confirm with python --version] and the library versions pinned in requirements.txt.
