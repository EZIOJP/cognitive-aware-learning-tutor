@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

"%PY%" "%~dp0server_lifecycle.py" prepare-api
if errorlevel 10 goto :Start
if errorlevel 1 exit /b 1
echo API already healthy on :8000 — not starting a second instance.
pause
exit /b 0

:Start
echo API (local): http://localhost:8000/health
echo NOTE: No --reload — stable for phone sync / shared corpus.
call "%~dp0print_lan_urls.bat"
"%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 30 --ws-ping-timeout 120
endlocal
