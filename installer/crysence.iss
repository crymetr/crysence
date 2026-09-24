; Inno Setup script for CrySence - per-user install, no admin required.
; Build:  iscc installer\crysence.iss   (after PyInstaller has produced dist\CrySence)
; Output: dist\CrySence-Setup-<version>.exe

#define AppName "CrySence"
#define AppVersion "0.3.5"
#define AppExe "CrySence.exe"
#define AppPublisher "crymetr"

[Setup]
AppId={{5DA096C7-0D55-4077-B2E5-FFAAF55E246D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppSupportURL=https://github.com/crymetr/crysence
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
; Restart Manager hangs trying to close the tray app (hidden Tk/pystray
; windows never answer), so it's off; PrepareToInstall below waits for the
; app's singleton mutex to go away and force-kills it if it doesn't.
CloseApplications=no
RestartApplications=no

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
; After a silent in-app update, relaunch straight into the tray.
Filename: "{app}\{#AppExe}"; Parameters: "--hidden"; Flags: nowait; \
  Check: WizardSilent

[UninstallDelete]
; Leave user data (config, enrolled face, captures) unless the user removes it.
Type: dirifempty; Name: "{localappdata}\{#AppName}"

[Code]
const
  AppMutex = 'CrySence-singleton-5DA096C7-0D55-4077-B2E5-FFAAF55E246D';

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  I, ResultCode: Integer;
begin
  Result := '';
  // In-app update: the app exits right after launching us. Give it ~5 s.
  for I := 1 to 10 do
  begin
    if not CheckForMutexes(AppMutex) then
      Break;
    Sleep(500);
  end;
  // Still running (older builds could linger invisibly): force it.
  if CheckForMutexes(AppMutex) then
  begin
    Exec(ExpandConstant('{sys}\taskkill.exe'),
      '/F /IM {#AppExe} /FI "USERNAME eq ' + GetUserNameString + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
  end;
end;
