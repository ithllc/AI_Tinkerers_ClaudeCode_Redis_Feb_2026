"""
Tests for Phase 2: Data Layer (seeder + fetch_data handler).

Run: python -m pytest tests/test_data_layer.py -v
Requires Redis Stack running with RedisJSON module.
"""

import asyncio
import json
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.seed_dataset import seed_dataset, build_dataset
from backend.data_connector import handle_fetch_data


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
def seed_data(event_loop):
    """Seed the dataset once for the whole module."""
    event_loop.run_until_complete(seed_dataset())


# ---------------------------------------------------------------------------
# Seeder tests
# ---------------------------------------------------------------------------

class TestSeeder:
    def test_record_count(self):
        ds = build_dataset()
        assert len(ds["records"]) == 240

    def test_schema_fields(self):
        ds = build_dataset()
        assert ds["dataset_id"] == "pedalforce"
        assert ds["company_name"] == "PedalForce Bicycles"
        assert ds["currency"] == "USD"
        assert ds["fiscal_year"] == 2025
        assert set(ds["categories"]) == {
            "Road Bikes", "Mountain Bikes", "E-Bikes", "Kids Bikes", "Accessories"
        }
        assert set(ds["regions"]) == {"North", "South", "East", "West"}

    def test_record_fields(self):
        ds = build_dataset()
        rec = ds["records"][0]
        required = {"month", "category", "region", "units_sold", "revenue", "avg_unit_price"}
        assert required.issubset(rec.keys())

    def test_all_combinations_present(self):
        ds = build_dataset()
        combos = {(r["month"], r["category"], r["region"]) for r in ds["records"]}
        assert len(combos) == 240


# ---------------------------------------------------------------------------
# fetch_data tests
# ---------------------------------------------------------------------------

class TestFetchData:
    def test_no_filter(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({"dataset_id": "pedalforce"})
        ))
        assert result["record_count"] == 240
        assert result["company_name"] == "PedalForce Bicycles"

    def test_filter_by_region(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({
                "dataset_id": "pedalforce",
                "filters": {"regions": ["East"]}
            })
        ))
        assert result["record_count"] == 60  # 12 months x 5 categories

    def test_filter_by_category(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({
                "dataset_id": "pedalforce",
                "filters": {"categories": ["E-Bikes", "Road Bikes"]}
            })
        ))
        assert result["record_count"] == 96  # 12 months x 2 cats x 4 regions

    def test_filter_by_month(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({
                "dataset_id": "pedalforce",
                "filters": {"months": ["2025-06"]}
            })
        ))
        assert result["record_count"] == 20  # 1 month x 5 cats x 4 regions

    def test_group_by_category(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({
                "dataset_id": "pedalforce",
                "group_by": ["category"]
            })
        ))
        assert result["record_count"] == 5
        categories = {r["category"] for r in result["records"]}
        assert categories == {"Road Bikes", "Mountain Bikes", "E-Bikes", "Kids Bikes", "Accessories"}

    def test_group_by_region(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({
                "dataset_id": "pedalforce",
                "group_by": ["region"]
            })
        ))
        assert result["record_count"] == 4

    def test_group_by_month(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({
                "dataset_id": "pedalforce",
                "group_by": ["month"]
            })
        ))
        assert result["record_count"] == 12

    def test_filter_and_group(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({
                "dataset_id": "pedalforce",
                "filters": {"regions": ["East"]},
                "group_by": ["category"]
            })
        ))
        assert result["record_count"] == 5

    def test_unknown_dataset(self, event_loop):
        result = json.loads(event_loop.run_until_complete(
            handle_fetch_data({"dataset_id": "nonexistent"})
        ))
        assert "error" in result
        assert "nonexistent" in result["error"]
