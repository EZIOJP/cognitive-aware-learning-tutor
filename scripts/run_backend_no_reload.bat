@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo API (local): http://localhost:8000/health
echo NOTE: No --reload — safe to run alongside Transcript Notes Studio (shared Qdrant corpus).
call "%~dp0print_lan_urls.bat"
"%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --ws-ping-interval 30 --ws-ping-timeout 120
endlocal
