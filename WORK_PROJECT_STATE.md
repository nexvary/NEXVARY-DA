# Work Project State

Runtime operational state lives locally in `.nexvary-da/state.sqlite3`. GitHub remains the code-history source of truth.

## Repository

- Repository: `nexvary/NEXVARY-DA`
- Development branch: `dev/v0.1-core`
- Product: NEXVARY Developer Agent
- Current target: hybrid v0.1 Core

## Verified baseline before hybrid expansion

Run #13 on commit `0c6b4c73bb43d592424d65a00823706dcc3dc59e` passed on Ubuntu 24.04 and Windows. It covered compile, unit/integration tests, CLI smoke test, source distribution and wheel creation, distribution validation and artifact upload.

## Hybrid architecture now incorporated in source

- Cloud Intelligence boundary with explicit network permission.
- Local execution remains authoritative for files, shell, Git, build and tests.
- Fast, Engineer and strict Release modes.
- Independent delete/network/git-commit permissions.
- Git push requires both git-push and network.
- Per-Agent persistent Terminal Pool.
- Add Project from GitHub backend with matching-clone reuse.
- Local project catalog under the selected Projects Root.
- Change discovery from local Git for scoped validation.
- Strict Release Gate fails closed on missing heavy QA evidence.
- Artifact discovery and SHA-256 release evidence.
- Minimal UI controls for work mode and Add Project from GitHub.

## Still incomplete

- Concrete cloud-provider adapter and credential configuration.
- Autonomous cloud-plan -> approved local tool-call loop.
- Validation cache and file watcher.
- Targeted test selection beyond current Builder/QA project adapters.
- GitHub PR/Actions/Release API integration inside the local app.
- Android UI/device QA and ADB lab adapters.
- UI/RTL/localization/broken-button/navigation/dead-link/orphan-page heavy adapters.
- Node/CMake project profiles.
- Signed Windows/Linux installers.

## Completion rule

No code path may claim strict Release READY while required evidence is missing. The hybrid batch must pass Windows and Ubuntu CI before it is treated as the new verified baseline.
