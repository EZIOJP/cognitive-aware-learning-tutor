@echo off
REM Prompt for TRACKER_EXIT_PIN / exit phrase before stop/restart/uninstall.
REM Usage: call "%~dp0_require_exit_pin.bat" "reason text"
REM Exit code 0 = accepted, 1 = denied / cancelled.

setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

cd /d "%ROOT%"
set "REASON=%~1"
if "%REASON%"=="" set "REASON=stop / restart / uninstall tracker"

"%PY%" -m backend.behavior.tracker_exit --reason "%REASON%"
set "RC=%ERRORLEVEL%"
endlocal & exit /b %RC%
