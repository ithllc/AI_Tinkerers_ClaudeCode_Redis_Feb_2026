# Voice Responsive Data Visualization Tool Technical Implementation Plan

# Technical Implementation Plan

Phase 1: The "Memory" Layer (Redis Agent Memory Server)
Goal: Deploy the Redis Agent Memory Server and configure dual-tier memory for VoxVisual sessions.

**1a. Infrastructure Setup**
- Run the Redis Agent Memory Server alongside the VoxVisual backend. The server exposes a REST API (default port 8000) and an optional MCP server (port 9000).
- All LLM calls use the **Anthropic Claude API** exclusively. Required environment variables:
  ```
  REDIS_URL=redis://localhost:6379

  # Anthropic Claude API
  ANTHROPIC_API_KEY=sk-ant-...
  GENERATION_MODEL=claude-sonnet-4-5-20250929
  SLOW_MODEL=claude-sonnet-4-5-20250929
  FAST_MODEL=claude-haiku-4-5-20251001
  EMBEDDING_MODEL=text-embedding-3-small

  # Memory Server
  LONG_TERM_MEMORY=true
  ENABLE_DISCRETE_MEMORY_EXTRACTION=true
  ENABLE_TOPIC_EXTRACTION=true
  ENABLE_NER=true
  DISABLE_AUTH=true                              # set false in production
  ```
- Install the Python SDK in the VoxVisual backend: `pip install agent-memory-client`
- Install the Anthropic SDK: `pip install anthropic`

**1b. Working Memory (Session Context)**
- Each VoxVisual session is represented as a Working Memory document, keyed by `session_id`.
- The `messages` array stores the full voice-transcript / response history as `MemoryMessage` objects (`role`, `content`, `created_at`).
- The `data` field (arbitrary JSON) stores session-specific state:
  ```json
  {
    "last_query": "Show me Q3 revenue by region",
    "connected_dataset": "pedalforce",
    "current_filters": { "quarter": "Q3", "metric": "revenue" },
    "visual_theme": "cyberpunk",
    "last_svg_hash": "abc123"
  }
  ```
- REST endpoints used:
  - `PUT /v1/working-memory/{session_id}` — create/update session state after each interaction.
  - `GET /v1/working-memory/{session_id}` — retrieve session context before prompt assembly.
- Auto-summarization: When the conversation history grows past the `SUMMARIZATION_THRESHOLD` (default 70% of the context window), the server automatically compresses older messages into a `context` summary field, keeping the session lightweight.
- Directive: Use Redis Timeseries if the data is live-streaming sensor data.

**1c. Long-term Memory (Cross-Session Intelligence)**
- After each working-memory update, the server's background workers automatically extract discrete memories (preferences, facts, events) using the configured `long_term_memory_strategy`.
- Memory types stored:
  - **Semantic**: User preferences and facts (e.g., "User prefers dark cyberpunk themes", "Primary dataset is PedalForce").
  - **Episodic**: Time-stamped visualization events (e.g., "User analyzed 2025 E-Bike sales by region on 2026-02-21").
- REST endpoints used:
  - `POST /v1/long-term-memory/search` — semantic search for relevant past memories before prompt assembly.
  - `POST /v1/long-term-memory/` — manually create memories when needed.
- Deduplication: The server deduplicates semantically similar memories (threshold: `DEDUPLICATION_DISTANCE_THRESHOLD=0.35`) to prevent bloat.
- Forgetting: Optional policy-based forgetting can be enabled to auto-expire stale memories.

---

Phase 2: The "Data" Layer (Demo Dataset & Data Connector)
Goal: Seed Redis with the PedalForce Bicycles demo dataset and implement the `fetch_data` tool that Claude calls to query it.

