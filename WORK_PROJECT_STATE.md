# Work Project State

This file is the human-readable handover. Runtime state is stored locally in `.nexvary-da/state.sqlite3`.

## Repository

- Repository: `nexvary/NEXVARY-DA`
- Development branch: `dev/v0.1-core`
- Product: NEXVARY Developer Agent
- Current target: v0.1 Core

## Implemented on the development branch

Workspace Guard; independent capabilities; SQLite state; persistent terminal; file/process/Git tools; environment discovery; durable Agent Pool; executable Builder and QA adapters; transport-independent Tool Kernel; Release Gate v0.1; minimal desktop UI; core tests.

## Explicitly not complete

MCP transport; GitHub Actions API integration inside the local app; external model-provider orchestration; Android UI/device QA; generic dead-link/orphan-page/UI adapters; signed packaging and release publication.

## v0.1 merge condition

Do not call v0.1 Core complete until both Ubuntu and Windows CI compile and pass the unit tests.
