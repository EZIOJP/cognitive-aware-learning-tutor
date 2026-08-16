@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

cd /d "%ROOT%"

echo === Restart Desktop Activity Tracker ===
echo.

REM Restart kills the live process — require PIN so it is not a silent bypass.
call "%~dp0_require_exit_pin.bat" "restart the desktop tracker"
if errorlevel 1 (
  echo Restart aborted.
  endlocal & exit /b 1
)

echo [1/3] Ensuring edge-tts for Jarvis voice (best-effort)...
"%PIP%" install edge-tts 1>nul 2>nul
if errorlevel 1 (
  echo   WARN: edge-tts install skipped or failed - TTS may fall back to Piper/SAPI.
) else (
  echo   OK: edge-tts ready.
)
echo.

echo [2/3] Stopping existing tracker (PIN already confirmed)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -match 'desktop_tracker' } | ForEach-Object { Write-Host ('  Ending PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
ping -n 2 127.0.0.1 >nul
call "%~dp0_log_tracker_launch.bat" restart "stopped for restart (PIN ok)"
echo.

echo [3/3] Starting tracker (system tray)...
REM Skip second PIN — already confirmed above.
set "CALT_TRACKER_SKIP_STOP_PIN=1"
call "%~dp0run_desktop_tracker.bat"
set "RC=%ERRORLEVEL%"
set "CALT_TRACKER_SKIP_STOP_PIN="
echo.
if not "%RC%"=="0" (
  echo Restart finished with errors. Exit code: %RC%
  endlocal & exit /b %RC%
)
echo Restart complete. Hub: http://127.0.0.1:8765/health  ^(if hub enabled^)
echo Tray icon near the clock. Logs: data\logs\desktop_tracker.log
endlocal
exit /b 0
