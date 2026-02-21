# Skill: claude-svg-generator

## Description
Core SVG visualization generation pipeline for VoxVisual. Assembles memory-enriched prompts, calls the Anthropic Claude API with the `fetch_data` tool, handles the tool-use loop, and parses the structured JSON response containing SVG code, CSS animations, and TTS explanation text.

## When to Use
Invoke this skill when:
- Processing a user voice transcript into an SVG visualization
- Debugging prompt assembly or Claude API tool-use issues
- Testing SVG generation quality with different prompts or data slices
- Tuning the system prompt for better visualization output
- Running the demo walkthrough pipeline end-to-end

## User Invocation
- "Generate a visualization for: Show me 2025 sales by category"
- "Test the SVG pipeline"
- "Debug the Claude tool-use loop"
- "Run a prompt through the generator"

## Behavior

### Generation Flow
1. **Receive transcript**: Accept the user's voice transcript (text).
2. **Retrieve memory context**: Call the Redis Agent Memory Server to get working memory (session state) and search long-term memory for relevant past interactions.
3. **Assemble system prompt**: Combine the "Designer" system prompt with memory context (preferences, session filters, past visualizations).
4. **Call Claude API**: Send the prompt to `claude-sonnet-4-5-20250929` via the Anthropic SDK with the `fetch_data` tool definition.
5. **Handle tool-use loop**: When Claude responds with a `tool_use` block for `fetch_data`, resolve it against Redis and return the data as a `tool_result`. Claude then generates the final SVG.
6. **Parse response**: Extract the structured JSON response:
   ```json
   {
     "explanation": "Brief text for TTS",
     "svg_code": "<svg>...</svg>",
     "css_styles": "@keyframes..."
   }
   ```
7. **Update working memory**: Store the new interaction (user transcript + assistant explanation) and updated session state (filters, theme, connected dataset) in Redis Agent Memory Server.

### System Prompt Template
```
You are a senior data visualization designer. You output only valid SVG and CSS.
Use <animate> tags for motion. Ensure the SVG is responsive (width='100%').
You have access to the `fetch_data` tool — always call it to get real data before
generating a visualization. Never invent or hallucinate data.

{memory_context}

Return your response as a JSON object with exactly three keys:
- "explanation": A 1-2 sentence insight for text-to-speech readback.
- "svg_code": A complete, valid <svg> element with animations.
- "css_styles": Any @keyframes or CSS rules the SVG needs.
```

### Tool-Use Loop
The `fetch_data` tool is defined in the Technical Implementation Plan (Phase 2d). The loop:
1. Claude sends `tool_use` with `name: "fetch_data"` and `input: {dataset_id, filters?, group_by?}`.
2. Backend calls `handle_fetch_data(tool_input)` which reads from Redis JSON, filters, aggregates.
3. Backend returns the result as a `tool_result` message.
4. Claude uses the real data to generate the SVG.
5. If Claude calls `fetch_data` multiple times (e.g., comparative queries), repeat steps 2-3.

## Scripts

### `generate_svg.py`
Runs the full generation pipeline for a given transcript.

```bash
python scripts/generate_svg.py "Show me 2025 sales by category" \
    --session-id demo-001 \
    --user-id demo-user \
    [--redis-url REDIS_URL] \
    [--memory-url MEMORY_URL] \
    [--output-file output.json]
```

Options:
- `--session-id`: Working memory session identifier
- `--user-id`: User identifier for long-term memory search
- `--redis-url`: Redis connection URL for dataset queries (default: env `REDIS_URL`)
- `--memory-url`: Redis Agent Memory Server URL (default: `http://localhost:8000`)
- `--output-file`: Write the full JSON response to a file

### `validate_svg.py`
Validates that a generated SVG string is well-formed and contains animations.

```bash
python scripts/validate_svg.py '<svg>...</svg>'
# or pipe from file:
python scripts/validate_svg.py --file output.json
```

Checks:
- Valid XML/SVG structure
- Contains at least one `<animate>`, `<animateTransform>`, or `@keyframes` block
- Has `width="100%"` for responsiveness
- No script injection (`<script>` tags)

### `log_execution.py`
Standard execution logger.

```bash
python scripts/log_execution.py <skill_name> <success> <message>
```

## Claude API Configuration
- **Model**: `claude-sonnet-4-5-20250929`
- **Max tokens**: 4096
- **Environment**: `ANTHROPIC_API_KEY` must be set
- **Tools**: `fetch_data` tool definition (see Technical Implementation Plan Phase 2d)

## Token Efficiency
- **System prompt**: Keep under 500 tokens. Memory context is appended dynamically.
- **Tool results**: The `fetch_data` handler returns only the requested slice (filtered/aggregated), not the full 240-record dataset.
- **Response**: Claude returns a single JSON object. No preamble or explanation outside the JSON.

## Learned Context
Before executing, check `memory/learned_context.md` for:
- SVG patterns that render well across browsers
- Prompt adjustments that improved visualization quality
- Common tool-use loop failure modes and fixes

## Dependencies
- `anthropic` — Anthropic Claude API SDK
- `agent-memory-client` — Redis Agent Memory Server Python SDK
- `redis[hiredis]` — Redis client for `fetch_data` handler
