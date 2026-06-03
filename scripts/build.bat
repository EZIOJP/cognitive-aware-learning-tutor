@echo off
setlocal
call "%~dp0_common.bat" env-only
echo Building frontend to dist\ ...
call npm.cmd run build
endlocal
