#!/usr/bin/env python3
"""
State Manager - "The Scribe"
Handles Kanban state persistence and JSON <-> Markdown synchronization.
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import shutil
import argparse

SKILL_DIR = Path(__file__).parent.parent
STATE_FILE = SKILL_DIR / "kanban_state.json"
BOARD_FILE = SKILL_DIR / "KANBAN_BOARD.md"
BACKUP_DIR = SKILL_DIR / "memory" / "backups"


class StateManager:
    """Manages the Kanban board state with JSON/Markdown synchronization."""

    def __init__(self):
        self.state: Dict[str, Any] = {}
        self.load_state()

    def load_state(self) -> Dict[str, Any]:
        """Load state from JSON file."""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                self.state = json.load(f)
        else:
            self.state = self._default_state()
        return self.state

    def save_state(self, create_backup: bool = False) -> None:
        """Save state to JSON file and sync to Markdown."""
        self.state["last_updated"] = datetime.now().isoformat()

        if create_backup:
            self._create_backup()

        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

        self._sync_to_markdown()

    def _create_backup(self) -> str:
        """Create a timestamped backup of the current state."""
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = BACKUP_DIR / f"state_{timestamp}.json"

        if STATE_FILE.exists():
            shutil.copy(STATE_FILE, backup_path)
        else:
            with open(backup_path, 'w') as f:
                json.dump(self.state, f, indent=2)

        return str(backup_path)

    def _default_state(self) -> Dict[str, Any]:
        """Return default state structure."""
        return {
            "version": "1.0.0",
            "last_updated": None,
            "session": {
                "status": "IDLE",
                "started_at": None,
                "daily_completed": 0,
                "total_tokens_used": 0
            },
            "config": {
                "max_workers": 3,
                "max_retries": 3,
                "daily_task_limit": 15,
                "worktree_base": "../worktrees",
                "graceful_timeout_seconds": 10,
                "sync_interval_seconds": 30,
                "active_plan_path": None
            },
            "workers": {
                f"worker-{i}": {
                    "status": "IDLE",
                    "pid": None,
                    "current_task_id": None,
                    "worktree": f"worktree-{i}",
                    "branch": None,
                    "started_at": None,
                    "domain_affinity": None
                } for i in range(1, 4)
            },
            "tasks": {
                "backlog": [],
                "in_progress": [],
                "review": [],
                "done": [],
                "escalated": []
            },
            "metrics": {
                "total_tasks_completed": 0,
                "total_tasks_failed": 0,
                "success_rate": 0.0,
                "average_duration_seconds": 0,
                "tokens_by_domain": {},
                "tasks_by_domain": {}
            },
            "next_task_id": 1
        }

    # Task Management
    def add_task(self, title: str, domain: str, task_type: str,
                 description: str = "", priority: int = 5,
                 files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Add a new task to the backlog."""
        task = {
            "id": self.state["next_task_id"],
            "title": title,
            "description": description,
            "domain": domain,
            "type": task_type,
            "priority": priority,
            "status": "TODO",
            "files": files or [],
            "retry_count": 0,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "worker_id": None,
            "branch": None,
            "tokens_used": 0,
            "error_log": []
        }

        self.state["tasks"]["backlog"].append(task)
        self.state["next_task_id"] += 1
        self.save_state()
        return task

    def get_task(self, task_id: int) -> Optional[Dict[str, Any]]:
        """Get a task by ID from any queue."""
        for queue_name in ["backlog", "in_progress", "review", "done", "escalated"]:
            for task in self.state["tasks"][queue_name]:
                if task["id"] == task_id:
                    return task
        return None

    def move_task(self, task_id: int, from_status: str, to_status: str,
                  worker_id: Optional[str] = None,
                  branch: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Move a task between queues."""
        status_to_queue = {
            "TODO": "backlog",
            "IN_PROGRESS": "in_progress",
            "REVIEW": "review",
            "DONE": "done",
            "ESCALATED": "escalated"
        }

        from_queue = status_to_queue.get(from_status)
        to_queue = status_to_queue.get(to_status)

        if not from_queue or not to_queue:
            return None

        # Find and remove from source queue
        task = None
        for i, t in enumerate(self.state["tasks"][from_queue]):
            if t["id"] == task_id:
                task = self.state["tasks"][from_queue].pop(i)
                break

        if not task:
            return None

        # Update task metadata
        task["status"] = to_status
        if to_status == "IN_PROGRESS":
            task["started_at"] = datetime.now().isoformat()
            task["worker_id"] = worker_id
            task["branch"] = branch
        elif to_status in ["DONE", "REVIEW"]:
            task["completed_at"] = datetime.now().isoformat()

        # Add to destination queue
        self.state["tasks"][to_queue].append(task)
        self.save_state()
        return task

    def fail_task(self, task_id: int, error_message: str) -> Optional[Dict[str, Any]]:
        """Mark a task as failed, increment retry, or escalate."""
        task = None
        for i, t in enumerate(self.state["tasks"]["in_progress"]):
            if t["id"] == task_id:
                task = self.state["tasks"]["in_progress"].pop(i)
                break

        if not task:
            return None

        task["retry_count"] += 1
        task["error_log"].append({
            "timestamp": datetime.now().isoformat(),
            "message": error_message
        })
        task["worker_id"] = None
        task["branch"] = None

        max_retries = self.state["config"]["max_retries"]
        if task["retry_count"] >= max_retries:
            task["status"] = "ESCALATED"
            self.state["tasks"]["escalated"].append(task)
            self.state["metrics"]["total_tasks_failed"] += 1
        else:
            task["status"] = "TODO"
            # Add back to front of backlog for retry
            self.state["tasks"]["backlog"].insert(0, task)

        self._update_success_rate()
        self.save_state()
        return task

    def complete_task(self, task_id: int, tokens_used: int = 0) -> Optional[Dict[str, Any]]:
        """Mark a task as done."""
        task = self.move_task(task_id, "REVIEW", "DONE")
        if task:
            task["tokens_used"] = tokens_used
            self.state["session"]["daily_completed"] += 1
            self.state["session"]["total_tokens_used"] += tokens_used
            self.state["metrics"]["total_tasks_completed"] += 1

            # Update domain metrics
            domain = task.get("domain", "unknown")
            if domain not in self.state["metrics"]["tokens_by_domain"]:
                self.state["metrics"]["tokens_by_domain"][domain] = 0
                self.state["metrics"]["tasks_by_domain"][domain] = 0
            self.state["metrics"]["tokens_by_domain"][domain] += tokens_used
            self.state["metrics"]["tasks_by_domain"][domain] += 1

            self._update_success_rate()
            self.save_state()
        return task

    def _update_success_rate(self) -> None:
        """Update the success rate metric."""
        total = (self.state["metrics"]["total_tasks_completed"] +
                 self.state["metrics"]["total_tasks_failed"])
        if total > 0:
            self.state["metrics"]["success_rate"] = (
                self.state["metrics"]["total_tasks_completed"] / total
            )

    # Worker Management
    def update_worker(self, worker_id: str, **kwargs) -> None:
        """Update worker state."""
        if worker_id in self.state["workers"]:
            self.state["workers"][worker_id].update(kwargs)
            self.save_state()

    def get_idle_workers(self) -> List[str]:
        """Get list of idle worker IDs."""
        return [
            wid for wid, w in self.state["workers"].items()
            if w["status"] == "IDLE"
        ]

    def get_active_worker_pids(self) -> List[int]:
        """Get PIDs of all active workers."""
        pids = []
        for worker in self.state["workers"].values():
            if worker["pid"] is not None and worker["status"] != "IDLE":
                pids.append(worker["pid"])
        return pids

    # Session Management
    def start_session(self) -> None:
        """Start a new orchestration session."""
        self.state["session"]["status"] = "RUNNING"
        self.state["session"]["started_at"] = datetime.now().isoformat()
        self.state["session"]["daily_completed"] = 0
        self.state["session"]["total_tokens_used"] = 0
        self.save_state()

    def stop_session(self) -> None:
        """Stop the orchestration session."""
        self.state["session"]["status"] = "STOPPED"
        for worker_id in self.state["workers"]:
            self.state["workers"][worker_id]["status"] = "IDLE"
            self.state["workers"][worker_id]["pid"] = None
        self.save_state(create_backup=True)

    # Markdown Synchronization
    def _sync_to_markdown(self) -> None:
        """Sync state to KANBAN_BOARD.md."""
        session = self.state["session"]
        active_count = sum(
            1 for w in self.state["workers"].values()
            if w["status"] != "IDLE"
        )

        md_content = f"""# Project Manager Kanban Board

> Last Updated: {self.state.get('last_updated', 'Never')}
> Active Workers: {active_count}/{self.state['config']['max_workers']}
> Session Status: {session['status']}

---

## BACKLOG (TODO)

<!-- Tasks waiting to be picked up -->

| ID | Title | Domain | Type | Priority |
|----|-------|--------|------|----------|
"""

        backlog = self.state["tasks"]["backlog"]
        if backlog:
            for task in sorted(backlog, key=lambda t: t.get("priority", 5)):
                md_content += f"| {task['id']} | {task['title']} | {task['domain']} | {task['type']} | {task.get('priority', 5)} |\n"
        else:
            md_content += "| - | No tasks in backlog | - | - | - |\n"

        md_content += """
---

## IN PROGRESS

<!-- Tasks currently being worked on by workers -->

| ID | Title | Worker | Branch | Started |
|----|-------|--------|--------|---------|
"""

        in_progress = self.state["tasks"]["in_progress"]
        if in_progress:
            for task in in_progress:
                started = task.get("started_at", "")[:19] if task.get("started_at") else "-"
                md_content += f"| {task['id']} | {task['title']} | {task.get('worker_id', '-')} | {task.get('branch', '-')} | {started} |\n"
        else:
            md_content += "| - | No active tasks | - | - | - |\n"

        md_content += """
---

## REVIEW

<!-- Tasks completed, awaiting merge verification -->

| ID | Title | Worker | Branch | Completed |
|----|-------|--------|--------|-----------|
"""

        review = self.state["tasks"]["review"]
        if review:
            for task in review:
                completed = task.get("completed_at", "")[:19] if task.get("completed_at") else "-"
                md_content += f"| {task['id']} | {task['title']} | {task.get('worker_id', '-')} | {task.get('branch', '-')} | {completed} |\n"
        else:
            md_content += "| - | No tasks in review | - | - | - |\n"

        md_content += """
---

## DONE (Today)

<!-- Tasks completed and merged today -->

| ID | Title | Domain | Duration | Tokens |
|----|-------|--------|----------|--------|
"""

        done = self.state["tasks"]["done"]
        if done:
            for task in done[-10:]:  # Show last 10
                duration = self._calc_duration(task)
                md_content += f"| {task['id']} | {task['title']} | {task['domain']} | {duration} | {task.get('tokens_used', 0)} |\n"
        else:
            md_content += "| - | No completed tasks | - | - | - |\n"

        md_content += """
---

## ESCALATED

<!-- Tasks that failed 3+ times and need human intervention -->

| ID | Title | Error Summary | Attempts | Last Failed |
|----|-------|---------------|----------|-------------|
"""

        escalated = self.state["tasks"]["escalated"]
        if escalated:
            for task in escalated:
                last_error = task["error_log"][-1]["message"][:50] if task["error_log"] else "-"
                last_failed = task["error_log"][-1]["timestamp"][:19] if task["error_log"] else "-"
                md_content += f"| {task['id']} | {task['title']} | {last_error}... | {task['retry_count']} | {last_failed} |\n"
        else:
            md_content += "| - | No escalated tasks | - | - | - |\n"

        metrics = self.state["metrics"]
        success_pct = f"{metrics['success_rate']*100:.1f}%" if metrics['success_rate'] > 0 else "N/A"
        avg_dur = f"{metrics['average_duration_seconds']}s" if metrics['average_duration_seconds'] > 0 else "N/A"

        md_content += f"""
---

## Statistics

- **Today's Completed:** {session['daily_completed']} / {self.state['config']['daily_task_limit']} target
- **Success Rate:** {success_pct}
- **Avg Task Duration:** {avg_dur}
- **Total Tokens Used:** {session['total_tokens_used']}

---

## Notes

<!-- Add manual notes here - they will be preserved during sync -->

- Board auto-syncs with `kanban_state.json` every {self.state['config']['sync_interval_seconds']} seconds
- Edit this file directly to add tasks (will be parsed on next sync)
- Use `/project-manager status` for real-time view
"""

        with open(BOARD_FILE, 'w') as f:
            f.write(md_content)

    def _calc_duration(self, task: Dict[str, Any]) -> str:
        """Calculate task duration as human-readable string."""
        if not task.get("started_at") or not task.get("completed_at"):
            return "-"
        try:
            start = datetime.fromisoformat(task["started_at"])
            end = datetime.fromisoformat(task["completed_at"])
            delta = end - start
            mins = int(delta.total_seconds() / 60)
            return f"{mins}m"
        except:
            return "-"

    def parse_markdown_tasks(self) -> List[Dict[str, Any]]:
        """Parse tasks from KANBAN_BOARD.md backlog section for manual additions."""
        if not BOARD_FILE.exists():
            return []

        with open(BOARD_FILE, 'r') as f:
            content = f.read()

        # Find backlog table
        backlog_match = re.search(
            r'## BACKLOG.*?\n\|.*?\n\|[-\s|]+\n(.*?)(?=\n---|\n##)',
            content, re.DOTALL
        )

        if not backlog_match:
            return []

        new_tasks = []
        existing_ids = {t["id"] for t in self.state["tasks"]["backlog"]}

        for line in backlog_match.group(1).strip().split('\n'):
            if not line.strip() or line.startswith('|') == False:
                continue

            parts = [p.strip() for p in line.split('|')[1:-1]]
            if len(parts) >= 4 and parts[0] != '-':
                try:
                    task_id = int(parts[0])
                    if task_id not in existing_ids:
                        # This is a manually added task
                        new_tasks.append({
                            "title": parts[1],
                            "domain": parts[2],
                            "type": parts[3],
                            "priority": int(parts[4]) if len(parts) > 4 else 5
                        })
                except ValueError:
                    continue

        return new_tasks

    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of current state for display."""
        return {
            "session_status": self.state["session"]["status"],
            "backlog_count": len(self.state["tasks"]["backlog"]),
            "in_progress_count": len(self.state["tasks"]["in_progress"]),
            "review_count": len(self.state["tasks"]["review"]),
            "done_today": self.state["session"]["daily_completed"],
            "escalated_count": len(self.state["tasks"]["escalated"]),
            "active_workers": sum(
                1 for w in self.state["workers"].values()
                if w["status"] != "IDLE"
            ),
            "total_workers": len(self.state["workers"]),
            "success_rate": self.state["metrics"]["success_rate"],
            "tokens_used": self.state["session"]["total_tokens_used"]
        }


def main():
    parser = argparse.ArgumentParser(description="Project Manager State Manager")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # add-task command
    add_parser = subparsers.add_parser("add-task", help="Add a new task")
    add_parser.add_argument("--title", required=True, help="Task title")
    add_parser.add_argument("--domain", required=True, help="Task domain (auth, api, frontend, etc.)")
    add_parser.add_argument("--type", required=True, dest="task_type", help="Task type (feature, bugfix, refactor)")
    add_parser.add_argument("--description", default="", help="Task description")
    add_parser.add_argument("--priority", type=int, default=5, help="Priority (1-10, lower is higher)")
    add_parser.add_argument("--files", nargs="*", help="Related files")

    # list command
    subparsers.add_parser("list", help="List all tasks")

    # status command
    subparsers.add_parser("status", help="Show status summary")

    # update-task command
    update_parser = subparsers.add_parser("update-task", help="Update task status")
    update_parser.add_argument("--id", type=int, required=True, help="Task ID")
    update_parser.add_argument("--status", required=True, help="New status (TODO, IN_PROGRESS, REVIEW, DONE)")

    # backup command
    subparsers.add_parser("backup", help="Create state backup")

    args = parser.parse_args()
    manager = StateManager()

    if args.command == "add-task":
        task = manager.add_task(
            title=args.title,
            domain=args.domain,
            task_type=args.task_type,
            description=args.description,
            priority=args.priority,
            files=args.files
        )
        print(f"Created task #{task['id']}: {task['title']}")

    elif args.command == "list":
        for status, queue in [
            ("BACKLOG", "backlog"),
            ("IN PROGRESS", "in_progress"),
            ("REVIEW", "review"),
            ("DONE", "done"),
            ("ESCALATED", "escalated")
        ]:
            tasks = manager.state["tasks"][queue]
            if tasks:
                print(f"\n{status}:")
                for t in tasks:
                    print(f"  #{t['id']}: {t['title']} [{t['domain']}] ({t['type']})")

    elif args.command == "status":
        summary = manager.get_status_summary()
        print(f"""
Project Manager Status
======================
Session: {summary['session_status']}
Workers: {summary['active_workers']}/{summary['total_workers']} active

Tasks:
  Backlog:     {summary['backlog_count']}
  In Progress: {summary['in_progress_count']}
  In Review:   {summary['review_count']}
  Done Today:  {summary['done_today']}
  Escalated:   {summary['escalated_count']}

Metrics:
  Success Rate: {summary['success_rate']*100:.1f}%
  Tokens Used:  {summary['tokens_used']}
""")

    elif args.command == "update-task":
        task = manager.get_task(args.id)
        if task:
            manager.move_task(args.id, task["status"], args.status)
            print(f"Task #{args.id} moved to {args.status}")
        else:
            print(f"Task #{args.id} not found")

    elif args.command == "backup":
        path = manager._create_backup()
        print(f"Backup created: {path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
