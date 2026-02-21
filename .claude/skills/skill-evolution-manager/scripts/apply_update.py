#!/usr/bin/env python3
"""
Safely applies proposed updates to a skill's learned_context.md.

Usage:
    python apply_update.py <skill_path> [--content <markdown_content>] [--from-proposals]

Options:
    --content         Direct markdown content to append
    --from-proposals  Generate and apply proposals automatically
    --dry-run         Show what would be applied without writing

Safety:
    - Always APPENDS to learned_context.md (never overwrites)
    - Creates backup before modification
    - Optionally creates git commit
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from typing import Optional

# Import sibling module
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from propose_updates import propose_updates


def create_backup(filepath: str) -> str:
    """Create a timestamped backup of a file."""
    if not os.path.exists(filepath):
        return ""

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{filepath}.backup_{timestamp}"
    shutil.copy2(filepath, backup_path)
    return backup_path


def append_to_learned_context(skill_path: str, content: str, dry_run: bool = False) -> dict:
    """Append content to a skill's learned_context.md."""
    memory_dir = os.path.join(skill_path, 'memory')
    context_file = os.path.join(memory_dir, 'learned_context.md')

    # Ensure memory directory exists
    os.makedirs(memory_dir, exist_ok=True)

    # Prepare the update with timestamp header
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    update_content = f"\n\n---\n## Learning Update ({timestamp})\n\n{content}"

    if dry_run:
        return {
            "status": "dry_run",
            "would_append": update_content,
            "target_file": context_file
        }

    # Create backup if file exists
    backup_path = ""
    if os.path.exists(context_file):
        backup_path = create_backup(context_file)

    # Read existing content or create header
    if os.path.exists(context_file):
        with open(context_file, 'r') as f:
            existing = f.read()
    else:
        skill_name = os.path.basename(skill_path)
        existing = f"""# Learned Context: {skill_name}

This file contains adaptations and learnings accumulated during skill execution.
The skill-evolution-manager automatically maintains this file.

**DO NOT EDIT MANUALLY** - Changes may be overwritten by the learning system.
"""

    # Append new content
    new_content = existing + update_content

    with open(context_file, 'w') as f:
        f.write(new_content)

    return {
        "status": "applied",
        "target_file": context_file,
        "backup_file": backup_path,
        "content_length": len(update_content)
    }


def git_commit_update(skill_path: str, message: str) -> dict:
    """Create a git commit for the learned_context.md update."""
    context_file = os.path.join(skill_path, 'memory', 'learned_context.md')

    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ['git', 'rev-parse', '--git-dir'],
            cwd=skill_path,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return {"status": "not_git_repo"}

        # Stage the file
        subprocess.run(
            ['git', 'add', context_file],
            cwd=skill_path,
            check=True
        )

        # Commit
        subprocess.run(
            ['git', 'commit', '-m', message],
            cwd=skill_path,
            check=True
        )

        return {"status": "committed", "message": message}

    except subprocess.CalledProcessError as e:
        return {"status": "git_error", "error": str(e)}
    except FileNotFoundError:
        return {"status": "git_not_found"}


def main():
    parser = argparse.ArgumentParser(
        description="Apply updates to a skill's learned_context.md"
    )
    parser.add_argument('skill_path', help='Path to the skill directory')
    parser.add_argument('--content', help='Markdown content to append')
    parser.add_argument('--from-proposals', action='store_true',
                        help='Generate and apply proposals automatically')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be applied without writing')
    parser.add_argument('--git-commit', action='store_true',
                        help='Create a git commit after applying')

    args = parser.parse_args()

    if not os.path.exists(args.skill_path):
        print(f"Error: Skill path does not exist: {args.skill_path}")
        sys.exit(1)

    content = args.content

    # Generate content from proposals if requested
    if args.from_proposals:
        result = propose_updates(args.skill_path)
        if not result['markdown_content']:
            print("No proposals to apply.")
            sys.exit(0)
        content = result['markdown_content']

    if not content:
        print("Error: No content provided. Use --content or --from-proposals")
        sys.exit(1)

    # Apply the update
    result = append_to_learned_context(args.skill_path, content, args.dry_run)

    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Target: {result['target_file']}")
        print(f"\nWould append:\n{result['would_append']}")
    else:
        print(f"Update applied to: {result['target_file']}")
        if result.get('backup_file'):
            print(f"Backup created: {result['backup_file']}")

        # Git commit if requested
        if args.git_commit:
            skill_name = os.path.basename(args.skill_path)
            commit_msg = f"skill-evolution-manager: Update learned_context.md for {skill_name}"
            git_result = git_commit_update(args.skill_path, commit_msg)
            print(f"Git: {git_result['status']}")


if __name__ == "__main__":
    main()
