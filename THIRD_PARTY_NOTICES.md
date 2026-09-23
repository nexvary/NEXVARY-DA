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
