@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

cd /d "%ROOT%"

echo === Desktop Activity Tracker ===
echo Default launch is now CALT Desktop (PySide6).
echo Legacy pystray tray: set CALT_USE_LEGACY_TRAY=1
echo.
call "%~dp0_log_tracker_launch.bat" tray "launch requested"

rem Detect an already-running tracker/desktop (CommandLine match).
set "TRACKER_ALREADY=0"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and ($_.CommandLine -match 'desktop_tracker' -or $_.CommandLine -match 'calt_desktop') -and $_.CommandLine -notmatch 'tracker_keepalive' }) { '1' } else { '0' }"`) do set "TRACKER_ALREADY=%%A"

if "%TRACKER_ALREADY%"=="1" (
  if /i not "%CALT_TRACKER_SKIP_STOP_PIN%"=="1" (
    echo Existing tracker is running — PIN required before replacing it.
    call "%~dp0_require_exit_pin.bat" "replace the running desktop tracker"
    if errorlevel 1 (
      echo Launch aborted — tracker left running.
      endlocal & exit /b 1
    )
  )
  echo Stopping existing tracker so a fresh instance can start...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and ($_.CommandLine -match 'desktop_tracker' -or $_.CommandLine -match 'calt_desktop') -and $_.CommandLine -notmatch 'tracker_keepalive' } | ForEach-Object { Write-Host ('  Ending PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
  ping -n 2 127.0.0.1 >nul
)

echo Starting CALT Desktop via launcher VBS...
wscript.exe //B "%~dp0tracker_tray_launch.vbs" "%PY%"
if errorlevel 1 (
  call "%~dp0_log_tracker_launch.bat" tray "ERROR wscript failed"
  echo ERROR: wscript failed to launch.
  exit /b 1
)
call "%~dp0_log_tracker_launch.bat" tray "wscript ok — see data\logs\desktop_tracker.log"
echo Started - teal tray icon near the clock ^(CALT Desktop^).
echo Logs: data\logs\desktop_tracker.log  and  data\logs\tracker_launcher.log
echo Login: http://localhost:5173/login  (default admin / admin123)
echo Stop ^(PIN^): scripts\admin_only\stop_desktop_tracker.bat
endlocal
