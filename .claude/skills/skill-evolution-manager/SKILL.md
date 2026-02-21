# Skill: skill-evolution-manager

## Description
Global Learning Orchestrator for Claude Agent Skills. Analyzes execution logs and user feedback across all skills to identify patterns, failures, and improvement opportunities. Proposes and applies updates to skill `learned_context.md` files.

## When to Use
- Run periodically (nightly or on-demand) to analyze skill performance
- After receiving user feedback about skill behavior
- When a skill repeatedly fails on specific inputs
- To consolidate and prune accumulated learnings

## Capabilities
1. **Analyze Performance**: Scan `memory/logs/` across skills to identify failure patterns
2. **Process Feedback**: Read `memory/feedback/` to extract user corrections
3. **Propose Updates**: Generate improved content for `learned_context.md`
4. **Apply Updates**: Safely write changes (append-only for safety)
5. **Prune Context**: Summarize old learnings to prevent context bloat

## Scripts

### `analyze_skill_performance.py`
Reads a target skill's `memory/logs/execution_history.jsonl` and generates failure analysis.

```bash
python scripts/analyze_skill_performance.py <skill_path>
```

### `propose_updates.py`
Analyzes logs and feedback to generate proposed updates for `learned_context.md`.

```bash
python scripts/propose_updates.py <skill_path>
```

### `apply_update.py`
Safely appends proposed updates to `learned_context.md` (creates git commit if in repo).

```bash
python scripts/apply_update.py <skill_path> <update_content>
```

## Learning Heuristics
- **Error Threshold**: If a specific error occurs > 3 times, add a "Troubleshooting" entry
- **User Correction Priority**: User-provided corrections are added as "High Priority Examples"
- **Staleness Pruning**: Learnings older than 30 days with no recent matches are candidates for removal

## Token Efficiency
- **Concise Output Mode**: Provide minimal chat output (e.g., "Analyzed 3 skills, 2 updates proposed")
- **Verbose Action Mode**: File content may be comprehensive; chat responses must be brief
- **Summarized Context**: Periodically summarize `learned_context.md` to prevent bloat

## Learned Context
Before executing, check `memory/learned_context.md` for recent adaptations and edge cases.

## Safety Constraints
- NEVER overwrite existing `learned_context.md` content; always APPEND
- NEVER modify `SKILL.md` directly; all learnings go to `learned_context.md` first
- Always create a backup before applying updates
- Require human review for any learning that changes core skill behavior
