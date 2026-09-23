# NEXVARY-DA — 20-Stage UI/UX, Performance and Reliability Pass

This pass advances the verified hybrid baseline without changing the core security model: cloud intelligence is optional and local execution remains permission-gated.

1. Central dark/gold/blue design tokens.
2. QHD-aware responsive sizing.
3. Branded engineering-status header.
4. Persistent project navigator.
5. Segmented Fast / Engineer / Release controls.
6. Build / QA / Ready status rail.
7. Analyze → Patch → Build → Test → Inspect → Ready timeline.
8. Project summary cards.
9. Evidence-oriented activity console.
10. Agent cards with live durable state.
11. Permission-layer visibility.
12. Professional persistent-terminal surface.
13. Terminal command history and keyboard shortcuts.
14. Polished Add Project from GitHub workflow.
15. UI geometry and work-mode persistence.
16. Low-cost file-change tracking that ignores generated trees.
17. Content-addressed validation cache for Fast/Engineer mode; Release never uses cached evidence.
18. Explicit build profiles for Python, Gradle, Node and CMake.
19. Cancellable process registry with retained bounded output.
20. Automated regression tests for theme, QHD scaling, change tracking and validation-cache correctness.

## Release discipline

Fast and Engineer modes may reuse validation evidence only when the commit/change-set/content/toolchain fingerprint matches. Release Mode always performs fresh verification and remains fail-closed when required heavy adapters are not configured.
