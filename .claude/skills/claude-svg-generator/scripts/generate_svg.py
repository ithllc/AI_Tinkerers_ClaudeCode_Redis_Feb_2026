#!/usr/bin/env python3
"""
Runs the full VoxVisual SVG generation pipeline for a given voice transcript.

Usage:
    python generate_svg.py "Show me 2025 sales by category" \
        --session-id demo-001 --user-id demo-user

Requires:
    - ANTHROPIC_API_KEY environment variable
    - Redis running with the PedalForce dataset seeded
    - Redis Agent Memory Server running (default http://localhost:8000)
"""

import argparse
import asyncio
import json
import os
import sys

try:
    import anthropic
except ImportError:
    print("Error: anthropic package required. Install with: pip install anthropic")
    sys.exit(1)

try:
    import redis as redis_lib
except ImportError:
    print("Error: redis package required. Install with: pip install redis[hiredis]")
    sys.exit(1)


# ---------------------------------------------------------------------------
# fetch_data tool definition (matches Technical Implementation Plan Phase 2d)
# ---------------------------------------------------------------------------

FETCH_DATA_TOOL = {
    "name": "fetch_data",
    "description": (
        "Retrieve sales data from a connected dataset stored in Redis. "
        "Returns filtered JSON records. Always call this tool before generating "
        "a visualization — never invent data."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "dataset_id": {
                "type": "string",
                "description": "The dataset to query, e.g. 'pedalforce'",
            },
            "filters": {
                "type": "object",
                "description": "Optional filters to narrow the data",
                "properties": {
                    "months": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by month(s), e.g. ['2025-01', '2025-06']",
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by product category, e.g. ['E-Bikes', 'Road Bikes']",
                    },
                    "regions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Filter by region, e.g. ['East', 'West']",
                    },
                },
            },
            "group_by": {
                "type": "array",
                "items": {"type": "string", "enum": ["month", "category", "region"]},
                "description": "Dimensions to group/aggregate by. Revenue and units are summed; avg_unit_price is weighted.",
            },
        },
        "required": ["dataset_id"],
    },
}

SYSTEM_PROMPT_TEMPLATE = """You are a senior data visualization designer. You output only valid SVG and CSS.
Use <animate> tags for motion. Ensure the SVG is responsive (width='100%').
You have access to the `fetch_data` tool — always call it to get real data before
generating a visualization. Never invent or hallucinate data.

{memory_context}

Return your response as a JSON object with exactly three keys:
- "explanation": A 1-2 sentence insight for text-to-speech readback.
- "svg_code": A complete, valid <svg> element with animations.
- "css_styles": Any @keyframes or CSS rules the SVG needs."""


# ---------------------------------------------------------------------------
# fetch_data tool handler (resolves against Redis)
# ---------------------------------------------------------------------------

def handle_fetch_data(tool_input: dict, redis_url: str) -> str:
    """Resolve Claude's fetch_data tool call against Redis."""
    r = redis_lib.from_url(redis_url, decode_responses=True)
    dataset_id = tool_input["dataset_id"]

    raw = r.json().get(f"dataset:{dataset_id}")
    if not raw:
        return json.dumps({"error": f"Dataset '{dataset_id}' not found"})

    records = raw["records"]

    # Apply filters
    filters = tool_input.get("filters", {})
    if filters.get("months"):
        records = [rec for rec in records if rec["month"] in filters["months"]]
    if filters.get("categories"):
        records = [rec for rec in records if rec["category"] in filters["categories"]]
    if filters.get("regions"):
        records = [rec for rec in records if rec["region"] in filters["regions"]]

    # Apply group_by aggregation
    group_by = tool_input.get("group_by")
    if group_by:
        groups = {}
        for rec in records:
            key = tuple(rec[dim] for dim in group_by)
            if key not in groups:
                groups[key] = {"units_sold": 0, "revenue": 0, "_weighted_price": 0}
                for dim in group_by:
                    groups[key][dim] = rec[dim]
            groups[key]["units_sold"] += rec["units_sold"]
            groups[key]["revenue"] += rec["revenue"]
            groups[key]["_weighted_price"] += rec["avg_unit_price"] * rec["units_sold"]
        result = []
        for g in groups.values():
            g["avg_unit_price"] = (
                round(g.pop("_weighted_price") / g["units_sold"], 2) if g["units_sold"] else 0
            )
            result.append(g)
        records = result

    return json.dumps({
        "dataset_id": dataset_id,
        "company_name": raw["company_name"],
        "currency": raw["currency"],
        "record_count": len(records),
        "records": records,
    })


# ---------------------------------------------------------------------------
# Main generation pipeline
# ---------------------------------------------------------------------------

def generate(
    transcript: str,
    session_id: str,
    user_id: str,
    redis_url: str,
    memory_url: str,
) -> dict:
    """
    Run the full SVG generation pipeline.

    Returns:
        dict with keys: explanation, svg_code, css_styles, tool_calls_made
    """
    client = anthropic.Anthropic()

    # Build memory context (simplified — in production, call memory server)
    memory_context = f"Session: {session_id} | User: {user_id}"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(memory_context=memory_context)

    messages = [{"role": "user", "content": transcript}]
    tool_calls_made = []

    # Tool-use loop (max 5 rounds to prevent infinite loops)
    for _ in range(5):
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=system_prompt,
            tools=[FETCH_DATA_TOOL],
            messages=messages,
        )

        # Check if Claude wants to use a tool
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # No more tool calls — extract final response
            break

        # Resolve each tool call
        tool_results = []
        for tool_block in tool_use_blocks:
            if tool_block.name == "fetch_data":
                result = handle_fetch_data(tool_block.input, redis_url)
                tool_calls_made.append({
                    "tool": "fetch_data",
                    "input": tool_block.input,
                    "record_count": json.loads(result).get("record_count", 0),
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_block.id,
                    "content": result,
                })

        # Append assistant response and tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
    else:
        return {"error": "Tool-use loop exceeded maximum rounds (5)"}

    # Extract text response
    text_blocks = [b for b in response.content if hasattr(b, "text")]
    if not text_blocks:
        return {"error": "No text response from Claude after tool-use loop"}

    raw_text = text_blocks[0].text

    # Parse JSON response
    try:
        result = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
        if match:
            result = json.loads(match.group(1))
        else:
            return {"error": "Failed to parse JSON from Claude response", "raw": raw_text}

    result["tool_calls_made"] = tool_calls_made
    return result


def main():
    parser = argparse.ArgumentParser(description="VoxVisual SVG generation pipeline")
    parser.add_argument("transcript", help="The user's voice transcript")
    parser.add_argument("--session-id", default="demo-001", help="Session identifier")
    parser.add_argument("--user-id", default="demo-user", help="User identifier")
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("REDIS_URL", "redis://localhost:6379"),
        help="Redis connection URL",
    )
    parser.add_argument(
        "--memory-url",
        default=os.environ.get("MEMORY_URL", "http://localhost:8000"),
        help="Redis Agent Memory Server URL",
    )
    parser.add_argument("--output-file", help="Write JSON response to file")
    args = parser.parse_args()

    result = generate(
        transcript=args.transcript,
        session_id=args.session_id,
        user_id=args.user_id,
        redis_url=args.redis_url,
        memory_url=args.memory_url,
    )

    output = json.dumps(result, indent=2)

    if args.output_file:
        with open(args.output_file, "w") as f:
            f.write(output)
        print(f"Response written to {args.output_file}")
    else:
        print(output)

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
