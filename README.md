# NEXVARY Developer Agent (NEXVARY-DA)

NEXVARY-DA is a hybrid developer-agent runtime: **cloud intelligence for fast reasoning, secure local execution for real development work**.

A large local LLM is not required. Files, persistent terminals, Git, builds, tests and device/toolchain operations stay local inside approved workspaces.

> **Status:** v0.1 Core under engineering. It is not production-ready; strict Release Mode deliberately blocks READY while required heavy adapters are missing.

## Current engine

- Cloud-reasoning provider boundary with explicit network permission.
- Fast / Engineer / Release work modes.
- Approved workspace roots with independent permissions.
- Read/write/delete file controls.
- Persistent per-Agent terminal sessions.
- Local Git status/diff/commit/push controls.
- SQLite project state and reusable workers.
- Builder/QA coordination and Definition of Done.
- Project-bound MCP tools.
- Add Project from GitHub with local clone reuse.
- Environment discovery for Git, Java/JDK, Gradle, ADB, CMake, Node/npm and Python.
- Strict Release Gate with secrets, artifact and SHA-256 evidence.
- Minimal desktop UI using the real engine.
- Windows and Ubuntu CI with package artifacts.

## Local bootstrap

Requires Python 3.12+.

```bash
python -m pip install -e .

nexvary-da init /path/to/project --repo owner/repo --allow-write --allow-shell

nexvary-da verify /path/to/project --mode fast
nexvary-da verify /path/to/project --mode engineer
nexvary-da verify /path/to/project --mode release

nexvary-da add-github /path/to/Projects https://github.com/owner/repo \
  --allow-write --allow-shell

nexvary-da status /path/to/project
nexvary-da discover /path/to/project
nexvary-da shell /path/to/project
nexvary-da ui /path/to/project
nexvary-da mcp /path/to/project
```

Sensitive project permissions are explicit: `--allow-delete`, `--allow-network`, `--allow-git-commit`, `--allow-git-push`, `--allow-release`, `--allow-adb`, and `--allow-desktop-automation`.

See `HYBRID_ARCHITECTURE.md`, `ARCHITECTURE.md`, `SECURITY_MODEL.md`, `RELEASE_GATE.md`, `ROADMAP.md`, and `WORK_PROJECT_STATE.md`.

## Optional ZCode Agent Engine

NEXVARY-DA supports the official ZCode CLI as a guarded planning engine. Select **Native**, **ZCode**, or **Hybrid** in the desktop UI, or use:

    nexvary-da plan "your task" --path . --engine hybrid --mode engineer

ZCode is forced into plan-only mode. NEXVARY remains the authority for file, shell, Git, build, ADB and release execution. Set `NEXVARY_DA_ZCODE_BIN` when the `zcode` executable is not already on `PATH`. See `ZCODE_INTEGRATION.md`.

