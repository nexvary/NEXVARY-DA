# NEXVARY-DA Architecture v0.1

## Scope

v0.1 establishes a local-first developer-agent core. It intentionally avoids browser/DOM coupling and does not claim generic UI automation, Android device control, or autonomous model execution before those adapters have verifiable evidence.

## Layers

1. **Workspace Guard** — canonical approved roots and independent capabilities.
2. **Core Tools** — files, exact patching, search, process execution and Git.
3. **Persistent Terminal** — one long-lived shell per project session; cwd and environment survive commands.
4. **Persistent Project State** — SQLite under `.nexvary-da/state.sqlite3`.
5. **Tool Kernel** — transport-independent dispatch with live permission checks and event recording.
6. **MCP Transport** — project-bound local MCP facade over the real runtime; it cannot select arbitrary roots.
7. **Agent Pool** — durable role slots and worker reuse; Builder and QA have executable v0.1 adapters.
8. **Goal Engine** — durable Definition of Done; every required obligation needs explicit PASS evidence.
9. **Release Gate** — evidence-producing checks; unsupported checks are SKIP/NOT_CONFIGURED, never false PASS.
10. **Environment Discovery** — Windows/Linux/Android/JDK/Gradle/ADB/Python/CMake/Node/Git discovery.
11. **Desktop UI** — minimal Tk UI over the same real runtime. The UI is not a source of truth.

## State and source of truth

The project directory owns operational continuity. Chat history is not required to resume. When a project is connected to GitHub, Git history is authoritative for code. Local SQLite records operational state such as tasks, gate results, tool events, goals and agent slots.

## Terminal lifecycle

One-shot commands use `ProcessRunner`. Interactive continuity uses `PersistentTerminal`. Windows uses a long-lived `cmd.exe` session with framed command output; POSIX systems use a long-lived shell. Both paths are covered by CI tests that prove cwd continuity across calls.

## MCP boundary

The MCP server binds to one initialized project at startup. Read/write/search/terminal/Git/release-gate tools delegate to the same guarded runtime rather than implementing a second permission model. Write and shell actions therefore remain subject to Workspace Guard.

## Agent direction

Stable roles are Coordinator, Builder, Code Inspector, UI Inspector, QA Agent, Security Inspector, Git Agent and Release Manager. Worker identity is durable. v0.1 implements deterministic Builder/QA adapters; higher-level model-provider orchestration remains separate.

## Reference review

The review of `totec448-spec/chat-on-steroids` reinforced principles adopted independently here: authorization belongs below tool surfaces, workspace identity must not be guessed from UI state, worker state should be durable, and missing evidence must never be reported as success. NEXVARY-DA is focused specifically on software-development workflows and does not clone that project.
