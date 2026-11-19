import json
import io
import os
import tempfile
import time
import unittest
from pathlib import Path
from datetime import date
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import requests

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from analysis import AnalysisDataError, daily_summary, hourly_dataframe
from appliances import (
    ConstantLoadAppliance,
    CyclingAppliance,
    Household,
    load_appliance_table,
)
from report import build_report_text, save_report
from solar_estimator import SolarDataError, SolarEstimator
from solar_predictor import PredictionDataError, SolarPredictor
from text_match import ApplianceMatcher, parse_appliance_text
from weather import WeatherClient, WeatherDataError
from main import (
    add_appliances_from_text,
    add_manual_appliance,
    check_weather,
    invalidate_recommendation,
)
from visualization import monthly_demand_kwh, plot_sunshine_vs_cloud_cover


class ApplianceTests(unittest.TestCase):
    def setUp(self):
        self.table = load_appliance_table(
            Path(__file__).resolve().parents[1] / "data" / "raw" / "appliances.csv"
        )

    def test_appliance_calculations(self):
        fan = ConstantLoadAppliance("Fan", 75, 10)
        fridge = CyclingAppliance("Fridge", 150, 24, 0.4)
        self.assertAlmostEqual(fan.daily_kwh(), 0.75)
        self.assertAlmostEqual(fridge.daily_kwh(), 1.44)

    def test_non_finite_appliance_specs_are_rejected(self):
        for watts in (float("nan"), float("inf")):
            with self.subTest(watts=watts):
                with self.assertRaises(ValueError):
                    ConstantLoadAppliance("Bad load", watts, 1)

    def test_negative_and_fraction_quantity_are_rejected(self):
        household = Household()
        fan = ConstantLoadAppliance("Fan", 75, 10)
        for quantity in (-1, 0, 1.5):
            with self.subTest(quantity=quantity):
                with self.assertRaises(ValueError):
                    household.add_appliance(fan, quantity)

    def test_nlp_examples(self):
        matcher = ApplianceMatcher(self.table)
        parsed = parse_appliance_text(
            "I use 3 fans, 2 LED bulbs and one refrigerator.", matcher
        )
        recognized = {item["row"]["key"]: item["quantity"] for item in parsed if item["row"]}
        self.assertEqual(recognized["ceiling fan"], 3)
        self.assertEqual(recognized["led bulb"], 2)
        self.assertEqual(recognized["refrigerator"], 1)

    def test_unknown_and_duplicate_mentions(self):
        matcher = ApplianceMatcher(self.table)
        unknown = parse_appliance_text("quantum toaster", matcher)[0]
        self.assertIsNone(unknown["row"])
        duplicate_mentions = parse_appliance_text("2 fans and 3 fans", matcher)
        self.assertEqual([item["quantity"] for item in duplicate_mentions], [2, 3])
        household = Household()
        for item in duplicate_mentions:
            household.add_appliance(
                ConstantLoadAppliance("Fan", 75, 10), item["quantity"]
            )
        self.assertAlmostEqual(household.total_daily_kwh(), 3.75)

    def test_ton_ac_quantity(self):
        matcher = ApplianceMatcher(self.table)
        parsed = parse_appliance_text("Two 1.5 ton ACs", matcher)
        item = parsed[0]
        self.assertEqual(item["quantity"], 2)
        self.assertEqual(item["row"]["key"], "ac 1.5 ton")

    def test_zero_quantity_is_not_defaulted(self):
        matcher = ApplianceMatcher(self.table)
        item = parse_appliance_text("0 fans", matcher)[0]
        self.assertEqual(item["quantity"], 0)
        self.assertIsNone(item["row"])
        self.assertIn("error", item)

    def test_generic_ac_requires_tonnage(self):
        matcher = ApplianceMatcher(self.table)
        item = parse_appliance_text("2 ACs", matcher)[0]
        self.assertTrue(item["ambiguous_ac"])
        self.assertEqual(item["quantity"], 2)
        self.assertIsNone(item["row"])
        inverter = parse_appliance_text("inverter AC", matcher)[0]
        self.assertTrue(inverter["ambiguous_ac"])
        self.assertIsNone(inverter["row"])

    def test_generic_ac_cli_confirms_tonnage(self):
        matcher = ApplianceMatcher(self.table)
        household = Household()
        with patch("builtins.input", side_effect=["2 ACs", "1.5"]):
            add_appliances_from_text(household, self.table, matcher)
        self.assertEqual(household._items[0][1], 2)
        self.assertEqual(household._items[0][0].name, "AC (1.5 ton)")


