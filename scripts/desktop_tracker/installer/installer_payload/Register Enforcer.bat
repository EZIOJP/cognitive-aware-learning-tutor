@echo off
rem Optional: register CALT Enforcer scheduled task via repo script (v2b/v2d).
setlocal EnableExtensions
set "APPDIR=%~dp0"
set "REPO="

if defined CALT_REPO set "REPO=%CALT_REPO%"
if not defined REPO if exist "%APPDIR%repo_root.txt" (
  set /p REPO=<"%APPDIR%repo_root.txt"
)
if defined REPO set "REPO=%REPO:"=%"
if defined REPO for %%I in ("%REPO%") do set "REPO=%%~fI"

if not defined REPO (
  echo ERROR: set repo_root.txt or CALT_REPO first.
  pause
  exit /b 1
)

set "PS1=%REPO%\scripts\desktop_tracker\install\install_enforcer_service.ps1"
if not exist "%PS1%" set "PS1=%REPO%\scripts\desktop_tracker\install_enforcer_service.ps1"
if not exist "%PS1%" (
  echo ERROR: missing install\install_enforcer_service.ps1
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Start
echo.
echo Done. Unregister later:
echo   Unregister-ScheduledTask -TaskName "CALT Enforcer" -Confirm:$false
pause
endlocal
