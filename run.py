#!/usr/bin/env python3
"""
VoxVisual — startup script.

Usage:
    python run.py              # seed data + start server on port 8080
    python run.py --port 3000  # custom port
    python run.py --seed-only  # just seed the dataset
"""

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent / ".env")


def check_redis():
    """Verify Redis is reachable and has the JSON module."""
    try:
        result = subprocess.run(
            ["redis-cli", "ping"],
            capture_output=True, text=True, timeout=5,
        )
        if "PONG" not in result.stdout:
            print("ERROR: Redis is not running. Start it with:")
            print("  /opt/redis-stack/bin/redis-server --daemonize yes --loadmodule /opt/redis-stack/lib/rejson.so")
            sys.exit(1)
    except FileNotFoundError:
        print("ERROR: redis-cli not found. Install Redis Stack.")
        sys.exit(1)

    result = subprocess.run(
        ["redis-cli", "MODULE", "LIST"],
        capture_output=True, text=True, timeout=5,
    )
    if "ReJSON" not in result.stdout:
        print("WARNING: RedisJSON module not loaded. JSON operations may fail.")
        print("  Start Redis with: /opt/redis-stack/bin/redis-server --daemonize yes --loadmodule /opt/redis-stack/lib/rejson.so")


async def seed():
    """Seed the PedalForce dataset."""
    # Add project root to path
    sys.path.insert(0, ".")
    from scripts.seed_dataset import seed_dataset
    await seed_dataset()


def main():
    parser = argparse.ArgumentParser(description="VoxVisual server")
    parser.add_argument("--port", type=int, default=8080, help="Server port")
    parser.add_argument("--seed-only", action="store_true", help="Only seed dataset")
    parser.add_argument("--no-seed", action="store_true", help="Skip seeding")
    args = parser.parse_args()

    check_redis()

    if not args.no_seed:
        print("Seeding demo dataset...")
        asyncio.run(seed())

    if args.seed_only:
        return

    import uvicorn
    print(f"\nStarting VoxVisual on http://localhost:{args.port}")
    print("Press Ctrl+C to stop\n")
    uvicorn.run("backend.app:app", host="0.0.0.0", port=args.port, reload=False)


if __name__ == "__main__":
    main()
