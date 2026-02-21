#!/usr/bin/env python3
"""
Validates the PedalForce demo dataset stored in Redis.

Usage:
    python validate_dataset.py [--redis-url REDIS_URL] [--verbose]

Checks:
    - Key exists and is valid JSON
    - 240 records present
    - All 5 categories and 4 regions represented
    - Each month has exactly 20 records
    - Revenue totals are plausible
"""

import argparse
import json
import os
import sys
from collections import Counter

try:
    import redis
except ImportError:
    print("Error: redis package required. Install with: pip install redis[hiredis]")
    sys.exit(1)


DATASET_KEY = "dataset:pedalforce"
EXPECTED_RECORDS = 240
EXPECTED_CATEGORIES = {"Road Bikes", "Mountain Bikes", "E-Bikes", "Kids Bikes", "Accessories"}
EXPECTED_REGIONS = {"North", "South", "East", "West"}
EXPECTED_MONTHS = 12
RECORDS_PER_MONTH = 20  # 5 categories x 4 regions


def validate(redis_url: str, verbose: bool = False) -> dict:
    """
    Validate the PedalForce dataset in Redis.

    Returns:
        dict with passed (bool), checks (list of check results), summary (str)
    """
    r = redis.from_url(redis_url, decode_responses=True)
    checks = []

    # 1. Key exists
    raw = r.json().get(DATASET_KEY)
    if not raw:
        return {
            "passed": False,
            "checks": [{"name": "key_exists", "passed": False, "detail": f"Key '{DATASET_KEY}' not found"}],
            "summary": f"FAIL: Key '{DATASET_KEY}' not found in Redis",
        }
    checks.append({"name": "key_exists", "passed": True, "detail": "Key exists"})

    records = raw.get("records", [])

    # 2. Record count
    count_ok = len(records) == EXPECTED_RECORDS
    checks.append({
        "name": "record_count",
        "passed": count_ok,
        "detail": f"{len(records)} records (expected {EXPECTED_RECORDS})",
    })

    # 3. Categories
    found_categories = set(r["category"] for r in records)
    cat_ok = found_categories == EXPECTED_CATEGORIES
    checks.append({
        "name": "categories",
        "passed": cat_ok,
        "detail": f"Found: {sorted(found_categories)}",
    })

    # 4. Regions
    found_regions = set(r["region"] for r in records)
    reg_ok = found_regions == EXPECTED_REGIONS
    checks.append({
        "name": "regions",
        "passed": reg_ok,
        "detail": f"Found: {sorted(found_regions)}",
    })

    # 5. Monthly distribution
    month_counts = Counter(r["month"] for r in records)
    monthly_ok = len(month_counts) == EXPECTED_MONTHS and all(
        v == RECORDS_PER_MONTH for v in month_counts.values()
    )
    checks.append({
        "name": "monthly_distribution",
        "passed": monthly_ok,
        "detail": f"{len(month_counts)} months, records per month: {dict(month_counts)}" if not monthly_ok else f"{len(month_counts)} months, {RECORDS_PER_MONTH} records each",
    })

    # 6. Revenue sanity (should be > $10M and < $50M)
    total_revenue = sum(r["revenue"] for r in records)
    revenue_ok = 10_000_000 < total_revenue < 50_000_000
    checks.append({
        "name": "revenue_total",
        "passed": revenue_ok,
        "detail": f"${total_revenue:,.0f}",
    })

    # 7. No zero or negative values
    bad_records = [r for r in records if r["units_sold"] <= 0 or r["revenue"] <= 0]
    values_ok = len(bad_records) == 0
    checks.append({
        "name": "positive_values",
        "passed": values_ok,
        "detail": f"{len(bad_records)} records with zero/negative values" if not values_ok else "All values positive",
    })

    all_passed = all(c["passed"] for c in checks)

    return {
        "passed": all_passed,
        "checks": checks,
        "summary": f"{'PASS' if all_passed else 'FAIL'}: {sum(1 for c in checks if c['passed'])}/{len(checks)} checks passed — {len(records)} records, ${total_revenue:,.0f} revenue",
    }


def main():
    parser = argparse.ArgumentParser(description="Validate PedalForce dataset in Redis")
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL", "redis://localhost:6379"),
        help="Redis connection URL",
    )
    parser.add_argument("--verbose", action="store_true", help="Show all check details")
    args = parser.parse_args()

    result = validate(args.redis_url, args.verbose)
    print(result["summary"])

    if args.verbose or not result["passed"]:
        for check in result["checks"]:
            status = "PASS" if check["passed"] else "FAIL"
            print(f"  [{status}] {check['name']}: {check['detail']}")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
