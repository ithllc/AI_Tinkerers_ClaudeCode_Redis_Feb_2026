#!/usr/bin/env python3
"""
Scheduler - "The Traffic Controller"
Implements affinity-based task scheduling to minimize context switching.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict

SKILL_DIR = Path(__file__).parent.parent
STATE_FILE = SKILL_DIR / "kanban_state.json"


@dataclass
class TaskScore:
    """Scoring breakdown for task-worker affinity."""
    task_id: int
    worker_id: str
    base_priority: int
    domain_affinity_bonus: int
    type_affinity_bonus: int
    recency_bonus: int
    total_score: int


class AffinityScheduler:
    """
    Implements "Sticky Assignment" scheduling to minimize context switching.

    Workers develop affinity for domains they've recently worked on,
    and the scheduler preferentially assigns related tasks to leverage
    loaded context/cache.
    """

    # Affinity weights
    DOMAIN_AFFINITY_WEIGHT = 30  # Bonus for matching domain
    TYPE_AFFINITY_WEIGHT = 10   # Bonus for matching task type
    RECENCY_WEIGHT = 5          # Bonus for recent related work
    PRIORITY_WEIGHT = 10        # Base priority scaling

    # Related domains (tasks in related domains get partial affinity)
    DOMAIN_RELATIONS = {
        "auth": ["api", "security", "user"],
        "api": ["auth", "database", "backend"],
        "frontend": ["ui", "components", "styling"],
        "database": ["api", "backend", "migration"],
        "infra": ["devops", "cloud", "deployment"],
        "testing": ["api", "frontend", "backend"],
    }

    def __init__(self):
        self.state = self._load_state()
        self.worker_history: Dict[str, List[Dict]] = defaultdict(list)
        self._load_worker_history()

    def _load_state(self) -> Dict[str, Any]:
        """Load current state from JSON."""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def _load_worker_history(self) -> None:
        """Load recent task history per worker from done tasks."""
        done_tasks = self.state.get("tasks", {}).get("done", [])

        for task in done_tasks[-30:]:  # Look at last 30 completed tasks
            worker_id = task.get("worker_id")
            if worker_id:
                self.worker_history[worker_id].append({
                    "domain": task.get("domain"),
                    "type": task.get("type"),
                    "completed_at": task.get("completed_at")
                })

    def get_worker_affinity(self, worker_id: str) -> Dict[str, Any]:
        """Get the current domain/type affinity for a worker."""
        worker = self.state.get("workers", {}).get(worker_id, {})
        history = self.worker_history.get(worker_id, [])

        # Count domain occurrences in recent history
        domain_counts = defaultdict(int)
        type_counts = defaultdict(int)

        for entry in history[-5:]:  # Weight recent tasks more
            if entry.get("domain"):
                domain_counts[entry["domain"]] += 1
            if entry.get("type"):
                type_counts[entry["type"]] += 1

        primary_domain = max(domain_counts, key=domain_counts.get) if domain_counts else None
        primary_type = max(type_counts, key=type_counts.get) if type_counts else None

        return {
            "worker_id": worker_id,
            "primary_domain": primary_domain or worker.get("domain_affinity"),
            "primary_type": primary_type,
            "domain_counts": dict(domain_counts),
            "type_counts": dict(type_counts)
        }

    def score_task_for_worker(self, task: Dict[str, Any],
                               worker_id: str) -> TaskScore:
        """
        Calculate affinity score for assigning a task to a worker.
        Higher score = better fit.
        """
        affinity = self.get_worker_affinity(worker_id)

        # Base priority (lower priority number = higher score)
        base_priority = (11 - task.get("priority", 5)) * self.PRIORITY_WEIGHT

        # Domain affinity
        domain_bonus = 0
        task_domain = task.get("domain", "")
        worker_domain = affinity.get("primary_domain")

        if worker_domain:
            if task_domain == worker_domain:
                domain_bonus = self.DOMAIN_AFFINITY_WEIGHT
            elif task_domain in self.DOMAIN_RELATIONS.get(worker_domain, []):
                domain_bonus = self.DOMAIN_AFFINITY_WEIGHT // 2

        # Type affinity
        type_bonus = 0
        task_type = task.get("type", "")
        worker_type = affinity.get("primary_type")

        if worker_type and task_type == worker_type:
            type_bonus = self.TYPE_AFFINITY_WEIGHT

        # Recency bonus (how recently worker worked on this domain)
        recency_bonus = 0
        for i, entry in enumerate(reversed(self.worker_history.get(worker_id, [])[-5:])):
            if entry.get("domain") == task_domain:
                recency_bonus = self.RECENCY_WEIGHT * (5 - i)
                break

        total = base_priority + domain_bonus + type_bonus + recency_bonus

        return TaskScore(
            task_id=task["id"],
            worker_id=worker_id,
            base_priority=base_priority,
            domain_affinity_bonus=domain_bonus,
            type_affinity_bonus=type_bonus,
            recency_bonus=recency_bonus,
            total_score=total
        )

    def select_task_for_worker(self, worker_id: str,
                                backlog: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Select the best task from the backlog for a specific worker.
        Returns the task with highest affinity score.
        """
        if not backlog:
            return None

        scored_tasks = [
            (self.score_task_for_worker(task, worker_id), task)
            for task in backlog
        ]

        # Sort by score descending
        scored_tasks.sort(key=lambda x: x[0].total_score, reverse=True)

        return scored_tasks[0][1] if scored_tasks else None

    def select_worker_for_task(self, task: Dict[str, Any],
                                idle_workers: List[str]) -> Optional[str]:
        """
        Select the best worker for a specific task.
        Returns the worker ID with highest affinity score.
        """
        if not idle_workers:
            return None

        scores = [
            (self.score_task_for_worker(task, worker_id), worker_id)
            for worker_id in idle_workers
        ]

        # Sort by score descending
        scores.sort(key=lambda x: x[0].total_score, reverse=True)

        return scores[0][1] if scores else None

    def batch_tasks_by_epic(self, tasks: List[Dict[str, Any]],
                            batch_size: int = 5) -> List[List[Dict[str, Any]]]:
        """
        Group tasks into logical "epics" based on domain similarity.
        This allows workers to focus on related tasks in sequence.
        """
        if not tasks:
            return []

        # Group by domain
        by_domain: Dict[str, List[Dict]] = defaultdict(list)
        for task in tasks:
            by_domain[task.get("domain", "unknown")].append(task)

        # Create batches prioritizing domain coherence
        batches = []
        current_batch = []

        for domain in sorted(by_domain.keys(), key=lambda d: -len(by_domain[d])):
            domain_tasks = sorted(by_domain[domain], key=lambda t: t.get("priority", 5))

            for task in domain_tasks:
                current_batch.append(task)
                if len(current_batch) >= batch_size:
                    batches.append(current_batch)
                    current_batch = []

        if current_batch:
            batches.append(current_batch)

        return batches

    def get_scheduling_report(self, idle_workers: List[str],
                               backlog: List[Dict[str, Any]]) -> str:
        """Generate a human-readable scheduling report."""
        lines = ["Scheduling Report", "=" * 40, ""]

        # Worker affinities
        lines.append("Worker Affinities:")
        for worker_id in self.state.get("workers", {}).keys():
            affinity = self.get_worker_affinity(worker_id)
            status = "IDLE" if worker_id in idle_workers else "BUSY"
            lines.append(f"  {worker_id} [{status}]: {affinity['primary_domain'] or 'none'} / {affinity['primary_type'] or 'none'}")

        lines.append("")
        lines.append("Task Scores (for idle workers):")

        for task in backlog[:5]:  # Top 5 tasks
            lines.append(f"  Task #{task['id']}: {task['title'][:30]}...")
            for worker_id in idle_workers:
                score = self.score_task_for_worker(task, worker_id)
                lines.append(f"    -> {worker_id}: {score.total_score} "
                           f"(pri:{score.base_priority} dom:{score.domain_affinity_bonus} "
                           f"type:{score.type_affinity_bonus} rec:{score.recency_bonus})")

        return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Affinity Scheduler")
    parser.add_argument("--report", action="store_true", help="Show scheduling report")
    parser.add_argument("--worker", help="Get best task for specific worker")
    parser.add_argument("--task-id", type=int, help="Get best worker for specific task")

    args = parser.parse_args()
    scheduler = AffinityScheduler()

    # Reload state
    scheduler.state = scheduler._load_state()
    backlog = scheduler.state.get("tasks", {}).get("backlog", [])
    idle_workers = [
        wid for wid, w in scheduler.state.get("workers", {}).items()
        if w.get("status") == "IDLE"
    ]

    if args.report:
        print(scheduler.get_scheduling_report(idle_workers, backlog))

    elif args.worker:
        task = scheduler.select_task_for_worker(args.worker, backlog)
        if task:
            score = scheduler.score_task_for_worker(task, args.worker)
            print(f"Best task for {args.worker}:")
            print(f"  #{task['id']}: {task['title']}")
            print(f"  Score: {score.total_score}")
        else:
            print("No tasks available")

    elif args.task_id:
        task = None
        for t in backlog:
            if t["id"] == args.task_id:
                task = t
                break

        if task:
            worker = scheduler.select_worker_for_task(task, idle_workers)
            if worker:
                score = scheduler.score_task_for_worker(task, worker)
                print(f"Best worker for task #{task['id']}:")
                print(f"  {worker} (score: {score.total_score})")
            else:
                print("No idle workers available")
        else:
            print(f"Task #{args.task_id} not found in backlog")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
