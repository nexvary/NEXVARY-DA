# Release Gate v0.1

The gate reports evidence, not optimism.

## Status vocabulary

- **PASS** — the check actually ran and succeeded.
- **FAIL** — the check ran and failed.
- **NOT_CONFIGURED** — a required check cannot run because a project profile is missing.
- **SKIP** — an optional or project-specific adapter is not configured.

A release is `ready=true` only when every required step is PASS.

## v0.1 adapters

For Python: `compileall`, unittest discovery, secrets scan and (in Git worktrees) `git diff --check`.

For Gradle/Android: wrapper `test`, `lint`, `assembleDebug`, secrets scan and Git diff check.

Node and CMake are detected but v0.1 refuses to guess project-specific build semantics; an explicit profile is required.

## Planned heavy QA adapters

Dead links, orphan pages, broken-button/navigation probes, RTL, localization completeness, UI overflow, missing-resource validation, artifact validation, signing and release publication. Until a real adapter exists these checks are never shown as PASS.
