@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating venv...
  python -m venv .venv
)
call .venv\Scripts\pip install -q -r requirements-captions.txt
if errorlevel 1 (
  echo ERROR: Failed to install Live Captions dependencies.
  exit /b 1
)
echo Live Captions dependencies installed.
echo In the GUI: open the "Live Captions" tab and press Start (Win+Ctrl+L first).
