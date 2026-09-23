# Work Project State

GitHub is the source of truth for source history. Runtime state remains under each approved project's `.nexvary-da/` directory.

## Repository

- Repository: `nexvary/NEXVARY-DA`
- Development branch: `dev/v0.1-core`
- Product: NEXVARY Developer Agent
- Current milestone candidate: Stage 460

## Verified baseline before Stage 300

Stage 250 was verified at commit `0d9eedbdcd0c2479127344661681b86e8daf55b3` with Core CI Run #25 passing Ubuntu and Windows.

Stage 251–275 introduced the runtime UI probe and actual Linux/Xvfb screenshot evidence. That batch must independently pass before the Stage 276–300 candidate is accepted.

## Stage 251–300 capabilities

- Runtime Tk geometry inspection.
- Interactive overlap and clipping detection.
- Probe-safe control invocation.
- Real Linux CI screenshot with SHA-256 and visual-variation evidence.
- UI evidence tied to the current source fingerprint and consumed by strict Release Gate.
- Android ADB runtime UI hierarchy inspection.
- Tap-by-label, Back, component start and Android screenshot capture.
- PyInstaller native one-file builds on Windows/Linux.
- Portable native ZIP/tar.gz packaging.
- NSIS Windows installer with install/smoke/uninstall CI.
- Debian package with install/smoke/remove CI.
- Signing readiness diagnostics with no secret-value disclosure.

## Security boundaries retained

- ZCode remains plan-only behind NEXVARY.
- Machine plans still pass PlanGuard and ToolKernel.
- Android runtime actions require ADB permission.
- Desktop UI probing requires Desktop Automation permission.
- Screenshot writes require Write permission.
- Release signing is not simulated with self-signed credentials.

## Still externally dependent

- Production Windows Authenticode certificate.
- Production Linux signing key / package-repository signing policy.
- A real authorized Android device/emulator for target-specific runtime traversal.
- Production cloud-provider/model/API credentials and cost policy.

## Completion rule

The Stage 300 candidate becomes the verified baseline only after the exact branch head passes both Ubuntu and Windows CI, including native executable/package checks. Any credential-dependent signing step remains explicitly unverified until genuine credentials are supplied.


## Verified Stage 300 baseline

The Stage 300 baseline was verified at commit fed16db221c4c2b72c4be9df1a76940402419fa1 with Core CI Run #30 succeeding after native NSIS/packaging fixes.

## Stage 301-350 candidate capabilities

- Optional Plugin Hub with six built-in integration families and status-only custom manifests.
- FastMCP server launcher through the managed process registry.
- Cua Driver computer-use adapter with read-only/mutating allowlists and explicit mutation approval.
- Oya Browser SDK bridge for explicit tasks and playbook recording without copying browser credentials.
- VoiceStudio loopback/HTTPS service adapter.
- Qwen-Image 2.1 external runtime adapter with non-commercial license boundary surfaced.
- MoneyPrinterTurbo workspace-contained CLI video adapter.
- CLI, MCP, and desktop UI integration readiness surfaces.
- No external project is auto-installed, auto-downloaded, or granted permissions by discovery.

Stage 350 is accepted only after the exact candidate head passes Windows and Ubuntu CI, including the Stage 300 native packaging checks.


## Stage 351-400 usability candidate

- Easy Mode is the default desktop experience.
- Advanced engineering controls and terminal are hidden until explicitly requested.
- Graphical Setup Center replaces manual environment-variable/path configuration for non-secret integration settings.
- Session credentials such as Oya API keys are not persisted.
- Graphical Tool Box exposes Desktop, Browser, Image, Video, Voice, and MCP workflows as forms.
- Common task planning automatically selects Hybrid when ZCode is available, otherwise Native.
- Strict release verification is available from one visible button.

The candidate is accepted only after the exact Stage 400 head passes Windows and Ubuntu Core CI, runtime UI probe, and native packaging/install smoke tests.


## Stage 401-425 visual candidate

- Neon/electric multi-color identity over a deep black/navy chassis.
- Metallic silver/chrome borders across primary GUI surfaces.
- Neon green reserved for clickable action affordances; PASS/READY moved to cyan.
- Easy Mode cards use distinct cyan/blue/purple/magenta/orange/gold accents.
- Setup Center and Tool Box share the same visual system.
- Acceptance still requires runtime UI probe, screenshot evidence, Windows CI/installer smoke, and Ubuntu/Debian smoke.


## Stage 426-460 information/security/navigation candidate

- About / عنا page with official NEXVARY social channels.
- System Overview / حول النظام page documenting all major platform capabilities and verification boundaries.
- Dedicated Navigation Integrity Probe opens every registered window, integration page, Tool Box category, and Add Project dialog.
- Strict Release Gate requires current navigation evidence for the NEXVARY desktop UI.
- CI adds dependency vulnerability auditing with pip-audit while retaining source/secret/workspace/UI/package checks.
