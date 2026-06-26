@echo off
setlocal
rem Force reinstall Python + npm deps (after requirements.txt or package.json changes)
call "%~dp0_common.bat" refresh
if errorlevel 1 exit /b 1

echo.
echo [setup] Upgrading Python packages...
"%PIP%" install -r "%ROOT%\backend\requirements.txt"
"%PIP%" install -r "%ROOT%\backend\requirements-notes.txt"
if exist "%ROOT%\backend\requirements-corpus.txt" (
  "%PIP%" install -r "%ROOT%\backend\requirements-corpus.txt"
)

echo.
echo [setup] Refreshing npm packages...
call npm.cmd install --no-fund --no-audit

where pandoc >nul 2>&1
if errorlevel 1 (
  echo.
  echo [setup] NOTE: pandoc not found on PATH — EPUB textbook ingest will fail until installed.
  echo         Download: https://pandoc.org/installing.html
) else (
  echo [setup] pandoc found — EPUB corpus ingest OK
)

echo ok>"%ROOT%\.venv\.deps-installed"
echo.
echo Setup complete. Run run.bat from project root to start the app.
endlocal
