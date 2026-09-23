# Work Project State

Runtime operational state lives locally in `.nexvary-da/state.sqlite3`. GitHub remains the code-history source of truth.

## Repository

- Repository: `nexvary/NEXVARY-DA`
- Development branch: `dev/v0.1-core`
- Product: NEXVARY Developer Agent
- Current milestone: Stage 180 hybrid core/hardening candidate

## Last verified baseline before Stage 180

Stage 100 commit `7c6d5ae2f9c3d07f91763acd5ee600fef3865a4e` passed cross-platform CI after the Stage 21–60 and 61–100 batches. Stage 101–180 changes are accepted as the new baseline only after their branch-head CI passes on both Ubuntu 24.04 and Windows.

## Implemented through the Stage 180 candidate

- Hybrid cloud-intelligence / secure-local-execution boundary.
- Provider-neutral HTTPS cloud adapter with environment-only credential references.
- Strict machine-plan parser and permission-gated local ToolKernel execution.
- Durable task dependency DAG.
- Fast / Engineer / strict Release modes.
- Content-addressed validation cache and file-change tracker.
- Targeted test-selection profiles.
- Python, Gradle, Node and CMake build/test profiles.
- Android SDK/Gradle/ADB adapter with independent ADB permission.
- Direct local GitHub REST integration for PRs, Actions, artifacts and releases.
- Draft release mutation additionally requires Release permission.
- Static QA: Python AST audit, dead local Markdown links, HTML orphan routes, Tk buttons, RTL signals and localization key completeness.
- Workspace health: symlink escape, case collision and oversized-source checks.
- Artifact manifest and SHA-256 evidence.
- Managed/cancellable process registry.
- MCP surfaces for managed processes, recent events, Android and GitHub snapshot.
- State schema v2 event/gate history access and pruning.
- Dark/Gold/Blue QHD-aware engineering-control UI, persistent terminal and Add Project from GitHub.

## Deliberately still fail-closed / future work

- Runtime screenshot + interactive UI inspection adapter.
- Full desktop/Android broken-button/navigation automation beyond static evidence.
- Signed Windows/Linux installer pipeline.
- Production release publication workflow.
- A concrete paid cloud provider selection, credentials and cost policy.
- Optional local/offline model adapters.

## Completion rule

A branch head is never called verified merely because code was pushed. Windows and Ubuntu CI must pass. Strict Release READY also remains blocked when the configured policy requires evidence that no adapter can currently prove.
