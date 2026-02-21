# Skill: voxvisual-e2e-tester

## Description
End-to-end testing skill for the VoxVisual proof-of-concept. Runs the canonical demo walkthrough, validates SVG output, checks data accuracy against the PedalForce dataset in Redis, verifies memory persistence, and produces a structured test report.

## When to Use
Invoke this skill when:
- Running the canonical demo walkthrough from the PRD (Section 5)
- Validating that the full pipeline works after code changes
- Checking SVG generation quality and animation presence
- Verifying data accuracy (generated charts match actual Redis data)
- Testing cross-session memory recall
- Producing a test report before a demo or review

## User Invocation
- "Run the e2e tests"
- "Run the demo walkthrough"
- "Test the full VoxVisual pipeline"
- "Validate the demo is working"

## Behavior

### Demo Walkthrough Test
Executes the 4-step canonical walkthrough from the PRD:

**Step 1 — Connect & Overview**
- Input: "Connect to the PedalForce dataset and let's look at the 2025 sales data"
- Assert: Claude calls `fetch_data` with `dataset_id: "pedalforce"`
- Assert: Response contains valid SVG with animations
- Assert: Explanation mentions PedalForce and revenue figures

**Step 2 — Quarterly Breakdown**
- Input: "Break that down by quarter"
- Assert: Claude calls `fetch_data` with `group_by: ["month"]` or similar quarterly aggregation
- Assert: SVG differs from Step 1 (new visualization)
- Assert: Working memory `current_filters` updated

**Step 3 — Regional Filter**
- Input: "Show me just the East region"
- Assert: Claude calls `fetch_data` with `filters.regions: ["East"]`
- Assert: Returned data contains only East records
- Assert: Revenue totals match known East-region figures (~30% of grand total)

**Step 4 — Best Month Query**
- Input: "What was our best month?"
- Assert: Claude calls `fetch_data` with appropriate grouping
- Assert: Explanation identifies the correct peak month from the filtered data
- Assert: SVG highlights or emphasizes the peak month

### Unit Test Suite
Individual checks that can be run independently:

| Test | What It Checks |
|---|---|
| `test_dataset_seeded` | PedalForce dataset exists in Redis with 240 records |
| `test_fetch_data_no_filter` | `fetch_data({dataset_id: "pedalforce"})` returns 240 records |
| `test_fetch_data_filter_region` | Region filter returns correct subset (60 records for one region) |
| `test_fetch_data_group_by` | Group-by aggregation produces correct sums |
| `test_svg_valid_xml` | Generated SVG parses as valid XML |
| `test_svg_has_animation` | SVG contains `<animate>`, `<animateTransform>`, or `@keyframes` |
| `test_svg_responsive` | SVG has `width="100%"` or `viewBox` |
| `test_svg_no_script` | SVG contains no `<script>` tags |
| `test_working_memory_roundtrip` | PUT then GET returns same session data |
| `test_memory_extraction` | Background extraction produces long-term memory records |
| `test_cross_session_recall` | New session retrieves preferences from long-term memory |

### Test Report Format
```
=== VoxVisual E2E Test Report ===
Date: 2026-02-21
Environment: redis://localhost:6379 | memory://localhost:8000

DEMO WALKTHROUGH
  [PASS] Step 1 — Connect & Overview (2.3s)
  [PASS] Step 2 — Quarterly Breakdown (1.8s)
  [PASS] Step 3 — Regional Filter (1.5s)
  [FAIL] Step 4 — Best Month Query: Expected June, got July

UNIT TESTS
  [PASS] test_dataset_seeded (0.1s)
  [PASS] test_fetch_data_no_filter (0.2s)
  ...

SUMMARY: 13/14 passed | 1 failed | 0 skipped
```

## Scripts

### `run_demo_walkthrough.py`
Executes the full 4-step demo walkthrough and produces a report.

```bash
python scripts/run_demo_walkthrough.py \
    --session-id test-001 \
    --user-id test-user \
    [--redis-url REDIS_URL] \
    [--memory-url MEMORY_URL] \
    [--report-file report.md]
```

### `run_unit_tests.py`
Runs the individual unit test checks.

```bash
python scripts/run_unit_tests.py \
    [--redis-url REDIS_URL] \
    [--memory-url MEMORY_URL] \
    [--verbose]
```

### `check_data_accuracy.py`
Compares a Claude-generated explanation against actual dataset values. Extracts numbers from the explanation text and validates them against `fetch_data` results.

```bash
python scripts/check_data_accuracy.py \
    --explanation "PedalForce had $22.1M in revenue" \
    --dataset-id pedalforce \
    [--tolerance 0.05]
```

Options:
- `--tolerance`: Acceptable deviation (default 5%) to account for rounding in TTS text

### `log_execution.py`
Standard execution logger.

```bash
python scripts/log_execution.py <skill_name> <success> <message>
```

## Token Efficiency
- **Walkthrough**: Report pass/fail per step with timing. Only show details on failure.
- **Unit tests**: One-line summary per test.
- **Data accuracy**: Report only mismatches.

## Learned Context
Before executing, check `memory/learned_context.md` for known flaky tests, timing thresholds, and acceptable tolerances.

## Dependencies
- `anthropic` — For running the generation pipeline
- `agent-memory-client` — For memory operations
- `redis[hiredis]` — For dataset queries
- `claude-svg-generator` skill — Used internally for SVG generation steps
- `redis-dataset-seeder` skill — Used to verify dataset state before tests