**2a. Dataset JSON Schema**
The demo dataset is stored as a single Redis JSON document at key `dataset:pedalforce`. The schema:
```json
{
  "dataset_id": "pedalforce",
  "company_name": "PedalForce Bicycles",
  "description": "Fictional bicycle manufacturer — 2025 monthly sales data across 5 product categories and 4 regions.",
  "currency": "USD",
  "fiscal_year": 2025,
  "categories": ["Road Bikes", "Mountain Bikes", "E-Bikes", "Kids Bikes", "Accessories"],
  "regions": ["North", "South", "East", "West"],
  "records": [
    {
      "month": "2025-01",
      "category": "Road Bikes",
      "region": "North",
      "units_sold": 120,
      "revenue": 156000,
      "avg_unit_price": 1300
    }
  ]
}
```
Each record in the `records` array represents one (month, category, region) combination. With 12 months x 5 categories x 4 regions = **240 records** total.

**2b. Demo Dataset (PedalForce Bicycles — Full 2025 Sales Data)**

The seeder script writes the following data to `dataset:pedalforce` in Redis on application startup. Summary totals by category for the full year:

| Category | Total Units | Total Revenue | Avg Unit Price |
|---|---|---|---|
| Road Bikes | 5,640 | $7,332,000 | $1,300 |
| Mountain Bikes | 4,320 | $3,456,000 | $800 |
| E-Bikes | 3,480 | $8,700,000 | $2,500 |
| Kids Bikes | 6,960 | $2,088,000 | $300 |
| Accessories | 18,000 | $540,000 | $30 |
| **Grand Total** | **38,400** | **$22,116,000** | — |

Monthly revenue pattern (all categories combined) — designed to show seasonality typical of bicycle retail:

| Month | Revenue | Notes |
|---|---|---|
| Jan | $1,105,800 | Post-holiday low |
| Feb | $1,216,380 | Slight uptick |
| Mar | $1,548,120 | Spring prep begins |
| Apr | $2,100,720 | Spring selling season |
| May | $2,543,040 | Peak season ramp-up |
| Jun | $2,764,800 | Peak — summer starts |
| Jul | $2,654,520 | High summer |
| Aug | $2,433,960 | Late summer |
| Sep | $1,879,560 | Back-to-school dip |
| Oct | $1,437,480 | Autumn slowdown |
| Nov | $1,216,380 | Pre-holiday lull |
| Dec | $1,215,240 | Holiday gift spike (Kids & Accessories) |

Regional split (approximate annual share):
- **North**: 28% of revenue — strong road bike market
- **South**: 22% of revenue — year-round riding, strong E-Bike adoption
- **East**: 30% of revenue — largest metro density, highest volume
- **West**: 20% of revenue — mountain bike and E-Bike strength

The full 240-record array is generated by a seeder script (`scripts/seed_dataset.py`) that distributes the above totals across months and regions with realistic seasonal and regional weighting.

**2c. Redis Seeder Script**
On application startup (or via `python scripts/seed_dataset.py`), the script:
1. Connects to Redis at `REDIS_URL`.
2. Builds the 240-record array using the seasonal weights and regional splits above.
3. Stores the full document with `JSON.SET dataset:pedalforce $ <payload>`.
4. Logs: `Seeded dataset:pedalforce — 240 records, FY2025`.

**2d. Data Connector (`fetch_data` Tool)**
Claude is given a tool called `fetch_data` that the backend resolves by querying Redis. Tool definition passed to the Anthropic Claude API:
```json
{
  "name": "fetch_data",
  "description": "Retrieve sales data from a connected dataset stored in Redis. Returns filtered JSON records. Always call this tool before generating a visualization — never invent data.",
  "input_schema": {
    "type": "object",
    "properties": {
      "dataset_id": {
        "type": "string",
        "description": "The dataset to query, e.g. 'pedalforce'"
      },
      "filters": {
        "type": "object",
        "description": "Optional filters to narrow the data",
        "properties": {
          "months": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Filter by month(s), e.g. ['2025-01', '2025-06']"
          },
          "categories": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Filter by product category, e.g. ['E-Bikes', 'Road Bikes']"
          },
          "regions": {
            "type": "array",
            "items": { "type": "string" },
            "description": "Filter by region, e.g. ['East', 'West']"
          }
        }
      },
      "group_by": {
        "type": "array",
        "items": { "type": "string", "enum": ["month", "category", "region"] },
        "description": "Dimensions to group/aggregate by. Revenue and units are summed; avg_unit_price is weighted."
      }
    },
    "required": ["dataset_id"]
  }
}
```

