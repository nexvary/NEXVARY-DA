# Security and Permission Model

## Default posture

An approved project has a canonical Workspace Root. Capabilities are independent and opt-in.

Current capabilities:

- `read`
- `write`
- `delete`
- `shell`
- `network`
- `git_commit`
- `git_push`
- `release`
- `adb`
- `desktop_automation`

`write` does not imply `delete`. `git_commit` does not imply `git_push`. `git_push` also requires `network`. A strict release gate requires `release`.

## Cloud intelligence

Cloud reasoning requires `network` permission. The cloud provider receives only explicitly constructed reasoning context. The local filesystem is not automatically serialized or uploaded.

A cloud model never bypasses Workspace Guard; local tools remain separate capabilities.

## Path containment

Workspace Guard resolves existing paths canonically. New paths resolve their nearest existing ancestor before authorization, preventing a symlink/junction from silently escaping an approved root.

## Project import

Add Project from GitHub is restricted to canonical HTTPS GitHub repository URLs in v0.1. Clones are placed only below a selected Projects Root. Existing directories are reused only when they are Git worktrees whose `origin` matches the requested repository.

## Shell

Persistent shells are real long-lived processes and require `shell`. Terminals can be separated per worker identity through TerminalPool.

Command-level allowlists are not yet implemented, so shell remains a strong capability.

## Git

Reading status/diff uses local shell access. Creating a commit requires `git_commit`. Pushing requires both `git_push` and `network`.

## Releases

Release mode is intentionally fail-closed. Missing required heavy adapters are reported as `NOT_CONFIGURED`, which prevents READY.

## Secrets

The Release Gate includes a local high-confidence scanner for common private-key headers, GitHub token formats and AWS access-key identifiers. It is not a replacement for dedicated enterprise secret scanning.

## Non-goals

No whole-machine filesystem access, automatic privilege elevation, silent deletion, silent network access, silent Git push, silent release publication, browser credential extraction or unrestricted desktop automation.
