# NEXVARY-DA Roadmap

## Stage 300 developer-agent platform

- Workspace permission boundary and persistent state.
- Native / ZCode / Hybrid planning.
- Guarded plan execution with dry-run and explicit mutation approval.
- Persistent terminals, managed processes, Git/build/test/Android/GitHub tools.
- Fast / Engineer / Release verification.
- Python / Gradle / Node / CMake build profiles.
- Static QA and Android source QA.
- Artifact/source SHA-256 provenance.
- Checkpoint / Compact / Resume.
- Runtime desktop UI geometry and interaction probe.
- Linux/Xvfb real screenshot evidence tied to source fingerprint.
- Android ADB runtime UI harness.
- Windows/Linux native one-file binaries.
- Windows NSIS installer.
- Debian package.
- Portable native bundles.
- Production signing-readiness diagnostics.
- Project-bound MCP.
- QHD-aware Dark/Gold/Blue desktop shell.

## Next hardening

- Production Authenticode signing once a real certificate is supplied.
- Linux repository/package signing once an organizational signing key is supplied.
- Target Android emulator/device matrices for specific application projects.
- Screenshot baselines and pixel/structural diff thresholds per project.
- Rich GitHub Actions artifact-download and release-publication UX.
- OS credential vault integration.
- Reproducible-build comparison across isolated runners.
- Crash recovery and task replay across interrupted local executions.

## External decisions / credentials required

NEXVARY-DA will not invent or self-sign production identities. Windows code signing, Linux package/repository signing, and production cloud API usage require organization-controlled credentials and explicit policy.