**Backend tool handler** (Python pseudocode):
```python
import json
import redis.asyncio as redis

async def handle_fetch_data(tool_input: dict) -> str:
    """Resolve Claude's fetch_data tool call against Redis."""
    r = redis.from_url(REDIS_URL)
    dataset_id = tool_input["dataset_id"]

    # 1. Retrieve full dataset from Redis JSON
    raw = await r.json().get(f"dataset:{dataset_id}")
    if not raw:
        return json.dumps({"error": f"Dataset '{dataset_id}' not found"})

    records = raw["records"]

    # 2. Apply filters
    filters = tool_input.get("filters", {})
    if filters.get("months"):
        records = [r for r in records if r["month"] in filters["months"]]
    if filters.get("categories"):
        records = [r for r in records if r["category"] in filters["categories"]]
    if filters.get("regions"):
        records = [r for r in records if r["region"] in filters["regions"]]

    # 3. Apply group_by aggregation
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
            g["avg_unit_price"] = round(g.pop("_weighted_price") / g["units_sold"], 2) if g["units_sold"] else 0
            result.append(g)
        records = result

    return json.dumps({
        "dataset_id": dataset_id,
        "company_name": raw["company_name"],
        "currency": raw["currency"],
        "record_count": len(records),
        "records": records
    })
```

**Example tool-call flow** for the voice command *"Connect to the PedalForce dataset and let's look at the 2025 sales data"*:
1. User's voice is transcribed to text.
2. Backend retrieves working memory and long-term memory context.
3. Backend calls Claude (`claude-sonnet-4-5-20250929`) via the Anthropic SDK with the user transcript, memory context, and the `fetch_data` tool definition.
4. Claude responds with a `tool_use` block:
   ```json
   {
     "type": "tool_use",
     "name": "fetch_data",
     "input": {
       "dataset_id": "pedalforce",
       "group_by": ["category"]
     }
   }
   ```
5. Backend executes `handle_fetch_data(...)` against Redis and returns the aggregated data to Claude as a `tool_result`.
6. Claude generates the SVG visualization and explanation based on the real data.

---

Phase 3: The "Brain" (Claude API Integration)
Goal: Create a backend service that orchestrates the data and the AI, enriched by the memory layer. All LLM calls use the **Anthropic Claude API** via the `anthropic` Python SDK.

**Claude API Call Structure**
```python
import anthropic

client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

response = client.messages.create(
    model="claude-sonnet-4-5-20250929",
    max_tokens=4096,
    system=system_prompt,       # includes memory context
    tools=[fetch_data_tool],    # the tool definition from Phase 2d
    messages=conversation_messages
)
```

System Prompting: Define Claude's role as a "Frontend Engineer Specializing in SVG."
Tool Use: Provide Claude with the following tools:
- `fetch_data(dataset_id, filters?, group_by?)` — retrieves and aggregates sales data from Redis (defined in Phase 2d).
- Memory tools via MCP (optional): If using the MCP server, Claude can directly call `search_long_term_memory`, `set_working_memory`, and `memory_prompt` as native tools, removing the need for manual memory orchestration in the backend.

**Prompt Assembly with Memory Context**
- Option A (REST — recommended): Use the `POST /v1/memory/prompt` endpoint to generate a memory-enriched system prompt. This endpoint retrieves both working memory (current session) and relevant long-term memories (semantic search), and returns a consolidated prompt context.
  ```python
  from agent_memory_client import create_memory_client

  memory_client = await create_memory_client("http://localhost:8000")

  # Get memory-enriched prompt context
  prompt_context = await memory_client.memory_prompt(
      text=user_transcript,
      session_id=session_id,
      user_id=user_id
  )
  ```
