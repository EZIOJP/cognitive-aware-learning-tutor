@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  echo Run run.bat once first to create .venv
  set "PY=python"
)

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set TOKENIZERS_PARALLELISM=false
chcp 65001 >nul

echo Classic Notes — LM Studio Gemma only ^(no RAG, no mermaid^)
echo Capture/Tune: use run.bat ^(main Studio^)
echo.

"%PY%" -u run_legacy_notes.py
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Failed with code %EXIT_CODE%.
  pause
)
endlocal & exit /b %EXIT_CODE%
