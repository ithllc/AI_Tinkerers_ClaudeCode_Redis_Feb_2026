# Learned Context: redis-memory-manager

This file contains adaptations and learnings accumulated during skill execution.
The skill-evolution-manager automatically maintains this file.

**DO NOT EDIT MANUALLY** - Changes may be overwritten by the learning system.

---
## Initial Setup (2026-02-21)

This skill was created for the VoxVisual proof-of-concept.
No learnings have been recorded yet.

---
## Working Memory Best Practices (Baseline)

These are starting guidelines — to be refined through execution feedback:

- Always include `connected_dataset` in the `data` field so follow-up queries know which dataset to use.
- Merge `current_filters` incrementally — never overwrite the entire object. A user saying "Show East region" should add to existing filters, not replace them.
- Store `last_svg_hash` to enable cache-hit detection when the user repeats a query.
- Set reasonable TTL values for sessions (e.g., 3600s = 1 hour) to prevent stale session accumulation.
