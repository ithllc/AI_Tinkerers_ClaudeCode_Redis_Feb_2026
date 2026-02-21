#!/usr/bin/env python3
"""
Metrics - Performance tracking and reporting.
Provides dashboards, exports, and analysis for project manager operations.
"""

import json
import csv
import sys
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict

SKILL_DIR = Path(__file__).parent.parent
STATE_FILE = SKILL_DIR / "kanban_state.json"
LOG_DIR = SKILL_DIR / "memory" / "logs"
HISTORY_FILE = LOG_DIR / "execution_history.jsonl"


class MetricsCollector:
    """Collects and analyzes project manager metrics."""

    def __init__(self):
        self.state = self._load_state()
        self.history = self._load_history()

    def _load_state(self) -> Dict[str, Any]:
        """Load current state."""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {}

    def _load_history(self) -> List[Dict[str, Any]]:
        """Load execution history."""
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
        return entries

    def log_execution(self, task_id: int, worker_id: str,
                      success: bool, duration_seconds: int,
                      tokens_used: int, domain: str,
                      error_message: Optional[str] = None,
                      quality_metrics: Optional[Dict[str, Any]] = None) -> None:
        """Log a task execution to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "task_id": task_id,
            "worker_id": worker_id,
            "success": success,
            "duration_seconds": duration_seconds,
            "tokens_used": tokens_used,
            "domain": domain,
            "error": error_message,
            "quality_metrics": quality_metrics or {"skill_usage_score": 0, "skills_detected": []}
        }

        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(HISTORY_FILE, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        self.history.append(entry)

    @staticmethod
    def analyze_skill_usage(log_content: str) -> Dict[str, Any]:
        """
        Analyze execution log for correct skill usage.
        Returns metrics dict with score and list of skills used.
        """
        score = 0
        skills_detected = []
        
        # Regex patterns for skill usage
        patterns = {
            "feedback-helper": r"\.claude/skills/feedback-helper/",
            "skill-evolution-manager": r"\.claude/skills/skill-evolution-manager/",
            "project-manager": r"\.claude/skills/project-manager/"
        }

        for skill, pattern in patterns.items():
            if re.search(pattern, log_content):
                skills_detected.append(skill)
                score += 25 # Simple weighted score (max 100 if all 4 used, unlikely but OK)
        
        # Cap score at 100
        score = min(score, 100)
        
        # If no skills used but task succeeded, it might be raw code.
        # We give a small baseline if empty to avoid 0s on simple tasks.
        if score == 0:
            score = 10 

        return {
            "skill_usage_score": score,
            "skills_detected": skills_detected
        }

    def get_summary(self, days: int = 1) -> Dict[str, Any]:
        """Get metrics summary for the last N days."""
        cutoff = datetime.now() - timedelta(days=days)

        recent = [
            e for e in self.history
            if datetime.fromisoformat(e["timestamp"]) > cutoff
        ]

        total = len(recent)
        success = sum(1 for e in recent if e["success"])
        failed = total - success

        durations = [e["duration_seconds"] for e in recent if e.get("duration_seconds")]
        tokens = [e["tokens_used"] for e in recent if e.get("tokens_used")]

        # Domain breakdown
        by_domain = defaultdict(lambda: {"total": 0, "success": 0, "tokens": 0})
        for e in recent:
            domain = e.get("domain", "unknown")
            by_domain[domain]["total"] += 1
            if e["success"]:
                by_domain[domain]["success"] += 1
            by_domain[domain]["tokens"] += e.get("tokens_used", 0)

        # Worker breakdown
        by_worker = defaultdict(lambda: {"total": 0, "success": 0, "avg_duration": 0})
        worker_durations = defaultdict(list)
        for e in recent:
            worker = e.get("worker_id", "unknown")
            by_worker[worker]["total"] += 1
            if e["success"]:
                by_worker[worker]["success"] += 1
            if e.get("duration_seconds"):
                worker_durations[worker].append(e["duration_seconds"])

        for worker, durs in worker_durations.items():
            if durs:
                by_worker[worker]["avg_duration"] = sum(durs) / len(durs)

        return {
            "period_days": days,
            "total_tasks": total,
            "successful": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0,
            "avg_duration_seconds": sum(durations) / len(durations) if durations else 0,
            "total_tokens": sum(tokens),
            "avg_tokens_per_task": sum(tokens) / len(tokens) if tokens else 0,
            "by_domain": dict(by_domain),
            "by_worker": dict(by_worker)
        }

    def get_dashboard(self) -> str:
        """Generate text dashboard."""
        state = self.state
        metrics = state.get("metrics", {})
        session = state.get("session", {})
        workers = state.get("workers", {})
        tasks = state.get("tasks", {})

        summary = self.get_summary(days=1)

        lines = [
            "=" * 60,
            "PROJECT MANAGER DASHBOARD",
            "=" * 60,
            f"Last Updated: {state.get('last_updated', 'Never')}",
            "",
            "SESSION STATUS",
            "-" * 40,
            f"  Status:         {session.get('status', 'UNKNOWN')}",
            f"  Started:        {session.get('started_at', 'N/A')}",
            f"  Tasks Today:    {session.get('daily_completed', 0)} / {state.get('config', {}).get('daily_task_limit', 15)}",
            f"  Tokens Used:    {session.get('total_tokens_used', 0):,}",
            "",
            "WORKERS",
            "-" * 40,
        ]

        for worker_id, worker in workers.items():
            status_icon = "🟢" if worker.get("status") == "IDLE" else "🔵"
            task_info = f"Task #{worker.get('current_task_id')}" if worker.get('current_task_id') else "Idle"
            lines.append(f"  {status_icon} {worker_id}: {task_info}")
            if worker.get("domain_affinity"):
                lines.append(f"      Affinity: {worker['domain_affinity']}")

        lines.extend([
            "",
            "TASK QUEUE",
            "-" * 40,
            f"  Backlog:        {len(tasks.get('backlog', []))}",
            f"  In Progress:    {len(tasks.get('in_progress', []))}",
            f"  In Review:      {len(tasks.get('review', []))}",
            f"  Done:           {len(tasks.get('done', []))}",
            f"  Escalated:      {len(tasks.get('escalated', []))}",
            "",
            "TODAY'S METRICS",
            "-" * 40,
            f"  Total Tasks:    {summary['total_tasks']}",
            f"  Success Rate:   {summary['success_rate']*100:.1f}%",
            f"  Avg Duration:   {summary['avg_duration_seconds']:.0f}s",
            f"  Total Tokens:   {summary['total_tokens']:,}",
            "",
            "BY DOMAIN (Today)",
            "-" * 40,
        ])

        for domain, stats in summary.get("by_domain", {}).items():
            rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            lines.append(f"  {domain}: {stats['total']} tasks, {rate:.0f}% success")

        lines.extend([
            "",
            "BY WORKER (Today)",
            "-" * 40,
        ])

        for worker, stats in summary.get("by_worker", {}).items():
            rate = stats["success"] / stats["total"] * 100 if stats["total"] > 0 else 0
            lines.append(f"  {worker}: {stats['total']} tasks, {rate:.0f}% success, avg {stats['avg_duration']:.0f}s")

        lines.extend([
            "",
            "LIFETIME METRICS",
            "-" * 40,
            f"  Total Completed: {metrics.get('total_tasks_completed', 0)}",
            f"  Total Failed:    {metrics.get('total_tasks_failed', 0)}",
            f"  Success Rate:    {metrics.get('success_rate', 0)*100:.1f}%",
            "",
            "=" * 60
        ])

        return "\n".join(lines)

    def export_csv(self, output_path: Optional[str] = None) -> str:
        """Export history to CSV."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(LOG_DIR / f"metrics_export_{timestamp}.csv")

        if not self.history:
            return "No data to export"

        fields = ["timestamp", "task_id", "worker_id", "success",
                  "duration_seconds", "tokens_used", "domain", "error"]

        with open(output_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for entry in self.history:
                writer.writerow({k: entry.get(k, "") for k in fields})

        return output_path

    def export_json(self, output_path: Optional[str] = None) -> str:
        """Export metrics summary to JSON."""
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(LOG_DIR / f"metrics_export_{timestamp}.json")

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "summary_1d": self.get_summary(days=1),
            "summary_7d": self.get_summary(days=7),
            "summary_30d": self.get_summary(days=30),
            "current_state": {
                "session": self.state.get("session"),
                "metrics": self.state.get("metrics"),
                "task_counts": {
                    k: len(v) for k, v in self.state.get("tasks", {}).items()
                }
            },
            "history_count": len(self.history)
        }

        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)

        return output_path

    def get_failure_analysis(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Analyze recent failures for patterns."""
        failures = [e for e in self.history if not e["success"]][-limit:]

        analysis = []
        for f in failures:
            analysis.append({
                "task_id": f.get("task_id"),
                "domain": f.get("domain"),
                "worker": f.get("worker_id"),
                "error": f.get("error", "Unknown")[:100],
                "timestamp": f.get("timestamp")
            })

        return analysis


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Project Manager Metrics")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # dashboard command
    subparsers.add_parser("dashboard", help="Show dashboard")

    # summary command
    summary_parser = subparsers.add_parser("summary", help="Show summary")
    summary_parser.add_argument("--days", type=int, default=1, help="Days to include")

    # export command
    export_parser = subparsers.add_parser("export", help="Export metrics")
    export_parser.add_argument("--format", choices=["csv", "json"], default="json")
    export_parser.add_argument("--output", help="Output path")

    # failures command
    failures_parser = subparsers.add_parser("failures", help="Analyze failures")
    failures_parser.add_argument("--limit", type=int, default=10, help="Number to show")

    args = parser.parse_args()
    collector = MetricsCollector()

    if args.command == "dashboard":
        print(collector.get_dashboard())

    elif args.command == "summary":
        summary = collector.get_summary(days=args.days)
        print(json.dumps(summary, indent=2))

    elif args.command == "export":
        if args.format == "csv":
            path = collector.export_csv(args.output)
        else:
            path = collector.export_json(args.output)
        print(f"Exported to: {path}")

    elif args.command == "failures":
        failures = collector.get_failure_analysis(limit=args.limit)
        if failures:
            print(f"\nRecent Failures (last {len(failures)}):\n")
            for f in failures:
                print(f"  Task #{f['task_id']} ({f['domain']})")
                print(f"    Worker: {f['worker']}")
                print(f"    Error: {f['error']}")
                print(f"    Time: {f['timestamp']}")
                print()
        else:
            print("No failures recorded")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