- Option B (MCP): Configure Claude with the Redis Agent Memory Server as an MCP tool provider. Claude autonomously retrieves and stores memories during the conversation.

Output Format: Force Claude to return a structured JSON response:
```json
{
  "explanation": "Brief text for TTS",
  "svg_code": "<svg>...</svg>",
  "css_styles": "@keyframes..."
}
```

**Post-Response Memory Update**
After Claude responds, update working memory with the new interaction:
```python
from agent_memory_client import create_memory_client
from agent_memory_client.models import WorkingMemoryResponse, MemoryMessage

memory_client = await create_memory_client("http://localhost:8000")

await memory_client.put_working_memory(
    session_id=session_id,
    working_memory=WorkingMemoryResponse(
        messages=[
            MemoryMessage(role="user", content=user_transcript),
            MemoryMessage(role="assistant", content=claude_response["explanation"])
        ],
        data={
            "last_query": user_transcript,
            "connected_dataset": "pedalforce",
            "current_filters": updated_filters,
            "visual_theme": current_theme,
            "last_svg_hash": svg_hash
        }
    )
)
```
The server's background workers will then automatically extract long-term memories from the new messages.

Phase 4: The "Ear/Mouth" (Web Audio API)
Input: Implement window.SpeechRecognition (or a Whisper API relay) to capture the prompt.
Output: Feed the explanation field from Claude into window.speechSynthesis.

Phase 5: The "Canvas" (Frontend Rendering)
Component Sandbox: Create a React wrapper that uses dangerouslySetInnerHTML (safely sanitized) to inject the SVG and \<style\> tags generated by Claude.
Animation Trigger: Use a useEffect hook to trigger the entry animations as soon as the SVG string is injected.

---

# Step-by-Step Directives for Developers

1. **Initialize Environment**: Setup a Next.js project with Tailwind CSS. Deploy the Redis Agent Memory Server (via `uvx agent-memory-server` or Docker) and verify connectivity to Redis. Set the `ANTHROPIC_API_KEY` environment variable.
2. **Install Dependencies**:
   ```bash
   pip install anthropic agent-memory-client redis
   ```
   Initialize clients:
   ```python
   import anthropic
   from agent_memory_client import create_memory_client

   claude = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
   memory = await create_memory_client("http://localhost:8000")
   ```
3. **Seed the Demo Dataset**: Run `python scripts/seed_dataset.py` to populate `dataset:pedalforce` in Redis with the 240-record PedalForce Bicycles 2025 sales dataset. Verify with `redis-cli JSON.GET dataset:pedalforce $.company_name`.
4. **Implement the `fetch_data` Tool Handler**: Build the backend function from Phase 2d that reads from Redis JSON, applies filters, aggregates by `group_by`, and returns the result to Claude as a `tool_result`.
5. **Build Prompt Wrapper**: Create a function that:
   - Retrieves the current working memory via `memory.get_working_memory(session_id)`.
   - Searches long-term memory for relevant context via `memory.search_long_term_memory(text=user_transcript, user_id=user_id, limit=5)`.
   - Assembles the system prompt with the working memory `context` (auto-summary), the `data` (current filters/theme/connected dataset), and relevant long-term memories.
   - Alternatively, use `memory.memory_prompt(text=user_transcript, session_id=session_id, user_id=user_id)` for a single-call prompt assembly.
6. **Construct "Designer" System Prompt**:
   **"You are a senior data visualization designer. You output only valid SVG and CSS. Use \<animate\> tags for motion. Ensure the SVG is responsive (width='100%'). You have access to the `fetch_data` tool — always call it to get real data before generating a visualization. Never invent or hallucinate data."**
   Append the memory context (user preferences, current session state, relevant past visualizations) to the system prompt.
