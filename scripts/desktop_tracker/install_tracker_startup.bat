@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

set "LAUNCHER=%ROOT%\scripts\desktop_tracker\tracker_autostart.bat"
set "KEEPALIVE=%ROOT%\scripts\desktop_tracker\keepalive_tracker.bat"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LINK=%STARTUP%\CALT Desktop Tracker.lnk"

if not exist "%LAUNCHER%" (
  echo ERROR: Missing %LAUNCHER%
  exit /b 1
)

echo === CALT Desktop Tracker — auto-start + keep-alive ===
echo Project:   %ROOT%
echo.

set "INSTALLED=0"

echo [1/2] Scheduled tasks (logon + every 5 min keep-alive)...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_install_tracker_tasks.ps1" -Launcher "%LAUNCHER%" -Keepalive "%KEEPALIVE%"
if errorlevel 1 (
  echo       WARN — scheduled tasks failed; Startup shortcut still helps at login.
) else (
  echo       OK
  set "INSTALLED=1"
)

echo [2/2] Startup folder shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_create_tracker_startup_shortcut.ps1" -Launcher "%LAUNCHER%" -Root "%ROOT%" -Link "%LINK%"
if errorlevel 1 (
  echo       ERROR: Could not create Startup shortcut.
) else (
  echo       OK — %LINK%
  set "INSTALLED=1"
)

echo.
if "%INSTALLED%"=="1" (
  echo SUCCESS — if the tracker is killed, it comes back within about 5 minutes.
  echo   Start now: scripts\desktop_tracker\run_desktop_tracker.bat
  echo   Full persistence + HKCU Run: scripts\install_tracker_persistence.bat
) else (
  echo FAILED — run this .bat from Explorer.
)
endlocal
