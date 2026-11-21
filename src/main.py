"""SolarSense - console interface and end-to-end solar-planning workflow.

Run from the repository root: python src/main.py
"""
import calendar
import math
from typing import Literal, Union, overload

from appliances import (
    ConstantLoadAppliance,
    CyclingAppliance,
    Household,
    create_appliance,
    load_appliance_table,
)
from config import APPLIANCE_CSV, CITIES
from report import save_report
from text_match import ApplianceMatcher, parse_appliance_text
from weather import WeatherClient, WeatherDataError
from analysis import hourly_dataframe, AnalysisDataError
from solar_estimator import SolarEstimator, SolarDataError
from solar_predictor import SolarPredictor, PredictionDataError
from visualization import (
    plot_daily_radiation,
    plot_monthly_generation,
    plot_actual_vs_predicted,
    plot_consumption_breakdown,
    plot_sunshine_vs_cloud_cover,
    monthly_demand_kwh,
)


@overload
def read_number(
    prompt: str,
    low: Union[int, float],
    high: Union[int, float],
    as_int: Literal[True],
) -> int:
    ...


@overload
def read_number(
    prompt: str,
    low: Union[int, float],
    high: Union[int, float],
    as_int: Literal[False] = False,
) -> float:
    ...


def read_number(
    prompt: str,
    low: Union[int, float],
    high: Union[int, float],
    as_int: bool = False,
) -> Union[int, float]:
    """Keep asking until the user types a valid number between low and high."""
    while True:
        text = input(prompt).strip()
        try:
            value = int(text) if as_int else float(text)
        except ValueError:
            print("Please type a number.")
            continue
        if low <= value <= high:
            return value
        print(f"Please type a value between {low} and {high}.")


def choose_city():
    """Show the supported cities and return the chosen name."""
    names = list(CITIES)
    for number, name in enumerate(names, start=1):
        print(f"  {number}. {name}")
    choice = read_number("City number: ", 1, len(names), as_int=True)
    return names[choice - 1]


def invalidate_recommendation(report_lines):
    """Drop results tied to an earlier city or appliance configuration."""
    report_lines.clear()


def add_appliance_from_list(household, table):
    """Let the user pick an appliance from the table, then give count and hours."""
    items = sorted(table.values(), key=lambda row: row["name"])
    for number, row in enumerate(items, start=1):
        print(f"  {number}. {row['name']} ({row['watts']:g} W)")
    row = items[read_number("Appliance number: ", 1, len(items), as_int=True) - 1]
    quantity = read_number("How many? ", 1, 50, as_int=True)
    hours = read_number(f"Hours per day (typical {row['default_hours']:g}): ", 0, 24)
    household.add_appliance(create_appliance(row, hours), quantity)
    print(f"Added {quantity} x {row['name']}.")


def add_appliances_from_text(household, table, matcher):
    """Read a sentence, match each part to the table and add what was understood."""
    text = input("Describe your appliances, e.g. 2 ACs 8 hours, 4 fans, fridge\n> ").strip()
    if not text:
        print("Nothing typed.")
        return
    for item in parse_appliance_text(text, matcher):
        if item.get("error"):
            print(f"Skipped '{item['original']}': {item['error']}")
            continue
        row = item["row"]
        if item.get("ambiguous_ac"):
            prefix = "inverter ac" if item["phrase"] == "inverter ac" else "ac"
            available = ", ".join(
                key[len(prefix) + 1:-4]
                for key in table
                if key.startswith(prefix + " ") and key.endswith(" ton")
            )
            tonnage = input(
                f"{'Inverter ' if prefix == 'inverter ac' else ''}AC tonnage "
                f"(available: {available}), or Enter to skip: "
            ).strip()
            row = table.get(f"{prefix} {tonnage} ton")
            if row is None:
                print(f"Skipped '{item['original']}': choose an available AC tonnage.")
                continue
        if row is None:
            print(f"Could not recognise '{item['original']}'.")
            if input("Pick it from the list instead? (y/n): ").strip().lower() == "y":
                add_appliance_from_list(household, table)
            continue
        try:
            appliance = create_appliance(row, item["hours"])
            household.add_appliance(appliance, item["quantity"])
        except ValueError as error:
            print(f"Skipped '{item['original']}': {error}.")
            continue
        print(f"Understood '{item['original']}' as {item['quantity']} x "
              f"{row['name']} ({appliance.hours_per_day:g} h/day).")


