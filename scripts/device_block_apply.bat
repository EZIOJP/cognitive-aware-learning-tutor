@echo off
setlocal EnableDelayedExpansion
rem Native Device lock apply — no Python. Pass confirm as %%1 (re-passed after UAC).
call "%~dp0_common.bat" env-only
if errorlevel 1 exit /b 1

set "CONFIRM=%~1"
if "%CONFIRM%"=="" (
  echo ERROR: confirm phrase required. Example:
  echo   %~nx0 "DEVICE LOCK"
  exit /b 2
)

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting admin...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '\"%CONFIRM%\"' -Verb RunAs"
  exit /b 0
)

cd /d "%ROOT%"

set "EXE="
if exist "%ROOT%\calt-focus\backend\calt_enforcer\build\Release\calt_enforcer.exe" set "EXE=%ROOT%\calt-focus\backend\calt_enforcer\build\Release\calt_enforcer.exe"
if exist "%ROOT%\calt-focus\backend\calt_enforcer\build\calt_enforcer.exe" set "EXE=%ROOT%\calt-focus\backend\calt_enforcer\build\calt_enforcer.exe"
if not defined EXE if exist "%ROOT%\scripts\desktop_tracker\installer\installer_payload\bin\calt_enforcer.exe" set "EXE=%ROOT%\scripts\desktop_tracker\installer\installer_payload\bin\calt_enforcer.exe"

if not defined EXE (
  echo ERROR: calt_enforcer.exe not found — build native enforcer first.
  pause
  exit /b 1
)

echo Applying Device lock via "%EXE%"
"%EXE%" --device-block-apply --confirm "%CONFIRM%"
set RC=%ERRORLEVEL%
if %RC% NEQ 0 (
  echo FAILED rc=%RC%
  pause
  exit /b %RC%
)

echo Done. Close/reopen browsers if a site still loads.
pause
endlocal
