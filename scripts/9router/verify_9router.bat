@echo off
setlocal
set "PORT=20128"
set "BASE=http://127.0.0.1:%PORT%"

echo.
echo [9Router] Checking local gateway...
echo   Expected: %BASE%/v1
echo.

where curl >nul 2>&1
if errorlevel 1 (
  echo ERROR: curl not found. Open %BASE%/dashboard in browser manually.
  exit /b 1
)

curl -s -o NUL -w "dashboard HTTP %{http_code}\n" "%BASE%/dashboard"
curl -s -o NUL -w "api       HTTP %{http_code}\n" "%BASE%/v1/models"
if errorlevel 1 (
  echo.
  echo WARN: Could not reach 9Router API.
  echo        Start first: scripts\9router\start_9router.bat
  exit /b 2
)

echo.
echo OK: 9Router looks reachable on port %PORT%.
echo Next: scripts\9router\setup_cursor_9router.bat
endlocal
exit /b 0
