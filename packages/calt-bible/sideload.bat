@echo off
REM CALT Bible — QR install for Amazfit T-Rex 3
cd /d "%~dp0"

where zeus >nul 2>&1
if errorlevel 1 (
  echo Installing @zeppos/zeus-cli...
  call npm i @zeppos/zeus-cli -g
)

if not exist "assets\480x480-t-rex-3\bible\index.json" (
  echo Packing WEB Bible assets...
  python "%~dp0..\..\scripts\pack_watch_bible.py"
  if errorlevel 1 (
    echo Pack failed.
    pause
    exit /b 1
  )
)

if not exist "icon.png" if exist "%~dp0..\calt-zepp\icon.png" copy /Y "%~dp0..\calt-zepp\icon.png" "icon.png" >nul
if not exist "assets\480x480-t-rex-3\icon.png" (
  mkdir "assets\480x480-t-rex-3" 2>nul
  if exist "icon.png" copy /Y "icon.png" "assets\480x480-t-rex-3\icon.png" >nul
)

echo.
echo ========================================
echo  CALT Bible — offline WEB reader
echo ========================================
echo.
echo Phone: Developer Mode -^> + -^> Scan this QR
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
