$ErrorActionPreference = "Stop"
$installer = Resolve-Path "release-native\NEXVARY-DA-Setup.exe"
& $installer /S
if ($LASTEXITCODE -ne 0) { throw "installer failed: $LASTEXITCODE" }

$installDir = Join-Path $env:LOCALAPPDATA "NEXVARY\Developer Agent"
$exe = Join-Path $installDir "NEXVARY-DA.exe"
if (-not (Test-Path $exe)) { throw "installed executable missing: $exe" }

$output = & $exe --help 2>&1
if ($LASTEXITCODE -ne 0) { throw "installed executable smoke failed: $LASTEXITCODE" }
if (($output -join "`n") -notmatch "nexvary-da") { throw "unexpected installed help output" }

$uninstaller = Join-Path $installDir "Uninstall.exe"
if (-not (Test-Path $uninstaller)) { throw "uninstaller missing" }
& $uninstaller /S
if ($LASTEXITCODE -ne 0) { throw "uninstaller failed: $LASTEXITCODE" }
Start-Sleep -Seconds 2
if (Test-Path $exe) { throw "executable still exists after uninstall" }
Write-Host "NSIS install/smoke/uninstall PASS"
