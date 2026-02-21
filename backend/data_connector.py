"""
VoxVisual data connector — fetches and aggregates sales data from Redis.

This module provides:
    - FETCH_DATA_TOOL: The tool definition dict passed to Claude's API so the
      model knows how to call ``fetch_data``.
    - handle_fetch_data(): An async function that resolves a ``fetch_data``
      tool call against a Redis JSON dataset.

Usage::

    from backend.data_connector import FETCH_DATA_TOOL, handle_fetch_data

    # Pass FETCH_DATA_TOOL to Claude via the ``tools`` parameter.
    # When Claude returns a tool_use block for "fetch_data", resolve it:
    result_json = await handle_fetch_data(tool_block.input)
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any

import redis.asyncio as aioredis

# ---------------------------------------------------------------------------
# Tool definition (matches Technical Implementation Plan Phase 2d)
# ---------------------------------------------------------------------------

FETCH_DATA_TOOL: dict[str, Any] = {
    "name": "fetch_data",
    "description": (
        "Retrieve sales data from a connected dataset stored in Redis. "
        "Returns filtered JSON records. Always call this tool before generating "
        "a visualization \u2014 never invent data."
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
                        "description": (
                            "Filter by month(s), e.g. ['2025-01', '2025-06']"
                        ),
                    },
                    "categories": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filter by product category, e.g. ['E-Bikes', 'Road Bikes']"
                        ),
                    },
                    "regions": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Filter by region, e.g. ['East', 'West']"
                        ),
                    },
                },
            },
            "group_by": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["month", "category", "region"],
                },
                "description": (
                    "Dimensions to group/aggregate by. Revenue and units are "
                    "summed; avg_unit_price is weighted."
                ),
            },
        },
        "required": ["dataset_id"],
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_REDIS_URL = "redis://localhost:6379"


def _get_redis_url(override: str | None = None) -> str:
    """Return the Redis URL from *override*, ``REDIS_URL`` env-var, or the default."""
    if override:
        return override
    return os.environ.get("REDIS_URL", _DEFAULT_REDIS_URL)


def _apply_filters(records: list[dict], filters: dict) -> list[dict]:
    """Return *records* narrowed by the optional month/category/region filters."""
    if not filters:
        return records

    months = filters.get("months")
    categories = filters.get("categories")
    regions = filters.get("regions")

    if months:
        month_set = set(months)
        records = [r for r in records if r["month"] in month_set]
    if categories:
        category_set = set(categories)
        records = [r for r in records if r["category"] in category_set]
    if regions:
        region_set = set(regions)
        records = [r for r in records if r["region"] in region_set]

    return records


def _apply_group_by(records: list[dict], group_by: list[str]) -> list[dict]:
    """Aggregate *records* along the given dimensions.

    - ``revenue`` and ``units_sold`` are summed.
    - ``avg_unit_price`` is computed as a weighted average
      (weighted by ``units_sold``).
    """
    if not group_by:
        return records

    groups: dict[tuple, dict] = defaultdict(
        lambda: {"units_sold": 0, "revenue": 0, "_weighted_price": 0.0}
    )

    for rec in records:
        key = tuple(rec[dim] for dim in group_by)
        bucket = groups[key]
        # Copy dimension values on first encounter
        if bucket["units_sold"] == 0 and bucket["revenue"] == 0:
            for dim in group_by:
                bucket[dim] = rec[dim]
        bucket["units_sold"] += rec["units_sold"]
        bucket["revenue"] += rec["revenue"]
        bucket["_weighted_price"] += rec["avg_unit_price"] * rec["units_sold"]

    aggregated: list[dict] = []
    for bucket in groups.values():
        total_units = bucket["units_sold"]
        weighted = bucket.pop("_weighted_price")
        bucket["avg_unit_price"] = (
            round(weighted / total_units, 2) if total_units else 0
        )
        aggregated.append(bucket)

    return aggregated


# ---------------------------------------------------------------------------
# Public async handler
# ---------------------------------------------------------------------------


async def handle_fetch_data(
    tool_input: dict,
    redis_url: str | None = None,
) -> str:
    """Resolve a ``fetch_data`` tool call against a Redis JSON dataset.

    Parameters
    ----------
    tool_input:
        The ``input`` dict from Claude's ``tool_use`` content block.  Must
        contain at least ``dataset_id``.  May optionally contain ``filters``
        and ``group_by``.
    redis_url:
        Redis connection string.  Falls back to the ``REDIS_URL`` environment
        variable, then ``redis://localhost:6379``.

    Returns
    -------
    str
        A JSON string with the keys ``dataset_id``, ``company_name``,
        ``currency``, ``record_count``, and ``records`` on success, or a
        JSON object with an ``error`` key if the dataset is not found.
    """
    url = _get_redis_url(redis_url)
    r = aioredis.from_url(url, decode_responses=True)

    try:
        dataset_id: str = tool_input["dataset_id"]
        raw = await r.json().get(f"dataset:{dataset_id}")

        if not raw:
            return json.dumps({"error": f"Dataset '{dataset_id}' not found"})

        records: list[dict] = raw["records"]

        # --- filtering ---
        filters = tool_input.get("filters") or {}
        records = _apply_filters(records, filters)

        # --- aggregation ---
        group_by = tool_input.get("group_by")
        if group_by:
            records = _apply_group_by(records, group_by)

        return json.dumps(
            {
                "dataset_id": dataset_id,
                "company_name": raw["company_name"],
                "currency": raw["currency"],
                "record_count": len(records),
                "records": records,
            }
        )
    finally:
        await r.aclose()
