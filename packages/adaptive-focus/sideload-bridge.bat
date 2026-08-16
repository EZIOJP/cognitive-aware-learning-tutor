@echo off
REM Bridge install Adaptive Focus (phone Bridge ON — no Scan menu)
cd /d "%~dp0"

where zeus >nul 2>&1
if errorlevel 1 (
  echo Installing @zeppos/zeus-cli...
  call npm i @zeppos/zeus-cli -g
)

echo.
echo ========================================
echo  Adaptive Focus — Bridge install
echo ========================================
echo.
echo ON PHONE (leave Bridge connected):
echo  Developer Mode -^> + -^> Bridge  (not Scan)
echo  Same Zepp account as PC
echo.
echo This will try: connect + install automatically.
echo If the prompt stays open, type:  connect   then   install
echo.
pause

call zeus login
if errorlevel 1 (
  echo Login failed.
  pause
  exit /b 1
)

echo.
echo Building then bridging...
call zeus build -t "Amazfit T-Rex 3" 2>nul
echo.

REM Pipe connect/install into bridge (works on many Zeus versions)
(
  echo connect
  ping -n 4 127.0.0.1 >nul
  echo install
  ping -n 8 127.0.0.1 >nul
  echo exit
) | call zeus bridge

echo.
echo If install did not finish, run:  zeus bridge
echo then type:  connect   /   install
echo.
pause
