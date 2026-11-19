"""Appliance classes, the appliance table loader and the Household container."""
import csv
import math
from abc import ABC, abstractmethod

from config import APPLIANCE_CSV


class Appliance(ABC):
    """Abstract base class for anything in the home that uses electricity.

    The attributes are private. They are read through properties, and the
    setters check the values so an appliance can never hold nonsense.
    """

    def __init__(self, name, watts, hours_per_day):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("appliance name cannot be empty")
        self._name = name
        self._watts = 0.0
        self._hours_per_day = 0.0
        self.watts = watts                  # goes through the checking setter
        self.hours_per_day = hours_per_day  # goes through the checking setter

    @property
    def name(self):
        """Name of the appliance."""
        return self._name

    @property
    def watts(self):
        """Power drawn while running, in watts."""
        return self._watts

    @watts.setter
    def watts(self, value):
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError("watts must be greater than 0")
        self._watts = value

    @property
    def hours_per_day(self):
        """Hours the appliance is switched on each day."""
        return self._hours_per_day

    @hours_per_day.setter
    def hours_per_day(self, value):
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 24:
            raise ValueError("hours per day must be between 0 and 24")
        self._hours_per_day = value

    @abstractmethod
    def daily_kwh(self):
        """Return the electricity used in one day, in kWh."""

    def describe(self):
        """Return a one-line description of this appliance."""
        return (f"{self._name}: {self._watts:g} W x {self._hours_per_day:g} h "
                f"= {self.daily_kwh():.2f} kWh/day")


class ConstantLoadAppliance(Appliance):
    """Appliance that draws its full power for every hour it is on (fan, light)."""

    def daily_kwh(self):
        """Return watts x hours / 1000."""
        return self._watts * self._hours_per_day / 1000


class CyclingAppliance(Appliance):
    """Appliance whose compressor or heater switches on and off (fridge, AC).

    The duty cycle is the fraction of the 'on' time it really draws power.
    """

    def __init__(self, name, watts, hours_per_day, duty_cycle=0.5):
        super().__init__(name, watts, hours_per_day)
        duty_cycle = float(duty_cycle)
        if not math.isfinite(duty_cycle) or not 0 < duty_cycle <= 1:
            raise ValueError("duty cycle must be above 0 and at most 1")
        self._duty_cycle = duty_cycle

    @property
    def duty_cycle(self):
        """Fraction of the running time the appliance actually draws power."""
        return self._duty_cycle

    def daily_kwh(self):
        """Return watts x hours x duty cycle / 1000."""
        return self._watts * self._hours_per_day * self._duty_cycle / 1000


def load_appliance_table(path=APPLIANCE_CSV):
    """Read the appliance CSV and return a dict: key -> row of typed values.

    A dictionary is the right structure because we always look an appliance
    up by its key. Bad rows are skipped with a message instead of crashing.
    Raises FileNotFoundError if the CSV is missing (the menu handles it).
    """
    table = {}
    with open(path, newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            try:
                key = row["key"].strip().lower()
                table[key] = {
                    "key": key,
                    "name": row["name"].strip(),
                    "watts": float(row["watts"]),
                    "kind": row["kind"].strip().lower(),
                    "duty_cycle": float(row["duty_cycle"]),
                    "default_hours": float(row["default_hours"]),
                    "aliases": [a.strip().lower()
                                for a in row["aliases"].split(";") if a.strip()],
                }
            except (KeyError, ValueError, AttributeError) as error:
                print(f"Skipping a bad row in {path}: {error!r}")
    return table


def create_appliance(row, hours=None):
    """Build the right Appliance subclass from one table row.

    hours: hours per day; if None the typical default from the table is used.
    """
    if hours is None:
        hours = row["default_hours"]
    if row["kind"] == "cycling":
        return CyclingAppliance(row["name"], row["watts"], hours, row["duty_cycle"])
    return ConstantLoadAppliance(row["name"], row["watts"], hours)


class Household:
    """A home: a city plus the appliances in it."""

    def __init__(self, city="Karachi"):
        self.city = city
        self._items = []  # list of (appliance, quantity) tuples

    def add_appliance(self, appliance, quantity=1):
        """Add `quantity` copies of an appliance."""
        if isinstance(quantity, bool):
            raise ValueError("quantity must be a whole number")
        try:
            numeric_quantity = float(quantity)
        except (TypeError, ValueError):
            raise ValueError("quantity must be a whole number")
        if not numeric_quantity.is_integer() or numeric_quantity < 1:
            raise ValueError("quantity must be at least 1")
        quantity = int(numeric_quantity)
        self._items.append((appliance, quantity))

    def is_empty(self):
        """True if no appliance has been added yet."""
        return not self._items

    def total_daily_kwh(self):
        """Add up daily_kwh() of every appliance. Polymorphism: each object
        uses its own formula, whatever its type."""
        return sum(quantity * appliance.daily_kwh()
                   for appliance, quantity in self._items)

    def summary(self):
        """Return a multi-line text summary of the household."""
        lines = [f"Household in {self.city}:"]
        for appliance, quantity in self._items:
            lines.append(f"  {quantity} x {appliance.describe()}")
        lines.append(f"Total: {self.total_daily_kwh():.2f} kWh per day")
        return "\n".join(lines)
