---
name: project-manager
description: Meta-orchestration agent that manages high-volume development workflows by spawning and coordinating parallel Claude Code CLI sessions using Git Worktrees for isolation. Use when executing multiple development tasks autonomously with 3 concurrent workers.
---

# Project Manager Skill ("The Architect")

## Overview

The Project Manager is a **Meta-Agent** that orchestrates up to 3 parallel Claude Code CLI sessions ("Workers") to execute development tasks autonomously. It uses:

- **Git Worktrees** for environment isolation (no file conflicts)
- **Affinity Scheduling** to minimize context switching
- **Greenfield/Brownfield** strategies for optimal prompting
- **Autonomous execution** with no human-in-the-loop for sub-processes

Target throughput: **15 tasks/day**

## When to Use

- Executing multiple development tasks in parallel
- Batch processing of backlog items (bugs, features, refactors)
- Large-scale refactoring across multiple domains
- Automated code generation campaigns

## Quick Start

```bash
# Invoke the skill
/project-manager

# Or with initial tasks
/project-manager --tasks "Add auth middleware" "Fix pagination bug" "Refactor user model"
```

## Key Commands

### Start Orchestration
```bash
# Start with default settings (3 workers)
python .claude/skills/project-manager/scripts/orchestrate.py start

# Start with custom worker count
python .claude/skills/project-manager/scripts/orchestrate.py start --workers 2
```

### Monitor Status
```bash
# View real-time status
python .claude/skills/project-manager/scripts/orchestrate.py status

# View metrics dashboard
python .claude/skills/project-manager/scripts/metrics.py dashboard
```

### Kill Switch (Emergency Stop)
```bash
# Graceful shutdown - saves state and terminates all workers
python .claude/skills/project-manager/scripts/orchestrate.py kill

# Force kill (immediate, still saves state)
python .claude/skills/project-manager/scripts/orchestrate.py kill --force
```

### Manage Tasks
```bash
# Add tasks to backlog
python .claude/skills/project-manager/scripts/state_manager.py add-task \
    --title "Add user authentication" \
    --domain "auth" \
    --type "feature"

# List all tasks
python .claude/skills/project-manager/scripts/state_manager.py list

# Move task status
python .claude/skills/project-manager/scripts/state_manager.py update-task \
    --id 3 --status DONE
```

## Architecture

### Components

| Component | File | Role |
|-----------|------|------|
| Orchestrator | `orchestrate.py` | "The Boss" - manages workers and worktrees |
| Scheduler | `scheduler.py` | "Traffic Controller" - affinity-based task assignment |
| Context Curator | `context_curator.py` | "Briefing Officer" - generates prompts |
| State Manager | `state_manager.py` | "The Scribe" - JSON/MD sync |
| Metrics | `metrics.py` | Performance tracking and reporting |

### Directory Structure
```
project-manager/
├── SKILL.md                  # This file
├── KANBAN_BOARD.md           # Human-readable task board
├── kanban_state.json         # Machine-readable state
├── learned_context.md        # Shared learnings
├── scripts/
│   ├── orchestrate.py        # Main orchestrator
│   ├── scheduler.py          # Affinity scheduling
│   ├── context_curator.py    # Prompt generation
│   ├── state_manager.py      # State management
│   ├── metrics.py            # Performance metrics
│   └── setup_worktrees.sh    # Git worktree setup
├── templates/
│   ├── task_greenfield.j2    # New feature template
│   └── task_brownfield.j2    # Maintenance template
└── memory/
    ├── learned_context.md
    └── logs/
```

## Task Workflow

### States
```
TODO → IN_PROGRESS → REVIEW → DONE
         ↓
      FAILED (retry_count > 3 → escalate)
```

### Affinity Scheduling

Tasks are tagged with:
- **domain**: `auth`, `api`, `frontend`, `database`, `infra`, etc.
- **type**: `feature`, `bugfix`, `refactor`, `test`, `docs`

Workers maintain "sticky" domain affinity - a worker that just completed an `auth` task will preferentially receive another `auth` task to leverage loaded context.

### Context Curation (2-Paragraph Rule)

**Paragraph 1 - Objective:**
- High-level goal
- Definition of Done
- Expected output

**Paragraph 2 - Constraints:**
- Technical boundaries
- Banned libraries/patterns
- Required patterns to follow

## Git Worktree Isolation

Each worker operates in an isolated worktree:
```
project-root/
├── main/                     # Original repo (untouched during work)
├── worktree-1/               # Worker 1's isolated environment
├── worktree-2/               # Worker 2's isolated environment
└── worktree-3/               # Worker 3's isolated environment
```

Workers create branches, make changes, and upon verification, the orchestrator merges completed work back to main.

## Kill Switch

The kill switch provides safe emergency shutdown:

1. **Signal Propagation**: Sends SIGTERM to all worker subprocesses
2. **State Preservation**: Saves current state to `kanban_state.json` and backup
3. **Graceful Timeout**: Workers get 10 seconds to clean up before SIGKILL
4. **Worktree Protection**: Preserves worktree state for manual recovery

```bash
# Graceful kill (recommended)
python .claude/skills/project-manager/scripts/orchestrate.py kill

# Immediate force kill
python .claude/skills/project-manager/scripts/orchestrate.py kill --force
```

State backups are saved to: `memory/backups/state_YYYYMMDD_HHMMSS.json`

## Monitoring

### Real-time Dashboard
```bash
python .claude/skills/project-manager/scripts/metrics.py dashboard
```

Displays:
- Active workers and their current tasks
- Queue depth and estimated completion
- Success/failure rates
- Token usage per task
- Domain distribution

### Log Files
- `memory/logs/orchestrator.log` - Main orchestration events
- `memory/logs/worker_N.log` - Per-worker output
- `memory/logs/execution_history.jsonl` - Structured execution log

### Metrics Export
```bash
# Export to CSV for analysis
python .claude/skills/project-manager/scripts/metrics.py export --format csv

# Export to JSON
python .claude/skills/project-manager/scripts/metrics.py export --format json
```

## Error Handling

### Automatic Retry
- Failed tasks return to queue with `retry_count + 1`
- Max retries: 3 (configurable)

### Escalation
After 3 failures:
1. Task marked as `ESCALATED`
2. Details logged to `memory/logs/escalations.log`
3. Notification added to `KANBAN_BOARD.md`
4. Human review required before retry

## Integration

### With feedback-helper
```bash
# After escalation, get human feedback
/feedback-helper --context "project-manager task failure"
```

### With skill-evolution-manager
Automatically triggered at end of batch to:
- Analyze failure patterns
- Update `learned_context.md`
- Propose workflow improvements

## Configuration

Edit `kanban_state.json` config section:
```json
{
  "config": {
    "max_workers": 3,
    "max_retries": 3,
    "daily_task_limit": 15,
    "worktree_base": "../worktrees",
    "graceful_timeout_seconds": 10
  }
}
```

## See Also

- `KANBAN_BOARD.md` - Visual task board
- `memory/learned_context.md` - Accumulated learnings
- `/feedback-helper` - Capture learning from failures
- `/skill-evolution-manager` - Nightly learning consolidation
