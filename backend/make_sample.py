"""Generates sample_sales.csv: 6 months of daily sales for a fictional coffee shop (deterministic)."""
import csv
import random
from datetime import date, timedelta

random.seed(42)
PRODUCTS = {  # name: (category, price, base daily quantity)
    "Latte": ("Drinks", 4.75, 38), "Cold brew": ("Drinks", 4.25, 14), "Croissant": ("Food", 3.50, 22),
    "Bagel": ("Food", 2.95, 15), "Coffee beans (1 lb)": ("Retail", 15.00, 3),
}
LOCATIONS = {"Downtown": 1.0, "Riverside": 0.75, "Airport": 1.35}

with open("sample_sales.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["date", "location", "product", "category", "quantity", "revenue"])
    day = date(2026, 1, 1)
    while day <= date(2026, 6, 30):
        growth = 1 + (day - date(2026, 1, 1)).days / 181 * 0.18          # ~18% growth over 6 months
        weekend = 1.25 if day.weekday() >= 5 else 1.0
        for loc, loc_factor in LOCATIONS.items():
            for product, (category, price, base) in PRODUCTS.items():
                season = 1.0
                if product == "Cold brew":
                    season = 0.6 + (day.month - 1) * 0.28                    # cold brew climbs into summer
                if product == "Latte" and day.month >= 5:
                    season = 0.9
                qty = max(0, round(base * loc_factor * growth * weekend * season * random.uniform(0.8, 1.2)))
                w.writerow([day.isoformat(), loc, product, category, qty, f"{qty * price:.2f}"])
        day += timedelta(days=1)
