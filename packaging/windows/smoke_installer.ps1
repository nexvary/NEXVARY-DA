$ErrorActionPreference = "Stop"

$installer = (Resolve-Path "release-native\NEXVARY-DA-Setup.exe").Path
$installProcess = Start-Process -FilePath $installer -ArgumentList "/S" -Wait -PassThru
if ($installProcess.ExitCode -ne 0) {
    throw "installer failed: $($installProcess.ExitCode)"
}

$installDir = Join-Path $env:LOCALAPPDATA "NEXVARY\Developer Agent"
$exe = Join-Path $installDir "NEXVARY-DA.exe"
$guiExe = Join-Path $installDir "NEXVARY-DA-GUI.exe"
if (-not (Test-Path $exe)) {
    throw "installed CLI executable missing: $exe"
}
if (-not (Test-Path $guiExe)) {
    throw "installed GUI executable missing: $guiExe"
}

$output = & $exe --help 2>&1
$helpExit = $LASTEXITCODE
if ($helpExit -ne 0) {
    throw "installed executable smoke failed: $helpExit"
}
if (($output -join "`n") -notmatch "nexvary-da") {
    throw "unexpected installed help output"
}

$shortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\NEXVARY\NEXVARY Developer Agent.lnk"
if (-not (Test-Path $shortcut)) {
    throw "Start Menu shortcut missing: $shortcut"
}
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "NEXVARY Developer Agent.lnk"
if (-not (Test-Path $desktopShortcut)) {
    throw "Desktop shortcut missing: $desktopShortcut"
}
$ws = New-Object -ComObject WScript.Shell
$targetPath = $ws.CreateShortcut($shortcut).TargetPath
if ((Resolve-Path $targetPath).Path -ne (Resolve-Path $guiExe).Path) {
    throw "Start Menu shortcut points to wrong executable: $targetPath"
}
$desktopTargetPath = $ws.CreateShortcut($desktopShortcut).TargetPath
if ((Resolve-Path $desktopTargetPath).Path -ne (Resolve-Path $guiExe).Path) {
    throw "Desktop shortcut points to wrong executable: $desktopTargetPath"
}

$env:NEXVARY_DA_APPDATA = Join-Path $env:TEMP "nexvary-da-installed-gui-smoke"
$guiProcess = Start-Process -FilePath $guiExe -ArgumentList "--smoke" -Wait -PassThru
if ($guiProcess.ExitCode -ne 0) {
    throw "installed GUI launcher smoke failed: $($guiProcess.ExitCode)"
}
$workspaceConfig = Join-Path $env:NEXVARY_DA_APPDATA "Workspace\.nexvary-da\project.json"
if (-not (Test-Path $workspaceConfig)) {
    throw "installed GUI launcher did not create first-run workspace"
}
Remove-Item Env:NEXVARY_DA_APPDATA

$uninstaller = Join-Path $installDir "Uninstall.exe"
if (-not (Test-Path $uninstaller)) {
    throw "uninstaller missing"
}

$uninstallProcess = Start-Process -FilePath $uninstaller -ArgumentList "/S" -Wait -PassThru
if ($uninstallProcess.ExitCode -ne 0) {
    throw "uninstaller failed: $($uninstallProcess.ExitCode)"
}

$deadline = (Get-Date).AddSeconds(15)
while (((Test-Path $exe) -or (Test-Path $guiExe)) -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 250
}
if ((Test-Path $exe) -or (Test-Path $guiExe)) {
    throw "executable still exists after uninstall"
}
if (Test-Path $desktopShortcut) {
    throw "Desktop shortcut still exists after uninstall"
}

Write-Host "NSIS install/smoke/uninstall PASS"
