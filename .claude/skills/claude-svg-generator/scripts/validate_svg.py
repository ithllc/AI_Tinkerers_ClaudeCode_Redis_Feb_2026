#!/usr/bin/env python3
"""
Validates that a generated SVG string is well-formed and contains animations.

Usage:
    python validate_svg.py '<svg>...</svg>'
    python validate_svg.py --file output.json

Checks:
    - Valid XML/SVG structure
    - Contains animation elements (<animate>, <animateTransform>, @keyframes)
    - Has responsive width attribute
    - No <script> tag injection
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET


def validate_svg(svg_string: str, css_string: str = "") -> dict:
    """
    Validate an SVG string for correctness, animations, and safety.

    Returns:
        dict with passed (bool), checks (list), summary (str)
    """
    checks = []

    # 1. Valid XML
    try:
        root = ET.fromstring(svg_string)
        checks.append({"name": "valid_xml", "passed": True, "detail": "Valid XML"})
    except ET.ParseError as e:
        checks.append({"name": "valid_xml", "passed": False, "detail": str(e)})
        return {
            "passed": False,
            "checks": checks,
            "summary": f"FAIL: Invalid XML — {e}",
        }

    # 2. Root element is <svg>
    tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
    is_svg = tag == "svg"
    checks.append({
        "name": "svg_root",
        "passed": is_svg,
        "detail": f"Root element: <{tag}>",
    })

    # 3. Responsive width
    width = root.get("width", "")
    has_responsive = width == "100%" or root.get("viewBox") is not None
    checks.append({
        "name": "responsive",
        "passed": has_responsive,
        "detail": f"width='{width}', viewBox={'present' if root.get('viewBox') else 'missing'}",
    })

    # 4. Contains animation elements
    svg_text = svg_string + css_string
    has_animate = bool(re.search(r"<animate[\s>]", svg_text))
    has_animate_transform = bool(re.search(r"<animateTransform[\s>]", svg_text))
    has_keyframes = bool(re.search(r"@keyframes", svg_text))
    has_animation = has_animate or has_animate_transform or has_keyframes

    animation_types = []
    if has_animate:
        animation_types.append("<animate>")
    if has_animate_transform:
        animation_types.append("<animateTransform>")
    if has_keyframes:
        animation_types.append("@keyframes")

    checks.append({
        "name": "has_animation",
        "passed": has_animation,
        "detail": f"Found: {', '.join(animation_types)}" if animation_types else "No animation elements found",
    })

    # 5. No script injection
    has_script = bool(re.search(r"<script[\s>]", svg_string, re.IGNORECASE))
    checks.append({
        "name": "no_script_injection",
        "passed": not has_script,
        "detail": "No <script> tags" if not has_script else "WARNING: <script> tag detected",
    })

    # 6. Reasonable size (under 100KB)
    size_kb = len(svg_string.encode()) / 1024
    size_ok = size_kb < 100
    checks.append({
        "name": "reasonable_size",
        "passed": size_ok,
        "detail": f"{size_kb:.1f} KB",
    })

    all_passed = all(c["passed"] for c in checks)
    return {
        "passed": all_passed,
        "checks": checks,
        "summary": f"{'PASS' if all_passed else 'FAIL'}: {sum(1 for c in checks if c['passed'])}/{len(checks)} checks",
    }


def main():
    parser = argparse.ArgumentParser(description="Validate SVG output from Claude")
    parser.add_argument("svg", nargs="?", help="SVG string to validate")
    parser.add_argument("--file", help="JSON file with svg_code and css_styles keys")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            data = json.load(f)
        svg_string = data.get("svg_code", "")
        css_string = data.get("css_styles", "")
    elif args.svg:
        svg_string = args.svg
        css_string = ""
    else:
        print("Error: Provide an SVG string or --file argument")
        sys.exit(1)

    result = validate_svg(svg_string, css_string)
    print(result["summary"])
    for check in result["checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        print(f"  [{status}] {check['name']}: {check['detail']}")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
