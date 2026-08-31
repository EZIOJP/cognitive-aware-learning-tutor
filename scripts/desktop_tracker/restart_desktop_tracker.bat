@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

cd /d "%ROOT%"

echo === Restart Desktop Activity Tracker ===
echo.

REM Restart kills the live process — require PIN when configured.
if /i not "%CALT_TRACKER_SKIP_STOP_PIN%"=="1" (
  call "%~dp0_require_exit_pin.bat" "restart the desktop tracker"
  if errorlevel 1 (
    echo Restart aborted.
    endlocal & exit /b 1
  )
)

echo [1/2] Ensuring edge-tts for Jarvis voice (best-effort)...
"%PIP%" install edge-tts 1>nul 2>nul
if errorlevel 1 (
  echo   WARN: edge-tts install skipped or failed - TTS may fall back to Piper/SAPI.
) else (
  echo   OK: edge-tts ready.
)
echo.

echo [2/2] Restarting tracker (reload Python code — SQLite/CSV unchanged)...
"%PY%" -m backend.behavior.tracker_restart go
set "RC=%ERRORLEVEL%"
call "%~dp0_log_tracker_launch.bat" restart "force restart rc=%RC%"
if not "%RC%"=="0" (
  echo Restart failed — tracker may still be running. Check data\logs\desktop_tracker.log
  endlocal & exit /b %RC%
)
echo.
echo Restart complete. Hub: http://127.0.0.1:8765/health  ^(if hub enabled^)
echo Tray icon near the clock. Logs: data\logs\desktop_tracker.log
endlocal
exit /b 0
