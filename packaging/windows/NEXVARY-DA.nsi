Unicode True
RequestExecutionLevel user

!include "MUI2.nsh"

!define APPNAME "NEXVARY Developer Agent"
!define COMPANY "NEXVARY"
!define EXE "NEXVARY-DA.exe"
!define GUIEXE "NEXVARY-DA-GUI.exe"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\NEXVARY Developer Agent"

Name "${APPNAME}"
OutFile "..\..\release-native\NEXVARY-DA-Setup.exe"
InstallDir "$LOCALAPPDATA\NEXVARY\Developer Agent"
InstallDirRegKey HKCU "Software\NEXVARY\DeveloperAgent" "InstallDir"

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "NEXVARY Developer Agent"
!define MUI_WELCOMEPAGE_TEXT "سيتم تثبيت NEXVARY Developer Agent على هذا الجهاز.$\r$\n$\r$\nسيتم إنشاء اختصار في قائمة Start وأيقونة على سطح المكتب."
!define MUI_FINISHPAGE_RUN "$INSTDIR\${GUIEXE}"
!define MUI_FINISHPAGE_RUN_TEXT "تشغيل NEXVARY Developer Agent الآن"
!define MUI_FINISHPAGE_NOAUTOCLOSE

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  SetOutPath "$INSTDIR"
  File "..\..\dist-native\NEXVARY-DA.exe"
  File "..\..\dist-native\NEXVARY-DA-GUI.exe"
  File "..\..\README.md"
  File "..\..\LICENSE"
  File "..\..\THIRD_PARTY_NOTICES.md"

  WriteRegStr HKCU "Software\NEXVARY\DeveloperAgent" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "${APPNAME}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "${COMPANY}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${GUIEXE}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1

  WriteUninstaller "$INSTDIR\Uninstall.exe"

  CreateDirectory "$SMPROGRAMS\NEXVARY"
  CreateShortCut "$SMPROGRAMS\NEXVARY\NEXVARY Developer Agent.lnk" "$INSTDIR\${GUIEXE}"
  CreateShortCut "$DESKTOP\NEXVARY Developer Agent.lnk" "$INSTDIR\${GUIEXE}"
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\NEXVARY Developer Agent.lnk"
  Delete "$SMPROGRAMS\NEXVARY\NEXVARY Developer Agent.lnk"
  RMDir "$SMPROGRAMS\NEXVARY"
  Delete "$INSTDIR\${EXE}"
  Delete "$INSTDIR\${GUIEXE}"
  Delete "$INSTDIR\README.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\THIRD_PARTY_NOTICES.md"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  DeleteRegKey HKCU "Software\NEXVARY\DeveloperAgent"
SectionEnd
