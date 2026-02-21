# Skill: feedback-helper

## Description
Interactive feedback capture skill for the Continual Learning system. Conducts a structured interview with the user to capture high-quality feedback about skill execution errors or suboptimal behaviors.

## When to Use
Invoke this skill when:
- Claude executed a skill incorrectly and the user wants to provide a correction
- The user says phrases like "Use the feedback skill to correct that" or "Log that as feedback"
- A skill produced suboptimal output and the user knows a better approach
- A new edge case was discovered that the skill doesn't handle

## User Invocation
The user can invoke this skill by saying:
- "Use the feedback skill"
- "Log feedback for [skill-name]"
- "Correct that last error"
- "/feedback" (if configured as slash command)

## Behavior

### Interview Flow
1. **Identify Target Skill**: Determine which skill the feedback is about
2. **Capture Situation**: "What were you trying to do when the issue occurred?"
3. **Capture Error**: "What was the specific error or suboptimal behavior?"
4. **Capture Correction**: "What is the correct behavior or approach?"
5. **Capture Rationale**: "Why is this approach better? (helps prevent similar issues)"
6. **Confirm & Save**: Review the feedback with user, then save to target skill's memory

### Output
Generates a structured markdown file in the target skill's `memory/feedback/` directory:
```
correction_YYYYMMDD_HHMMSS.md
```

## Scripts

### `capture_feedback.py`
Saves structured feedback to a skill's memory/feedback/ directory.

```bash
python scripts/capture_feedback.py <target_skill_path> "<situation>" "<error>" "<correction>" "<rationale>"
```

### `log_execution.py`
Standard execution logger (same as other skills).

```bash
python scripts/log_execution.py <skill_name> <success> <message>
```

## Token Efficiency
- **Concise Output Mode**: After saving feedback, respond briefly: "Feedback saved to [skill-name]"
- **Interview Mode**: Ask questions one at a time to minimize back-and-forth confusion

## Learned Context
Before executing, check `memory/learned_context.md` for recent adaptations and edge cases.

## Example Conversation

**User**: The log correlation skill missed some agent events in my log file.

**Claude**: I'll help capture that feedback. Which specific events were missed?

**User**: It didn't detect the "intake_agent" events because they use a different log format.

**Claude**: Got it. What's the correct way to detect these events?

**User**: The pattern should also match "author=intake_agent" not just "[Step: intake_agent]"

**Claude**: That makes sense - expanding the regex pattern improves coverage. Let me save this feedback.

*[Saves feedback to target-skill/memory/feedback/]*

Feedback saved to target-skill. The skill-evolution-manager will process this during the next learning cycle.
