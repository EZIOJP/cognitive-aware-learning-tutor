@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo.
echo Starting Cognitive-Aware Learning Tutor...
echo   API:       http://localhost:8000/health
echo   Frontend:  http://localhost:5173
echo   Login:     admin / admin123
call "%~dp0print_lan_urls.bat"

start "API" cmd /k call "%~dp0run_backend.bat"
start "Frontend" cmd /k call "%~dp0run_frontend.bat"

echo API and Frontend opened in separate windows.
echo Desktop tracker is standalone — install once: scripts\desktop_tracker\install_tracker_startup.bat
echo Or start everything including tracker: scripts\run_full.bat
endlocal
