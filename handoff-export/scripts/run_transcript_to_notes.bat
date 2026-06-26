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
echo === Transcript to Notes (legacy launcher) ===
echo   Primary workflow: transcript-notes-studio\run.bat
echo   This script runs: python -m transcript_studio.cli generate
echo.

"%PY%" -m pip install -q -r backend\requirements-notes.txt
if errorlevel 1 exit /b 1

if "%~1"=="" (
  echo Usage:
  echo   scripts\run_transcript_to_notes.bat --latest
  echo   scripts\run_transcript_to_notes.bat -i live_captions_YYYYMMDD_HHMMSS.txt
  echo.
  echo Or use Studio CLI directly:
  echo   cd transcript-notes-studio
  echo   python -m transcript_studio.cli generate --latest
  exit /b 1
)

cd transcript-notes-studio
if "%~1"=="--latest" (
  "%PY%" -m transcript_studio.cli generate --latest %2 %3 %4 %5 %6 %7 %8 %9
) else if "%~1"=="--input" (
  "%PY%" -m transcript_studio.cli generate --input %2 %3 %4 %5 %6 %7 %8 %9
) else if "%~1"=="-i" (
  "%PY%" -m transcript_studio.cli generate -i %2 %3 %4 %5 %6 %7 %8 %9
) else (
  "%PY%" -m transcript_studio.cli generate -i %*
)
set EXIT=%ERRORLEVEL%
cd ..
exit /b %EXIT%
