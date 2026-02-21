#!/usr/bin/env python3
"""
Generate a memory-enriched prompt context from the Redis Agent Memory Server.

Usage:
    python memory_prompt.py "Show me Q3 sales" --session-id demo-001 --user-id demo-user
"""

import argparse
import asyncio
import os
import sys


async def get_prompt(text: str, session_id: str, user_id: str | None, memory_url: str):
    """Generate and display a memory-enriched prompt context."""
    from agent_memory_client import create_memory_client

    client = await create_memory_client(memory_url)

    kwargs = {"text": text, "session_id": session_id}
    if user_id:
        kwargs["user_id"] = user_id

    prompt_context = await client.memory_prompt(**kwargs)

    print("=== Memory-Enriched Prompt Context ===")
    print(prompt_context)
    print("=== End ===")


def main():
    parser = argparse.ArgumentParser(description="Generate memory-enriched prompt context")
    parser.add_argument("text", help="User transcript / query text")
    parser.add_argument("--session-id", required=True, help="Working memory session ID")
    parser.add_argument("--user-id", help="User ID for long-term memory search")
    parser.add_argument(
        "--memory-url",
        default=os.environ.get("MEMORY_URL", "http://localhost:8000"),
        help="Redis Agent Memory Server URL",
    )
    args = parser.parse_args()

    asyncio.run(get_prompt(args.text, args.session_id, args.user_id, args.memory_url))


if __name__ == "__main__":
    main()
