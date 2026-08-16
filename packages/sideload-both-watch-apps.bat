@echo off
REM Install BOTH watch apps: CALT Sync + Adaptive Focus
REM Uses zeus preview -t so you are NOT stuck on a device-select menu.
setlocal
cd /d "%~dp0"

where zeus >nul 2>&1
if errorlevel 1 (
  echo Installing @zeppos/zeus-cli...
  call npm i @zeppos/zeus-cli -g
)

echo.
echo ============================================================
echo  Install BOTH Amazfit apps (two QR scans)
echo ============================================================
echo.
echo  App 1: CALT Sync          (calendar / health)   appId 1088801
echo  App 2: Adaptive Focus     (Pomodoro timer)      appId 1088802
echo.
echo  They are DIFFERENT apps — each needs its own Scan.
echo.
echo ON PHONE before continuing:
echo  1. Same Wi-Fi as PC, same Zepp account as zeus login
echo  2. Developer Mode unlocked (About -^> tap logo 7x)
echo  3. Watch page -^> Developer Mode -^> keep that screen ready
echo.
pause

call zeus login
if errorlevel 1 (
  echo Login failed.
  pause
  exit /b 1
)

echo.
echo ========== [1/2] CALT Sync ==========
echo Open phone: Developer Mode -^> + -^> Scan
echo Scan the QR that appears. Wait until install finishes on watch.
echo Then come back here and press a key for app 2.
echo.
cd /d "%~dp0calt-zepp"
call zeus preview -t "Amazfit T-Rex 3"
echo.
echo --- CALT Sync preview ended ---
echo If it installed OK, press any key for Adaptive Focus.
echo If Scan failed, press Ctrl+C and run: packages\calt-zepp\sideload-bridge.bat
echo.
pause

echo.
echo ========== [2/2] Adaptive Focus ==========
echo AGAIN: Developer Mode -^> + -^> Scan  (new QR)
echo This installs the Pomodoro app next to CALT Sync.
echo.
cd /d "%~dp0adaptive-focus"
if not exist "icon.png" copy /Y "%~dp0calt-zepp\icon.png" "icon.png" >nul
if not exist "assets\480x480-t-rex-3\icon.png" (
  mkdir "assets\480x480-t-rex-3" 2>nul
  copy /Y "icon.png" "assets\480x480-t-rex-3\icon.png" >nul
)
call zeus preview -t "Amazfit T-Rex 3"
if errorlevel 1 (
  echo preview -t failed, opening select menu...
  call zeus preview -s
)

echo.
echo ========== Done ==========
echo On watch you should see:
echo   - CALT Sync
echo   - Adaptive Focus
echo.
echo Prefer no QR? Keep Bridge ON on phone, then run:
echo   packages\sideload-both-bridge.bat
echo.
pause
