# ZCode Integration

NEXVARY-DA integrates the official `zai-org/ZCode` project as an **optional planning worker**.

## Security boundary

ZCode does not replace NEXVARY's local execution layer.

When NEXVARY invokes ZCode headlessly it always supplies:

- `--mode plan`
- `--output-format json`
- `--no-color`
- the approved project path through `--cwd`
- a disallow list for shell/write/edit/delete/web-search tools

This matters because the reviewed ZCode v3.14.3 source defines the default headless `--prompt` mode as `yolo` when no explicit mode is supplied. NEXVARY never relies on that default.

The adapter additionally requires all of:

- Read
- Write — ZCode keeps isolated runtime/session data under `.nexvary-da/zcode-data`
- Shell
- Network

ZCode output is treated as an untrusted proposal. It must parse into NEXVARY's strict execution-plan schema. Proposed actions do not bypass ToolKernel or Workspace Guard.

## Engine modes

- **Native** — NEXVARY planning and validation only.
- **ZCode** — ZCode contributes the plan; NEXVARY remains execution authority.
- **Hybrid** — combines NEXVARY project/change/validation context with a ZCode plan.

## CLI

`NEXVARY_DA_ZCODE_BIN` may point to the official `zcode` executable. If unset, NEXVARY searches `PATH`.

Example:

    nexvary-da plan "Review the changed files and propose the next engineering steps" --path . --engine hybrid --mode engineer

The desktop UI exposes the same Native / ZCode / Hybrid selector and a **PLAN TASK** action.

## Upstream

Reviewed upstream repository: `https://github.com/zai-org/ZCode`

The integration was developed against ZCode v3.14.3 as published in the upstream README on 2026-09-23. ZCode is licensed under Apache-2.0.

NEXVARY-DA currently interoperates with the external ZCode CLI and does not vendor or redistribute ZCode source or binaries. If a future release bundles or modifies ZCode, the applicable Apache-2.0 LICENSE/NOTICE obligations must be included in that distribution.
