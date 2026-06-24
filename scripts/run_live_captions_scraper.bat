@echo off

setlocal

cd /d "%~dp0.."

if exist ".venv\Scripts\python.exe" (

  call scripts\_common.bat env-only

) else (

  call scripts\_common.bat

)

if errorlevel 1 exit /b 1



echo.

echo === Live Captions Scraper (Step 1 of lecture pipeline) ===

echo   1. Play your lecture in Chrome/player

echo   2. Press Win+Ctrl+L to turn on Windows Live Captions

echo   3. This script listens until YOU press Ctrl+C — that is normal, not a loop

echo   4. Then run: scripts\run_transcript_to_notes.bat --latest

echo.



"%PY%" -m pip install -q -r backend\requirements-captions.txt

if errorlevel 1 (

  echo ERROR: Failed to install caption scraper dependencies.

  exit /b 1

)



if "%~1"=="" (

  echo Starting scraper ^(Ctrl+C to stop and save^)...

  echo Optional: --duration 3600  ^(auto-stop after 1 hour^)

  echo.

)



"%PY%" -m backend.scripts.live_captions_scraper %*

set EXIT=%ERRORLEVEL%

if %EXIT% neq 0 (

  echo.

  echo Troubleshooting:

  echo   - Windows 11 only; enable Live Captions with Win+Ctrl+L

  echo   - pip install -r backend\requirements-captions.txt

)

exit /b %EXIT%

