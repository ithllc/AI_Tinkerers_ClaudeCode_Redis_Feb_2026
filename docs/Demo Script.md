# VoxVisual Demo Script

## Prerequisites
```bash
# 1. Start Redis Stack
/opt/redis-stack/bin/redis-server --daemonize yes --port 6379 --loadmodule /opt/redis-stack/lib/rejson.so

# 2. Start VoxVisual
python3 run.py --port 8080

# 3. Open browser to http://localhost:8080
```

---

## Step 1 — Load the Dataset

**Say or type:**
> "Connect to the PedalForce dataset and show me 2025 sales by category"

**What happens:** Claude calls the `fetch_data` tool to pull all 240 records from Redis, groups them by category, and generates an animated bar chart. TTS reads back the revenue summary.

**What to look for:** A bar chart with 5 categories (Road Bikes, Mountain Bikes, E-Bikes, Kids Bikes, Accessories). E-Bikes should lead in revenue.

---

## Step 2 — Drill Down by Quarter

**Say or type:**
> "Break that down by quarter"

**What happens:** Claude calls `fetch_data` again with a month-based grouping, maps months to quarters, and generates a grouped bar chart showing seasonal trends.

**What to look for:** Revenue peaks in Q2/Q3 (summer cycling season) and dips in Q1/Q4 (winter).

---

## Step 3 — Filter by Region

**Say or type:**
> "Show me just the East region"

**What happens:** Claude calls `fetch_data` with a region filter set to "East". Only 60 records are returned. A new chart renders with East-only data.

**What to look for:** The chart updates to show only East region data. East represents ~30% of total revenue (the largest region).

---

## Step 4 — Find the Best Month

**Say or type:**
> "What was our best month?"

**What happens:** Claude calls `fetch_data` grouped by month with the East filter still applied, identifies the peak month, and highlights it visually.

**What to look for:** June 2025 should be highlighted as the top revenue month. TTS reads back the insight.

---

## Step 5 — Compare Two Categories

**Say or type:**
> "Compare E-Bikes and Road Bikes across all regions"

**What happens:** Claude fetches data filtered to just E-Bikes and Road Bikes, grouped by region. Generates a side-by-side or grouped comparison chart.

**What to look for:** E-Bikes lead in revenue ($2,500 avg price) but Road Bikes sell more units in the North region.

---

## Step 6 — Ask a Summary Question

**Say or type:**
> "Give me a summary of the full year performance"

**What happens:** Claude pulls the full dataset, aggregates totals, and generates an overview visualization with key metrics. TTS delivers the executive summary.

**What to look for:** Grand total ~$22.1M revenue, 38,400 units sold across all categories and regions.

---

## What to Explain at Each Step

| Step | Key Concept |
|------|-------------|
| 1 | Claude uses **tool calling** to fetch real data from Redis — it never invents numbers |
| 2 | The system maintains **conversation context** so "break that down" refers to the previous chart |
| 3 | **Filters** are applied server-side in Redis before data reaches Claude |
| 4 | Claude **analyzes** the data and highlights insights, not just charts |
| 5 | Multiple filters and groupings can be **combined** in a single query |
| 6 | The **TTS output** reads the explanation aloud for hands-free use |

---

## Troubleshooting

- **No voice input?** Use the text box instead. Speech Recognition requires Chrome/Edge.
- **Loading takes long?** First query may take 5-10 seconds as Claude generates the SVG.
- **No sound?** Click anywhere on the page first — browsers block autoplay audio until user interaction.
