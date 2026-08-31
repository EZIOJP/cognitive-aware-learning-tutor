@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

cd /d "%ROOT%"

echo === CALT Desktop (PySide6) ===
echo Starts tracker + hub :8765 + productivity UI in one process.
echo Calendar remains: http://localhost:5173/productivity
echo.

rem Prefer pythonw so no console; fall back to PY.
set "PYW=%ROOT%\.venv\Scripts\pythonw.exe"
if not exist "%PYW%" set "PYW=%PY%"

"%PY%" -c "import PySide6" 1>nul 2>nul
if errorlevel 1 (
  echo Installing PySide6...
  "%PIP%" install "PySide6>=6.6.0"
  if errorlevel 1 (
    echo ERROR: pip install PySide6 failed.
    endlocal & exit /b 1
  )
)

echo Launching...
start "" "%PYW%" -m backend.behavior.calt_desktop
echo Started. Look for teal tray icon near the clock.
echo Logs: data\logs\desktop_tracker.log
endlocal
exit /b 0
