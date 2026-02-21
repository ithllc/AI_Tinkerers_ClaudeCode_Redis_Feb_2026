#!/usr/bin/env python3
"""
Executes the canonical 4-step VoxVisual demo walkthrough and produces a test report.

Usage:
    python run_demo_walkthrough.py --session-id test-001 --user-id test-user

Requires:
    - ANTHROPIC_API_KEY environment variable
    - Redis with PedalForce dataset seeded
    - Redis Agent Memory Server running
"""

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# Demo walkthrough steps (from PRD Section 5)
# ---------------------------------------------------------------------------

WALKTHROUGH_STEPS = [
    {
        "name": "Connect & Overview",
        "transcript": "Connect to the PedalForce dataset and let's look at the 2025 sales data",
        "assertions": [
            "tool_call_made",       # Claude must call fetch_data
            "svg_valid",            # Response contains valid SVG
            "has_animation",        # SVG has animation elements
            "mentions_pedalforce",  # Explanation mentions PedalForce
        ],
    },
    {
        "name": "Quarterly Breakdown",
        "transcript": "Break that down by quarter",
        "assertions": [
            "tool_call_made",
            "svg_valid",
            "has_animation",
            "svg_changed",          # SVG differs from previous step
        ],
    },
    {
        "name": "Regional Filter",
        "transcript": "Show me just the East region",
        "assertions": [
            "tool_call_made",
            "svg_valid",
            "has_animation",
            "filter_applied_east",  # fetch_data was called with East filter
        ],
    },
    {
        "name": "Best Month Query",
        "transcript": "What was our best month?",
        "assertions": [
            "tool_call_made",
            "svg_valid",
            "explanation_has_month", # Explanation names a specific month
        ],
    },
]


def check_svg_valid(svg_code: str) -> bool:
    """Check if SVG is valid XML."""
    try:
        ET.fromstring(svg_code)
        return True
    except ET.ParseError:
        return False


def check_has_animation(svg_code: str, css_styles: str = "") -> bool:
    """Check if SVG or CSS contains animation elements."""
    combined = svg_code + css_styles
    return bool(
        re.search(r"<animate[\s>]", combined)
        or re.search(r"<animateTransform[\s>]", combined)
        or re.search(r"@keyframes", combined)
    )


def run_assertions(step: dict, result: dict, prev_svg: str | None) -> list[dict]:
    """Run assertions for a single walkthrough step."""
    checks = []

    svg_code = result.get("svg_code", "")
    css_styles = result.get("css_styles", "")
    explanation = result.get("explanation", "")
    tool_calls = result.get("tool_calls_made", [])

    for assertion in step["assertions"]:
        if assertion == "tool_call_made":
            passed = len(tool_calls) > 0
            detail = f"{len(tool_calls)} tool call(s)" if passed else "No tool calls"

        elif assertion == "svg_valid":
            passed = check_svg_valid(svg_code)
            detail = "Valid XML" if passed else "Invalid XML"

        elif assertion == "has_animation":
            passed = check_has_animation(svg_code, css_styles)
            detail = "Animation found" if passed else "No animation elements"

        elif assertion == "mentions_pedalforce":
            passed = "pedalforce" in explanation.lower() or "pedal force" in explanation.lower()
            detail = "PedalForce mentioned" if passed else f"Not found in: {explanation[:100]}"

        elif assertion == "svg_changed":
            passed = prev_svg is not None and svg_code != prev_svg
            detail = "SVG differs from previous" if passed else "SVG unchanged"

        elif assertion == "filter_applied_east":
            passed = any(
                "East" in str(tc.get("input", {}).get("filters", {}).get("regions", []))
                for tc in tool_calls
            )
            detail = "East filter applied" if passed else "East filter not found in tool calls"

        elif assertion == "explanation_has_month":
            months = ["january", "february", "march", "april", "may", "june",
                      "july", "august", "september", "october", "november", "december"]
            passed = any(m in explanation.lower() for m in months)
            detail = "Month named" if passed else f"No month found in: {explanation[:100]}"

        else:
            passed = False
            detail = f"Unknown assertion: {assertion}"

        checks.append({"assertion": assertion, "passed": passed, "detail": detail})

    return checks


def run_walkthrough(session_id: str, user_id: str, redis_url: str, memory_url: str) -> dict:
    """
    Execute the full demo walkthrough.

    Returns:
        dict with steps (list of step results) and summary.
    """
    # Import the generator from the sibling skill
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../claude-svg-generator/scripts"))
    from generate_svg import generate

    step_results = []
    prev_svg = None
    total_passed = 0
    total_checks = 0

    for i, step in enumerate(WALKTHROUGH_STEPS):
        start = time.time()

        result = generate(
            transcript=step["transcript"],
            session_id=session_id,
            user_id=user_id,
            redis_url=redis_url,
            memory_url=memory_url,
        )

        elapsed = time.time() - start

        if "error" in result:
            checks = [{"assertion": "pipeline", "passed": False, "detail": result["error"]}]
        else:
            checks = run_assertions(step, result, prev_svg)
            prev_svg = result.get("svg_code")

        step_passed = all(c["passed"] for c in checks)
        total_passed += sum(1 for c in checks if c["passed"])
        total_checks += len(checks)

        step_results.append({
            "step": i + 1,
            "name": step["name"],
            "transcript": step["transcript"],
            "passed": step_passed,
            "elapsed_seconds": round(elapsed, 1),
            "checks": checks,
        })

    return {
        "steps": step_results,
        "summary": {
            "total_steps": len(WALKTHROUGH_STEPS),
            "steps_passed": sum(1 for s in step_results if s["passed"]),
            "total_checks": total_checks,
            "checks_passed": total_passed,
        },
    }


def format_report(results: dict) -> str:
    """Format test results as a readable report."""
    lines = ["=== VoxVisual E2E Demo Walkthrough Report ===", ""]

    for step in results["steps"]:
        status = "PASS" if step["passed"] else "FAIL"
        lines.append(f"  [{status}] Step {step['step']} — {step['name']} ({step['elapsed_seconds']}s)")
        if not step["passed"]:
            for check in step["checks"]:
                if not check["passed"]:
                    lines.append(f"         FAIL: {check['assertion']} — {check['detail']}")

    lines.append("")
    s = results["summary"]
    lines.append(
        f"SUMMARY: {s['checks_passed']}/{s['total_checks']} checks passed | "
        f"{s['steps_passed']}/{s['total_steps']} steps passed"
    )

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Run VoxVisual demo walkthrough test")
    parser.add_argument("--session-id", default="e2e-test-001")
    parser.add_argument("--user-id", default="e2e-test-user")
    parser.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://localhost:6379"))
    parser.add_argument("--memory-url", default=os.environ.get("MEMORY_URL", "http://localhost:8000"))
    parser.add_argument("--report-file", help="Write report to file")
    args = parser.parse_args()

    results = run_walkthrough(args.session_id, args.user_id, args.redis_url, args.memory_url)
    report = format_report(results)
    print(report)

    if args.report_file:
        with open(args.report_file, "w") as f:
            f.write(report)
        print(f"\nReport written to {args.report_file}")

    all_passed = results["summary"]["steps_passed"] == results["summary"]["total_steps"]
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
