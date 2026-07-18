@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo.
echo Starting Cognitive-Aware Learning Tutor...
echo   API:       http://localhost:8000/health
echo   Frontend:  http://localhost:5173
echo   Login:     admin / admin123
echo   Solo sync: phone+web share one calendar (no login required)
call "%~dp0print_lan_urls.bat"

echo.
echo [smart] Checking existing servers (reuse healthy, replace hung)...
"%PY%" "%~dp0server_lifecycle.py" ensure
if errorlevel 1 (
  echo ERROR: server ensure failed.
  exit /b 1
)

echo.
echo Done. Re-run run.bat anytime — it will not double-bind ports.
echo Control panel: control.bat  ^(status / restart API or Frontend / stop^)
echo Stop both: scripts\stop_servers.bat
echo Desktop tracker is standalone — install once: scripts\desktop_tracker\install_tracker_startup.bat
echo Or start everything including tracker: scripts\run_full.bat
endlocal
