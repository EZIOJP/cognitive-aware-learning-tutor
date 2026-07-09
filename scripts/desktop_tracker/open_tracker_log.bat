@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1
cd /d "%ROOT%"
start "" notepad "%ROOT%\data\logs\desktop_tracker.log"
endlocal
