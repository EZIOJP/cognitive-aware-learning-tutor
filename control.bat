@echo off
REM Manual server control menu (status / restart / stop).
cd /d "%~dp0"
call "%~dp0scripts\_common.bat"
if errorlevel 1 exit /b 1
"%PY%" "%~dp0scripts\server_lifecycle.py" menu
