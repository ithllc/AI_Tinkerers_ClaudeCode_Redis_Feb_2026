# Skill: redis-dataset-seeder

## Description
Seeds, validates, and resets the PedalForce Bicycles demo dataset in Redis. Manages the `dataset:pedalforce` JSON document containing 240 sales records (12 months x 5 categories x 4 regions) for fiscal year 2025.

## When to Use
Invoke this skill when:
- Setting up the VoxVisual development environment for the first time
- Resetting the demo dataset to a known-good state after testing
- Validating that the dataset in Redis matches the expected schema and totals
- Adding or modifying product categories, regions, or monthly data
- Debugging data-related issues in the `fetch_data` tool pipeline

## User Invocation
- "Seed the PedalForce dataset"
- "Reset the demo data"
- "Validate the dataset in Redis"
- "Show me the dataset stats"

## Behavior

### Seed Flow
1. Connect to Redis at `REDIS_URL` (default: `redis://localhost:6379`)
2. Generate the 240-record array using seasonal weights and regional splits
3. Store as a Redis JSON document at key `dataset:pedalforce`
4. Run validation to confirm record count and revenue totals

### Validation Flow
1. Retrieve `dataset:pedalforce` from Redis
2. Assert 240 records exist
3. Assert all 5 categories and 4 regions are present
4. Assert grand total revenue matches expected $22,116,000
5. Assert each month has exactly 20 records (5 categories x 4 regions)
6. Report pass/fail with details

### Reset Flow
1. Delete existing `dataset:pedalforce` key
2. Run full seed flow
3. Run validation flow

## Dataset Specification

**Company:** PedalForce Bicycles (fictional bicycle manufacturer)
**Fiscal Year:** 2025
**Currency:** USD

**Categories & Avg Unit Prices:**
| Category | Avg Unit Price |
|---|---|
| Road Bikes | $1,300 |
| Mountain Bikes | $800 |
| E-Bikes | $2,500 |
| Kids Bikes | $300 |
| Accessories | $30 |

**Regions:** North (28%), South (22%), East (30%), West (20%)

**Seasonal Weights (monthly revenue distribution):**
| Month | Weight | Notes |
|---|---|---|
| Jan | 0.050 | Post-holiday low |
| Feb | 0.055 | Slight uptick |
| Mar | 0.070 | Spring prep |
| Apr | 0.095 | Spring selling |
| May | 0.115 | Peak ramp-up |
| Jun | 0.125 | Peak summer |
| Jul | 0.120 | High summer |
| Aug | 0.110 | Late summer |
| Sep | 0.085 | Back-to-school dip |
| Oct | 0.065 | Autumn slowdown |
| Nov | 0.055 | Pre-holiday lull |
| Dec | 0.055 | Holiday gift spike |

## Scripts

### `seed_dataset.py`
Seeds the full PedalForce dataset into Redis.

```bash
python scripts/seed_dataset.py [--redis-url REDIS_URL] [--force]
```

Options:
- `--redis-url`: Override Redis connection URL (default: env `REDIS_URL` or `redis://localhost:6379`)
- `--force`: Overwrite existing dataset without prompting

### `validate_dataset.py`
Validates the dataset currently stored in Redis.

```bash
python scripts/validate_dataset.py [--redis-url REDIS_URL] [--verbose]
```

### `log_execution.py`
Standard execution logger.

```bash
python scripts/log_execution.py <skill_name> <success> <message>
```

## Token Efficiency
- **Seed**: Report only the summary line: "Seeded dataset:pedalforce — 240 records, $22.1M revenue, FY2025"
- **Validate**: Report pass/fail with counts. Only show details on failure.
- **Reset**: Combine delete + seed + validate into a single summary.

## Learned Context
Before executing, check `memory/learned_context.md` for recent adaptations and edge cases.

## Dependencies
- `redis[hiredis]` — Redis client with JSON support
- Running Redis instance with RedisJSON module enabled
