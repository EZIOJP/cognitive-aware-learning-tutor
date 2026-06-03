@echo off
setlocal
rem Force reinstall Python + npm deps (after requirements.txt or package.json changes)
call "%~dp0_common.bat" refresh
if errorlevel 1 exit /b 1

echo.
echo [setup] Upgrading Python packages...
"%PIP%" install -r "%ROOT%\backend\requirements.txt"

echo.
echo [setup] Refreshing npm packages...
call npm.cmd install --no-fund --no-audit

echo ok>"%ROOT%\.venv\.deps-installed"
echo.
echo Setup complete. Run run.bat from project root to start the app.
endlocal
