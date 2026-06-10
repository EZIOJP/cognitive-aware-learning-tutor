@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo API (local): http://localhost:8000/health
call "%~dp0print_lan_urls.bat"
"%PY%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
endlocal