def add_manual_appliance(household):
    """Add a custom appliance with user-provided power and usage."""
    name = input("Appliance name: ").strip()
    if not name:
        print("Appliance name cannot be empty.")
        return
    watts = read_number("Rated power in watts: ", 0.01, 100000)
    hours = read_number("Hours per day: ", 0, 24)
    quantity = read_number("Quantity: ", 1, 50, as_int=True)
    kind = input("Load type (constant/cycling): ").strip().lower()
    if kind not in {"constant", "cycling"}:
        print("Choose 'constant' or 'cycling'.")
        return
    if kind == "cycling":
        duty = read_number("Duty cycle (0.01 to 1): ", 0.01, 1)
        appliance = CyclingAppliance(name, watts, hours, duty)
    else:
        appliance = ConstantLoadAppliance(name, watts, hours)
    household.add_appliance(appliance, quantity)
    print(f"Added {quantity} x {name} ({watts:g} W).")


def check_weather(city):
    """Fetch (or load saved) history for the city and print a quick check."""
    try:
        hourly = WeatherClient(city).fetch_history()
    except WeatherDataError as error:
        print(f"Weather data problem: {error}")
        return
    values = []
    for value in hourly.get("shortwave_radiation", []):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric) and numeric >= 0:
            values.append(numeric)
    print(f"Got {len(hourly.get('time', []))} hourly rows for {city}.")
    if not values:
        print("No usable solar-radiation values were returned.")
        return
    print(f"Strongest sunshine in the year: {max(values):g} W/m2")


def save_report_from_menu(household, extra_lines=None):
    """Save the TXT report and tell the user where it went (or what failed)."""
    try:
        path = save_report(household, extra_lines=extra_lines)
    except ValueError as error:
        print(error)
    except OSError as error:
        print(f"Could not save the report: {error}")
    else:
        print(f"Report saved to {path}")


