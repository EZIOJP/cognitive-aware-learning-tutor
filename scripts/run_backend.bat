@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

rem Exit codes from prepare-api:
rem   0 = already healthy (do not start another)
rem   10 = port free / cleared — start uvicorn
rem   1 = failure
"%PY%" "%~dp0server_lifecycle.py" prepare-api
if errorlevel 10 goto :Start
if errorlevel 1 exit /b 1
echo API already healthy on :8000 — not starting a second instance.
echo Stop first: scripts\stop_servers.bat
pause
exit /b 0

:Start
echo API (local): http://localhost:8000/health
call "%~dp0print_lan_urls.bat"
rem Prefer no-reload for stability (reload often leaves hung workers on Windows).
"%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 30 --ws-ping-timeout 120
endlocal
