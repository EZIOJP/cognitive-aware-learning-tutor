@echo off
REM CALT Voice — QR install for Amazfit T-Rex 3
cd /d "%~dp0"

where zeus >nul 2>&1
if errorlevel 1 (
  echo Installing @zeppos/zeus-cli...
  call npm i @zeppos/zeus-cli -g
)

echo.
echo ========================================
echo  CALT Voice — black-screen recorder
echo ========================================
echo.
echo  Open app or shortcut card → auto-records
echo  Black screen · tap to stop · max 5 min
echo  Needs 1GB free disk · vibe start/end
echo.
echo Phone: Developer Mode -^> + -^> Scan QR
echo.
pause

call zeus login
if errorlevel 1 (
  echo Login failed.
  pause
  exit /b 1
)

echo.
echo Preview target: Amazfit T-Rex 3
call zeus preview -t "Amazfit T-Rex 3"
if errorlevel 1 (
  echo -t failed, opening select...
  call zeus preview -s
)

pause
