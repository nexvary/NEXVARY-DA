# Work Project State

Runtime operational state lives under `.nexvary-da/`. GitHub remains the code-history source of truth.

## Repository

- Repository: `nexvary/NEXVARY-DA`
- Development branch: `dev/v0.1-core`
- Product: NEXVARY Developer Agent
- Current milestone candidate: Stage 250

## Verified baseline before Stage 250

Stage 180 and the ZCode integration baseline reached commit `f435c9a4055fbb8250bed3e71d12fc36ad25f40c`, with Core CI Run #22 passing Windows and Ubuntu.

## Stage 181–250 additions

- Guarded plan execution through the real NEXVARY ToolKernel.
- Explicit mutation approval and dry-run defaults.
- Execution receipts with Git/change evidence.
- Durable redacted Checkpoint / Compact / Resume.
- Android Manifest/resource/localization static QA.
- Android QA evidence in the strict Release Gate.
- Deterministic source provenance with SHA-256 fingerprints.
- Project Doctor diagnostics.
- CLI and MCP surfaces for checkpoint/resume/provenance/doctor.
- ZCode remains plan-only and cannot bypass NEXVARY permissions.

## Deliberately incomplete / fail-closed

- Runtime screenshot + interactive desktop UI automation.
- Full Android emulator/device interaction traversal and screenshot baselines.
- Signed Windows/Linux installers.
- Production release publication.
- Production cloud-provider/model/credential selection.
- Optional local/offline AI models.

## Completion rule

The Stage 250 candidate becomes the new verified baseline only after the exact branch head passes Windows and Ubuntu CI. Strict Release READY remains blocked whenever required evidence cannot be proven.
