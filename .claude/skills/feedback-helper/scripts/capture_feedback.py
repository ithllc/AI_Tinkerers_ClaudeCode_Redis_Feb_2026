#!/usr/bin/env python3
"""
Saves structured feedback to a target skill's memory/feedback/ directory.

Usage:
    python capture_feedback.py <target_skill_path> "<situation>" "<error>" "<correction>" "<rationale>"

Example:
    python capture_feedback.py /path/to/.claude/skills/my-skill \
        "Describe what you were trying to do" \
        "Describe the error or suboptimal behavior" \
        "Describe the correct behavior" \
        "Explain why this approach is better"
"""

import sys
import datetime
import os
import json
from typing import Optional


def capture_feedback(
    target_skill_path: str,
    situation: str,
    error: str,
    correction: str,
    rationale: str,
    metadata: Optional[dict] = None
) -> dict:
    """
    Saves structured feedback to a target skill's memory/feedback/ directory.

    Args:
        target_skill_path: Path to the skill directory
        situation: What the user was trying to do
        error: The specific error or suboptimal behavior
        correction: The correct behavior or approach
        rationale: Why the correction is better
        metadata: Optional additional metadata

    Returns:
        dict with status and file path
    """
    # Validate skill path
    if not os.path.exists(target_skill_path):
        return {"status": "error", "message": f"Skill path not found: {target_skill_path}"}

    # Use script location as anchor for relative paths
    feedback_dir = os.path.join(target_skill_path, 'memory', 'feedback')
    os.makedirs(feedback_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"correction_{timestamp}.md"
    filepath = os.path.join(feedback_dir, filename)

    skill_name = os.path.basename(target_skill_path)

    content = f"""# User Feedback - {timestamp}

**Target Skill:** {skill_name}
**Captured:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Situation
{situation}

## Error / Suboptimal Behavior
{error}

## Correction
{correction}

## Rationale (Why is this better?)
{rationale}
"""

    if metadata:
        content += f"\n## Metadata\n```json\n{json.dumps(metadata, indent=2)}\n```\n"

    with open(filepath, 'w') as f:
        f.write(content)

    return {
        "status": "saved",
        "filepath": filepath,
        "skill_name": skill_name,
        "timestamp": timestamp
    }


def main():
    if len(sys.argv) < 6:
        print("Usage: capture_feedback.py <target_skill_path> <situation> <error> <correction> <rationale>")
        print("\nExample:")
        print('  python capture_feedback.py /path/to/skill "Situation" "Error" "Correction" "Rationale"')
        sys.exit(1)

    target_skill_path = sys.argv[1]
    situation = sys.argv[2]
    error = sys.argv[3]
    correction = sys.argv[4]
    rationale = sys.argv[5]

    result = capture_feedback(target_skill_path, situation, error, correction, rationale)

    if result["status"] == "saved":
        print(f"Feedback saved to {result['filepath']}")
    else:
        print(f"Error: {result['message']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