7. **Implement API Route**: `/api/generate-ui` takes audio text → retrieves working memory from the Redis Agent Memory Server → searches long-term memory for relevant context → calls Claude (`claude-sonnet-4-5-20250929`) via the Anthropic SDK with the `fetch_data` tool → handles the tool-use loop (Claude calls `fetch_data`, backend resolves against Redis, returns data, Claude generates SVG) → updates working memory → returns the UI JSON.
8. **Build the Frontend Listener**: Create a "Record" button that, upon release, sends audio to the API and waits for the SVG payload.
9. **(Optional) MCP Integration**: For advanced setups, configure the Redis Agent Memory Server's MCP endpoint so Claude can autonomously manage memory. Add to your MCP config:
   ```json
   {
     "mcpServers": {
       "memory": {
         "command": "uvx",
         "args": ["--from", "agent-memory-server", "agent-memory", "mcp"],
         "env": {
           "REDIS_URL": "redis://localhost:6379",
           "ANTHROPIC_API_KEY": "sk-ant-..."
         }
       }
     }
   }
   ```

---

# Testing Rubrics & Criteria

1\. Unit Testing (Logic)
| Test Case | Method | Success Criteria |
|---|---|---|
| SVG Validation | Regex/DOM Parser | Generated string must be valid XML/SVG. |
| Dataset Seeder | `redis-cli JSON.GET dataset:pedalforce` | Key exists, contains 240 records, totals match expected values. |
| `fetch_data` — No Filter | Call with `{"dataset_id": "pedalforce"}` | Returns all 240 records. |
| `fetch_data` — Filter by Region | Call with `filters.regions: ["East"]` | Returns only East-region records (60 records). |
| `fetch_data` — Group by Category | Call with `group_by: ["category"]` | Returns 5 aggregated records with correct revenue sums. |
| `fetch_data` — Unknown Dataset | Call with `{"dataset_id": "nonexistent"}` | Returns `{"error": "Dataset 'nonexistent' not found"}`. |
| Working Memory Persistence | `agent-memory-client` | `PUT` then `GET` on a `session_id` must return the correct `data` (filters, theme, connected dataset) and `messages`. |
| Long-term Memory Extraction | Redis Agent Memory Server logs / `GET /v1/long-term-memory/{id}` | After a working memory update, background extraction must produce at least one semantic or episodic memory record. |
| Long-term Memory Search | `POST /v1/long-term-memory/search` | Searching "E-Bike sales" must return episodic memories from sessions where that topic was discussed. |
| State Merging | Logic Test | New filters must merge with, not overwrite, the `data` field in working memory. |

2\. Integration Testing (End-to-End)
| Test Case | Method | Success Criteria |
|---|---|---|
| Demo Walkthrough | Manual/Cypress | Voice command "Connect to the PedalForce dataset and let's look at the 2025 sales data" renders an animated SVG chart within 5 seconds. |
| Tool-Use Loop | Backend log inspection | Claude issues a `fetch_data` tool call, backend resolves it against Redis, and Claude generates SVG from the returned data (not hallucinated). |
| Animation Presence | DOM Inspection | SVG must contain at least one \<animate\>, \<animateTransform\>, or @keyframes block. |
| TTS Sync | Audio Event Listen | Speech begins within 500ms of the SVG appearing on screen. |
| Follow-Up Filter | Manual | After initial chart, say "Show me just the East region." Chart re-renders with only East data, verified against known East totals. |
| Cross-Session Recall | Multi-session test | Start a new session and say "Use my usual theme." The system must retrieve the user's preferred theme from long-term memory and apply it. |
| Memory-Enriched Prompt | Backend log inspection | The prompt sent to Claude must include working memory context and at least one relevant long-term memory when available. |

3\. UX/Performance Rubric
Code Correctness: Does the SVG render without a console error? (Pass/Fail)
Data Accuracy: Does the chart match the actual numbers from the PedalForce dataset in Redis? (Pass/Fail)
Contextual Awareness: If the user says "Change it to blue," does the color change while keeping the data the same? (Score 1-5)
Cross-Session Awareness: Does the system personalize visualizations based on stored preferences from prior sessions? (Score 1-5)
Fluidity: Is the generated animation jitter-free on mobile devices? (Pass/Fail)
