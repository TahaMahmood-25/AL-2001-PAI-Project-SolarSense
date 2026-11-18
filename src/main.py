"""SolarSense - console menu (skeleton).

Run from the repository root:  python src/main.py
Parts marked TODO are built by Member B and plugged in later.
"""
from appliances import Household, create_appliance, load_appliance_table
from config import APPLIANCE_CSV, CITIES
from report import save_report
from weather import WeatherClient, WeatherDataError


def read_number(prompt, low, high, as_int=False):
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


def check_weather(city):
    """Fetch (or load saved) history for the city and print a quick check."""
    try:
        hourly = WeatherClient(city).fetch_history()
    except WeatherDataError as error:
        print(f"Weather data problem: {error}")
        return
    values = [v for v in hourly["shortwave_radiation"] if v is not None]
    print(f"Got {len(hourly['time'])} hourly rows for {city}.")
    print(f"Strongest sunshine in the year: {max(values):g} W/m2")


def save_report_from_menu(household):
    """Save the TXT report and tell the user where it went (or what failed)."""
    try:
        path = save_report(household)
    except ValueError as error:
        print(error)
    except OSError as error:
        print(f"Could not save the report: {error}")
    else:
        print(f"Report saved to {path}")


def main():
    """Run the menu loop."""
    try:
        table = load_appliance_table(APPLIANCE_CSV)
    except FileNotFoundError:
        print(f"Cannot find the appliance table at {APPLIANCE_CSV}.")
        return
    household = Household()
    while True:
        print("\n=== SolarSense ===")
        print("1. Choose city")
        print("2. Add an appliance from the list")
        print("3. Type appliances in plain words   (TODO - Member B)")
        print("4. Show my appliances and daily use")
        print("5. Check weather data")
        print("6. Recommend a solar system         (TODO - Member B)")
        print("7. Save a report (TXT)")
        print("0. Exit")
        choice = read_number("Choose: ", 0, 7, as_int=True)
        if choice == 0:
            print("Goodbye!")
            break
        if choice == 1:
            household.city = choose_city()
            print(f"City set to {household.city}.")
        elif choice == 2:
            add_appliance_from_list(household, table)
        elif choice == 4:
            print("No appliances yet." if household.is_empty() else household.summary())
        elif choice == 5:
            check_weather(household.city)
        elif choice == 7:
            save_report_from_menu(household)
        else:
            print("Not built yet.")


if __name__ == "__main__":
    main()