def recommend_solar_system(household, report_lines):
    """Run weather analysis, solar sizing, optional ML comparison and charts."""
    if household.is_empty():
        print("Add at least one appliance before requesting a solar recommendation.")
        return

    try:
        history_client = WeatherClient(household.city)
        hourly = history_client.fetch_history()
        frame = hourly_dataframe(hourly)
    except (WeatherDataError, AnalysisDataError) as error:
        print(f"Weather data problem: {error}")
        return

    daily_kwh = household.total_daily_kwh()
    try:
        estimator = SolarEstimator(hourly)
        recommendation = estimator.recommend_size(daily_kwh)
    except SolarDataError as error:
        print(f"Could not estimate a solar system: {error}")
        return

    monthly_output = recommendation["monthly_output_kwh"]
    print("\n=== Solar recommendation ===")
    print(f"City: {household.city}")
    print(f"Estimated daily consumption: {daily_kwh:.2f} kWh")
    print(f"Recommended capacity: {recommendation['capacity_kwp']:.2f} kWp")
    print(f"Panels: {recommendation['panel_count']} x "
          f"{recommendation['panel_wattage']:g} W")
    print(f"Suggested inverter: about {recommendation['inverter_kw']:.1f} kVA")
    print(f"Historical weather archive ({history_client.last_source}): "
          f"{frame.index.min():%Y-%m-%d} to {frame.index.max():%Y-%m-%d}, "
          f"{len(frame)} hourly rows.")
    cloud_values = frame["cloud_cover"].dropna()
    mean_cloud = f"{cloud_values.mean():.1f}%" if not cloud_values.empty else "unavailable"
    print(f"Observed archive maximum irradiance: "
          f"{frame['shortwave_radiation'].max():.1f} W/m2; "
          f"average cloud cover: {mean_cloud}.")
    if recommendation["missing_radiation_hours"]:
        print(f"Warning: {recommendation['missing_radiation_hours']} radiation hours "
              "were unavailable and excluded from generation totals.")
    print(f"Sizing constraint: lowest average yield is "
          f"{recommendation['worst_month_avg_daily_kwh']:.2f} kWh/day/kWp "
          f"in {recommendation['worst_month']}")
    print("\nEstimated monthly generation:")
    for month, kwh in monthly_output.items():
        days = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
        demand = monthly_demand_kwh(daily_kwh, month)
        coverage = 100 * kwh / demand if demand else 0
        print(f"  {month}: {kwh:.1f} kWh ({coverage:.0f}% of estimated {days}-day demand)")

    report_lines.clear()
    report_lines.extend([
        f"City: {household.city}",
        f"Daily household consumption: {daily_kwh:.2f} kWh",
        "",
        "Historical Open-Meteo archive summary:",
        f"  Retrieved from: {history_client.last_source}",
        f"  Coverage: {frame.index.min():%Y-%m-%d} through "
        f"{frame.index.max():%Y-%m-%d} ({len(frame)} hourly rows)",
        f"  Maximum hourly irradiance: "
        f"{frame['shortwave_radiation'].max():.1f} W/m2",
        f"  Mean cloud cover: {mean_cloud}",
        f"Recommended system capacity: {recommendation['capacity_kwp']:.2f} kWp",
        f"Recommended panels: {recommendation['panel_count']} x "
        f"{recommendation['panel_wattage']:g} W",
        f"Suggested inverter: about {recommendation['inverter_kw']:.1f} kVA",
        f"System assumptions: {recommendation['performance_ratio']:.0%} "
        f"performance ratio, {recommendation['capacity_margin']:.0%} capacity margin",
        f"Lowest-month sizing basis: {recommendation['worst_month']} "
        f"at {recommendation['worst_month_avg_daily_kwh']:.2f} kWh/day/kWp",
        "",
        "Estimated monthly solar generation:",
    ])
    if recommendation["missing_radiation_hours"]:
        report_lines.append(
            "  Missing radiation hours excluded: "
            f"{recommendation['missing_radiation_hours']}"
        )
    for month, kwh in monthly_output.items():
        report_lines.append(
            f"  {month}: generation {kwh:.1f} kWh; "
            f"estimated household demand {monthly_demand_kwh(daily_kwh, month):.1f} kWh"
        )

    try:
        chart_paths = [
            plot_daily_radiation(frame),
            plot_sunshine_vs_cloud_cover(frame),
            plot_monthly_generation(monthly_output, daily_kwh),
            plot_consumption_breakdown(household),
        ]
    except (ValueError, OSError) as error:
        print(f"Could not create some charts: {error}")
        chart_paths = []

    try:
        predictor = SolarPredictor(frame)
        results = predictor.train()
        best_name = min(results, key=lambda name: results[name]["RMSE"])
        baseline_rmse = results["Naive mean baseline"]["RMSE"]
        model_improved = any(
            results[name]["RMSE"] < baseline_rmse
            for name in ("Linear Regression", "Random Forest")
        )
        print("\nRadiation-model comparison (complete held-out months):")
        for name, metrics in results.items():
            train_metrics = predictor.train_results[name]
            print(f"  {name}: MAE={metrics['MAE']:.3f} kWh/m2, "
                  f"RMSE={metrics['RMSE']:.3f} kWh/m2, R2={metrics['R2']:.3f} "
                  f"(training RMSE={train_metrics['RMSE']:.3f}, R2={train_metrics['R2']:.3f})")
        if model_improved:
            print("At least one trained model has lower test RMSE than the naive baseline.")
        else:
            print("Neither trained model beats the naive baseline on test RMSE.")

        report_lines.extend(["", "Machine-learning comparison:",
                             "Target: daily total short-wave radiation (kWh/m2)",
                             "Features: mean cloud cover, mean temperature and annual sine/cosine seasonality",
                             "Evaluation: last complete unseen calendar months",
                             "Baseline: training-period mean prediction",
                             f"Best test RMSE: {best_name}",
                             "Trained-model improvement over baseline: "
                             + ("yes" if model_improved else "no")])
        for name, metrics in results.items():
            report_lines.append(
                f"  {name}: MAE={metrics['MAE']:.3f}, "
                f"RMSE={metrics['RMSE']:.3f}, R2={metrics['R2']:.3f}"
            )

        try:
            chart_paths.append(plot_actual_vs_predicted(
                predictor.test_dates,
                predictor.actual,
                results[best_name]["predictions"],
                f"Actual vs {best_name} Prediction",
            ))
        except (ValueError, OSError) as error:
            print(f"Could not create the model chart: {error}")

        forecast_lines = [
            "",
            "Tomorrow's predicted daily short-wave radiation "
            "(not panel electricity generation):",
        ]
        try:
            forecast_client = WeatherClient(household.city)
            forecast_hourly = forecast_client.fetch_forecast()
            forecast_frame = hourly_dataframe(forecast_hourly)
            tomorrow = predictor.tomorrow()
            model_name, predicted_radiation = predictor.predict_from_forecast(
                forecast_frame, target_day=tomorrow
            )
            text = (f"  {tomorrow}: {predicted_radiation:.2f} kWh/m2 "
                    f"(model: {model_name}; forecast source: "
                    f"{forecast_client.last_source})")
            print("\n" + text.strip())
            forecast_lines.append(text)
        except (WeatherDataError, AnalysisDataError, PredictionDataError) as error:
            text = f"  Unavailable: {error}"
            print("\nTomorrow's estimate unavailable: " + str(error))
            forecast_lines.append(text)
        report_lines.extend(forecast_lines)
    except PredictionDataError as error:
        print(f"\nMachine-learning comparison unavailable: {error}")
        report_lines.extend([
            "",
            "Machine-learning comparison unavailable:",
            f"  {error}",
        ])

    if chart_paths:
        print("\nCharts saved:")
        for path in chart_paths:
            print(f"  {path}")

    report_lines.extend([
        "",
        "Limitations:",
        "  Estimates assume standard panel orientation and no detailed shading study.",
        "  Irradiance is not guaranteed electricity generation.",
        "  Wattages and duty cycles are typical planning values, not measured loads.",
        "  Battery, inverter configuration, shading and roof area require an installer.",
    ])


