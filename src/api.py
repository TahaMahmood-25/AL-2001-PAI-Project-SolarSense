"""HTTP API that exposes the existing SolarSense planning workflow."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.lines import Line2D
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pydantic import BaseModel, Field

from analysis import AnalysisDataError, hourly_dataframe
from appliances import ConstantLoadAppliance, CyclingAppliance, Household, create_appliance, load_appliance_table
from config import BASE_DIR, CITIES
from solar_estimator import SolarDataError, SolarEstimator
from solar_predictor import PredictionDataError, SolarPredictor
from text_match import ApplianceMatcher, parse_appliance_text
from weather import WeatherClient, WeatherDataError
from visualization import monthly_demand_kwh


app = FastAPI(title="SolarSense", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

APPLIANCE_TABLE = load_appliance_table()
MATCHER = ApplianceMatcher(APPLIANCE_TABLE)
PALETTE = {
    "paper": "#F2EDE3",
    "ink": "#242321",
    "orange": "#E97848",
    "lilac": "#C9B8DF",
    "yellow": "#E3DC75",
    "stone": "#D6CEC0",
}


class ApplianceInput(BaseModel):
    key: Optional[str] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    watts: Optional[float] = Field(default=None, gt=0, le=50000)
    hours: float = Field(ge=0, le=24)
    quantity: int = Field(default=1, ge=1, le=50)
    kind: Optional[str] = None
    duty_cycle: Optional[float] = Field(default=None, gt=0, le=1)


class PlanInput(BaseModel):
    city: str = "Karachi"
    appliances: list[ApplianceInput] = Field(min_length=1, max_length=50)


class ParseInput(BaseModel):
    text: str = Field(min_length=1, max_length=500)


def _household(plan: PlanInput) -> Household:
    if plan.city not in CITIES:
        raise HTTPException(status_code=422, detail="Choose a supported city.")
    household = Household(plan.city)
    for item in plan.appliances:
        if item.key:
            row = APPLIANCE_TABLE.get(item.key.lower())
            if row is None:
                raise HTTPException(status_code=422, detail=f"Unknown appliance: {item.key}")
            edited_row = {
                **row,
                "watts": item.watts if item.watts is not None else row["watts"],
                "duty_cycle": (
                    item.duty_cycle
                    if item.duty_cycle is not None
                    else row["duty_cycle"]
                ),
            }
            appliance = create_appliance(edited_row, item.hours)
        else:
            name = (item.name or "").strip()
            if not name or item.watts is None:
                raise HTTPException(
                    status_code=422,
                    detail="Custom appliances need a name and a wattage.",
                )
            kind = item.kind or "constant"
            if kind == "cycling":
                appliance = CyclingAppliance(
                    name, item.watts, item.hours, item.duty_cycle or 0.5
                )
            elif kind == "constant":
                appliance = ConstantLoadAppliance(name, item.watts, item.hours)
            else:
                raise HTTPException(status_code=422, detail="Unknown appliance load type.")
        household.add_appliance(appliance, item.quantity)
    return household


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/catalog")
def catalog():
    return {
        "cities": [
            {"name": city, "latitude": coordinates[0], "longitude": coordinates[1]}
            for city, coordinates in CITIES.items()
        ],
        "appliances": [
            {
                "key": row["key"],
                "name": row["name"],
                "watts": row["watts"],
                "kind": row["kind"],
                "duty_cycle": row["duty_cycle"],
                "default_hours": row["default_hours"],
            }
            for row in APPLIANCE_TABLE.values()
        ],
    }


@app.post("/api/parse")
def parse_text(request: ParseInput):
    parsed = parse_appliance_text(request.text.strip(), MATCHER)
    return {
        "items": [
            {
                "original": item["original"],
                "phrase": item["phrase"],
                "key": item["row"]["key"] if item.get("row") else None,
                "name": item["row"]["name"] if item.get("row") else None,
                "watts": item["row"]["watts"] if item.get("row") else None,
                "kind": item["row"]["kind"] if item.get("row") else None,
                "duty_cycle": item["row"]["duty_cycle"] if item.get("row") else None,
                "default_hours": item["row"]["default_hours"] if item.get("row") else None,
                "quantity": item["quantity"],
                "hours": item["hours"],
                "score": item["score"],
                "ambiguous_ac": item.get("ambiguous_ac", False),
                "error": item.get("error"),
            }
            for item in parsed
        ]
    }


@app.post("/api/analyze")
def analyze(plan: PlanInput):
    household = _household(plan)
    try:
        client = WeatherClient(plan.city)
        hourly = client.fetch_history()
        frame = hourly_dataframe(hourly)
        estimate = SolarEstimator(hourly).recommend_size(household.total_daily_kwh())
    except (WeatherDataError, AnalysisDataError, SolarDataError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    daily_kwh = household.total_daily_kwh()
    breakdown = [
        {
            "name": appliance.name,
            "quantity": quantity,
            "watts": appliance.watts,
            "hours": appliance.hours_per_day,
            "daily_kwh": appliance.daily_kwh() * quantity,
            "type": "cycling" if isinstance(appliance, CyclingAppliance) else "constant",
        }
        for appliance, quantity in household._items
    ]
    total = sum(item["daily_kwh"] for item in breakdown)
    for item in breakdown:
        item["share"] = item["daily_kwh"] / total * 100 if total else 0

    daily_weather = frame.resample("D").agg(
        radiation=("shortwave_radiation", "mean"),
        cloud=("cloud_cover", "mean"),
        temperature=("temperature_2m", "mean"),
    ).dropna(subset=["radiation"])
    radiation_days = [
        {"date": timestamp.strftime("%Y-%m-%d"), "value": round(float(value), 2)}
        for timestamp, value in daily_weather["radiation"].items()
    ]
    cloud_values = frame["cloud_cover"].dropna()

    generation = estimate["monthly_output_kwh"]
    months = [
        {
            "month": month,
            "generation_kwh": round(value, 1),
            "demand_kwh": round(monthly_demand_kwh(daily_kwh, month), 1),
        }
        for month, value in generation.items()
    ]

    models = None
    actual_vs_predicted = []
    forecast = {"available": False, "message": "Forecast unavailable."}
    try:
        predictor = SolarPredictor(frame)
        results = predictor.train()
        if predictor.test_dates is None:
            raise PredictionDataError("Prediction training produced no held-out dates.")
        models = {
            name: {
                "mae": round(metrics["MAE"], 3),
                "rmse": round(metrics["RMSE"], 3),
                "r2": round(metrics["R2"], 3),
            }
            for name, metrics in results.items()
        }
        best_name = min(results, key=lambda name: results[name]["RMSE"])
        actual_vs_predicted = [
            {
                "date": timestamp.strftime("%Y-%m-%d"),
                "actual": round(float(actual), 3),
                "predicted": round(float(predicted), 3),
            }
            for timestamp, actual, predicted in zip(
                predictor.test_dates,
                predictor.actual,
                results[best_name]["predictions"],
            )
        ]
        try:
            forecast_client = WeatherClient(plan.city)
            forecast_frame = hourly_dataframe(forecast_client.fetch_forecast())
            tomorrow = predictor.tomorrow()
            model_name, predicted = predictor.predict_from_forecast(
                forecast_frame, target_day=tomorrow
            )
            forecast = {
                "available": True,
                "date": tomorrow.isoformat(),
                "radiation_kwh_m2": round(predicted, 2),
                "model": model_name,
                "source": forecast_client.last_source,
            }
        except (WeatherDataError, AnalysisDataError, PredictionDataError) as error:
            forecast = {"available": False, "message": str(error)}
    except PredictionDataError as error:
        models = {"unavailable": {"message": str(error)}}

    return {
        "city": plan.city,
        "source": client.last_source,
        "archive": {
            "start": frame.index.min().strftime("%Y-%m-%d"),
            "end": frame.index.max().strftime("%Y-%m-%d"),
            "hours": len(frame),
            "mean_cloud_cover": round(float(cloud_values.mean()), 1)
            if not cloud_values.empty else None,
            "max_irradiance": round(float(frame["shortwave_radiation"].max()), 1),
        },
        "consumption": {
            "daily_kwh": round(daily_kwh, 3),
            "monthly_kwh": round(daily_kwh * 30, 1),
        },
        "appliances": breakdown,
        "recommendation": {
            "capacity_kwp": round(estimate["capacity_kwp"], 2),
            "panel_count": estimate["panel_count"],
            "panel_wattage": estimate["panel_wattage"],
            "inverter_kw": estimate["inverter_kw"],
            "worst_month": estimate["worst_month"],
            "worst_month_avg_daily_kwh": round(
                estimate["worst_month_avg_daily_kwh"], 2
            ),
            "performance_ratio": estimate["performance_ratio"],
            "capacity_margin": estimate["capacity_margin"],
            "missing_radiation_hours": estimate["missing_radiation_hours"],
        },
        "monthly": months,
        "radiation": radiation_days,
        "prediction": {
            "models": models,
            "best_model": min(models, key=lambda name: models[name]["rmse"])
            if models and "unavailable" not in models else None,
            "test_months": predictor.test_months if models and "unavailable" not in models else [],
            "actual_vs_predicted": actual_vs_predicted,
            "forecast": forecast,
        },
    }


@app.post("/api/report")
def report(plan: PlanInput):
    household = _household(plan)
    try:
        client = WeatherClient(plan.city)
        hourly = client.fetch_history()
        recommendation = SolarEstimator(hourly).recommend_size(household.total_daily_kwh())
    except (WeatherDataError, SolarDataError, ValueError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    daily_kwh = household.total_daily_kwh()
    stream = BytesIO()
    with PdfPages(stream) as pdf:
        fig = plt.figure(figsize=(8.27, 11.69), facecolor=PALETTE["paper"])
        fig.text(0.09, 0.92, "SOLARSENSE   /   FIELD REPORT", color=PALETTE["orange"],
                 fontsize=10, fontweight="bold", family="monospace")
        fig.text(0.09, 0.86, "A solar plan,\nmade for your home.", color=PALETTE["ink"],
                 fontsize=32, fontweight="bold", linespacing=1.12)
        fig.text(0.09, 0.73, f"{plan.city.upper()}   ·   {datetime.now():%d %B %Y}",
                 fontsize=10, family="monospace", color="#6e6960")
        fig.add_artist(Line2D([0.09, 0.91], [0.69, 0.69], color=PALETTE["ink"], lw=0.8))

        fig.text(0.09, 0.63, "DAILY HOUSEHOLD DEMAND", fontsize=8, family="monospace")
        fig.text(0.09, 0.55, f"{daily_kwh:.2f}", fontsize=36, fontweight="bold")
        fig.text(0.33, 0.57, "kWh / day", fontsize=10, family="monospace")
        fig.text(0.55, 0.63, "RECOMMENDED ARRAY", fontsize=8, family="monospace")
        fig.text(0.55, 0.56, f"{recommendation['capacity_kwp']:.2f} kWp",
                 fontsize=23, fontweight="bold", color=PALETTE["orange"])
        fig.text(0.55, 0.50,
                 f"{recommendation['panel_count']} × {recommendation['panel_wattage']:g} W panels"
                 f"   /   {recommendation['inverter_kw']:.1f} kW inverter",
                 fontsize=7, family="monospace")
        fig.add_artist(Line2D([0.09, 0.91], [0.45, 0.45], color=PALETTE["ink"], lw=0.6))
        fig.text(0.09, 0.41, "APPLIANCE PROFILE / QUANTITY · WATTS · HOURS · kWh PER DAY",
                 fontsize=7, family="monospace")
        lines = [
            f"{quantity:>2}× {appliance.name:<22.22} "
            f"{appliance.watts:g}W·{appliance.hours_per_day:g}h "
            f"{appliance.daily_kwh() * quantity:.2f}kWh"
            for appliance, quantity in household._items
        ]
        midpoint = (len(lines) + 1) // 2
        fig.text(0.09, 0.37, "\n".join(lines[:midpoint]), fontsize=5.5,
                 family="monospace", linespacing=1.25)
        fig.text(0.55, 0.37, "\n".join(lines[midpoint:]), fontsize=5.5,
                 family="monospace", linespacing=1.25)
        fig.text(0.09, 0.07,
                 f"Weather archive: {client.last_source} · {datetime.now():%Y-%m-%d}",
                 fontsize=7, family="monospace", color="#6e6960")
        fig.text(0.09, 0.04, "PLANNING ESTIMATE ONLY / NOT A SITE SURVEY OR ENGINEERING DESIGN",
                 fontsize=6, family="monospace", color="#6e6960")
        pdf.savefig(fig, facecolor=fig.get_facecolor())
        plt.close(fig)

        monthly = recommendation["monthly_output_kwh"]
        fig, axis = plt.subplots(figsize=(8.27, 11.69), facecolor=PALETTE["paper"])
        axis.set_facecolor(PALETTE["paper"])
        labels = list(monthly)
        values = list(monthly.values())
        demand = [monthly_demand_kwh(daily_kwh, month) for month in labels]
        x = np.arange(len(labels))
        axis.bar(x, values, color=PALETTE["orange"], width=0.58, label="Solar generation")
        axis.plot(x, demand, color=PALETTE["ink"], marker="o", lw=1.5, label="Household demand")
        axis.set_xticks(x, [datetime.strptime(month, "%Y-%m").strftime("%b") for month in labels])
        axis.set_ylabel("Estimated energy · kWh / month")
        axis.set_title("MONTHLY GENERATION   /   COMPARED WITH DEMAND", loc="left", pad=20)
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=0.2)
        axis.legend(frameon=False, loc="upper right")
        fig.subplots_adjust(left=0.12, right=0.94, top=0.88, bottom=0.25)
        fig.text(0.09, 0.15, "SIZING BASIS / LEAST-PRODUCTIVE MONTH",
                 fontsize=8, family="monospace")
        fig.text(
            0.09,
            0.11,
            f"{recommendation['worst_month']} · {recommendation['worst_month_avg_daily_kwh']:.2f} "
            "kWh/day/kWp · 82% performance ratio · 10% capacity margin",
            fontsize=8,
            color="#6e6960",
        )
        fig.text(
            0.09,
            0.07,
            "Roof orientation, shade, batteries and net-metering are not modelled.",
            fontsize=8,
            color="#6e6960",
        )
        pdf.savefig(fig, facecolor=fig.get_facecolor())
        plt.close(fig)

    filename = f"solarsense-{plan.city.lower()}-report.pdf"
    return Response(
        content=stream.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


WEB_DIST_DIR = BASE_DIR / "frontend" / "dist"
if WEB_DIST_DIR.is_dir():
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=str(WEB_DIST_DIR), html=True), name="web")
