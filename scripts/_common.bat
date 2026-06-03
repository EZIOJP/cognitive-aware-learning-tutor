@echo off
rem Shared bootstrap — sets ROOT, PY, PIP and installs deps once.
rem Usage:  call "%~dp0_common.bat"          (ensure deps)
rem         call "%~dp0_common.bat" env-only (paths only, no install)
rem         call "%~dp0_common.bat" refresh  (force reinstall)

set "SCRIPTS=%~dp0"
for %%I in ("%SCRIPTS%..") do set "ROOT=%%~fI"
cd /d "%ROOT%"

if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PY=%ROOT%\.venv\Scripts\python.exe"
  set "PIP=%ROOT%\.venv\Scripts\pip.exe"
) else (
  set "PY=python"
  set "PIP=pip"
)

if /i "%~1"=="env-only" exit /b 0

if /i "%~1"=="refresh" goto :RefreshDeps
goto :EnsureDeps

:RefreshDeps
echo [setup] Refreshing all dependencies...
if exist "%ROOT%\.venv\.deps-installed" del /f /q "%ROOT%\.venv\.deps-installed"
goto :EnsureDeps

:EnsureDeps
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [setup] Creating Python venv at .venv ...
  python -m venv "%ROOT%\.venv"
  if errorlevel 1 (
    echo ERROR: Could not create venv. Install Python 3.10+ and try again.
    exit /b 1
  )
  set "PY=%ROOT%\.venv\Scripts\python.exe"
  set "PIP=%ROOT%\.venv\Scripts\pip.exe"
)

if not exist "%ROOT%\.venv\.deps-installed" (
  echo [setup] pip install -r backend\requirements.txt ^(first run only^)
  "%PIP%" install -r "%ROOT%\backend\requirements.txt"
  if errorlevel 1 (
    echo ERROR: pip install failed.
    exit /b 1
  )
  echo ok>"%ROOT%\.venv\.deps-installed"
)

echo [setup] alembic upgrade head
"%PY%" -m alembic upgrade head
if errorlevel 1 (
  echo ERROR: Database migration failed. See docs\MIGRATIONS.md
  exit /b 1
)

if not exist "%ROOT%\node_modules\" (
  echo [setup] npm install ^(first run only^)
  call npm.cmd install --no-fund --no-audit
  if errorlevel 1 (
    echo ERROR: npm install failed.
    exit /b 1
  )
)

exit /b 0
