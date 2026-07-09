@echo off
rem Auto-launched at Windows logon — system tray (no Quit). Do not set TRACKER_NO_TRAY.
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

set "TRACKER_NO_TRAY="
cd /d "%ROOT%"
wscript.exe "%~dp0tracker_tray_launch.vbs"
endlocal
