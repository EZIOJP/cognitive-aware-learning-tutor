@echo off
REM Fast launcher — starts/reuses API + Frontend without opening the control menu.
cd /d "%~dp0"
call "%~dp0scripts\_common.bat"
if errorlevel 1 exit /b 1
"%PY%" "%~dp0scripts\server_lifecycle.py" ensure-fast
