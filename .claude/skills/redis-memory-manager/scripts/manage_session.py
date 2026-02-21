#!/usr/bin/env python3
"""
CLI for working memory CRUD operations against the Redis Agent Memory Server.

Usage:
    python manage_session.py get --session-id demo-001
    python manage_session.py put --session-id demo-001 --data '{"visual_theme": "cyberpunk"}'
    python manage_session.py delete --session-id demo-001
    python manage_session.py list
"""

import argparse
import asyncio
import json
import os
import sys


async def run_get(session_id: str, memory_url: str):
    """Retrieve a working memory session."""
    from agent_memory_client import create_memory_client

    client = await create_memory_client(memory_url)
    session = await client.get_working_memory(session_id)

    if session is None:
        print(f"Session '{session_id}' not found")
        return

    print(f"Session: {session_id}")
    print(f"Messages: {len(session.messages) if session.messages else 0}")
    if session.context:
        print(f"Context summary: {session.context[:200]}...")
    if session.data:
        print(f"Data: {json.dumps(session.data, indent=2)}")


async def run_put(session_id: str, data: dict, memory_url: str):
    """Create or update a working memory session."""
    from agent_memory_client import create_memory_client
    from agent_memory_client.models import WorkingMemoryResponse

    client = await create_memory_client(memory_url)
    await client.put_working_memory(
        session_id=session_id,
        working_memory=WorkingMemoryResponse(data=data),
    )
    print(f"Session '{session_id}' updated with data: {json.dumps(data)}")


async def run_delete(session_id: str, memory_url: str):
    """Delete a working memory session."""
    from agent_memory_client import create_memory_client

    client = await create_memory_client(memory_url)
    await client.delete_working_memory(session_id)
    print(f"Session '{session_id}' deleted")


async def run_list(memory_url: str):
    """List all working memory sessions."""
    from agent_memory_client import create_memory_client

    client = await create_memory_client(memory_url)
    sessions = await client.list_working_memory()

    if not sessions:
        print("No active sessions")
        return

    print(f"Active sessions ({len(sessions)}):")
    for s in sessions:
        print(f"  - {s}")


def main():
    parser = argparse.ArgumentParser(description="Manage VoxVisual working memory sessions")
    parser.add_argument("action", choices=["get", "put", "delete", "list"])
    parser.add_argument("--session-id", help="Session identifier")
    parser.add_argument("--data", help="JSON data to store (for put action)")
    parser.add_argument(
        "--memory-url",
        default=os.environ.get("MEMORY_URL", "http://localhost:8000"),
        help="Redis Agent Memory Server URL",
    )
    args = parser.parse_args()

    if args.action in ("get", "put", "delete") and not args.session_id:
        print(f"Error: --session-id required for '{args.action}' action")
        sys.exit(1)

    if args.action == "get":
        asyncio.run(run_get(args.session_id, args.memory_url))
    elif args.action == "put":
        data = json.loads(args.data) if args.data else {}
        asyncio.run(run_put(args.session_id, data, args.memory_url))
    elif args.action == "delete":
        asyncio.run(run_delete(args.session_id, args.memory_url))
    elif args.action == "list":
        asyncio.run(run_list(args.memory_url))


if __name__ == "__main__":
    main()
