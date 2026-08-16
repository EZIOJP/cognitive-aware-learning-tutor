@echo off
REM Install BOTH apps via Bridge (recommended if Scan has no options / stuck)
setlocal
cd /d "%~dp0"

where zeus >nul 2>&1
if errorlevel 1 (
  echo Installing @zeppos/zeus-cli...
  call npm i @zeppos/zeus-cli -g
)

echo.
echo ============================================================
echo  Bridge install BOTH apps (automatic connect + install)
echo ============================================================
echo.
echo ON PHONE — do this ONCE and leave it open:
echo  1. Developer Mode -^> + -^> Bridge
echo  2. Wait until Bridge shows connected / waiting
echo  3. Same Zepp account as PC
echo.
echo Then this script installs:
echo   1) CALT Sync
echo   2) Adaptive Focus
echo.
pause

call zeus login
if errorlevel 1 (
  echo Login failed.
  pause
  exit /b 1
)

echo.
echo ========== [1/2] Bridge install CALT Sync ==========
cd /d "%~dp0calt-zepp"
call zeus build -t "Amazfit T-Rex 3" 2>nul
(
  echo connect
  ping -n 5 127.0.0.1 >nul
  echo install
  ping -n 12 127.0.0.1 >nul
  echo exit
) | call zeus bridge

echo.
echo If CALT Sync appeared on the watch, press a key for Adaptive Focus.
echo If not, in a new terminal: cd packages\calt-zepp ^& zeus bridge
echo   then type: connect   /   install
echo.
pause

echo.
echo ========== [2/2] Bridge install Adaptive Focus ==========
cd /d "%~dp0adaptive-focus"
if not exist "icon.png" copy /Y "%~dp0calt-zepp\icon.png" "icon.png" >nul
if not exist "assets\480x480-t-rex-3\icon.png" (
  mkdir "assets\480x480-t-rex-3" 2>nul
  copy /Y "icon.png" "assets\480x480-t-rex-3\icon.png" >nul
)
call zeus build -t "Amazfit T-Rex 3" 2>nul
(
  echo connect
  ping -n 5 127.0.0.1 >nul
  echo install
  ping -n 12 127.0.0.1 >nul
  echo exit
) | call zeus bridge

echo.
echo Done. Watch app list should include CALT Sync + Adaptive Focus.
echo If #2 failed, run: packages\adaptive-focus\sideload-bridge.bat
echo.
pause
