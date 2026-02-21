# Learned Context: claude-svg-generator

This file contains adaptations and learnings accumulated during skill execution.
The skill-evolution-manager automatically maintains this file.

**DO NOT EDIT MANUALLY** - Changes may be overwritten by the learning system.

---
## Initial Setup (2026-02-21)

This skill was created for the VoxVisual proof-of-concept.
No learnings have been recorded yet.

---
## SVG Best Practices (Baseline)

These are starting guidelines — to be refined through execution feedback:

- Prefer `<animate>` and `<animateTransform>` over CSS `@keyframes` for broader SVG compatibility.
- Always set `width="100%"` and use a `viewBox` attribute for responsive scaling.
- Use `fill-opacity` animations for smooth bar chart entry transitions.
- For bar charts, animate `height` and `y` simultaneously to grow bars upward from the baseline.
- Keep SVG complexity under ~50 elements to maintain sub-second render on mobile.
