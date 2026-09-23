# Optional Integration Fabric

NEXVARY-DA keeps external tools optional. The core never auto-installs them and never treats their presence as permission to execute them.

## FastMCP

FastMCP is used as an optional MCP server/tool fabric. Local targets must stay inside the approved workspace. Remote targets require Network permission and non-loopback plaintext HTTP is rejected.

## Cua Driver

Cua Driver provides native computer-use primitives. NEXVARY divides its calls into read-only and mutating allowlists. Mouse, keyboard, launch, drag, clipboard-write, and window mutation require explicit allow_mutation in addition to Desktop Automation permission.

## Oya Browser

The Oya integration uses the MIT-licensed @oya-ai/browser SDK surface when it is already installed under an approved Node workspace. NEXVARY passes task instructions to a short-lived local JSON file and does not accept passwords, cookies, MFA codes, or browser secrets through this adapter.

## VoiceStudio

VoiceStudio is treated as a separately installed external service. The default endpoint is loopback-only at http://127.0.0.1:3900. Non-loopback endpoints must use HTTPS. No VoiceStudio source or binary is bundled.

## Qwen-Image 2.1

The adapter can call a separately installed Diffusers QwenImage21Pipeline. Model weights are not bundled. The upstream Qwen Research License is non-commercial by default; commercial use requires a separate license from the upstream rightsholder.

## MoneyPrinterTurbo

MoneyPrinterTurbo remains a separate checkout. To preserve Workspace Guard guarantees, NEXVARY only executes it when its root is inside the currently approved workspace and contains cli.py.

## Environment variables

- NEXVARY_DA_FASTMCP_BIN
- NEXVARY_DA_CUA_BIN
- NEXVARY_DA_NODE_BIN
- NEXVARY_DA_OYA_NODE_ROOT
- OYA_API_KEY
- NEXVARY_DA_VOICESTUDIO_URL
- NEXVARY_DA_MONEYPRINTER_ROOT

Credential values are not included in plugin snapshots or event logs.
