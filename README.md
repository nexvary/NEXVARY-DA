# NEXVARY Developer Agent (NEXVARY-DA)

NEXVARY-DA is a local, permission-gated developer-agent runtime for approved software workspaces. It is designed around persistent project state, real terminal continuity, verifiable Definition-of-Done gates, and project-bound MCP tools.

> **Status:** v0.1 Core under engineering. It is not labelled production-ready until the remaining v0.1 scope and final Release Gate are verified.

## Working v0.1 surfaces

- Approved workspace roots with independent permissions.
- Atomic file writes, exact patching and bounded text search.
- Persistent Windows/POSIX terminal sessions whose cwd and environment survive commands.
- Process and Git helpers.
- SQLite project state.
- Reusable Agent Pool slots plus executable Builder and QA adapters.
- Durable Goal Engine requiring explicit evidence for required completion conditions.
- Project-bound local MCP server using the same permission-gated runtime.
- Environment discovery for Git, Java/JDK, Gradle, ADB, CMake, Node/npm and Python.
- Release Gate with Python and Gradle/Android adapters.
- High-confidence local secrets scan.
- Minimal desktop UI using the same real core.
- Windows and Ubuntu CI with MCP integration tests and package artifacts.

Unsupported generic checks are shown as `SKIP` or `NOT_CONFIGURED`; they are never presented as successful.

## Local bootstrap

Requires Python 3.12+.

```bash
python -m pip install -e .
nexvary-da init /path/to/project --repo owner/repo --allow-write --allow-shell
nexvary-da status /path/to/project
nexvary-da discover /path/to/project
nexvary-da build /path/to/project
nexvary-da qa /path/to/project
nexvary-da gate /path/to/project
nexvary-da shell /path/to/project
nexvary-da ui /path/to/project
nexvary-da mcp /path/to/project
```

Higher-risk permissions are opt-in: `--allow-git-push`, `--allow-release`, `--allow-adb`, and `--allow-desktop-automation`.

Runtime configuration/state is written under `.nexvary-da/` and ignored by Git.

## Engineering state

- `ARCHITECTURE.md`
- `SECURITY_MODEL.md`
- `RELEASE_GATE.md`
- `ROADMAP.md`
- `WORK_PROJECT_STATE.md`
- `THIRD_PARTY_NOTICES.md`
