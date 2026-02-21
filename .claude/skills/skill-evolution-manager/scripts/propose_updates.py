#!/usr/bin/env python3
"""
Proposes updates to a skill's learned_context.md based on logs and feedback.

Usage:
    python propose_updates.py <skill_path>

This script analyzes the skill's memory/ directory and generates markdown
content to be appended to learned_context.md.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

# Import sibling module
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from analyze_skill_performance import generate_summary


def format_troubleshooting_entry(error: str, count: int, examples: List[Dict]) -> str:
    """Format a troubleshooting entry for learned_context.md."""
    entry = f"""
### Troubleshooting: {error}

**Frequency:** {count} occurrences
**Added:** {datetime.now().strftime('%Y-%m-%d')}

**Symptoms:**
- Error message: `{error}`

**Resolution:**
- [TODO: Add resolution steps based on error analysis]

**Example inputs that triggered this:**
"""
    for ex in examples[:3]:
        entry += f"- `{ex.get('inputs', 'N/A')}`\n"

    return entry


def format_user_correction(correction: Dict) -> str:
    """Format a user correction for learned_context.md."""
    content = correction.get('content', '')
    timestamp = correction.get('timestamp', 'Unknown')

    # Extract sections from the feedback markdown
    lines = content.split('\n')
    situation = ""
    error = ""
    fix = ""
    rationale = ""

    current_section = None
    for line in lines:
        if '## Situation' in line:
            current_section = 'situation'
        elif '## Error' in line:
            current_section = 'error'
        elif '## Correction' in line:
            current_section = 'correction'
        elif '## Rationale' in line:
            current_section = 'rationale'
        elif current_section and line.strip():
            if current_section == 'situation':
                situation += line + "\n"
            elif current_section == 'error':
                error += line + "\n"
            elif current_section == 'correction':
                fix += line + "\n"
            elif current_section == 'rationale':
                rationale += line + "\n"

    return f"""
### User Correction ({timestamp})

**Priority:** HIGH

**Situation:**
{situation.strip()}

**Problem:**
{error.strip()}

**Correct Approach:**
{fix.strip()}

**Why This Is Better:**
{rationale.strip()}
"""


def propose_updates(skill_path: str) -> Dict[str, Any]:
    """Generate proposed updates for a skill's learned_context.md."""
    summary = generate_summary(skill_path)

    proposals = []
    markdown_content = ""

    # Process recurring errors into troubleshooting entries
    log_analysis = summary.get('log_analysis', {})
    if log_analysis.get('recurring_errors'):
        for err_info in log_analysis['recurring_errors']:
            # Find example inputs for this error
            examples = [
                f for f in log_analysis.get('recent_failures', [])
                if f.get('error') == err_info['error']
            ]

            entry = format_troubleshooting_entry(
                err_info['error'],
                err_info['count'],
                examples
            )
            markdown_content += entry + "\n"
            proposals.append({
                'type': 'troubleshooting',
                'error': err_info['error'],
                'count': err_info['count']
            })

    # Process user corrections
    feedback_analysis = summary.get('feedback_analysis', {})
    if feedback_analysis.get('corrections'):
        for correction in feedback_analysis['corrections']:
            entry = format_user_correction(correction)
            markdown_content += entry + "\n"
            proposals.append({
                'type': 'user_correction',
                'filename': correction.get('filename')
            })

    return {
        "skill_path": skill_path,
        "skill_name": summary.get('skill_name'),
        "proposals": proposals,
        "markdown_content": markdown_content.strip(),
        "generated_at": datetime.now().isoformat()
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python propose_updates.py <skill_path>")
        sys.exit(1)

    skill_path = sys.argv[1]

    if not os.path.exists(skill_path):
        print(f"Error: Skill path does not exist: {skill_path}")
        sys.exit(1)

    result = propose_updates(skill_path)

    if result['proposals']:
        print(f"=== Proposed Updates for {result['skill_name']} ===\n")
        print(f"Generated: {result['generated_at']}")
        print(f"Proposals: {len(result['proposals'])}")
        print("\n--- Markdown Content ---\n")
        print(result['markdown_content'])
        print("\n--- End ---")
    else:
        print(f"No updates to propose for {result['skill_name']}")


if __name__ == "__main__":
    main()
