# Project Manager User Guide

A comprehensive guide to using the Project Manager skill for autonomous, parallel development workflows.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Adding Tasks](#adding-tasks)
4. [Starting the Orchestrator](#starting-the-orchestrator)
5. [Monitoring Performance](#monitoring-performance)
6. [Using the Kill Switch](#using-the-kill-switch)
7. [Understanding Autonomous Mode](#understanding-autonomous-mode)
8. [Configuration](#configuration)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Overview

The Project Manager ("The Architect") is a meta-orchestration agent that manages high-volume development workflows. It:

- Spawns up to **3 parallel Claude Code workers**
- Uses **Git Worktrees** for environment isolation
- Applies **Affinity Scheduling** to minimize context switching
- Operates **autonomously** without human intervention for sub-processes
- Provides a **Kill Switch** for emergency shutdown with state preservation

**Target Throughput:** 15 tasks per day

---

## Quick Start

### 1. Ingest a Strategic Plan (Recommended)

The Project Manager works best when driven by a formal **Technical Implementation Plan**. Do not use status reports (like "Readiness Analysis"); use actionable architecture docs.

**The Golden Source Pattern:**
Your plan must be a Markdown file with headers defining Epics and lists defining Tasks.

**Command:**
```bash
# Ingest your project's implementation plan
python .claude/skills/project-manager/scripts/ingest_plan.py \
    "/path/to/your/project/docs/YOUR_PLAN.md"

# Clear old backlog and ingest new plan
python .claude/skills/project-manager/scripts/ingest_plan.py --clear \
    path/to/my_new_plan.md
```

This ensures the PM (and its workers) understand:
- The "Big Picture" objectives
- The target architecture
- The constraints of the specific phase

### 2. Manual Task Entry (Ad-hoc)

If you don't have a plan yet, you can add single tasks:

```bash
# Using the command line
python .claude/skills/project-manager/scripts/state_manager.py add-task \
    --title "Add user authentication" \
    --domain "auth" \
    --type "feature"

# Add multiple tasks
python .claude/skills/project-manager/scripts/state_manager.py add-task \
    --title "Fix pagination bug" \
    --domain "api" \
    --type "bugfix" \
    --files "src/api/pagination.py"
```

### 2. Start the Orchestrator

```bash
python .claude/skills/project-manager/scripts/orchestrate.py start
```

### 3. Monitor Progress

```bash
# Real-time dashboard
python .claude/skills/project-manager/scripts/metrics.py dashboard

# Or watch the Kanban board
cat .claude/skills/project-manager/KANBAN_BOARD.md
```

### 4. Stop When Needed

```bash
# Graceful shutdown
python .claude/skills/project-manager/scripts/orchestrate.py kill

# Emergency force stop
python .claude/skills/project-manager/scripts/orchestrate.py kill --force
```

---

## Adding Tasks

### Via Command Line

```bash
python .claude/skills/project-manager/scripts/state_manager.py add-task \
    --title "Task title" \
    --domain "domain-name" \
    --type "task-type" \
    --description "Optional detailed description" \
    --priority 3 \
    --files "file1.py" "file2.py"
```

**Parameters:**

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--title` | Yes | Short task title |
| `--domain` | Yes | Domain tag: `auth`, `api`, `frontend`, `database`, `infra`, etc. |
| `--type` | Yes | Task type: `feature`, `bugfix`, `refactor`, `test`, `docs` |
| `--description` | No | Detailed description for the worker |
| `--priority` | No | 1-10 (lower = higher priority, default: 5) |
| `--files` | No | Specific files to modify/reference |

### Via KANBAN_BOARD.md

You can also add tasks directly to the `KANBAN_BOARD.md` file:

```markdown
## BACKLOG (TODO)

| ID | Title | Domain | Type | Priority |
|----|-------|--------|------|----------|
| - | Add OAuth support | auth | feature | 2 |
| - | Fix memory leak | backend | bugfix | 1 |
```

Tasks with `-` as ID will be automatically assigned IDs on the next sync.

### Task Types Explained

| Type | Use Case | Worker Strategy |
|------|----------|-----------------|
| `feature` | New functionality | Greenfield prompt (architectural context) |
| `bugfix` | Fix existing bugs | Brownfield prompt (minimal changes) |
| `refactor` | Code improvements | Brownfield prompt (preserve behavior) |
| `test` | Add/improve tests | Brownfield prompt (focused on test files) |
| `docs` | Documentation | Greenfield prompt (new content) |

---

## Starting the Orchestrator

### Basic Start

```bash
python .claude/skills/project-manager/scripts/orchestrate.py start
```

### With Options

```bash
# Limit number of workers
python .claude/skills/project-manager/scripts/orchestrate.py start --workers 2

# Limit number of tasks (useful for testing)
python .claude/skills/project-manager/scripts/orchestrate.py start --max-tasks 5
```

### What Happens on Start

1. **Worktree Setup**: Creates git worktrees for each worker (`worktree-1`, `worktree-2`, `worktree-3`)
2. **Session Initialization**: Resets daily counters, sets status to RUNNING
3. **Task Assignment Loop**:
   - Checks for idle workers
   - Uses affinity scheduling to pick best task for each worker
   - Generates optimized prompts
   - Spawns Claude Code subprocesses
   - Monitors completion/failure
   - Updates state in real-time

---

## Monitoring Performance

### Real-Time Dashboard

```bash
python .claude/skills/project-manager/scripts/metrics.py dashboard
```

Output example:
```
============================================================
PROJECT MANAGER DASHBOARD
============================================================
Last Updated: 2025-01-15T14:30:00

SESSION STATUS
----------------------------------------
  Status:         RUNNING
  Started:        2025-01-15T09:00:00
  Tasks Today:    8 / 15
  Tokens Used:    45,230

WORKERS
----------------------------------------
  🔵 worker-1: Task #12 (auth domain)
  🔵 worker-2: Task #14 (api domain)
  🟢 worker-3: Idle

TASK QUEUE
----------------------------------------
  Backlog:        12
  In Progress:    2
  In Review:      0
  Done:           8
  Escalated:      1
```

### View Kanban Board

```bash
cat .claude/skills/project-manager/KANBAN_BOARD.md
```

The board auto-syncs every 30 seconds with `kanban_state.json`.

### Check Status

```bash
python .claude/skills/project-manager/scripts/orchestrate.py status
```

### View Logs

```bash
# Orchestrator main log
tail -f .claude/skills/project-manager/memory/logs/orchestrator.log

# Individual worker logs
tail -f .claude/skills/project-manager/memory/logs/worker-1.log
tail -f .claude/skills/project-manager/memory/logs/worker-2.log
```

### Export Metrics

```bash
# Export to CSV for spreadsheet analysis
python .claude/skills/project-manager/scripts/metrics.py export --format csv

# Export to JSON for programmatic analysis
python .claude/skills/project-manager/scripts/metrics.py export --format json
```

### Analyze Failures

```bash
python .claude/skills/project-manager/scripts/metrics.py failures --limit 10
```

---

## Using the Kill Switch

The kill switch provides **safe emergency shutdown** with complete state preservation.

### Graceful Shutdown (Recommended)

```bash
python .claude/skills/project-manager/scripts/orchestrate.py kill
```

**What happens:**
1. Current state is immediately backed up
2. SIGTERM is sent to all worker processes
3. Workers have 10 seconds to complete gracefully
4. Any remaining workers are force-killed
5. Session status is set to STOPPED
6. All in-progress tasks return to backlog

### Force Kill (Emergency Only)

```bash
python .claude/skills/project-manager/scripts/orchestrate.py kill --force
```

**What happens:**
1. State is backed up
2. SIGKILL is sent immediately to all workers
3. Session stops instantly

### State Backup Location

Backups are saved to: `.claude/skills/project-manager/memory/backups/`

Files are named: `emergency_state_YYYYMMDD_HHMMSS.json`

### Recovering from Kill

After a kill, to resume:

1. Check the backup for any tasks that need attention
2. In-progress tasks are automatically returned to backlog
3. Simply restart the orchestrator:

```bash
python .claude/skills/project-manager/scripts/orchestrate.py start
```

---

## Understanding Autonomous Mode

The Project Manager runs sub-processes **completely autonomously** without human-in-the-loop:

### How Autonomy Works

1. **Non-Interactive Claude**: Workers run with `--print` flag (no prompts for human input)
2. **Dangerously Skip Permissions**: Workers use `--dangerously-skip-permissions` flag
3. **Auto-Retry**: Failed tasks automatically retry up to 3 times
4. **Auto-Commit**: Workers commit changes autonomously
5. **Auto-Merge**: (When enabled) Completed work merges to main

### Safety Mechanisms

Even in autonomous mode, safety is maintained:

- **Worktree Isolation**: Workers can't interfere with each other
- **Branch Isolation**: Each task uses its own branch
- **Kill Switch**: Human can always stop everything
- **Escalation**: Tasks that fail 3 times are escalated for human review
- **State Preservation**: Complete state backup on any shutdown

### What Triggers Human Intervention

- **Escalated Tasks**: After 3 failures, task requires human review
- **Kill Switch**: Human-initiated emergency stop
- **Daily Limit**: Orchestrator pauses at 15 tasks/day (configurable)

---

## Configuration

### Edit Configuration

Configuration is stored in `kanban_state.json`:

```json
{
  "config": {
    "max_workers": 3,
    "max_retries": 3,
    "daily_task_limit": 15,
    "worktree_base": "../worktrees",
    "graceful_timeout_seconds": 10,
    "sync_interval_seconds": 30
  }
}
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `max_workers` | 3 | Maximum parallel workers |
| `max_retries` | 3 | Retries before escalation |
| `daily_task_limit` | 15 | Max tasks per day |
| `worktree_base` | `../worktrees` | Path to worktree directory |
| `graceful_timeout_seconds` | 10 | Shutdown grace period |
| `sync_interval_seconds` | 30 | Board sync frequency |

---

## Troubleshooting

### Workers Not Starting

**Check:**
1. Git worktrees exist: `git worktree list`
2. Claude CLI is installed: `claude --version`
3. Permissions: `chmod +x .claude/skills/project-manager/scripts/*.sh`

**Fix:**
```bash
bash .claude/skills/project-manager/scripts/setup_worktrees.sh
```

### Tasks Stuck in IN_PROGRESS

**Possible causes:**
- Worker crashed without reporting
- Process orphaned

**Fix:**
```bash
# Kill and restart
python .claude/skills/project-manager/scripts/orchestrate.py kill --force
python .claude/skills/project-manager/scripts/orchestrate.py start
```

### High Failure Rate

**Check failure patterns:**
```bash
python .claude/skills/project-manager/scripts/metrics.py failures
```

**Common fixes:**
- Add more specific file paths to tasks
- Improve task descriptions
- Check if domain patterns need updating

### State Corruption

**Restore from backup:**
```bash
# List backups
ls .claude/skills/project-manager/memory/backups/

# Restore (replace with actual backup filename)
cp .claude/skills/project-manager/memory/backups/state_YYYYMMDD_HHMMSS.json \
   .claude/skills/project-manager/kanban_state.json
```

---

## Best Practices

### Task Design

1. **Be Specific**: Include exact file paths when possible
2. **One Thing Per Task**: Don't combine unrelated changes
3. **Set Domain Correctly**: Enables affinity scheduling
4. **Use Priority**: Critical fixes should be priority 1-3

### Batch Planning

1. **Group by Domain**: Add related tasks together
2. **Order Matters**: Add foundational tasks first
3. **Leave Buffer**: Don't fill entire daily limit

### Monitoring

1. **Check Dashboard Regularly**: Catch issues early
2. **Review Escalations**: Don't let them pile up
3. **Export Weekly**: Keep historical metrics

### Safety

1. **Don't Disable Kill Switch**: It's your emergency brake
2. **Review Before Merge**: Verify worker changes
3. **Backup Before Big Runs**: Manual backup as insurance

---

## Command Reference

### State Manager

```bash
state_manager.py add-task --title "..." --domain "..." --type "..."
state_manager.py list
state_manager.py status
state_manager.py update-task --id N --status STATUS
state_manager.py backup
```

### Orchestrator

```bash
orchestrate.py start [--workers N] [--max-tasks N]
orchestrate.py status
orchestrate.py kill [--force]
```

### Metrics

```bash
metrics.py dashboard
metrics.py summary [--days N]
metrics.py export --format [csv|json] [--output PATH]
metrics.py failures [--limit N]
```

### Scheduler

```bash
scheduler.py --report
scheduler.py --worker WORKER_ID
scheduler.py --task-id TASK_ID
```

### Context Curator

```bash
context_curator.py --task-id N --worker WORKER --worktree PATH --branch NAME
context_curator.py --classify TASK_ID
```

---

## Support

For issues or feedback:

1. Check logs in `memory/logs/`
2. Review escalated tasks in `KANBAN_BOARD.md`
3. Use `/feedback-helper` to capture learnings
4. Invoke `/skill-evolution-manager` for automatic improvements
