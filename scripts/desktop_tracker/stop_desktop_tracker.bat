@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

REM Casual stop is a hard-block bypass — require exit PIN/phrase
REM unless an outer script already confirmed (CALT_TRACKER_SKIP_STOP_PIN=1).
if /i not "%CALT_TRACKER_SKIP_STOP_PIN%"=="1" (
  call "%~dp0_require_exit_pin.bat" "stop the desktop tracker"
  if errorlevel 1 (
    echo Stop aborted.
    endlocal & exit /b 1
  )
)

echo Stopping Desktop Activity Tracker...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -match 'desktop_tracker' } | ForEach-Object { Write-Host ('  Ending PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

ping -n 2 127.0.0.1 >nul
call "%~dp0_log_tracker_launch.bat" stop "tracker stopped (PIN ok)"
echo Done.
endlocal
