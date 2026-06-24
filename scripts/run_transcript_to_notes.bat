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

echo === Transcript to Notes (Step 2 of lecture pipeline) ===

echo   Step 1: scripts\run_live_captions_scraper.bat  ^(during lecture^)

echo   Step 2: this script — default is FAST ^(few LLM calls, not 99 chunks^)

echo   Step 3: open app - Lecture Notes - generate quiz - Review Hub

echo.



"%PY%" -m pip install -q -r backend\requirements-notes.txt

if errorlevel 1 (

  echo ERROR: Failed to install lecture-notes dependencies.

  echo Try: scripts\install_notes.bat

  exit /b 1

)



if "%~1"=="" (

  echo Usage:

  echo   scripts\run_transcript_to_notes.bat --latest

  echo   scripts\run_transcript_to_notes.bat --input live_captions_YYYYMMDD_HHMMSS.txt

  echo.

  echo Options:

  echo   --folder "lecture one"     Save under data\notes\

  echo   --full --refine            Slower, higher quality ^(max 12 LLM chunks^)

  echo   --reference path\to\ref.md

  echo.

  echo Requires: OLLAMA_ENABLED=1 and LM Studio/Ollama running.

  exit /b 1

)



"%PY%" -m backend.scripts.transcript_to_notes %*

set EXIT=%ERRORLEVEL%

if %EXIT% neq 0 (

  echo.

  echo Troubleshooting:

  echo   1. Set OLLAMA_ENABLED=1 in .env

  echo   2. Start LM Studio/Ollama and load your model

  echo   3. Use default ^(no --full^) for a quick run — avoids 50+ chunk loops

  echo   4. scripts\install_notes.bat only needed for --full semantic mode

)

exit /b %EXIT%

