# NEXVARY Developer Agent (NEXVARY-DA)

NEXVARY-DA is a hybrid developer-agent runtime: **cloud intelligence for fast reasoning, secure local execution for real development work**.

A large local LLM is not required. Files, persistent terminals, Git, builds, tests and device/toolchain operations stay local inside approved workspaces.

> **Status:** v0.1 Core under engineering. It is not production-ready; strict Release Mode deliberately blocks READY while required heavy adapters are missing.

## Current engine

- Cloud-reasoning provider boundary with explicit network permission.
- Fast / Engineer / Release work modes.
- Approved workspace roots with independent permissions.
- Read/write/delete file controls.
- Persistent per-Agent terminal sessions.
- Local Git status/diff/commit/push controls.
- SQLite project state and reusable workers.
- Builder/QA coordination and Definition of Done.
- Project-bound MCP tools.
- Add Project from GitHub with local clone reuse.
- Environment discovery for Git, Java/JDK, Gradle, ADB, CMake, Node/npm and Python.
- Strict Release Gate with secrets, artifact and SHA-256 evidence.
- Minimal desktop UI using the real engine.
- Windows and Ubuntu CI with package artifacts.

## Local bootstrap

Requires Python 3.12+.

```bash
python -m pip install -e .

nexvary-da init /path/to/project --repo owner/repo --allow-write --allow-shell

nexvary-da verify /path/to/project --mode fast
nexvary-da verify /path/to/project --mode engineer
nexvary-da verify /path/to/project --mode release

nexvary-da add-github /path/to/Projects https://github.com/owner/repo \
  --allow-write --allow-shell

nexvary-da status /path/to/project
nexvary-da discover /path/to/project
nexvary-da shell /path/to/project
nexvary-da ui /path/to/project
nexvary-da mcp /path/to/project
```

Sensitive project permissions are explicit: `--allow-delete`, `--allow-network`, `--allow-git-commit`, `--allow-git-push`, `--allow-release`, `--allow-adb`, and `--allow-desktop-automation`.

See `HYBRID_ARCHITECTURE.md`, `ARCHITECTURE.md`, `SECURITY_MODEL.md`, `RELEASE_GATE.md`, `ROADMAP.md`, and `WORK_PROJECT_STATE.md`.

## Optional ZCode Agent Engine

NEXVARY-DA supports the official ZCode CLI as a guarded planning engine. Select **Native**, **ZCode**, or **Hybrid** in the desktop UI, or use:

    nexvary-da plan "your task" --path . --engine hybrid --mode engineer

ZCode is forced into plan-only mode. NEXVARY remains the authority for file, shell, Git, build, ADB and release execution. Set `NEXVARY_DA_ZCODE_BIN` when the `zcode` executable is not already on `PATH`. See `ZCODE_INTEGRATION.md`.



## Runtime UI and native packaging

Stage 300 adds runtime UI/interaction evidence, Android ADB UI automation, and native packaging.

```bash
nexvary-da ui-probe . --screenshot .nexvary-da/ui-probe.png
nexvary-da android-ui . --tap "Settings" --screenshot .nexvary-da/android-ui/shot.png
nexvary-da signing-status .
```

The CI pipeline builds and smoke-tests a one-file native executable on Windows and Linux, an NSIS Windows Setup, a Debian package, and portable bundles. Production code signing is deliberately separate: real organization-controlled signing credentials are required and are never generated or committed by NEXVARY-DA.


## Optional automation and media fabric

Stages 301-350 add a guarded plugin/integration layer for FastMCP, Cua Driver, the MIT-licensed Oya SDK/CLI surface, VoiceStudio as an external service, Qwen-Image 2.1 as an optional separately licensed model runtime, and MoneyPrinterTurbo as a workspace-contained external checkout.

Useful commands:

    nexvary-da integrations .
    nexvary-da cua-call list_apps --path .
    nexvary-da fastmcp-run server.py:mcp --path .
    nexvary-da oya-task https://example.com "Inspect this page" --path . --playbook inspect-page
    nexvary-da voicestudio-health .
    nexvary-da qwen-image "A technical diagram" --path . --output .nexvary-da/media/diagram.png
    nexvary-da moneyprinter-video "A short engineering explainer" --path .

No external project is auto-installed or silently downloaded. Cua mutation requires Desktop Automation plus explicit mutation approval. Oya browser credentials/personas remain outside NEXVARY state. Qwen-Image 2.1 weights are not bundled; the reviewed upstream Research License is non-commercial by default, so commercial use requires a separate upstream license.

See INTEGRATIONS.md and STAGES_301_350.md.


## Easy Mode

The desktop UI now opens in **Easy Mode** by default. Common work is presented as outcomes rather than commands:

- Start a task
- Build & test
- Automation & media Tool Box
- Tools & integrations Setup Center
- Release check
- Add project

Advanced Mode keeps the terminal, agent pool, engine controls, evidence timeline, and low-level operations for engineering users.

Non-secret integration paths can be configured with file/folder pickers and are stored in `.nexvary-da/integrations.json`. API keys and credentials are never persisted there.
