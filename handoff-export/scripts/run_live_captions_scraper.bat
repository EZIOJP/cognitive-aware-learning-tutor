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
echo === Live Captions (legacy launcher) ===
echo   Primary workflow: transcript-notes-studio\run.bat
echo   This script runs: python -m transcript_studio.cli capture
echo.

"%PY%" -m pip install -q -r backend\requirements-captions.txt
if errorlevel 1 exit /b 1

cd transcript-notes-studio
"%PY%" -m transcript_studio.cli capture %*
set EXIT=%ERRORLEVEL%
cd ..
exit /b %EXIT%
