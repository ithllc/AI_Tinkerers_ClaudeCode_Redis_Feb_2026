#!/usr/bin/env python3
"""
Context Curator - "The Briefing Officer"
Generates optimized prompts using Greenfield vs Brownfield strategies.
Enforces the 2-paragraph rule for context efficiency.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA = True
except ImportError:
    HAS_JINJA = False

SKILL_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = SKILL_DIR / "templates"
STATE_FILE = SKILL_DIR / "kanban_state.json"
LEARNED_CONTEXT_FILE = SKILL_DIR / "learned_context.md"


class ContextCurator:
    """
    Generates worker prompts optimized for token efficiency.

    Two strategies:
    - Greenfield: New features with architectural context
    - Brownfield: Maintenance tasks with specific file focus
    """

    # Task types that are considered "Greenfield"
    GREENFIELD_TYPES = {"feature", "new", "create", "implement"}

    # Task types that are considered "Brownfield"
    BROWNFIELD_TYPES = {"bugfix", "fix", "refactor", "update", "patch", "hotfix"}

    def __init__(self):
        self.state = self._load_state()
        self.learned_context = self._load_learned_context()

        if HAS_JINJA:
            self.jinja_env = Environment(
                loader=FileSystemLoader(str(TEMPLATES_DIR)),
                trim_blocks=True,
                lstrip_blocks=True
            )

    def _load_state(self) -> Dict[str, Any]:
        """Load current state from JSON."""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def _load_learned_context(self) -> str:
        """Load learned context for domain-specific patterns."""
        if LEARNED_CONTEXT_FILE.exists():
            with open(LEARNED_CONTEXT_FILE, 'r') as f:
                return f.read()
        return ""

    def classify_task(self, task: Dict[str, Any]) -> str:
        """Classify task as 'greenfield' or 'brownfield'."""
        task_type = task.get("type", "").lower()

        if task_type in self.GREENFIELD_TYPES:
            return "greenfield"
        elif task_type in self.BROWNFIELD_TYPES:
            return "brownfield"
        else:
            # Heuristics based on title
            title = task.get("title", "").lower()
            if any(word in title for word in ["add", "new", "create", "implement"]):
                return "greenfield"
            elif any(word in title for word in ["fix", "bug", "patch", "update"]):
                return "brownfield"

        # Default to brownfield (more conservative context)
        return "brownfield"

    def generate_prompt(self, task: Dict[str, Any],
                        worker_id: str,
                        worktree_path: str,
                        branch_name: str) -> str:
        """
        Generate an optimized worker prompt following the 2-paragraph rule.

        Structure:
        - Paragraph 1: Objective (what to do, definition of done)
        - Paragraph 2: Constraints (technical boundaries, patterns)
        - Attachments: Relevant file paths only
        """
        task_class = self.classify_task(task)

        if HAS_JINJA:
            return self._generate_with_jinja(task, task_class, worker_id,
                                             worktree_path, branch_name)
        else:
            return self._generate_simple(task, task_class, worker_id,
                                         worktree_path, branch_name)

    def _generate_with_jinja(self, task: Dict[str, Any], task_class: str,
                              worker_id: str, worktree_path: str,
                              branch_name: str) -> str:
        """Generate prompt using Jinja2 templates."""
        template_name = f"task_{task_class}.j2"

        try:
            template = self.jinja_env.get_template(template_name)
        except:
            # Fallback to simple generation
            return self._generate_simple(task, task_class, worker_id,
                                         worktree_path, branch_name)

        # Extract domain-specific learnings
        domain_patterns = self._extract_domain_patterns(task.get("domain", ""))

        return template.render(
            task=task,
            worker_id=worker_id,
            worktree_path=worktree_path,
            branch_name=branch_name,
            domain_patterns=domain_patterns,
            timestamp=datetime.now().isoformat()
        )

    def _generate_simple(self, task: Dict[str, Any], task_class: str,
                          worker_id: str, worktree_path: str,
                          branch_name: str) -> str:
        """Generate prompt without Jinja2 (fallback)."""

        if task_class == "greenfield":
            prompt = self._greenfield_prompt(task, worktree_path, branch_name)
        else:
            prompt = self._brownfield_prompt(task, worktree_path, branch_name)

        # Add Source Context (from Implementation Plan)
        if task.get("source_context"):
            prompt += f"\n\n## Strategic Context\n{task['source_context']}\n(Derived from approved Implementation Plan - adhere to this scope)"

        # Add domain-specific context if available
        domain_patterns = self._extract_domain_patterns(task.get("domain", ""))
        if domain_patterns:
            prompt += f"\n\n## Domain Patterns\n{domain_patterns}"

        # Add Tool Footer
        prompt += self._get_tool_footer()

        return prompt

    def _get_tool_footer(self) -> str:
        """Standard footer priming the worker on available skills."""
        return """

