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

echo Ensuring dependencies - sentence-transformers, pydantic-settings, etc...
"%PIP%" install -q -r requirements.txt
if errorlevel 1 (
  echo ERROR: pip install failed. Try: .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
if exist "..\backend\requirements-notes.txt" (
  "%PIP%" install -q -r "..\backend\requirements-notes.txt"
  if errorlevel 1 (
    echo ERROR: pip install failed for backend notes dependencies.
    exit /b 1
  )
)
if exist "..\backend\requirements-corpus.txt" (
  echo Ensuring corpus / RAG dependencies - PyMuPDF, BM25, etc...
  "%PIP%" install -q -r "..\backend\requirements-corpus.txt"
  if errorlevel 1 (
    echo ERROR: pip install failed for corpus dependencies.
    exit /b 1
  )
)

echo Verifying pipeline imports...
"%PY%" verify_pipeline_imports.py
if errorlevel 1 exit /b 1

mkdir "data\transcripts" 2>nul
mkdir "data\notes" 2>nul

rem sys.path is set in run_gui.py (repo root)
rem UTF-8 console — progress/log unicode must not crash on cp1252
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set TOKENIZERS_PARALLELISM=false
set OMP_NUM_THREADS=1
set MKL_NUM_THREADS=1
set TRANSCRIPT_STUDIO_GUI=1
chcp 65001 >nul

"%PY%" -u run_gui.py
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo ERROR: Transcript Notes Studio exited with code %EXIT_CODE%.
  echo Log: ..\data\logs\transcript_studio.log
  echo.
  pause
)
endlocal & exit /b %EXIT_CODE%
