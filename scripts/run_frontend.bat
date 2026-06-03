@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Frontend: http://localhost:5173
npm.cmd run dev
endlocal
