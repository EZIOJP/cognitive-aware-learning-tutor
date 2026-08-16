@echo off
REM Removing Startup/tasks is part of uninstall — require PIN.
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

if /i not "%CALT_TRACKER_SKIP_STOP_PIN%"=="1" (
  call "%~dp0_require_exit_pin.bat" "remove tracker startup / scheduled tasks"
  if errorlevel 1 (
    echo Aborted.
    endlocal & exit /b 1
  )
)

set "TASK_NAME=CALT Desktop Tracker"
set "KEEPALIVE_NAME=CALT Tracker Keepalive"
set "LINK=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CALT Desktop Tracker.lnk"

echo Removing scheduled task: %TASK_NAME%
schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1
if errorlevel 1 (
  echo   Task not found or could not be deleted.
) else (
  echo   Task removed.
)

echo Removing keep-alive task: %KEEPALIVE_NAME%
schtasks /Delete /TN "%KEEPALIVE_NAME%" /F >nul 2>&1
if errorlevel 1 (
  echo   Keep-alive task not found or could not be deleted.
) else (
  echo   Keep-alive task removed.
)

if exist "%LINK%" (
  del /f /q "%LINK%"
  echo   Startup shortcut removed.
) else (
  echo   No startup shortcut found.
)

echo Done.
endlocal
