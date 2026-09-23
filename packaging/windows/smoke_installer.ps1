$ErrorActionPreference = "Stop"

$installer = (Resolve-Path "release-native\NEXVARY-DA-Setup.exe").Path
$installProcess = Start-Process -FilePath $installer -ArgumentList "/S" -Wait -PassThru
if ($installProcess.ExitCode -ne 0) {
    throw "installer failed: $($installProcess.ExitCode)"
}

$installDir = Join-Path $env:LOCALAPPDATA "NEXVARY\Developer Agent"
$exe = Join-Path $installDir "NEXVARY-DA.exe"
if (-not (Test-Path $exe)) {
    throw "installed executable missing: $exe"
}

$output = & $exe --help 2>&1
$helpExit = $LASTEXITCODE
if ($helpExit -ne 0) {
    throw "installed executable smoke failed: $helpExit"
}
if (($output -join "`n") -notmatch "nexvary-da") {
    throw "unexpected installed help output"
}

$uninstaller = Join-Path $installDir "Uninstall.exe"
if (-not (Test-Path $uninstaller)) {
    throw "uninstaller missing"
}

$uninstallProcess = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -PassThru
if ($uninstallProcess.ExitCode -ne 0) {
    throw "uninstaller failed: $($uninstallProcess.ExitCode)"
}

$deadline = (Get-Date).AddSeconds(15)
while ((Test-Path $exe) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
if (Test-Path $exe) {
    throw "executable still exists after uninstall"
}

Write-Host "NSIS install/smoke/uninstall PASS"
