@echo off
setlocal
call "%~dp0_common.bat" env-only

set "EXT_DIR=%ROOT%\selftracker-extension"
set "PROFILE_DIR=%ROOT%\.browser-profiles\edge-selftracker"
set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

if not exist "%EDGE_EXE%" set "EDGE_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" (
  echo Edge not found.
  pause
  exit /b 1
)

if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"

echo Launching Edge with SelfTracker extension...
start "" "%EDGE_EXE%" --user-data-dir="%PROFILE_DIR%" --load-extension="%EXT_DIR%" --no-first-run --disable-extensions-except="%EXT_DIR%" "chrome://extensions/"
endlocal
