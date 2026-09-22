# Work Project State

This file is the human-readable handover. Runtime state is stored locally in `.nexvary-da/state.sqlite3`.

## Repository

- Repository: `nexvary/NEXVARY-DA`
- Development branch: `dev/v0.1-core`
- Product: NEXVARY Developer Agent
- Current target: v0.1 Core

## Implemented on the development branch

- Workspace Guard with independent read/write/shell/git-push/release/ADB/desktop-automation capabilities.
- Persistent SQLite project state and reusable Agent Pool slots.
- Persistent terminal with cross-command cwd/environment continuity on Windows and Linux.
- File, exact-patch, search, process and Git tools.
- Environment discovery for Windows/Linux, Android SDK, Java/JDK, Gradle, ADB, Python, CMake, Node/npm and Git.
- Executable Builder and QA adapters.
- Transport-independent Tool Kernel.
- Persistent Definition-of-Done Goal Engine.
- Project-bound local MCP server using the official MCP Python SDK; MCP cannot switch to an unapproved workspace.
- Evidence-based Release Gate v0.1.
- Minimal real desktop UI backed by the same core.
- Windows and Ubuntu CI with real MCP integration tests.

## Validation evidence

Run #12 on commit `d542ec68d02225ac455b3b352b7a047231d17360` passed on both Ubuntu 24.04 and Windows. It covered package install, compile, nine unit/integration tests, persistent terminal behavior, in-process MCP tool calls, and `git diff --check`.

The next CI revision additionally builds and validates wheel/source distributions and uploads them as workflow artifacts.

## Explicitly not complete

- Coordinator task-graph execution beyond durable worker slots.
- GitHub PR/Actions/artifact integration inside the local application.
- External model-provider orchestration.
- Process registry with attach/cancel/output retention.
- Android UI/device QA and ADB lab workflows.
- Generic dead-link, orphan-page, broken-button, navigation, RTL and localization adapters.
- Node/CMake project profiles beyond environment detection.
- Signed desktop installers and release publication.

## v0.1 completion rule

Do not label v0.1 production-ready until the remaining v0.1 scope has evidence-producing adapters and the final Windows/Ubuntu Release Gate passes. Missing checks remain explicit rather than being reported as PASS.
