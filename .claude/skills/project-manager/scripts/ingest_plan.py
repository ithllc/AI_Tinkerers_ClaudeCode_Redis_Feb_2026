#!/usr/bin/env python3
"""
Ingest Plan - "The Strategist"
Parses Technical Implementation Plans into actionable Kanban tickets.
"""

import re
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from state_manager import StateManager

class PlanIngestor:
    """Parses markdown implementation plans into tasks."""

    def __init__(self):
        self.state_manager = StateManager()

    def ingest(self, plan_path: str, clear_backlog: bool = False, dry_run: bool = False) -> None:
        """Main ingestion flow."""
        path = Path(plan_path)
        if not path.exists():
            print(f"Error: Plan file not found at {path}")
            sys.exit(1)

        print(f"Reading plan from: {path.name}")
        content = path.read_text()
        
        # Extract tasks
        tasks = self._parse_tasks(content)
        print(f"Found {len(tasks)} potential tasks.")

        if dry_run:
            print("\n[Dry Run] Tasks identified:")
            for t in tasks:
                print(f"- [{t['domain']}] {t['title']}")
            return

        # Update State
        if clear_backlog:
            print("Clearing existing backlog...")
            self.state_manager.state["tasks"]["backlog"] = []
        
        # Set active plan
        self.state_manager.state["config"]["active_plan_path"] = str(path.absolute())
        
        # Add tasks
        current_max_id = self._get_max_id()
        for i, task in enumerate(tasks):
            new_id = current_max_id + i + 1
            task_entry = {
                "id": new_id,
                "title": task["title"],
                "description": task["description"],
                "domain": task["domain"],
                "type": task["type"],
                "status": "TODO",
                "created_at": self.state_manager.state["last_updated"],
                "source_context": task["context"] # Store snippet for prompt generation
            }
            self.state_manager.state["tasks"]["backlog"].append(task_entry)
            print(f"Added Task #{new_id}: {task['title']}")

        self.state_manager.save_state()
        print(f"\nSuccess! integrated {len(tasks)} tasks into KANBAN_BOARD.md")

    def _get_max_id(self) -> int:
        """Find max ID across all lists."""
        max_id = 0
        for list_name in ["backlog", "in_progress", "review", "done"]:
            for t in self.state_manager.state["tasks"].get(list_name, []):
                if t["id"] > max_id:
                    max_id = t["id"]
        return max_id

    def _parse_tasks(self, content: str) -> List[Dict[str, Any]]:
        """
        Heuristic parser for implementation plans.
        Looks for:
        1. Sections: 'Execution', 'Implementation', 'Steps', 'Objectives'
        2. Items: Numbered lists (1.), Bullet points (-), or Checkboxes (- [ ])
        """
        tasks = []
        lines = content.split('\n')
        current_section = "General"
        capturing = False
        
        # Regex patterns
        section_pattern = re.compile(r'^##+\s+(.+)$')
        # Catch "1. Task", "- Task", "- [ ] Task"
        task_pattern = re.compile(r'^\s*(?:- \[ \]|-\s+|\d+\.)\s+(.+)$')
        
        # Keywords to start/stop capturing
        capture_keywords = ["implementation", "execution", "steps", "deployment", "objectives", "tasks"]
        ignore_keywords = ["overview", "summary", "introduction", "conclusion"]

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Check Headers
            header_match = section_pattern.match(line)
            if header_match:
                header_text = header_match.group(1).strip()
                current_section = header_text
                
                # Determine if we should capture from this section
                is_irrelevant = any(k in header_text.lower() for k in ignore_keywords)
                is_relevant = any(k in header_text.lower() for k in capture_keywords)
                
                if is_relevant:
                    capturing = True
                elif is_irrelevant:
                    capturing = False
                # If neither, maintain previous state (allows subsections to inherit)
                
                continue

            if capturing:
                task_match = task_pattern.match(line)
                if task_match:
                    task_text = task_match.group(1).strip()
                    
                    # Skip trivial lines
                    if len(task_text) < 10: 
                        continue

                    # Infer domain from text
                    domain = "general"
                    task_type = "task"
                    
                    lower_text = task_text.lower()
                    if "frontend" in lower_text or "ui" in lower_text: domain = "frontend"
                    elif "test" in lower_text: domain = "test"
                    elif "api" in lower_text: domain = "backend"
                    elif "db" in lower_text or "sql" in lower_text: domain = "database"
                    elif "config" in lower_text or "env" in lower_text: domain = "devops"
                    
                    if "fix" in lower_text: task_type = "bugfix"
                    elif "create" in lower_text or "add" in lower_text: task_type = "feature"
                    
                    tasks.append({
                        "title": task_text,
                        "description": f"Derived from section: {current_section}",
                        "domain": domain,
                        "type": task_type,
                        "context": f"Section: {current_section}\nItem: {task_text}"
                    })

        return tasks

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Implementation Plan")
    parser.add_argument("plan_path", help="Path to the markdown plan")
    parser.add_argument("--clear", action="store_true", help="Clear existing backlog")
    parser.add_argument("--dry-run", action="store_true", help="Preview tasks without saving")
    
    args = parser.parse_args()
    
    ingestor = PlanIngestor()
    ingestor.ingest(args.plan_path, args.clear, args.dry_run)
