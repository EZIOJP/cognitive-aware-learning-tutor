@echo off

setlocal

call "%~dp0..\_common.bat" env-only

if errorlevel 1 exit /b 1



set "TASK_NAME=CALT Desktop Tracker"

set "LAUNCHER=%ROOT%\scripts\desktop_tracker\tracker_autostart.bat"

set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

set "LINK=%STARTUP%\CALT Desktop Tracker.lnk"



if not exist "%LAUNCHER%" (

  echo ERROR: Missing %LAUNCHER%

  exit /b 1

)



echo === CALT Desktop Tracker — auto-start at Windows login ===

echo Project:  %ROOT%

echo Launcher: %LAUNCHER%

echo Mode:     system tray (pythonw, plan popup, no Quit)

echo.



set "INSTALLED=0"



echo [1/2] Windows Scheduled Task (ONLOGON)...

schtasks /Create /TN "%TASK_NAME%" /TR "\"%LAUNCHER%\"" /SC ONLOGON /RL LIMITED /F >nul 2>&1

if errorlevel 1 (

  echo       Skipped — access denied or policy blocked. Trying Startup folder...

) else (

  echo       OK — task "%TASK_NAME%" created.

  set "INSTALLED=1"

)



echo [2/2] Startup folder shortcut...

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_create_tracker_startup_shortcut.ps1" -Launcher "%LAUNCHER%" -Root "%ROOT%" -Link "%LINK%"

if errorlevel 1 (

  echo       ERROR: Could not create Startup shortcut.

) else (

  echo       OK — shortcut: %LINK%

  set "INSTALLED=1"

)



echo.

if "%INSTALLED%"=="1" (

  echo SUCCESS — tracker will start when you sign in to Windows.

  echo   Start now:   scripts\desktop_tracker\run_desktop_tracker.bat

  echo   Stop:        scripts\desktop_tracker\stop_desktop_tracker.bat

  echo   Uninstall:   scripts\desktop_tracker\uninstall_tracker_startup.bat

) else (

  echo FAILED — double-click install_tracker_startup.bat from Explorer.

)

endlocal
