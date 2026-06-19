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

if not exist ".venv\.deps" (
  echo Installing dependencies...
  "%PIP%" install -r requirements.txt
  echo ok>".venv\.deps"
)

mkdir data\transcripts 2>nul
mkdir data\notes 2>nul

"%PY%" run_gui.py
endlocal
