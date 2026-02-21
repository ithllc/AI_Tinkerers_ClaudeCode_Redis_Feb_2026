"""
VoxVisual — Claude API integration with memory-enriched prompts.

Orchestrates: user query -> memory retrieval -> Claude API call with
fetch_data tool loop -> memory update -> structured response.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic

from backend.data_connector import FETCH_DATA_TOOL, handle_fetch_data

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = os.environ.get("GENERATION_MODEL", "claude-sonnet-4-5-20250929")
MEMORY_SERVER_URL = os.environ.get("MEMORY_SERVER_URL", "http://localhost:8000")

SYSTEM_PROMPT = """\
You are a senior data visualization designer. You output only valid SVG and CSS. \
Use <animate> tags for motion. Ensure the SVG is responsive (width='100%'). \
You have access to the `fetch_data` tool — always call it to get real data \
before generating a visualization. Never invent or hallucinate data.

When generating visualizations:
- Use vibrant colors with a dark background (#0f0f23)
- Include smooth animations using <animate> or <animateTransform>
- Make charts responsive with viewBox and width='100%'
- Label axes and data points clearly with white or light text
- Use proper spacing and padding
- For bar charts, use colorful gradients
- Include a chart title inside the SVG

Return your response as JSON with this exact structure:
{"explanation": "Brief text summary of insights for TTS", "svg_code": "<svg>...</svg>", "css_styles": "@keyframes... or empty string"}

IMPORTANT: Return ONLY the raw JSON object. No markdown, no code fences, no extra text.\
"""

# ---------------------------------------------------------------------------
# Memory helpers (gracefully degrade if server unavailable)
# ---------------------------------------------------------------------------


async def _get_memory_context(
    session_id: str, user_id: str, user_query: str
) -> str:
    """Retrieve memory context from the Redis Agent Memory Server."""
    try:
        from agent_memory_client import create_memory_client

        client = await create_memory_client(MEMORY_SERVER_URL)
        prompt_ctx = await client.memory_prompt(
            text=user_query,
            session_id=session_id,
            user_id=user_id,
        )
        return prompt_ctx if isinstance(prompt_ctx, str) else str(prompt_ctx)
    except Exception:
        return ""


async def update_memory(
    session_id: str,
    user_id: str,
    user_query: str,
    explanation: str,
    filters: dict | None = None,
) -> None:
    """Update working memory after an interaction."""
    try:
        from agent_memory_client import create_memory_client
        from agent_memory_client.models import MemoryMessage, WorkingMemoryResponse

        client = await create_memory_client(MEMORY_SERVER_URL)
        await client.put_working_memory(
            session_id=session_id,
            working_memory=WorkingMemoryResponse(
                messages=[
                    MemoryMessage(role="user", content=user_query),
                    MemoryMessage(role="assistant", content=explanation),
                ],
                data={
                    "last_query": user_query,
                    "connected_dataset": "pedalforce",
                    "current_filters": filters or {},
                },
            ),
        )
    except Exception:
        pass  # Memory server not available — silently skip


# ---------------------------------------------------------------------------
# Tool-use loop
# ---------------------------------------------------------------------------


def _extract_json(text: str) -> dict:
    """Parse JSON from Claude's response, handling code fences."""
    # Strip markdown code fences if present
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    return json.loads(text)


async def generate_visualization(
    user_query: str,
    session_id: str,
    user_id: str = "default",
) -> dict[str, Any]:
    """Generate a data visualization from a natural-language query.

    Returns a dict with keys: explanation, svg_code, css_styles.
    """
    client = anthropic.Anthropic()

    # -- Assemble system prompt with optional memory context ----------------
    memory_context = await _get_memory_context(session_id, user_id, user_query)
    system = SYSTEM_PROMPT
    if memory_context:
        system += f"\n\n## Session Context\n{memory_context}"

    # -- Initial Claude call ------------------------------------------------
    messages: list[dict] = [{"role": "user", "content": user_query}]

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=system,
        tools=[FETCH_DATA_TOOL],
        messages=messages,
    )

    # -- Tool-use loop (up to 10 rounds) ------------------------------------
    collected_filters: dict = {}
    for _ in range(10):
        if response.stop_reason != "tool_use":
            break

        # Process all tool_use blocks in the response
        tool_results = []
        for block in response.content:
            if block.type == "tool_use" and block.name == "fetch_data":
                tool_input = block.input
                # Track filters for memory
                if "filters" in tool_input:
                    collected_filters.update(tool_input["filters"])

                result_json = await handle_fetch_data(tool_input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_json,
                    }
                )

        if not tool_results:
            break

        # Send tool results back to Claude
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        response = client.messages.create(
            model=MODEL,
            max_tokens=8192,
            system=system,
            tools=[FETCH_DATA_TOOL],
            messages=messages,
        )

    # -- Extract final text response ----------------------------------------
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    if not final_text:
        return {
            "explanation": "I wasn't able to generate a visualization.",
            "svg_code": "",
            "css_styles": "",
        }

    # -- Parse structured JSON ----------------------------------------------
    try:
        result = _extract_json(final_text)
    except (json.JSONDecodeError, ValueError):
        # If parsing fails, treat the whole response as explanation
        result = {
            "explanation": final_text[:500],
            "svg_code": "",
            "css_styles": "",
        }

    # -- Update memory (fire-and-forget) ------------------------------------
    await update_memory(
        session_id=session_id,
        user_id=user_id,
        user_query=user_query,
        explanation=result.get("explanation", ""),
        filters=collected_filters,
    )

    return {
        "explanation": result.get("explanation", ""),
        "svg_code": result.get("svg_code", ""),
        "css_styles": result.get("css_styles", ""),
    }
