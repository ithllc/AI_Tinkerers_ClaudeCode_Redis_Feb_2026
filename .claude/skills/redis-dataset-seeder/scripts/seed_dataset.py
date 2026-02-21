#!/usr/bin/env python3
"""
Seeds the PedalForce Bicycles demo dataset into Redis as a JSON document.

Usage:
    python seed_dataset.py [--redis-url REDIS_URL] [--force]

The dataset is stored at key `dataset:pedalforce` and contains 240 sales
records: 12 months x 5 categories x 4 regions for fiscal year 2025.
"""

import argparse
import json
import math
import os
import sys

try:
    import redis
except ImportError:
    print("Error: redis package required. Install with: pip install redis[hiredis]")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Dataset constants
# ---------------------------------------------------------------------------

DATASET_KEY = "dataset:pedalforce"

COMPANY = {
    "dataset_id": "pedalforce",
    "company_name": "PedalForce Bicycles",
    "description": (
        "Fictional bicycle manufacturer — 2025 monthly sales data "
        "across 5 product categories and 4 regions."
    ),
    "currency": "USD",
    "fiscal_year": 2025,
    "categories": ["Road Bikes", "Mountain Bikes", "E-Bikes", "Kids Bikes", "Accessories"],
    "regions": ["North", "South", "East", "West"],
}

# Annual totals per category
CATEGORY_ANNUAL = {
    "Road Bikes":     {"units": 5640,  "avg_price": 1300},
    "Mountain Bikes": {"units": 4320,  "avg_price": 800},
    "E-Bikes":        {"units": 3480,  "avg_price": 2500},
    "Kids Bikes":     {"units": 6960,  "avg_price": 300},
    "Accessories":    {"units": 18000, "avg_price": 30},
}

# Seasonal weights per month (must sum to 1.0)
SEASONAL_WEIGHTS = {
    "2025-01": 0.050,
    "2025-02": 0.055,
    "2025-03": 0.070,
    "2025-04": 0.095,
    "2025-05": 0.115,
    "2025-06": 0.125,
    "2025-07": 0.120,
    "2025-08": 0.110,
    "2025-09": 0.085,
    "2025-10": 0.065,
    "2025-11": 0.055,
    "2025-12": 0.055,
}

# Regional revenue share
REGIONAL_SHARES = {
    "North": 0.28,
    "South": 0.22,
    "East":  0.30,
    "West":  0.20,
}


def generate_records() -> list[dict]:
    """Generate 240 sales records with seasonal and regional weighting."""
    records = []

    for month, season_weight in SEASONAL_WEIGHTS.items():
        for category, cat_data in CATEGORY_ANNUAL.items():
            annual_units = cat_data["units"]
            avg_price = cat_data["avg_price"]

            for region, region_share in REGIONAL_SHARES.items():
                units = max(1, round(annual_units * season_weight * region_share))
                revenue = units * avg_price

                records.append({
                    "month": month,
                    "category": category,
                    "region": region,
                    "units_sold": units,
                    "revenue": revenue,
                    "avg_unit_price": avg_price,
                })

    return records


def build_dataset() -> dict:
    """Build the complete dataset document."""
    records = generate_records()
    dataset = {**COMPANY, "records": records}
    return dataset


def seed(redis_url: str, force: bool = False) -> dict:
    """
    Seed the PedalForce dataset into Redis.

    Returns:
        dict with status, record_count, and total_revenue.
    """
    r = redis.from_url(redis_url, decode_responses=True)

    # Check for existing key
    if not force and r.exists(DATASET_KEY):
        return {
            "status": "skipped",
            "message": f"Key '{DATASET_KEY}' already exists. Use --force to overwrite.",
        }

    dataset = build_dataset()
    r.json().set(DATASET_KEY, "$", dataset)

    total_revenue = sum(rec["revenue"] for rec in dataset["records"])
    record_count = len(dataset["records"])

    return {
        "status": "seeded",
        "key": DATASET_KEY,
        "record_count": record_count,
        "total_revenue": total_revenue,
        "fiscal_year": 2025,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed PedalForce demo dataset into Redis")
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL", "redis://localhost:6379"),
        help="Redis connection URL",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing dataset without prompting",
    )
    args = parser.parse_args()

    result = seed(args.redis_url, args.force)

    if result["status"] == "seeded":
        revenue_fmt = f"${result['total_revenue']:,.0f}"
        print(
            f"Seeded {result['key']} — "
            f"{result['record_count']} records, "
            f"{revenue_fmt} revenue, "
            f"FY{result['fiscal_year']}"
        )
    else:
        print(result["message"])
        sys.exit(1)


if __name__ == "__main__":
    main()
