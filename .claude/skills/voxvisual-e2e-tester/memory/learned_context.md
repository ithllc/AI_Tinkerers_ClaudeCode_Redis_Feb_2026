# Learned Context: voxvisual-e2e-tester

This file contains adaptations and learnings accumulated during skill execution.
The skill-evolution-manager automatically maintains this file.

**DO NOT EDIT MANUALLY** - Changes may be overwritten by the learning system.

---
## Initial Setup (2026-02-21)

This skill was created for the VoxVisual proof-of-concept.
No learnings have been recorded yet.

---
## Testing Baselines (Initial)

These are starting guidelines — to be refined through execution feedback:

- SVG generation typically takes 2-4 seconds. Set timeout to 10s to account for cold starts.
- Data accuracy tolerance of 5% accounts for Claude rounding numbers in TTS text (e.g., "$22.1M" vs $22,116,000).
- Cross-session recall tests require a delay after working memory updates to allow background extraction to complete (recommended: 2-3 seconds).
- The demo walkthrough must be run sequentially — each step depends on the prior session state.
