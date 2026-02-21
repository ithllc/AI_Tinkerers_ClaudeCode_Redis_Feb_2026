# Skill: redis-memory-manager

## Description
Manages all interactions with the Redis Agent Memory Server for VoxVisual. Handles working memory CRUD (session context, conversation history, filters, theme), long-term memory operations (search, create, lifecycle), memory-enriched prompt generation, and session lifecycle management.

## When to Use
Invoke this skill when:
- Creating, reading, updating, or deleting a VoxVisual session's working memory
- Searching long-term memory for relevant past interactions or user preferences
- Generating a memory-enriched prompt before calling Claude
- Debugging session state issues (missing filters, lost context, stale sessions)
- Managing session lifecycle (listing sessions, expiring old ones, inspecting memory extraction)
- Verifying that background memory extraction produced expected long-term records

## User Invocation
- "Show the current session memory"
- "Search long-term memory for E-Bike preferences"
- "Reset this session"
- "What does the memory server have for user demo-user?"
- "Generate a memory-enriched prompt for this transcript"

## Behavior

### Working Memory Operations

**Create / Update Session**
```python
from agent_memory_client import create_memory_client
from agent_memory_client.models import WorkingMemoryResponse, MemoryMessage

client = await create_memory_client("http://localhost:8000")

await client.put_working_memory(
    session_id="session-001",
    working_memory=WorkingMemoryResponse(
        messages=[
            MemoryMessage(role="user", content="Show me 2025 sales by category"),
            MemoryMessage(role="assistant", content="PedalForce had $22.1M in total 2025 revenue...")
        ],
        data={
            "last_query": "Show me 2025 sales by category",
            "connected_dataset": "pedalforce",
            "current_filters": {},
            "visual_theme": "default",
            "last_svg_hash": "abc123"
        }
    )
)
```

**Retrieve Session**
```python
session = await client.get_working_memory("session-001")
# session.messages — conversation history
# session.data — filters, theme, connected dataset
# session.context — auto-generated summary of older messages
```

**Delete Session**
```python
await client.delete_working_memory("session-001")
```

### Long-term Memory Operations

**Search**
```python
results = await client.search_long_term_memory(
    text="user's preferred visualization theme",
    user_id="demo-user",
    limit=5
)
```

**Create**
```python
from agent_memory_client.models import ClientMemoryRecord, MemoryTypeEnum

await client.create_long_term_memory([
    ClientMemoryRecord(
        text="User prefers dark cyberpunk theme for visualizations",
        memory_type=MemoryTypeEnum.SEMANTIC,
        user_id="demo-user",
        topics=["preferences", "visual-theme"],
        entities=["cyberpunk"]
    )
])
```

### Memory-Enriched Prompt Generation
```python
prompt_context = await client.memory_prompt(
    text="Break down Q3 sales by region",
    session_id="session-001",
    user_id="demo-user"
)
# Returns combined working memory + relevant long-term memories
# Use this as context in the Claude system prompt
```

### REST API Quick Reference
| Operation | Endpoint | Method |
|---|---|---|
| List sessions | `/v1/working-memory/` | GET |
| Get session | `/v1/working-memory/{session_id}` | GET |
| Create/update session | `/v1/working-memory/{session_id}` | PUT |
| Delete session | `/v1/working-memory/{session_id}` | DELETE |
| Search long-term memory | `/v1/long-term-memory/search` | POST |
| Create long-term memory | `/v1/long-term-memory/` | POST |
| Get memory by ID | `/v1/long-term-memory/{memory_id}` | GET |
| Update memory | `/v1/long-term-memory/{memory_id}` | PATCH |
| Delete memories | `/v1/long-term-memory` | DELETE |
| Memory-enriched prompt | `/v1/memory/prompt` | POST |
| Background task status | `/v1/tasks/{task_id}` | GET |

## Scripts

### `manage_session.py`
CLI for working memory CRUD operations.

```bash
# Get session state
python scripts/manage_session.py get --session-id demo-001

# Create/update session
python scripts/manage_session.py put --session-id demo-001 \
    --data '{"connected_dataset": "pedalforce", "visual_theme": "cyberpunk"}'

# Delete session
python scripts/manage_session.py delete --session-id demo-001

# List all sessions
python scripts/manage_session.py list
```

### `search_memory.py`
Search long-term memory.

```bash
python scripts/search_memory.py "user's preferred theme" \
    --user-id demo-user --limit 5
```

### `memory_prompt.py`
Generate a memory-enriched prompt context.

```bash
python scripts/memory_prompt.py "Show me Q3 sales" \
    --session-id demo-001 --user-id demo-user
```

### `log_execution.py`
Standard execution logger.

```bash
python scripts/log_execution.py <skill_name> <success> <message>
```

## Session Data Schema (Working Memory `data` field)
```json
{
    "last_query": "string — the most recent user transcript",
    "connected_dataset": "string — e.g. 'pedalforce'",
    "current_filters": {
        "months": ["2025-01"],
        "categories": ["E-Bikes"],
        "regions": ["East"]
    },
    "visual_theme": "string — e.g. 'cyberpunk', 'minimalist', 'default'",
    "last_svg_hash": "string — hash of the last generated SVG for caching"
}
```

## Configuration
- **Memory Server URL**: env `MEMORY_URL` or default `http://localhost:8000`
- **Redis URL**: env `REDIS_URL` or default `redis://localhost:6379`
- **Auth**: Disabled for development (`DISABLE_AUTH=true`). Enable OAuth2 for production.

## Token Efficiency
- **Get/Put**: Report only key fields: session_id, message count, data summary.
- **Search**: Return memory text and relevance score. Omit vector embeddings.
- **Prompt**: Return the assembled prompt text only, not the raw memory records.

## Learned Context
Before executing, check `memory/learned_context.md` for common session management patterns and edge cases.

## Dependencies
- `agent-memory-client` — Redis Agent Memory Server Python SDK
- Running Redis Agent Memory Server instance (port 8000)
