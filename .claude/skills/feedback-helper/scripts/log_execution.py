#!/usr/bin/env python3
"""
Logs skill execution to memory/logs/execution_history.jsonl

Usage (CLI):
    python log_execution.py <skill_name> <success> <message>

Usage (Python import):
    from log_execution import log_execution
    log_execution("feedback-helper", {"user_query": "..."}, {"status": "saved"}, True)

Note: CLI mode uses simplified inputs. For structured data, import the function.
"""

import sys
import json
import datetime
import os
from typing import Any, Optional


def log_execution(
    skill_name: str,
    input_args: Any,
    output_result: Any,
    success: bool,
    error_msg: Optional[str] = None
) -> dict:
    """
    Logs skill execution to memory/logs/execution_history.jsonl

    Args:
        skill_name: Name of the skill being logged
        input_args: Input arguments (any serializable type)
        output_result: Output result (any serializable type)
        success: Whether execution succeeded
        error_msg: Optional error message if failed

    Returns:
        dict with status and log file path
    """
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../memory/logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'execution_history.jsonl')

    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "skill": skill_name,
        "inputs": input_args,
        "output": output_result,
        "success": success,
        "error": error_msg
    }

    with open(log_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')

    return {"status": "logged", "log_file": log_file}


if __name__ == "__main__":
    # CLI usage: python log_execution.py <skill_name> <success_bool> <message>
    if len(sys.argv) < 4:
        print("Usage: log_execution.py <skill_name> <success> <message>")
        print("\nExample:")
        print("  python log_execution.py feedback-helper True 'Feedback saved'")
        sys.exit(1)

    skill_name = sys.argv[1]
    success = sys.argv[2].lower() == "true"
    message = sys.argv[3]

    # CLI mode: simplified inputs
    result = log_execution(
        skill_name,
        "CLI_ARGS",  # Placeholder for CLI usage
        message,
        success,
        None if success else message
    )
    print(f"Logged to {result['log_file']}")
