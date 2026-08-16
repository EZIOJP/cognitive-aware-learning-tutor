@echo off
rem Logon helper — no lingering cmd: start wscript and exit immediately.
start "" /b wscript.exe //B "%~dp0tracker_tray_launch.vbs"
exit /b 0
