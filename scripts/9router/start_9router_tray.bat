@echo off
setlocal
title 9Router (tray)

where 9router >nul 2>&1
if errorlevel 1 (
  call "%~dp0install_9router.bat"
  if errorlevel 1 exit /b 1
)

echo [9Router] Starting in system tray on port 20128...
echo   Dashboard: http://localhost:20128/dashboard
9router -p 20128 -t

endlocal
