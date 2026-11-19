"""Save the results of a SolarSense session as a plain-text report."""
from datetime import datetime
from uuid import uuid4

from config import RESULTS_DIR


def build_report_text(household, extra_lines=None):
    """Return the whole report as one string.

    extra_lines: optional list of text lines (for example the solar
    recommendation) that are added after the household summary.
    """
    lines = [
        "SolarSense report",
        "=" * 40,
        f"Created: {datetime.now():%Y-%m-%d %H:%M}",
        "",
        household.summary(),
    ]
    if extra_lines:
        lines.append("")
        lines.extend(extra_lines)
    lines += [
        "",
        "Note: all numbers are estimates for planning, not engineering advice.",
        "Weather data by Open-Meteo.com",
    ]
    return "\n".join(lines)


def save_report(household, extra_lines=None, folder=RESULTS_DIR):
    """Write the report to a new .txt file and return its path.

    Raises ValueError if the household has no appliances, and OSError if the
    file cannot be written (the menu handles both).
    """
    if household.is_empty():
        raise ValueError("Add at least one appliance before saving a report.")
    folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = folder / f"solarsense_report_{timestamp}_{uuid4().hex[:8]}.txt"
    with open(path, "x", encoding="utf-8") as file:
        file.write(build_report_text(household, extra_lines))
    return path
