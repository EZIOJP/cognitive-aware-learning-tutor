@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

net session >nul 2>&1
if errorlevel 1 (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)

cd /d "%ROOT%"
"%PY%" -m backend.behavior.device_block_cli remove
pause
endlocal
