# Third-Party Notices

## chat-on-steroids

Architecture review reference:

- Repository: https://github.com/totec448-spec/chat-on-steroids
- Owner: totec448-spec
- License: MIT

NEXVARY-DA v0.1 was implemented independently and does not intentionally copy source code from that repository. If later work directly reuses MIT-licensed code, the applicable copyright and permission notice must be preserved with the reused material.

## ZCode

Optional runtime interoperability:

- Repository: https://github.com/zai-org/ZCode
- Owner: zai-org / Z.AI Co., Ltd
- License: Apache-2.0
- Reviewed integration target: ZCode v3.14.3

NEXVARY-DA invokes an independently installed ZCode CLI as an optional plan-only worker. This repository does not currently vendor or redistribute ZCode source code or binaries. If future packaging includes or modifies ZCode, NEXVARY must preserve the Apache-2.0 license and applicable NOTICE/attribution materials required by the upstream distribution.


## Native packaging toolchain

The CI/release toolchain may use the following external projects:

- PyInstaller — https://pyinstaller.org/ — GPL-2.0-or-later with the PyInstaller bootloader exception permitting distribution of packaged applications under their own license.
- NSIS — https://nsis.sourceforge.io/ — zlib/libpng license.
- Pillow — https://python-pillow.org/ — HPND license; used by the optional runtime screenshot QA path.

These tools are not copied into the NEXVARY-DA source tree as vendored projects. Native build outputs can contain the runtime/bootstrap components normally produced by those tools under their respective redistribution terms.


## Optional Stage 350 integrations

These projects are interoperated with as separately installed tools/services. NEXVARY-DA does not vendor their source or model weights in this integration.

- FastMCP — https://github.com/PrefectHQ/fastmcp — Apache-2.0.
- Cua Driver — https://github.com/trycua/cua — MIT.
- Oya Browser — https://github.com/OyadotAI/oya-browser — NEXVARY targets packages/sdk and packages/cli, which upstream LICENSE.md identifies as MIT. Other repository content is under separate Sustainable Use terms and is not copied by this integration.
- VoiceStudio — https://github.com/debpalash/VoiceStudio — AGPL-3.0-only. NEXVARY uses external API interoperability and does not vendor VoiceStudio.
- Qwen-Image 2.1 — https://github.com/QwenLM/Qwen-Image-2.1 — Qwen Research License Agreement. The reviewed upstream license limits the model materials to non-commercial use unless a separate commercial license is obtained. NEXVARY does not bundle the model weights.
- MoneyPrinterTurbo — https://github.com/harry0703/MoneyPrinterTurbo — MIT. NEXVARY invokes a separately installed workspace checkout.
