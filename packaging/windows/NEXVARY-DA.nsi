Unicode True
RequestExecutionLevel user

!define APPNAME "NEXVARY Developer Agent"
!define COMPANY "NEXVARY"
!define EXE "NEXVARY-DA.exe"

Name "${APPNAME}"
OutFile "..\..\release-native\NEXVARY-DA-Setup.exe"
InstallDir "$LOCALAPPDATA\NEXVARY\Developer Agent"
InstallDirRegKey HKCU "Software\NEXVARY\DeveloperAgent" "InstallDir"

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
  SetOutPath "$INSTDIR"
  File "..\..\dist-native\NEXVARY-DA.exe"
  File "..\..\README.md"
  File "..\..\LICENSE"
  File "..\..\THIRD_PARTY_NOTICES.md"
  WriteRegStr HKCU "Software\NEXVARY\DeveloperAgent" "InstallDir" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\NEXVARY"
  CreateShortCut "$SMPROGRAMS\NEXVARY\NEXVARY Developer Agent.lnk" "$INSTDIR\${EXE}"
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\NEXVARY\NEXVARY Developer Agent.lnk"
  RMDir "$SMPROGRAMS\NEXVARY"
  Delete "$INSTDIR\${EXE}"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\NEXVARY\DeveloperAgent"
SectionEnd
