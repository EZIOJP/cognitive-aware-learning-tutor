@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo.
echo Starting Cognitive-Aware Learning Tutor (API + Frontend + Tracker)...
echo   API:       http://localhost:8000/health
echo   Frontend:  http://localhost:5173
echo   Login:     admin / admin123
call "%~dp0print_lan_urls.bat"

echo.
echo [smart] Checking existing servers (reuse healthy, replace hung)...
"%PY%" "%~dp0server_lifecycle.py" ensure
if errorlevel 1 (
  echo ERROR: server ensure failed.
  exit /b 1
)

call "%~dp0desktop_tracker\run_desktop_tracker_headless.bat"

echo.
echo Full stack ready. Tracker logs: data\logs\desktop_tracker.log
echo Stop servers: scripts\stop_servers.bat
echo Stop tracker ^(PIN^): scripts\admin_only\stop_desktop_tracker.bat
endlocal
