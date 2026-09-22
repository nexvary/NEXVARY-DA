# Security and Permission Model

## Default posture

A directory is inaccessible until it is initialized as an approved project. `read` is mandatory for an approved root; every mutating or higher-risk capability is independent and opt-in.

Capabilities:

- `read`
- `write`
- `shell`
- `git_push`
- `release`
- `adb`
- `desktop_automation`

Granting `shell` does not grant `git_push`; granting `write` does not grant `release`.

## Path containment

Workspace Guard resolves existing paths canonically. For new paths it resolves the nearest existing ancestor before authorization, preventing a symlink/junction inside an approved root from silently redirecting access outside the root.

## Shell

Persistent shells are real long-lived processes and require the explicit `shell` capability. v0.1 does not yet implement command-level allowlists; shell permission is therefore a strong capability.

## Internal state

`.nexvary-da/` is reserved control-plane metadata created after the user approves a project. Source-file write permission remains independent from this internal state store.

## Sensitive actions

Git push, release publication, ADB and desktop automation are distinct capabilities. Higher-level adapters must check the relevant capability even if shell access exists.

## Secrets

The v0.1 Release Gate includes a local high-confidence scanner for common private-key headers, GitHub token forms and AWS access-key identifiers. It is not a substitute for enterprise secret scanning.

## v0.1 non-goals

No whole-machine filesystem access, automatic privilege elevation, browser credential extraction, silent Git push, silent release publication or unbounded desktop automation.
