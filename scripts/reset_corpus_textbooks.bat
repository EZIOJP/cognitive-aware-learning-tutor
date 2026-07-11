@echo off
setlocal
cd /d "%~dp0.."

echo ============================================================
echo Ensure notes RAG (textbooks only)
echo Skips rebuild if healthy. Pass --force to wipe.
echo ============================================================
echo.

if /I "%~1"=="--force" (
  python -m backend.corpus.cli rebuild-textbooks --force
) else if /I "%~1"=="force" (
  python -m backend.corpus.cli rebuild-textbooks --force
) else (
  python -m backend.corpus.cli rebuild-textbooks
)
if errorlevel 1 (
  echo.
  echo FAILED — if Qdrant locked, close Studio / end python for this project, then retry.
  exit /b 1
)

echo.
echo Status:
python -m backend.corpus.cli rebuild-textbooks --status-only
endlocal
exit /b 0
