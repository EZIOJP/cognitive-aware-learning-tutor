@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

cd /d "%ROOT%"
call "%~dp0_log_tracker_launch.bat" headless "launch requested"

for %%F in ("%PY%") do set "PYW=%%~dpFpythonw.exe"
if not exist "%PYW%" set "PYW=pythonw"
if not exist "%PYW%" (
  where pythonw >nul 2>&1
  if errorlevel 1 (
    call "%~dp0_log_tracker_launch.bat" headless "ERROR pythonw not found"
    echo ERROR: pythonw not found. Create the venv first: scripts\run_all.bat
    exit /b 1
  )
)

echo Starting Desktop Activity Tracker (headless - no tray icon)...
set "TRACKER_NO_TRAY=1"
start "CALT Tracker headless" /B "%PYW%" -m backend.behavior.desktop_tracker
if errorlevel 1 (
  call "%~dp0_log_tracker_launch.bat" headless "ERROR start failed"
  echo ERROR: could not start tracker process.
  exit /b 1
)
call "%~dp0_log_tracker_launch.bat" headless "process started"
echo Tracker launched in background. Stop: scripts\desktop_tracker\stop_desktop_tracker.bat
echo Logs: data\logs\desktop_tracker.log
endlocal
