import sys
import re
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api import (
    ApplianceInput,
    ParseInput,
    PlanInput,
    _household,
    analyze,
    catalog,
    parse_text,
    report,
)


def sample_weather():
    times = [
        f"2025-01-{day:02d}T{hour:02d}:00"
        for day in (1, 2)
        for hour in range(24)
    ]
    radiation_day = [0] * 6 + [100, 300, 600, 800, 900, 800, 600, 300] + [0] * 10
    return {
        "time": times,
        "shortwave_radiation": radiation_day * 2,
        "cloud_cover": [20] * 48,
        "temperature_2m": [25] * 48,
    }


class SolarSenseApiTests(unittest.TestCase):
    def test_catalog_exposes_supported_cities_and_loads(self):
        response = catalog()
        self.assertIn("Karachi", [city["name"] for city in response["cities"]])
        self.assertIn(
            "ceiling fan",
            [appliance["key"] for appliance in response["appliances"]],
        )

    def test_natural_language_parser_keeps_ambiguous_ac_for_review(self):
        response = parse_text(ParseInput(text="2 ACs 8 hours, 4 fans"))
        ac, fan = response["items"]
        self.assertTrue(ac["ambiguous_ac"])
        self.assertEqual(ac["quantity"], 2)
        self.assertEqual(fan["key"], "ceiling fan")
        self.assertEqual(fan["quantity"], 4)

    def test_household_uses_editable_and_custom_load_values(self):
        household = _household(PlanInput(
            city="Lahore",
            appliances=[
                ApplianceInput(key="ceiling fan", watts=100, hours=4, quantity=2),
                ApplianceInput(
                    name="Water pump",
                    watts=500,
                    hours=4,
                    quantity=1,
                    kind="cycling",
                    duty_cycle=0.4,
                ),
            ],
        ))
        self.assertEqual(household.city, "Lahore")
        self.assertAlmostEqual(household.total_daily_kwh(), 1.6)

    def test_analysis_returns_live_sizing_and_reports_prediction_limits(self):
        client = type("Weather", (), {
            "last_source": "test fixture",
            "fetch_history": lambda self: sample_weather(),
        })()
        with patch("api.WeatherClient", return_value=client):
            result = analyze(PlanInput(
                appliances=[ApplianceInput(key="ceiling fan", hours=8)]
            ))
        self.assertGreater(result["recommendation"]["capacity_kwp"], 0)
        self.assertEqual(result["source"], "test fixture")
        self.assertEqual(len(result["radiation"]), 2)
        self.assertEqual(len(result["monthly"]), 1)
        self.assertIn("unavailable", result["prediction"]["models"])

    def test_pdf_report_is_a_real_downloadable_pdf(self):
        client = type("Weather", (), {
            "last_source": "test fixture",
            "fetch_history": lambda self: sample_weather(),
        })()
        with patch("api.WeatherClient", return_value=client):
            response = report(PlanInput(
                appliances=[ApplianceInput(key="ceiling fan", hours=8)]
            ))
        self.assertEqual(response.media_type, "application/pdf")
        self.assertTrue(response.body.startswith(b"%PDF-"))
        self.assertEqual(len(re.findall(rb"/Type\s*/Page\b", response.body)), 2)
        self.assertIn("attachment;", response.headers["content-disposition"])


if __name__ == "__main__":
    unittest.main()