def main():
    """Run the menu loop."""
    try:
        table = load_appliance_table(APPLIANCE_CSV)
    except FileNotFoundError:
        print(f"Cannot find the appliance table at {APPLIANCE_CSV}.")
        return
    matcher = ApplianceMatcher(table)
    household = Household()
    report_lines = []
    while True:
        print("\n=== SolarSense ===")
        print("1. Choose city")
        print("2. Add an appliance from the list")
        print("3. Type appliances in plain words")
        print("4. Show my appliances and daily use")
        print("5. Check weather data")
        print("6. Recommend a solar system")
        print("7. Save a report (TXT)")
        print("8. Add an appliance with custom wattage")
        print("0. Exit")
        choice = read_number("Choose: ", 0, 8, as_int=True)
        if choice == 0:
            print("Goodbye!")
            break
        if choice == 1:
            city = choose_city()
            if city != household.city:
                invalidate_recommendation(report_lines)
            household.city = city
            print(f"City set to {household.city}.")
        elif choice == 2:
            invalidate_recommendation(report_lines)
            add_appliance_from_list(household, table)
        elif choice == 3:
            invalidate_recommendation(report_lines)
            add_appliances_from_text(household, table, matcher)
        elif choice == 4:
            print("No appliances yet." if household.is_empty() else household.summary())
        elif choice == 5:
            check_weather(household.city)
        elif choice == 6:
            recommend_solar_system(household, report_lines)
        elif choice == 7:
            save_report_from_menu(household, report_lines)
        elif choice == 8:
            invalidate_recommendation(report_lines)
            add_manual_appliance(household)
        else:
            print("Invalid menu option.")


if __name__ == "__main__":
    main()
