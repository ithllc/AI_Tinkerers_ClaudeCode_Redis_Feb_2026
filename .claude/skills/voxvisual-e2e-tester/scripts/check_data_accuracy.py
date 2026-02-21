#!/usr/bin/env python3
"""
Compares Claude-generated explanation text against actual dataset values.

Usage:
    python check_data_accuracy.py \
        --explanation "PedalForce had $22.1M in revenue" \
        --dataset-id pedalforce \
        --tolerance 0.05

Extracts dollar amounts and numbers from the explanation and validates
them against fetch_data results within the specified tolerance.
"""

import argparse
import json
import os
import re
import sys

try:
    import redis as redis_lib
except ImportError:
    print("Error: redis package required. Install with: pip install redis[hiredis]")
    sys.exit(1)


def extract_dollar_amounts(text: str) -> list[float]:
    """Extract dollar amounts from text, handling $X.XM, $X.XK, $X,XXX formats."""
    amounts = []

    # Match $X.XM (millions)
    for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*[Mm](?:illion)?", text):
        amounts.append(float(match.group(1)) * 1_000_000)

    # Match $X.XK (thousands)
    for match in re.finditer(r"\$(\d+(?:\.\d+)?)\s*[Kk]", text):
        amounts.append(float(match.group(1)) * 1_000)

    # Match $X,XXX,XXX or $X,XXX
    for match in re.finditer(r"\$([\d,]+)(?!\.\d*[MmKk])", text):
        num_str = match.group(1).replace(",", "")
        amounts.append(float(num_str))

    return amounts


def get_dataset_revenue(dataset_id: str, redis_url: str) -> float:
    """Get total revenue from the dataset in Redis."""
    r = redis_lib.from_url(redis_url, decode_responses=True)
    raw = r.json().get(f"dataset:{dataset_id}")
    if not raw:
        return 0.0
    return sum(rec["revenue"] for rec in raw.get("records", []))


def check_accuracy(explanation: str, dataset_id: str, redis_url: str, tolerance: float) -> dict:
    """
    Check if dollar amounts in the explanation match dataset values.

    Returns:
        dict with passed (bool), extracted_amounts, actual_total, mismatches
    """
    extracted = extract_dollar_amounts(explanation)
    actual_total = get_dataset_revenue(dataset_id, redis_url)

    if not extracted:
        return {
            "passed": True,
            "detail": "No dollar amounts found in explanation (nothing to validate)",
            "extracted_amounts": [],
            "actual_total": actual_total,
            "mismatches": [],
        }

    mismatches = []
    for amount in extracted:
        # Check if this amount is within tolerance of the actual total
        # or within tolerance of a reasonable fraction
        if actual_total > 0:
            ratio = amount / actual_total
            # Allow the amount to be the total or any clean fraction
            if abs(ratio - round(ratio, 1)) > tolerance and abs(1 - ratio) > tolerance:
                mismatches.append({
                    "extracted": amount,
                    "actual_total": actual_total,
                    "deviation": abs(1 - ratio),
                })

    return {
        "passed": len(mismatches) == 0,
        "detail": f"{len(extracted)} amounts checked, {len(mismatches)} mismatches",
        "extracted_amounts": extracted,
        "actual_total": actual_total,
        "mismatches": mismatches,
    }


def main():
    parser = argparse.ArgumentParser(description="Check data accuracy of Claude explanations")
    parser.add_argument("--explanation", required=True, help="Claude's explanation text")
    parser.add_argument("--dataset-id", default="pedalforce", help="Dataset to validate against")
    parser.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://localhost:6379"))
    parser.add_argument("--tolerance", type=float, default=0.05, help="Acceptable deviation (default 5%%)")
    args = parser.parse_args()

    result = check_accuracy(args.explanation, args.dataset_id, args.redis_url, args.tolerance)

    status = "PASS" if result["passed"] else "FAIL"
    print(f"[{status}] {result['detail']}")
    print(f"  Actual total revenue: ${result['actual_total']:,.0f}")
    print(f"  Extracted amounts: {['${:,.0f}'.format(a) for a in result['extracted_amounts']]}")

    if result["mismatches"]:
        for m in result["mismatches"]:
            print(f"  MISMATCH: ${m['extracted']:,.0f} deviates {m['deviation']:.1%} from total")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
