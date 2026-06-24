@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Installing lecture-notes dependencies (sentence-transformers + PyTorch CPU)...
"%PIP%" install -r "%ROOT%\backend\requirements-notes.txt"
if errorlevel 1 exit /b 1

echo.
echo Verifying sentence-transformers...
"%PY%" -c "from sentence_transformers import SentenceTransformer; print('OK: sentence-transformers ready')"
if errorlevel 1 (
  echo ERROR: Verification failed.
  exit /b 1
)
echo Done. Run scripts\run_transcript_to_notes.bat or transcript-notes-studio\run.bat
endlocal
