#!/usr/bin/env python3
"""
Seed the PedalForce Bicycles 2025 demo dataset into Redis.

Generates 240 sales records (12 months x 5 categories x 4 regions) with
realistic seasonal and regional weighting, then stores the complete document
at ``dataset:pedalforce`` using RedisJSON.

Usage (standalone)::

    export REDIS_URL=redis://localhost:6379
    python scripts/seed_dataset.py

Usage (as a module)::

    from scripts.seed_dataset import seed_dataset
    await seed_dataset()          # uses REDIS_URL env-var
    await seed_dataset(redis_url="redis://my-host:6380")
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import redis.asyncio as aioredis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATASET_KEY = "dataset:pedalforce"

COMPANY_META: dict[str, Any] = {
    "dataset_id": "pedalforce",
    "company_name": "PedalForce Bicycles",
    "description": (
        "Fictional bicycle manufacturer \u2014 2025 monthly sales data "
        "across 5 product categories and 4 regions."
    ),
    "currency": "USD",
    "fiscal_year": 2025,
    "categories": ["Road Bikes", "Mountain Bikes", "E-Bikes", "Kids Bikes", "Accessories"],
    "regions": ["North", "South", "East", "West"],
}

# Annual totals per category -------------------------------------------------
#   total_revenue = total_units * avg_unit_price
CATEGORIES: dict[str, dict[str, int]] = {
    "Road Bikes":     {"total_units": 5_640,  "total_revenue": 7_332_000,  "avg_unit_price": 1_300},
    "Mountain Bikes": {"total_units": 4_320,  "total_revenue": 3_456_000,  "avg_unit_price": 800},
    "E-Bikes":        {"total_units": 3_480,  "total_revenue": 8_700_000,  "avg_unit_price": 2_500},
    "Kids Bikes":     {"total_units": 6_960,  "total_revenue": 2_088_000,  "avg_unit_price": 300},
    "Accessories":    {"total_units": 18_000, "total_revenue": 540_000,    "avg_unit_price": 30},
}

GRAND_TOTAL_REVENUE = 22_116_000  # sum of all category revenues

# Target monthly combined revenue (all categories) ---------------------------
#   Designed to show seasonality (summer peak, winter trough).
MONTHLY_REVENUE_TARGETS: dict[str, int] = {
    "2025-01": 1_105_800,
    "2025-02": 1_216_380,
    "2025-03": 1_548_120,
    "2025-04": 2_100_720,
    "2025-05": 2_543_040,
    "2025-06": 2_764_800,
    "2025-07": 2_654_520,
    "2025-08": 2_433_960,
    "2025-09": 1_879_560,
    "2025-10": 1_437_480,
    "2025-11": 1_216_380,
    "2025-12": 1_215_240,
}

# Seasonal weights derived from the monthly revenue targets.
SEASONAL_WEIGHTS: dict[str, float] = {
    month: rev / GRAND_TOTAL_REVENUE
    for month, rev in MONTHLY_REVENUE_TARGETS.items()
}

# Regional share of annual revenue (must sum to 1.0) -------------------------
REGIONAL_SHARES: dict[str, float] = {
    "North": 0.28,
    "South": 0.22,
    "East":  0.30,
    "West":  0.20,
}


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def build_records() -> list[dict[str, Any]]:
    """Return 240 sales records distributed by month, category, and region.

    For each (month, category, region) triple:
      - raw_revenue  = category_total_revenue * seasonal_weight * regional_share
      - units_sold   = max(1, round(raw_revenue / avg_unit_price))
      - revenue      = units_sold * avg_unit_price   (keeps whole-number dollars)
    """
    records: list[dict[str, Any]] = []

    for month, season_w in SEASONAL_WEIGHTS.items():
        for cat_name, cat_data in CATEGORIES.items():
            avg_price = cat_data["avg_unit_price"]
            annual_rev = cat_data["total_revenue"]

            for region, region_share in REGIONAL_SHARES.items():
                raw_revenue = annual_rev * season_w * region_share
                units = max(1, round(raw_revenue / avg_price))
                revenue = units * avg_price

                records.append({
                    "month": month,
                    "category": cat_name,
                    "region": region,
                    "units_sold": units,
                    "revenue": revenue,
                    "avg_unit_price": avg_price,
                })

    return records


def build_dataset() -> dict[str, Any]:
    """Assemble the full dataset document ready for storage."""
    return {**COMPANY_META, "records": build_records()}


# ---------------------------------------------------------------------------
# Redis seeding
# ---------------------------------------------------------------------------

async def seed_dataset(
    redis_url: str | None = None,
    *,
    force: bool = True,
) -> dict[str, Any]:
    """Generate and store the PedalForce dataset in Redis.

    Parameters
    ----------
    redis_url:
        Redis connection string.  Falls back to the ``REDIS_URL`` environment
        variable, then ``redis://localhost:6379``.
    force:
        If *True* (the default), overwrite the key even if it already exists.

    Returns
    -------
    dict
        Summary with *status*, *key*, *record_count*, *total_revenue*, and
        *fiscal_year*.
    """
    url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379")
    r = aioredis.from_url(url, decode_responses=True)

    try:
        if not force and await r.exists(DATASET_KEY):
            return {
                "status": "skipped",
                "message": f"Key '{DATASET_KEY}' already exists. Pass force=True to overwrite.",
            }

        dataset = build_dataset()
        await r.json().set(DATASET_KEY, "$", dataset)

        record_count = len(dataset["records"])
        total_revenue = sum(rec["revenue"] for rec in dataset["records"])

        summary = {
            "status": "seeded",
            "key": DATASET_KEY,
            "record_count": record_count,
            "total_revenue": total_revenue,
            "fiscal_year": COMPANY_META["fiscal_year"],
        }

        print(
            f"Seeded {summary['key']} \u2014 "
            f"{summary['record_count']} records, "
            f"FY{summary['fiscal_year']}"
        )

        return summary
    finally:
        await r.aclose()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

async def _main() -> None:
    await seed_dataset()


if __name__ == "__main__":
    asyncio.run(_main())
