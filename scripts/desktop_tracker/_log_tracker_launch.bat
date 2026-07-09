@echo off
rem Append one line to data\logs\tracker_launcher.log
rem Usage: call _log_tracker_launch.bat <mode> <message>
setlocal
if "%~2"=="" exit /b 0
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1
"%PY%" "%~dp0log_tracker_launch.py" %1 %~2
endlocal
