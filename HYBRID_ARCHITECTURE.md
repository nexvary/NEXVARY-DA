# Hybrid Architecture — Cloud Intelligence + Secure Local Execution

## Core rule

NEXVARY-DA is not designed around a mandatory local LLM.

The default architecture is:

```text
Cloud AI / Reasoning
        |
        v
NEXVARY-DA Orchestrator
        |
        v
Permission Layer
        |
        v
Local Tools / Agent Terminals
        |
        v
Local Build + Test + Git
        |
        v
GitHub / CI / Releases
```

Cloud intelligence may analyze, plan and generate complex code decisions. It does not receive unrestricted filesystem or shell access. Local execution remains inside approved Workspace Roots.

## Cloud boundary

`CloudIntelligenceGateway` requires the independent `network` permission. It sends only an explicit `ReasoningRequest`. Project files are not automatically uploaded; the orchestrator must deliberately choose context.

A concrete cloud-provider adapter is intentionally separate from the execution engine. NEXVARY-DA can support different cloud providers later without changing the local permission, terminal, build or state layers.

Large local models remain optional for privacy/offline workflows and are not a runtime prerequisite.

## Local execution

These operations stay local:

- File read/write/delete.
- Persistent terminals.
- Git status/diff/commit/push dispatch.
- Gradle, Android SDK and ADB.
- Python, CMake and Node.js.
- Builds and tests.
- UI inspection adapters.
- Package/artifact inspection.

Network actions are additionally permission-gated. For example, `git_push` requires both `git_push` and `network`.

## Work modes

### Fast

Intended for a narrow change. Runs a minimal local validation path and does not invoke the full release gate.

### Engineer

Default development mode. Runs local build plus related QA without a clean release rebuild.

### Release

Runs strict release verification. Missing heavy adapters are `NOT_CONFIGURED` and block READY instead of being treated as PASS.

## Performance model

The engine should prefer local incremental feedback before remote CI. Git changed-file discovery is used to scope work. Re-cloning an already registered matching GitHub repository is avoided.

Planned performance layers include file watching, validation-result caching keyed by commit/change set/toolchain, Gradle build cache, targeted test selection and process reuse.

## GitHub flow

The intended lifecycle is:

```text
GitHub -> Add Project from GitHub -> local persistent workspace
       -> local edit/build/test -> optional commit/push -> independent CI
```

GitHub Actions remains independent verification, not the only build engine.
