@echo off
rem Register native C++ calt_enforcer as Windows Service (needs Admin).
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
  rem Running from repo scripts\desktop_tracker\installer\installer_payload\
  set "REPO=%~dp0..\..\..\.."
  for %%I in ("%REPO%") do set "REPO=%%~fI"
)

set "PS1=%REPO%\scripts\desktop_tracker\install\install_native_enforcer.ps1"
if not exist "%PS1%" set "PS1=%REPO%\scripts\desktop_tracker\install_native_enforcer.ps1"
if not exist "%PS1%" (
  echo ERROR: missing %PS1%
  pause
  exit /b 1
)

echo This installs the native Windows Service (Admin UAC).
echo Prefer daily no-admin: Register Enforcer.bat / install\install_enforcer_service.ps1
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%PS1%\"' -Wait"
echo.
echo If UAC was approved: check services.msc for CALTEnforcer.
pause
endlocal
