#!/usr/bin/env python3
"""
Runs individual unit test checks for VoxVisual components.

Usage:
    python run_unit_tests.py [--redis-url REDIS_URL] [--memory-url MEMORY_URL] [--verbose]
"""

import argparse
import json
import os
import sys
import time

try:
    import redis as redis_lib
except ImportError:
    print("Error: redis package required. Install with: pip install redis[hiredis]")
    sys.exit(1)


def test_dataset_seeded(redis_url: str) -> dict:
    """Check that PedalForce dataset exists in Redis with 240 records."""
    r = redis_lib.from_url(redis_url, decode_responses=True)
    raw = r.json().get("dataset:pedalforce")
    if not raw:
        return {"passed": False, "detail": "dataset:pedalforce key not found"}
    count = len(raw.get("records", []))
    passed = count == 240
    return {"passed": passed, "detail": f"{count} records (expected 240)"}


def test_fetch_data_no_filter(redis_url: str) -> dict:
    """fetch_data with no filters returns all 240 records."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../claude-svg-generator/scripts"))
    from generate_svg import handle_fetch_data

    result = json.loads(handle_fetch_data({"dataset_id": "pedalforce"}, redis_url))
    if "error" in result:
        return {"passed": False, "detail": result["error"]}
    count = result["record_count"]
    return {"passed": count == 240, "detail": f"{count} records returned"}


def test_fetch_data_filter_region(redis_url: str) -> dict:
    """fetch_data with East region filter returns 60 records."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../claude-svg-generator/scripts"))
    from generate_svg import handle_fetch_data

    result = json.loads(handle_fetch_data(
        {"dataset_id": "pedalforce", "filters": {"regions": ["East"]}},
        redis_url,
    ))
    count = result.get("record_count", 0)
    return {"passed": count == 60, "detail": f"{count} records (expected 60)"}


def test_fetch_data_group_by(redis_url: str) -> dict:
    """fetch_data grouped by category returns 5 aggregated records."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../claude-svg-generator/scripts"))
    from generate_svg import handle_fetch_data

    result = json.loads(handle_fetch_data(
        {"dataset_id": "pedalforce", "group_by": ["category"]},
        redis_url,
    ))
    count = result.get("record_count", 0)
    return {"passed": count == 5, "detail": f"{count} grouped records (expected 5)"}


def test_fetch_data_unknown_dataset(redis_url: str) -> dict:
    """fetch_data with unknown dataset returns error."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../claude-svg-generator/scripts"))
    from generate_svg import handle_fetch_data

    result = json.loads(handle_fetch_data({"dataset_id": "nonexistent"}, redis_url))
    passed = "error" in result
    return {"passed": passed, "detail": result.get("error", "No error returned")}


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

TESTS = [
    ("test_dataset_seeded", test_dataset_seeded),
    ("test_fetch_data_no_filter", test_fetch_data_no_filter),
    ("test_fetch_data_filter_region", test_fetch_data_filter_region),
    ("test_fetch_data_group_by", test_fetch_data_group_by),
    ("test_fetch_data_unknown_dataset", test_fetch_data_unknown_dataset),
]


def run_all(redis_url: str, verbose: bool = False) -> dict:
    """Run all unit tests and return results."""
    results = []
    for name, fn in TESTS:
        start = time.time()
        try:
            result = fn(redis_url)
        except Exception as e:
            result = {"passed": False, "detail": f"Exception: {e}"}
        elapsed = time.time() - start
        results.append({"name": name, "elapsed": round(elapsed, 2), **result})

    passed = sum(1 for r in results if r["passed"])
    return {"tests": results, "passed": passed, "total": len(results)}


def main():
    parser = argparse.ArgumentParser(description="VoxVisual unit tests")
    parser.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://localhost:6379"))
    parser.add_argument("--memory-url", default=os.environ.get("MEMORY_URL", "http://localhost:8000"))
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    results = run_all(args.redis_url, args.verbose)

    print(f"=== VoxVisual Unit Tests ===\n")
    for t in results["tests"]:
        status = "PASS" if t["passed"] else "FAIL"
        print(f"  [{status}] {t['name']} ({t['elapsed']}s)")
        if args.verbose or not t["passed"]:
            print(f"         {t['detail']}")

    print(f"\nSUMMARY: {results['passed']}/{results['total']} passed")
    sys.exit(0 if results["passed"] == results["total"] else 1)


if __name__ == "__main__":
    main()
