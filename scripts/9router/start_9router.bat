@echo off
setlocal
title 9Router - AI Provider Gateway

set "PORT=20128"
set "NEXT_PUBLIC_BASE_URL=http://localhost:20128"

where 9router >nul 2>&1
if errorlevel 1 (
  echo [9Router] Not installed globally. Running install first...
  call "%~dp0install_9router.bat"
  if errorlevel 1 exit /b 1
)

echo.
echo [9Router] Starting on http://localhost:%PORT%
echo   Dashboard: http://localhost:%PORT%/dashboard
echo   API:       http://localhost:%PORT%/v1
echo.
echo Connect providers in the dashboard, then point Cursor / CALT at the API URL.
echo Press Ctrl+C to stop.
echo.

9router -p %PORT% -n

endlocal
