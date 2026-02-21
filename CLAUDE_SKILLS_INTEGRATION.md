# Claude Code Portable Skills — Integration Guide

This directory contains three general-purpose Claude Code skills extracted from
the RESEARCH_WIZ_POC project. They carry no project-specific state and can be
dropped into any Claude Code project.

---

## Included Skills

| Skill | Purpose |
|-------|---------|
| `feedback-helper` | Structured interview tool that captures correction feedback and saves it to any target skill's `memory/feedback/` directory for learning |
| `project-manager` | Meta-orchestration agent ("The Architect") that spawns up to 3 parallel Claude Code CLI workers using Git Worktrees for isolated, high-throughput development |
| `skill-evolution-manager` | Analyses execution logs and feedback across skills, then rewrites `learned_context.md` files to improve future skill behaviour |

Also included: `settings.local.json` — a pre-configured Claude Code permissions
file with all RESEARCH_WIZ_* entries removed. Add entries specific to your
project on top of what is already there.

---

## Quick-Start: Integrate into a New Project

### 1. Copy `.claude/` into your project root

```bash
# From where you cloned CLI_Skills:
cp -r /llm_models_python_code_src/CLI_Skills/.claude /path/to/your/project/
```

This places the three skills under `<your-project>/.claude/skills/` and the
permissions file at `<your-project>/.claude/settings.local.json`.

### 2. Make sure you're in a Git repository

`project-manager` uses Git Worktrees for worker isolation, so your project must
be a git repo:

```bash
cd /path/to/your/project
git init          # (if not already a repo)
git add -A && git commit -m "initial"
```

### 3. Add skill permissions to `settings.local.json`

Open `<your-project>/.claude/settings.local.json` and append any project-
specific `allow` entries you need. The file already grants the core permissions
required by the three skills. At minimum, add:

```json
"Skill(feedback-helper)",
"Skill(project-manager)",
"Skill(skill-evolution-manager)"
```

inside the `"allow"` array so Claude Code can invoke the skills by name.

### 4. Open the project in Claude Code

```bash
claude /path/to/your/project
```

Claude Code will automatically detect `.claude/settings.local.json` and load
the skills from `.claude/skills/`.

---

## Using the Skills

### feedback-helper

Invoke after any skill execution that produced wrong or suboptimal output:

```
Use the feedback skill to log a correction for [skill-name]
```

or

```
Log feedback for project-manager — it started workers before the worktrees
were ready.
```

Claude will ask structured questions and save a `correction_YYYYMMDD_HHMMSS.md`
file inside `<target-skill>/memory/feedback/`.

---

### project-manager

1. **Set an active plan** (a Markdown file listing tasks / a planning doc):

   ```bash
   python .claude/skills/project-manager/scripts/ingest_plan.py \
       /path/to/your/project/docs/MY_PLAN.md
   ```

2. **Start orchestration** (spawns up to 3 Claude Code CLI workers):

   ```bash
   python .claude/skills/project-manager/scripts/orchestrate.py start
   ```

3. **Monitor progress**:

   ```bash
   python .claude/skills/project-manager/scripts/orchestrate.py status
   python .claude/skills/project-manager/scripts/metrics.py dashboard
   ```

4. **Emergency stop** (saves state before killing workers):

   ```bash
   python .claude/skills/project-manager/scripts/orchestrate.py kill
   ```

State is persisted in `.claude/skills/project-manager/kanban_state.json` and
backed up to `memory/backups/` on every kill.

See [.claude/skills/project-manager/USER_GUIDE.md](.claude/skills/project-manager/USER_GUIDE.md) for the full reference.

---

### skill-evolution-manager

Run periodically (or after accumulating feedback) to improve skill behaviour:

```bash
python .claude/skills/skill-evolution-manager/scripts/analyze_skill_performance.py \
    .claude/skills/project-manager

python .claude/skills/skill-evolution-manager/scripts/analyze_skill_performance.py \
    .claude/skills/feedback-helper
```

The script reads `memory/logs/` and `memory/feedback/`, then updates each
skill's `memory/learned_context.md` with prioritised learnings.

You can also trigger it inside Claude Code by saying:

```
Run the skill-evolution-manager and analyse project-manager's performance
```

---

## Directory Layout After Integration

```
<your-project>/
├── .claude/
│   ├── settings.local.json          ← permissions file (edit to add yours)
│   └── skills/
│       ├── feedback-helper/
│       │   ├── SKILL.md
│       │   ├── memory/
│       │   └── scripts/
│       ├── project-manager/
│       │   ├── SKILL.md
│       │   ├── USER_GUIDE.md
│       │   ├── KANBAN_BOARD.md      ← human-readable task board
│       │   ├── kanban_state.json    ← machine state (auto-managed)
│       │   ├── memory/
│       │   │   ├── learned_context.md
│       │   │   ├── logs/            ← worker logs (auto-populated)
│       │   │   └── backups/         ← state snapshots (auto-populated)
│       │   ├── scripts/
│       │   └── templates/
│       └── skill-evolution-manager/
│           ├── SKILL.md
│           ├── memory/
│           └── scripts/
└── ... (your project files)
```

---

## Skill Portability Notes

| Concern | Status |
|---------|--------|
| Project-specific paths | Removed — no hardcoded RESEARCH_WIZ_* paths remain |
| Project state (logs/backups) | Not copied — starts clean |
| `kanban_state.json` | Reset to empty — no previous task history |
| `learned_context.md` files | Kept — contain only generic initial setup notes |
| Python dependencies | Standard library only (`json`, `os`, `sys`, `subprocess`, `re`) |
| Git requirement | `project-manager` requires a git repo for worktrees |

---

## Troubleshooting

**"Skill not found" in Claude Code**  
Ensure your `.claude/settings.local.json` includes `"Skill(project-manager)"` etc. in the `allow` array.

**Worker fails to start (project-manager)**  
The repo must have at least one commit. Run `git add -A && git commit -m "init"` first.

**`analyze_skill_performance.py` shows no data**  
The skill needs execution logs in `memory/logs/`. Run the skill at least once to generate log data before analysing.

**Permissions denied errors in Claude Code**  
Add the specific `Bash(...)` pattern that Claude is being denied to the `allow` array in `settings.local.json`.
