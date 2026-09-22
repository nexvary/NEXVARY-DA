# Release Gate v0.1

## Two validation levels

Development validation may run only the checks that are currently applicable and configured.

Strict Release Mode is fail-closed: every required release category must produce evidence. Missing adapters are `NOT_CONFIGURED` and block `ready=true`.

## Status vocabulary

- **PASS** — the check ran and succeeded.
- **FAIL** — the check ran and failed.
- **NOT_CONFIGURED** — required evidence is unavailable.
- **SKIP** — optional/non-strict adapter not configured.

## Current executable checks

Depending on project kind:

- Compile/build.
- Unit tests.
- Gradle lint/package where applicable.
- Secrets scan.
- Git diff check.
- Git status.
- Artifact discovery in known output locations.
- Non-empty artifact validation.
- SHA-256 generation for recognized artifacts.

## Strict release obligations awaiting adapters

Until project-specific implementations exist, strict Release Mode blocks READY for missing integration tests, static analysis, dead links, orphan pages, broken buttons, navigation, UI gate, RTL and localization checks.

This is intentional: unsupported checks are never reported as PASS.
