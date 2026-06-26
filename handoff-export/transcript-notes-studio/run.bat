@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
  set "PIP=.venv\Scripts\pip.exe"
) else (
  set "PY=python"
  set "PIP=pip"
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating venv...
  python -m venv .venv
  set "PY=.venv\Scripts\python.exe"
  set "PIP=.venv\Scripts\pip.exe"
)

echo Ensuring dependencies (sentence-transformers, pydantic-settings, etc.)...
"%PIP%" install -q -r requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed. Try: .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
if exist "..\backend\requirements-notes.txt" (
  "%PIP%" install -q -r "..\backend\requirements-notes.txt"
)
if errorlevel 1 (
  echo ERROR: pip install failed for backend notes dependencies.
  exit /b 1
)

echo Verifying pipeline imports...
"%PY%" verify_pipeline_imports.py
if errorlevel 1 exit /b 1

mkdir "data\transcripts" 2>nul
mkdir "data\notes" 2>nul

rem sys.path is set in run_gui.py (repo root)

"%PY%" run_gui.py
endlocal