## Available Specialized Skills
Use these skills to complete your task efficiently. Do NOT write custom scripts for these functions:

1. Use available project skill scripts in `.claude/skills/` for specialized tasks rather than writing custom scripts.
2. Check skill SKILL.md files to understand available commands before implementing bespoke solutions.

3. **Paper Generation**: `bash .claude/skills/paper-generation-assistant/scripts/...`
   - Use for academic paper LaTeX generation, Z3 verification, or PDF compilation tasks.

4. **Feedback**: `python .claude/skills/feedback-helper/scripts/capture_feedback.py ...`
   - (System use) If you are stuck, requesting feedback is better than guessing.

**Rule:** Always check `.claude/skills/` before writing utility scripts.
"""

    def _greenfield_prompt(self, task: Dict[str, Any],
                           worktree_path: str, branch_name: str) -> str:
        """Generate Greenfield (new feature) prompt."""
        title = task.get("title", "Untitled Task")
        description = task.get("description", "")
        domain = task.get("domain", "unknown")
        files = task.get("files", [])

        # Paragraph 1: Objective
        objective = f"""## Objective

Implement: **{title}**

{description if description else f"Create a new {task.get('type', 'feature')} in the {domain} domain."}

**Definition of Done:**
- Feature is fully implemented and functional
- Code follows existing project patterns
- No linting errors or type issues
- Changes are committed to branch `{branch_name}`"""

        # Paragraph 2: Constraints
        constraints = f"""## Constraints

- Working directory: `{worktree_path}`
- Branch: `{branch_name}` (already checked out)
- Domain: `{domain}`
- Follow existing code patterns in the codebase
- Do NOT modify unrelated files
- Do NOT add unnecessary dependencies
- Commit your changes when complete with a descriptive message"""

        # Attachments
        attachments = ""
        if files:
            attachments = "\n\n## Reference Files\n" + "\n".join(f"- `{f}`" for f in files)

        return objective + "\n\n" + constraints + attachments

    def _brownfield_prompt(self, task: Dict[str, Any],
                           worktree_path: str, branch_name: str) -> str:
        """Generate Brownfield (maintenance) prompt."""
        title = task.get("title", "Untitled Task")
        description = task.get("description", "")
        domain = task.get("domain", "unknown")
        files = task.get("files", [])
        error_log = task.get("error_log", [])

        # Paragraph 1: Objective
        objective = f"""## Objective

{task.get('type', 'Fix').capitalize()}: **{title}**

{description if description else f"Apply maintenance to the {domain} domain."}

**Definition of Done:**
- Issue is resolved
- No regression in existing functionality
- Changes are minimal and focused
- Committed to branch `{branch_name}`"""

        # Include previous errors if this is a retry
        if error_log:
            last_error = error_log[-1].get("message", "")
            objective += f"\n\n**Previous Attempt Failed:**\n```\n{last_error[:500]}\n```\nAvoid this issue in your solution."

        # Paragraph 2: Constraints
        constraints = f"""## Constraints

