@echo off
REM Install Adaptive Focus via QR (non-interactive target select)
cd /d "%~dp0"

where zeus >nul 2>&1
if errorlevel 1 (
  echo Installing @zeppos/zeus-cli...
  call npm i @zeppos/zeus-cli -g
)

if not exist "icon.png" (
  echo ERROR: icon.png missing in %cd%
  echo Copy one from packages\calt-zepp\icon.png and re-run.
  pause
  exit /b 1
)

if not exist "assets\480x480-t-rex-3\icon.png" (
  mkdir "assets\480x480-t-rex-3" 2>nul
  copy /Y "icon.png" "assets\480x480-t-rex-3\icon.png" >nul
)

echo.
echo ========================================
echo  Adaptive Focus — QR install
echo ========================================
echo.
echo ON PHONE:
echo  1. Developer Mode on (tap Zepp logo 7x in About)
echo  2. Watch page -^> Developer Mode -^> + -^> Scan
echo  3. Scan the QR that appears BELOW (this app only)
echo.
echo Tip: CALT Sync is a SEPARATE QR — run packages\sideload-both-watch-apps.bat
echo      to install both one after another.
echo.
pause

call zeus login
if errorlevel 1 (
  echo Login failed.
  pause
  exit /b 1
)

echo.
echo Preview target: Amazfit T-Rex 3  (no menu — automatic)
echo Leave this window open while you scan.
echo.
call zeus preview -t "Amazfit T-Rex 3"
if errorlevel 1 (
  echo.
  echo preview -t "Amazfit T-Rex 3" failed — trying select menu...
  call zeus preview -s
)

pause
