@echo off
setlocal
call "%~dp0_common.bat" env-only

set "EXT_DIR=%ROOT%\selftracker-extension"
set "PROFILE_DIR=%ROOT%\.browser-profiles\chrome-selftracker"
set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"

if not exist "%CHROME_EXE%" (
  echo Chrome not found at "%CHROME_EXE%"
  pause
  exit /b 1
)

if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"

echo Launching Chrome with SelfTracker extension...
start "" "%CHROME_EXE%" --user-data-dir="%PROFILE_DIR%" --load-extension="%EXT_DIR%" --no-first-run --disable-extensions-except="%EXT_DIR%" "chrome://extensions/"
endlocal
