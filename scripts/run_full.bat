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

start "API" cmd /k call "%~dp0run_backend.bat"
start "Frontend" cmd /k call "%~dp0run_frontend.bat"

echo Waiting for API to start...
timeout /t 5 /nobreak >nul

call "%~dp0desktop_tracker\run_desktop_tracker_headless.bat"

echo.
echo Full stack started. Tracker logs: data\logs\desktop_tracker.log
echo Stop tracker: scripts\desktop_tracker\stop_desktop_tracker.bat
endlocal
