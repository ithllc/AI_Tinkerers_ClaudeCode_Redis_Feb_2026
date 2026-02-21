#!/usr/bin/env python3
"""
Analyzes execution logs for a specific skill to find failure patterns.

Usage:
    python analyze_skill_performance.py <skill_path>

Example:
    python analyze_skill_performance.py /path/to/.claude/skills/my-skill
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


def analyze_logs(skill_path: str) -> Dict[str, Any]:
    """Analyzes logs for a specific skill to find failure patterns."""
    log_file = os.path.join(skill_path, 'memory/logs/execution_history.jsonl')

    if not os.path.exists(log_file):
        return {"status": "no_logs", "skill_path": skill_path}

    entries = []
    failures = []
    successes = 0

    with open(log_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entries.append(entry)
                if entry.get('success', False):
                    successes += 1
                else:
                    failures.append({
                        'error': entry.get('error', 'Unknown Error'),
                        'inputs': entry.get('inputs'),
                        'timestamp': entry.get('timestamp')
                    })
            except json.JSONDecodeError:
                continue

    error_counts = Counter(f['error'] for f in failures)

    # Identify errors exceeding threshold (>3 occurrences)
    recurring_errors = [
        {'error': error, 'count': count}
        for error, count in error_counts.items()
        if count > 3
    ]

    return {
        "status": "analyzed",
        "skill_path": skill_path,
        "total_executions": len(entries),
        "successes": successes,
        "failures": len(failures),
        "success_rate": round(successes / len(entries) * 100, 1) if entries else 0,
        "top_errors": error_counts.most_common(5),
        "recurring_errors": recurring_errors,
        "recent_failures": failures[-10:]  # Last 10 failures for context
    }


def analyze_feedback(skill_path: str) -> Dict[str, Any]:
    """Analyzes user feedback files for a specific skill."""
    feedback_dir = os.path.join(skill_path, 'memory/feedback')

    if not os.path.exists(feedback_dir):
        return {"status": "no_feedback", "skill_path": skill_path}

    feedback_files = [f for f in os.listdir(feedback_dir) if f.endswith('.md')]

    if not feedback_files:
        return {"status": "no_feedback", "skill_path": skill_path}

    corrections = []
    for filename in feedback_files:
        filepath = os.path.join(feedback_dir, filename)
        with open(filepath, 'r') as f:
            content = f.read()
            corrections.append({
                'filename': filename,
                'content': content,
                'timestamp': filename.replace('correction_', '').replace('.md', '')
            })

    return {
        "status": "analyzed",
        "skill_path": skill_path,
        "total_corrections": len(corrections),
        "corrections": corrections
    }


def generate_summary(skill_path: str) -> Dict[str, Any]:
    """Generate a complete performance summary for a skill."""
    log_analysis = analyze_logs(skill_path)
    feedback_analysis = analyze_feedback(skill_path)

    skill_name = os.path.basename(skill_path)

    summary = {
        "skill_name": skill_name,
        "skill_path": skill_path,
        "log_analysis": log_analysis,
        "feedback_analysis": feedback_analysis,
        "recommendations": []
    }

    # Generate recommendations
    if log_analysis.get('recurring_errors'):
        for err in log_analysis['recurring_errors']:
            summary['recommendations'].append({
                'type': 'troubleshooting',
                'priority': 'high',
                'reason': f"Error '{err['error']}' occurred {err['count']} times",
                'action': f"Add troubleshooting entry for: {err['error']}"
            })

    if feedback_analysis.get('total_corrections', 0) > 0:
        summary['recommendations'].append({
            'type': 'user_correction',
            'priority': 'high',
            'reason': f"{feedback_analysis['total_corrections']} user corrections pending",
            'action': "Process user corrections into learned_context.md"
        })

    if log_analysis.get('success_rate', 100) < 80:
        summary['recommendations'].append({
            'type': 'review',
            'priority': 'medium',
            'reason': f"Success rate is {log_analysis.get('success_rate', 0)}%",
            'action': "Review skill instructions and examples"
        })

    return summary


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_skill_performance.py <skill_path>")
        print("\nExample:")
        print("  python analyze_skill_performance.py /path/to/.claude/skills/my-skill")
        sys.exit(1)

    skill_path = sys.argv[1]

    if not os.path.exists(skill_path):
        print(f"Error: Skill path does not exist: {skill_path}")
        sys.exit(1)

    summary = generate_summary(skill_path)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
