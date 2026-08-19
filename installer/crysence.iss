; Inno Setup script for CrySence - per-user install, no admin required.
; Build:  iscc installer\crysence.iss   (after PyInstaller has produced dist\CrySence)
; Output: dist\CrySence-Setup-<version>.exe

#define AppName "CrySence"
#define AppVersion "0.1.0"
#define AppExe "CrySence.exe"
#define AppPublisher "saitaskar"

[Setup]
AppId={{5DA096C7-0D55-4077-B2E5-FFAAF55E246D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL=https://github.com/saitaskar/crysence
DefaultDirName={localappdata}\Programs\{#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=CrySence-Setup-{#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\CrySence\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start CrySence automatically when I sign in"; GroupDescription: "Startup:"

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Per-user autostart, launched hidden into the tray. Removed on uninstall.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
  ValueType: string; ValueName: "{#AppName}"; \
  ValueData: """{app}\{#AppExe}"" --hidden"; \
  Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName} now"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Leave user data (config, enrolled face, captures) unless the user removes it.
Type: dirifempty; Name: "{localappdata}\{#AppName}"
