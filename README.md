# NEXVARY Developer Agent (NEXVARY-DA)

NEXVARY-DA is a local, permission-gated developer agent runtime for managing approved software workspaces, persistent project state, terminal sessions, build/test workflows, and release gates.

> Status: v0.1 Core bootstrap. The project is under active engineering and is not yet production-ready.

## Design principles

- Local-first execution.
- Explicit workspace boundaries and independent permissions.
- Project state lives with the project, not in chat history.
- Persistent shell sessions.
- Verifiable Definition of Done.
- Cross-platform support targeting Windows 10 and Ubuntu 24.04.
- GitHub as source of truth when a project is connected to a repository.
- No fake features, no mock success states, and no unrestricted shell by default.

## v0.1 priorities

Workspace Guard, persistent project state, persistent terminal, file/Git/process tools, coordinator/builder/QA agents, release-gate orchestration, Android/Gradle discovery, Windows/Linux environment discovery, and a minimal usable desktop UI.

See `ARCHITECTURE.md`, `SECURITY_MODEL.md`, `WORK_PROJECT_STATE.md`, and `RELEASE_GATE.md` as they land.
