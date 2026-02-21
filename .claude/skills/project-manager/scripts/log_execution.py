#!/usr/bin/env python3
"""
Standard execution logger for the project-manager skill.
Logs all skill invocations to memory/logs/execution_history.jsonl
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SKILL_DIR = Path(__file__).parent.parent
LOG_DIR = SKILL_DIR / "memory" / "logs"
HISTORY_FILE = LOG_DIR / "execution_history.jsonl"


def log_execution(
    skill_name: str,
    input_args: Any,
    output_result: Any,
    success: bool,
    error_msg: Optional[str] = None
) -> dict:
    """
    Log a skill execution to the history file.

    Args:
        skill_name: Name of the skill being executed
        input_args: Input arguments provided to the skill
        output_result: Output/result from the skill execution
        success: Whether the execution was successful
        error_msg: Error message if execution failed

    Returns:
        The logged entry as a dictionary
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now().isoformat(),
        "skill": skill_name,
        "inputs": _serialize(input_args),
        "output": _serialize(output_result),
        "success": success,
        "error": error_msg
    }

    with open(HISTORY_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

    return entry


def _serialize(obj: Any) -> Any:
    """Safely serialize an object for JSON storage."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_serialize(item) for item in obj]
    if isinstance(obj, dict):
        return {str(k): _serialize(v) for k, v in obj.items()}
    return str(obj)


def get_recent_executions(limit: int = 10) -> list:
    """Get the most recent execution entries."""
    if not HISTORY_FILE.exists():
        return []

    entries = []
    with open(HISTORY_FILE, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return entries[-limit:]


if __name__ == "__main__":
    # Test logging
    entry = log_execution(
        skill_name="project-manager",
        input_args={"command": "test"},
        output_result={"status": "ok"},
        success=True
    )
    print(f"Logged: {json.dumps(entry, indent=2)}")
