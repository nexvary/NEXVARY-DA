# NEXVARY-DA Roadmap

## v0.1 Core — implemented / being hardened

- Approved workspace roots and independent capabilities.
- Read/write/delete/shell/network/git-commit/git-push/release/ADB/desktop-control permission model.
- SQLite state and reusable Agent Pool.
- Persistent per-Agent terminal pool.
- File/process/Git tools.
- Environment discovery.
- Builder and QA adapters.
- Goal / Definition-of-Done engine.
- Fast, Engineer and strict Release modes.
- Project-bound MCP server.
- Cloud Intelligence provider boundary; no mandatory local LLM.
- Add Project from GitHub backend with existing-clone reuse and local project catalog.
- Strict Release Gate with artifact discovery and SHA-256 evidence.
- Minimal desktop UI with work-mode selector and Add Project from GitHub.
- Windows/Ubuntu CI and package artifacts.

## Next hardening

- Concrete cloud-provider adapters and secure credential configuration.
- Cloud/tool orchestration loop that converts plans into approved local tool calls.
- Validation cache keyed by commit/change set/toolchain.
- File watcher and changed-file event stream.
- Targeted test selection for Gradle/Python/Node/CMake.
- Explicit Node/CMake build profiles.
- Android SDK/Gradle/ADB project profile.
- Process registry with attach/cancel/output retention.
- Direct GitHub API integration for PRs, Actions logs, artifacts and releases.

## Heavy QA

- Android/desktop screenshot adapters.
- Broken-button and navigation automation.
- RTL and localization completeness.
- UI overflow and missing-resource checks.
- Dead-link and orphan-route analysis.
- Signed installer/release validation.

## Later

Optional local-model privacy/offline adapters, embeddings/code search, Compact & Resume snapshots, desktop automation permission broker and controlled signed release publication.
