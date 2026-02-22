; iGnition Installer — Inno Setup 6
; Build: pyinstaller iGnition.spec  →  dist\iGnition.exe
;        iscc installer\iGnition.iss  →  installer\Output\iGnition-Setup-0.1.0.exe

#define AppName      "iGnition"
#define AppVersion   "0.3.0"
#define AppPublisher "aech"
#define AppURL       "https://github.com/aechXIII/iGnition"
#define AppExeName   "iGnition.exe"
; Installation directory — AppData\Local\iGnition (no UAC needed)
#define AppInstDir   "{localappdata}\iGnition"

[Setup]
AppId={{B4A7C2E1-9F38-4D62-A1C5-7E8F0D2B3A96}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={#AppInstDir}
DisableDirPage=yes
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=iGnition-Setup-{#AppVersion}
SetupIconFile=..\src\ignition\gui\assets\ignition_logo.ico
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
; Do not remove the user config folder on uninstall
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";  Description: "Create a desktop shortcut";   GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "autostart";    Description: "Launch automatically with Windows (minimized to tray)"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\src\ignition\gui\assets\ignition_logo.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\ignition_logo.ico"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\ignition_logo.ico"; Tasks: desktopicon

[Registry]
; Autostart — launch with --background flag (minimized to tray)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"" --background"; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent; Parameters: ""

[UninstallRun]
; Kill running instance before uninstall
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
; Remove app files only — user data in AppData\Local\iGnition is preserved
Type: files; Name: "{app}\{#AppExeName}"
Type: files; Name: "{app}\ignition_logo.ico"
