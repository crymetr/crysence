@echo off
REM Portable, no-admin install for the work PC (no Inno Setup needed).
REM Run this from inside the extracted CrySence folder (next to CrySence.exe),
REM or from the repo after building dist\CrySence.
setlocal
set "SRC=%~dp0..\dist\CrySence"
if not exist "%SRC%\CrySence.exe" set "SRC=%~dp0"
if not exist "%SRC%\CrySence.exe" (
  echo Could not find CrySence.exe. Run this next to it or after building.
  pause & exit /b 1
)

set "DEST=%LOCALAPPDATA%\Programs\CrySence"
echo Installing to "%DEST%" ...
robocopy "%SRC%" "%DEST%" /MIR /NFL /NDL /NJH /NJS >nul

REM Autostart at login (per-user, hidden into the tray).
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v CrySence ^
  /t REG_SZ /d "\"%DEST%\CrySence.exe\" --hidden" /f >nul

REM Start Menu shortcut.
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell); $lnk=Join-Path ([Environment]::GetFolderPath('Programs')) 'CrySence.lnk'; $sc=$s.CreateShortcut($lnk); $sc.TargetPath='%DEST%\CrySence.exe'; $sc.Save()"

echo.
echo Done. Launching CrySence...
start "" "%DEST%\CrySence.exe"
echo To uninstall: delete "%DEST%" and remove the CrySence value under
echo HKCU\Software\Microsoft\Windows\CurrentVersion\Run.
pause
