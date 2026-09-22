# NEXVARY-DA Architecture v0.1

## Primary architecture

NEXVARY-DA is a hybrid developer-agent system: **fast cloud intelligence plus secure local execution**. A large local LLM is not required for the normal operating path.

Cloud reasoning is separated from local tools by the Orchestrator and Workspace Guard. The AI may propose actions; execution is performed locally and remains permission-gated.

See `HYBRID_ARCHITECTURE.md`.

## Layers

1. **Cloud Intelligence Boundary** — provider-neutral reasoning interface; requires `network`; never gains direct shell/filesystem authority.
2. **Orchestrator / Work Modes** — Fast, Engineer and Release modes choose the minimum justified validation scope.
3. **Workspace Guard** — canonical approved roots and independent capabilities.
4. **Core Tools** — files, exact patching, search, process execution and Git.
5. **Persistent Terminal Pool** — long-lived local shells can be assigned per Agent/worker.
6. **Persistent Project State** — SQLite under `.nexvary-da/state.sqlite3`.
7. **Tool Kernel / MCP** — project-bound local tool surface over the same guarded runtime.
8. **Agent Pool** — durable reusable role slots.
9. **Goal Engine** — Definition of Done requires explicit evidence for each required obligation.
10. **Release Gate** — strict mode blocks READY when required heavy checks are unavailable.
11. **Environment Discovery** — Windows/Linux/Android/JDK/Gradle/ADB/Python/CMake/Node/Git.
12. **Project Import / Catalog** — secure Add Project from GitHub backend with clone reuse.
13. **Desktop UI** — minimal real UI over the same engine.

## State and source of truth

GitHub is authoritative for repository history when a project is connected to a repository. Local SQLite stores operational continuity: tasks, tool events, gate results, goals and worker state.

Project source remains local during execution. Chat history is not needed to resume operational state.

## Persistent terminals

`TerminalPool` provides one real long-lived shell per owner identity. This allows Builder, QA, Git and other workers to keep separate cwd/environment/shell state instead of recreating shells per command.

Windows and POSIX terminal continuity are covered by CI.

## Project onboarding

`ProjectImporter` accepts canonical HTTPS GitHub repository URLs. It clones only into a user-approved Projects Root. If the matching repository is already present with the same origin, the clone is reused rather than downloaded again.

After onboarding the engine records repository URL, local path, project kind, branch/commit when permitted, and granted project permissions.

## Agent direction

Stable roles remain Coordinator, Builder, Code Inspector, UI Inspector, QA Agent, Security Inspector, Git Agent and Release Manager. The Coordinator chooses only the workers justified by the selected work mode.

## Reference review

The review of `totec448-spec/chat-on-steroids` reinforced principles adopted independently here: authorization below tool surfaces, durable worker state, explicit workspace identity, continuation from project state, and no false success when evidence is missing.
