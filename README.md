# VoxVisual — Voice-Responsive Data Visualization

**AI Tinkerers x Claude Code x Redis | February 2026 Hackathon**

VoxVisual transforms spoken or typed queries into animated SVG data visualizations. Ask a question about sales data using your voice, and the system fetches real data from Redis, sends it through Claude's API, and renders a live animated chart — all in seconds.

Built entirely with **Claude Code** using the project-manager skill for orchestration.

---

## How It Works

```
Voice/Text Query
      |
      v
  FastAPI Backend
      |
      v
  Claude API (claude-sonnet-4-5)
      |
      +---> fetch_data tool call
      |         |
      |         v
      |     Redis JSON (PedalForce dataset)
      |         |
      |         v
      +<--- real data returned
      |
      v
  Animated SVG + Explanation
      |
      v
  Browser renders chart + TTS reads insight aloud
```

**Key concepts demonstrated:**
- **Claude Tool Use** — Claude calls `fetch_data` to query Redis, never hallucinating data
- **Redis JSON** — 240 sales records stored and queried with filtering + aggregation
- **Generative UI** — SVG visualizations are created on-demand by Claude, not pre-built
- **Voice I/O** — Web Speech API for input, speechSynthesis for output
- **Agent Memory** — Optional Redis Agent Memory Server for session context and cross-session recall

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | Anthropic Claude API (`claude-sonnet-4-5-20250929`) |
| Data Store | Redis Stack with RedisJSON module |
| Backend | Python, FastAPI, Uvicorn |
| Frontend | Vanilla HTML/CSS/JS (no frameworks) |
| Voice Input | Web Speech API (`SpeechRecognition`) |
| Voice Output | Web Speech API (`speechSynthesis`) |
| Memory (optional) | Redis Agent Memory Server (`agent-memory-client`) |

---

## Project Structure

```
VoxVisual/
├── backend/
│   ├── app.py                  # FastAPI server + routes
│   ├── claude_integration.py   # Claude API + tool-use loop + memory
│   └── data_connector.py       # fetch_data tool definition + Redis handler
├── scripts/
│   └── seed_dataset.py         # PedalForce 240-record dataset seeder
├── static/
│   └── index.html              # Frontend UI (voice, SVG canvas, TTS)
├── tests/
│   └── test_data_layer.py      # 13 unit tests for data layer
├── docs/
│   ├── Demo Script.md          # Step-by-step verbal demo dialog
│   ├── Voice Responsive Data Visualization Tool PDR.md
│   └── Voice Responsive Data Visualization Tool Technical Implementation Plan.md
├── run.py                      # Startup script (seeds data + launches server)
├── requirements.txt            # Python dependencies
├── .env                        # API key config (not committed)
└── .gitignore
```

---

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Redis Stack (for the JSON module)
- An Anthropic API key

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
REDIS_URL=redis://localhost:6379
GENERATION_MODEL=claude-sonnet-4-5-20250929
```

### 4. Start Redis Stack

```bash
# Stop vanilla Redis if running
sudo systemctl stop redis-server

# Start Redis Stack with JSON module
/opt/redis-stack/bin/redis-server --daemonize yes --port 6379 \
  --loadmodule /opt/redis-stack/lib/rejson.so

# Verify
redis-cli ping          # should return PONG
redis-cli MODULE LIST   # should show ReJSON
```

### 5. Launch VoxVisual

```bash
python3 run.py --port 8080
```

This will:
1. Seed the PedalForce demo dataset (240 records) into Redis
2. Start the FastAPI server on `http://localhost:8080`

### 6. Open in Browser

Navigate to **http://localhost:8080** (Chrome or Edge recommended for voice input).

---

## Demo Dataset: PedalForce Bicycles

The built-in demo dataset represents a fictional bicycle company's 2025 sales:

- **240 records**: 12 months x 5 categories x 4 regions
- **Categories**: Road Bikes, Mountain Bikes, E-Bikes, Kids Bikes, Accessories
- **Regions**: North (28%), South (22%), East (30%), West (20%)
- **Total Revenue**: ~$22.1 million
- **Seasonality**: Summer peak (Jun), winter trough (Jan)

---

## Try It Out — Demo Dialog

Open the app and walk through these queries. You can speak them into the microphone or type them in.

### Step 1 — Load the Dataset
> "Connect to the PedalForce dataset and show me 2025 sales by category"

Claude fetches all records from Redis, groups by category, and generates an animated bar chart. E-Bikes lead at ~$8.7M revenue.

### Step 2 — Drill Down by Quarter
> "Break that down by quarter"

The system remembers the previous context. Revenue peaks in Q2/Q3 (summer cycling season).

### Step 3 — Filter by Region
> "Show me just the East region"

Only East-region data is returned (60 records). East is the largest region at ~30% of revenue.

### Step 4 — Find the Best Month
> "What was our best month?"

Claude analyzes the filtered data and highlights June 2025 as the peak month.

### Step 5 — Compare Categories
> "Compare E-Bikes and Road Bikes across all regions"

Side-by-side comparison showing E-Bikes lead in revenue but Road Bikes sell more units in the North.

### Step 6 — Full Year Summary
> "Give me a summary of the full year performance"

Executive overview with key metrics: $22.1M revenue, 38,400 units across all categories and regions.

See [docs/Demo Script.md](docs/Demo%20Script.md) for the full annotated walkthrough with explanations of what happens at each step.

---

## Running Tests

```bash
python3 -m pytest tests/test_data_layer.py -v
```

Tests cover:
- Dataset seeder (record count, schema, all combinations)
- fetch_data with no filter (240 records)
- Filter by region, category, month
- Group by category, region, month
- Combined filter + group
- Unknown dataset error handling

---

## API Reference

### `POST /api/generate-ui`

Generate a visualization from a natural language query.

**Request:**
```json
{
  "query": "Show me 2025 sales by category",
  "session_id": "my-session-123",
  "user_id": "default"
}
```

**Response:**
```json
{
  "explanation": "PedalForce Bicycles 2025 sales show E-Bikes leading...",
  "svg_code": "<svg viewBox='0 0 1000 600' width='100%'>...</svg>",
  "css_styles": ""
}
```

### `GET /api/health`

Returns `{"status": "ok"}` if the server is running.

---

## Architecture Details

### Claude Tool-Use Loop

1. User query is sent to Claude with the `fetch_data` tool definition
2. Claude decides what data it needs and calls `fetch_data` with filters/grouping
3. Backend resolves the tool call against Redis JSON
4. Real data is returned to Claude as a `tool_result`
5. Claude generates an animated SVG visualization based on the actual data
6. The explanation is read aloud via TTS

### Memory Integration (Optional)

When the Redis Agent Memory Server is running (`agent-memory-client`):
- **Working Memory**: Stores current session state (filters, theme, conversation history)
- **Long-term Memory**: Extracts user preferences and past visualization events for cross-session recall

The system gracefully degrades if the memory server is unavailable.

---

## License

See [LICENSE](LICENSE) for details.