- Working directory: `{worktree_path}`
- Branch: `{branch_name}` (already checked out)
- Domain: `{domain}`
- Make MINIMAL changes - fix only what's needed
- Do NOT refactor surrounding code
- Do NOT add new features
- Preserve existing behavior"""

        # Attachments - files are critical for brownfield
        attachments = ""
        if files:
            attachments = "\n\n## Files to Modify\n" + "\n".join(f"- `{f}` (READ THIS FIRST)" for f in files)
        else:
            attachments = f"\n\n## Finding the Issue\nSearch the `{domain}` domain for relevant files."

        return objective + "\n\n" + constraints + attachments

    def _extract_domain_patterns(self, domain: str) -> str:
        """Extract learned patterns for a specific domain."""
        if not domain or not self.learned_context:
            return ""

        # Look for domain-specific section in learned context
        lines = self.learned_context.split('\n')
        in_domain_section = False
        patterns = []

        for line in lines:
            if f"## {domain}" in line.lower() or f"### {domain}" in line.lower():
                in_domain_section = True
                continue
            elif line.startswith("## ") or line.startswith("### "):
                in_domain_section = False
            elif in_domain_section and line.strip():
                patterns.append(line)

        return "\n".join(patterns[:10])  # Limit to 10 lines

    def validate_prompt_length(self, prompt: str, max_paragraphs: int = 4) -> bool:
        """
        Validate that the prompt follows the 2-paragraph rule
        (plus attachments, max 4 sections total).
        """
        sections = prompt.split("##")
        return len(sections) <= max_paragraphs + 1  # +1 for content before first ##


# Simple in-place templates if Jinja2 not available
GREENFIELD_TEMPLATE = """## Objective

Implement: **{{ task.title }}**

{{ task.description or "Create a new " + task.type + " in the " + task.domain + " domain." }}

**Definition of Done:**
- Feature is fully implemented and functional
- Code follows existing project patterns
- No linting errors or type issues
- Changes are committed to branch `{{ branch_name }}`

## Constraints

- Working directory: `{{ worktree_path }}`
- Branch: `{{ branch_name }}` (already checked out)
- Domain: `{{ task.domain }}`
- Follow existing code patterns in the codebase
- Do NOT modify unrelated files
- Do NOT add unnecessary dependencies
- Commit your changes when complete

{% if task.files %}
## Reference Files
{% for f in task.files %}
- `{{ f }}`
{% endfor %}
{% endif %}

{% if domain_patterns %}
## Domain Patterns
{{ domain_patterns }}
{% endif %}
"""

BROWNFIELD_TEMPLATE = """## Objective

{{ task.type | capitalize }}: **{{ task.title }}**

{{ task.description or "Apply maintenance to the " + task.domain + " domain." }}

**Definition of Done:**
- Issue is resolved
- No regression in existing functionality
- Changes are minimal and focused
- Committed to branch `{{ branch_name }}`

{% if task.error_log %}
**Previous Attempt Failed:**
```
{{ task.error_log[-1].message[:500] }}
```
Avoid this issue in your solution.
{% endif %}

## Constraints

- Working directory: `{{ worktree_path }}`
- Branch: `{{ branch_name }}` (already checked out)
- Domain: `{{ task.domain }}`
- Make MINIMAL changes - fix only what's needed
- Do NOT refactor surrounding code
- Do NOT add new features
- Preserve existing behavior

{% if task.files %}
## Files to Modify
{% for f in task.files %}
- `{{ f }}` (READ THIS FIRST)
{% endfor %}
{% else %}
## Finding the Issue
Search the `{{ task.domain }}` domain for relevant files.
{% endif %}

{% if domain_patterns %}
## Domain Patterns
{{ domain_patterns }}
{% endif %}
"""


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Context Curator")
    parser.add_argument("--task-id", type=int, help="Generate prompt for task ID")
    parser.add_argument("--worker", default="worker-1", help="Worker ID")
    parser.add_argument("--worktree", default="/tmp/worktree-1", help="Worktree path")
    parser.add_argument("--branch", default="feature/task-1", help="Branch name")
    parser.add_argument("--classify", type=int, help="Classify task as greenfield/brownfield")

    args = parser.parse_args()
    curator = ContextCurator()

    if args.task_id or args.classify:
        task_id = args.task_id or args.classify

        # Find task in state
        task = None
        for queue in curator.state.get("tasks", {}).values():
            for t in queue:
                if t.get("id") == task_id:
                    task = t
                    break

        if not task:
            print(f"Task #{task_id} not found")
            return

        if args.classify:
            classification = curator.classify_task(task)
            print(f"Task #{task_id}: {classification}")
        else:
            prompt = curator.generate_prompt(
                task=task,
                worker_id=args.worker,
                worktree_path=args.worktree,
                branch_name=args.branch
            )
            print(prompt)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
