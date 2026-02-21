#!/usr/bin/env python3
"""
Search long-term memory in the Redis Agent Memory Server.

Usage:
    python search_memory.py "user's preferred theme" --user-id demo-user --limit 5
"""

import argparse
import asyncio
import json
import os
import sys


async def search(query: str, user_id: str | None, limit: int, memory_url: str):
    """Search long-term memory and display results."""
    from agent_memory_client import create_memory_client

    client = await create_memory_client(memory_url)

    kwargs = {"text": query, "limit": limit}
    if user_id:
        kwargs["user_id"] = user_id

    results = await client.search_long_term_memory(**kwargs)

    if not results:
        print("No memories found")
        return

    print(f"Found {len(results)} memories:")
    for i, mem in enumerate(results, 1):
        print(f"\n--- Memory {i} ---")
        print(f"  Text: {mem.text}")
        print(f"  Type: {mem.memory_type}")
        if hasattr(mem, "topics") and mem.topics:
            print(f"  Topics: {mem.topics}")
        if hasattr(mem, "entities") and mem.entities:
            print(f"  Entities: {mem.entities}")
        if hasattr(mem, "created_at") and mem.created_at:
            print(f"  Created: {mem.created_at}")


def main():
    parser = argparse.ArgumentParser(description="Search VoxVisual long-term memory")
    parser.add_argument("query", help="Search query text")
    parser.add_argument("--user-id", help="Filter by user ID")
    parser.add_argument("--limit", type=int, default=5, help="Max results (default: 5)")
    parser.add_argument(
        "--memory-url",
        default=os.environ.get("MEMORY_URL", "http://localhost:8000"),
        help="Redis Agent Memory Server URL",
    )
    args = parser.parse_args()

    asyncio.run(search(args.query, args.user_id, args.limit, args.memory_url))


if __name__ == "__main__":
    main()