class AnalysisAndEstimatorTests(unittest.TestCase):
    def setUp(self):
        times = pd.date_range("2025-01-01", periods=24 * 60, freq="h")
        radiation = np.tile(np.array([0]*6 + [100,300,600,800,900,800,600,300] +
                                     [0]*10), 60)
        self.hourly = {
            "time": [value.strftime("%Y-%m-%dT%H:%M") for value in times],
            "shortwave_radiation": radiation.tolist(),
            "cloud_cover": [20] * len(times),
            "temperature_2m": [25] * len(times),
        }

    def test_analysis_rejects_missing_radiation(self):
        with self.assertRaises(AnalysisDataError):
            hourly_dataframe({"time": ["2025-01-01T00:00"]})

    def test_empty_weather_datasets_are_rejected(self):
        empty_hourly = {
            "time": [],
            "shortwave_radiation": [],
            "cloud_cover": [],
            "temperature_2m": [],
        }
        with self.assertRaises(AnalysisDataError):
            hourly_dataframe(empty_hourly)
        with self.assertRaises(AnalysisDataError):
            daily_summary(pd.DataFrame())
        with self.assertRaises(SolarDataError):
            SolarEstimator(empty_hourly)

    def test_estimator_recommendation(self):
        estimator = SolarEstimator(self.hourly)
        result = estimator.recommend_size(10)
        self.assertGreater(result["capacity_kwp"], 0)
        self.assertGreater(result["panel_count"], 0)
        self.assertGreater(result["inverter_kw"], 0)
        self.assertTrue(result["monthly_output_kwh"])

    def test_estimator_rejects_bad_consumption(self):
        estimator = SolarEstimator(self.hourly)
        with self.assertRaises(SolarDataError):
            estimator.recommend_size(0)

    def test_estimator_rejects_non_finite_assumptions(self):
        for kwargs in (
            {"panel_wattage": float("nan")},
            {"performance_ratio": float("inf")},
            {"capacity_margin": float("nan")},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(SolarDataError):
                    SolarEstimator(self.hourly, **kwargs)

    def test_zero_radiation_does_not_divide_by_zero(self):
        zero_data = dict(self.hourly)
        zero_data["shortwave_radiation"] = [0] * len(self.hourly["time"])
        estimator = SolarEstimator(zero_data)
        with self.assertRaises(SolarDataError):
            estimator.recommend_size(4)

    def test_estimator_rejects_incomplete_hourly_day(self):
        with self.assertRaises(SolarDataError):
            SolarEstimator({
                "time": ["2025-01-01T00:00"],
                "shortwave_radiation": [0],
            })

    def test_daily_summary(self):
        frame = hourly_dataframe(self.hourly)
        daily = daily_summary(frame)
        self.assertEqual(len(daily), 60)
        self.assertIn("radiation_wh_m2", daily.columns)

    def test_daily_summary_rejects_same_missing_columns_as_hourly_loader(self):
        solar_only = hourly_dataframe({
            "time": ["2025-01-01T00:00"],
            "shortwave_radiation": [0],
        })
        self.assertIn("shortwave_radiation", solar_only)
        self.assertNotIn("cloud_cover", solar_only)
        with self.assertRaises(AnalysisDataError):
            daily_summary(pd.DataFrame({
                "shortwave_radiation": [0],
            }, index=pd.to_datetime(["2025-01-01"])))

    def test_calendar_month_demand(self):
        self.assertEqual(monthly_demand_kwh(2, "2024-02"), 58)
        self.assertEqual(monthly_demand_kwh(2, "2025-02"), 56)

    def test_numpy_daily_reshape_mask_and_axis_aggregation(self):
        estimator = SolarEstimator(self.hourly)
        self.assertEqual(estimator._daily_radiation.shape, (60, 24))
        self.assertEqual(estimator._daily_valid_mask.shape, (60, 24))
        dates, output = estimator.daily_output_kwh(1)
        self.assertEqual(len(dates), 60)
        self.assertEqual(output.shape, (60,))


class PredictorTests(unittest.TestCase):
    def test_predictor_insufficient_data(self):
        index = pd.date_range("2025-01-01", periods=30, freq="D")
        frame = pd.DataFrame({
            "shortwave_radiation": [5] * 30,
            "cloud_cover": [30] * 30,
            "temperature_2m": [25] * 30,
        }, index=index)
        with self.assertRaises(PredictionDataError):
            SolarPredictor(frame)

    def test_predictor_chronological_training(self):
        cloud = np.linspace(10, 80, 120)
        temp = np.linspace(20, 30, 120)
        radiation = 8 - cloud * 0.04 + temp * 0.02
        hourly_index = pd.date_range("2025-01-01", periods=120 * 24, freq="h")
        frame = pd.DataFrame({
            "shortwave_radiation": np.repeat(radiation * 1000 / 24, 24),
            "cloud_cover": np.repeat(cloud, 24),
            "temperature_2m": np.repeat(temp, 24),
        }, index=hourly_index)
        predictor = SolarPredictor(frame)
        results = predictor.train()
        self.assertEqual(set(results), {
            "Linear Regression", "Random Forest", "Naive mean baseline"
        })
        self.assertTrue(predictor.test_months)
        self.assertTrue(all(str(day.to_period("M")) in predictor.test_months
                            for day in predictor.test_dates))
        self.assertTrue(all(day.to_period("M") not in
                            [stamp.to_period("M") for stamp in predictor.daily.index
                             if stamp < predictor.test_dates[0]]
                            for day in predictor.test_dates))
        for metrics in results.values():
            self.assertIn("MAE", metrics)
            self.assertIn("RMSE", metrics)
            self.assertIn("R2", metrics)
            self.assertTrue(np.all(metrics["predictions"] >= 0))

    def test_forecast_prediction_and_missing_forecast(self):
        index = pd.date_range("2025-01-01", periods=24 * 180, freq="h")
        daily_cloud = np.repeat(np.linspace(10, 70, 180), 24)
        frame = pd.DataFrame({
            "shortwave_radiation": np.tile([0, 100, 300, 600] * 6, 180),
            "cloud_cover": daily_cloud,
            "temperature_2m": np.repeat(np.linspace(15, 35, 180), 24),
        }, index=index)
        predictor = SolarPredictor(frame)
        predictor.train()
        target = date(2026, 1, 2)
        forecast_index = pd.date_range("2026-01-02", periods=24, freq="h")
        forecast = pd.DataFrame({
            "shortwave_radiation": [0] * 24,
            "cloud_cover": [40] * 24,
            "temperature_2m": [25] * 24,
        }, index=forecast_index)
        model_name, prediction = predictor.predict_from_forecast(forecast, target)
        self.assertIn(model_name, predictor.results)
        self.assertGreaterEqual(prediction, 0)
        class SeasonalProbe:
            def predict(self, features):
                return np.array([features.iloc[0]["day_sin"]])

        predictor.models["seasonal-probe"] = SeasonalProbe()
        predictor.results["seasonal-probe"] = {
            "RMSE": -1.0,
            "MAE": 0.0,
            "R2": 1.0,
            "predictions": np.array([0.0]),
        }
        _, target_prediction = predictor.predict_from_forecast(forecast, target)
        expected_day_sin = np.sin(2 * np.pi * target.timetuple().tm_yday / 365.25)
        self.assertAlmostEqual(target_prediction, expected_day_sin)
        class NegativeModel:
            def predict(self, features):
                return np.full(len(features), -100.0)

        predictor.models["negative-test"] = NegativeModel()
        self.assertEqual(
            predictor.predict(
                {"cloud_cover": 40, "temperature_2m": 25}, "negative-test"
            ),
            0.0,
        )
        with self.assertRaises(PredictionDataError):
            predictor.predict_from_forecast(forecast.iloc[0:0], target)
        with self.assertRaises(PredictionDataError):
            predictor.predict_from_forecast(forecast.iloc[:12], target)


class WeatherAndReportTests(unittest.TestCase):
    def test_weather_cache_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            client = WeatherClient("Karachi", cache_dir=Path(directory))
            path = client._cache_path("history_2025-01-01_2025-12-31")
            with path.open("w", encoding="utf-8") as file:
                json.dump({
                    "time": ["2025-01-01T00:00"],
                    "shortwave_radiation": [0],
                    "cloud_cover": [0],
                    "temperature_2m": [25],
                }, file)
            stale_time = time.time() - 30 * 24 * 60 * 60
            os.utime(path, (stale_time, stale_time))
            with patch("weather.requests.get") as get:
                get.side_effect = requests.exceptions.ConnectionError("offline")
                data = client.fetch_history()
            self.assertEqual(data["time"], ["2025-01-01T00:00"])
            self.assertEqual(client.last_source, "cache fallback")
            get.assert_called_once()

    def test_invalid_cached_payload_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            client = WeatherClient("Karachi", cache_dir=Path(directory))
            path = client._cache_path("forecast")
            with path.open("w", encoding="utf-8") as file:
                json.dump({"time": ["2026-01-01T00:00"], "shortwave_radiation": [0]}, file)
            with patch("weather.requests.get") as get:
                get.side_effect = requests.exceptions.ConnectionError("offline")
                with self.assertRaises(WeatherDataError):
                    client.fetch_forecast()
            get.assert_called_once()

    def test_fresh_valid_cache_is_reused_and_age_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            client = WeatherClient("Karachi", cache_dir=Path(directory))
            path = client._cache_path("forecast")
            with path.open("w", encoding="utf-8") as file:
                json.dump({
                    "time": ["2026-01-01T00:00"],
                    "shortwave_radiation": [0],
                    "cloud_cover": [0],
                    "temperature_2m": [25],
                }, file)
            with patch("weather.requests.get") as get:
                output = io.StringIO()
                with redirect_stdout(output):
                    data = client.fetch_forecast()
            get.assert_not_called()
            self.assertEqual(data["time"], ["2026-01-01T00:00"])
            self.assertEqual(client.last_source, "fresh cache")
            self.assertIn("updated", output.getvalue())

    def test_forecast_failure_without_cache_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            client = WeatherClient("Karachi", cache_dir=Path(directory))
            with patch("weather.requests.get") as get:
                get.side_effect = requests.exceptions.ConnectionError("offline")
                with self.assertRaises(WeatherDataError):
                    client.fetch_forecast()

    def test_invalid_live_api_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            client = WeatherClient("Karachi", cache_dir=Path(directory))
            response = Mock()
            response.status_code = 200
            response.json.return_value = {"hourly": {"time": ["2026-01-01T00:00"]}}
            with patch("weather.requests.get", return_value=response):
                with self.assertRaises(WeatherDataError):
                    client.fetch_forecast()

    def test_unsupported_city_is_rejected(self):
        with self.assertRaises(ValueError):
            WeatherClient("Not a city")

    def test_stale_recommendation_is_invalidated(self):
        report_lines = ["old city recommendation", "old panel count"]
        invalidate_recommendation(report_lines)
        self.assertEqual(report_lines, [])

    def test_report_filenames_are_collision_safe(self):
        household = Household("Karachi")
        household.add_appliance(ConstantLoadAppliance("Fan", 75, 4))
        with tempfile.TemporaryDirectory() as directory:
            first = save_report(household, folder=Path(directory))
            second = save_report(household, folder=Path(directory))
        self.assertNotEqual(first.name, second.name)

    def test_weather_check_handles_empty_radiation(self):
        with patch("main.WeatherClient") as client_class:
            client_class.return_value.fetch_history.return_value = {
                "time": ["2025-01-01T00:00"],
                "shortwave_radiation": [None, "bad", float("inf")],
            }
            output = io.StringIO()
            with redirect_stdout(output):
                check_weather("Karachi")
        self.assertIn("No usable solar-radiation", output.getvalue())

    def test_manual_appliance_entry(self):
        household = Household()
        with patch("builtins.input", side_effect=[
            "Custom panel load", "100", "3", "2", "constant"
        ]):
            add_manual_appliance(household)
        self.assertAlmostEqual(household.total_daily_kwh(), 0.6)

    def test_sunshine_cloud_chart(self):
        frame = hourly_dataframe({
            "time": ["2025-01-01T00:00", "2025-01-01T01:00"],
            "shortwave_radiation": [0, 100],
            "cloud_cover": [20, 40],
            "temperature_2m": [15, 16],
        })
        with tempfile.TemporaryDirectory() as directory:
            path = plot_sunshine_vs_cloud_cover(frame, directory)
            self.assertTrue(path.exists())

    def test_report_rejects_empty_household(self):
        household = Household()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                save_report(household, folder=Path(directory))

    def test_report_text_includes_appliances_and_assumptions(self):
        household = Household("Lahore")
        household.add_appliance(ConstantLoadAppliance("Ceiling fan", 75, 10), 1)
        text = build_report_text(household, ["Recommended system: 1.5 kWp"])
        self.assertIn("Lahore", text)
        self.assertIn("Ceiling fan", text)
        self.assertIn("planning, not engineering advice", text)


if __name__ == "__main__":
    unittest.main()
