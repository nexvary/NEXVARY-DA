# NEXVARY-DA Architecture v0.1

## Scope

v0.1 establishes a local-first developer-agent core. It intentionally avoids browser/DOM coupling and does not claim generic UI automation, Android device control, or autonomous model execution before the permission and state layers are stable.

## Layers

1. **Workspace Guard** — canonical approved roots and independent capabilities.
2. **Core Tools** — files, exact patching, search, process execution, Git.
3. **Persistent Terminal** — one long-lived shell per session; cwd and environment survive commands.
4. **Persistent Project State** — SQLite under `.nexvary-da/state.sqlite3`.
5. **Tool Kernel** — transport-independent dispatch with live permission checks and event recording; this is the boundary an MCP transport will wrap.
6. **Agent Pool** — durable role slots so worker identity can be reused across tasks.
7. **Release Gate** — evidence-producing checks; unsupported checks are SKIP/NOT_CONFIGURED, never false PASS.
8. **Environment Discovery** — Windows/Linux/Android/JDK/Gradle/ADB/Python/CMake/Node/Git discovery.
9. **Desktop UI** — minimal Tk UI over the real core. The UI is not the source of truth.

## State and source of truth

The project directory owns operational continuity. Chat history is not required to resume. When the project is connected to GitHub, Git history remains authoritative for code; local SQLite records operational state such as tasks, gate results and agent slots.

## MCP direction

`ToolKernel` is transport-independent by design. MCP will be added as a wrapper and will not be allowed to bypass Workspace Guard or event recording.

## Reference review

The review of `totec448-spec/chat-on-steroids` reinforced four principles adopted independently here: authorization belongs below tool surfaces, workspace identity must not be guessed from UI state, worker state should be durable, and missing evidence must never be reported as success. NEXVARY-DA is focused specifically on software-development workflows and does not clone that project.
