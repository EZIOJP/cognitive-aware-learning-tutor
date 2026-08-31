@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

echo === Desktop Activity Tracker (legacy tray) ===
echo Prefer CALT Desktop: scripts\desktop_tracker\run_calt_desktop.bat
echo Legacy pystray tray kept as fallback.
echo.
call "%~dp0_log_tracker_launch.bat" tray "launch requested"

rem Detect an already-running tracker (CommandLine match).
set "TRACKER_ALREADY=0"
for /f "usebackq delims=" %%A in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -match 'desktop_tracker' }) { '1' } else { '0' }"`) do set "TRACKER_ALREADY=%%A"

if "%TRACKER_ALREADY%"=="1" (
  if /i not "%CALT_TRACKER_SKIP_STOP_PIN%"=="1" (
    echo Existing tracker is running — PIN required before replacing it.
    call "%~dp0_require_exit_pin.bat" "replace the running desktop tracker"
    if errorlevel 1 (
      echo Launch aborted — tracker left running.
      endlocal & exit /b 1
    )
  )
  echo Stopping existing tracker so tray mode can start...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -match 'desktop_tracker' } | ForEach-Object { Write-Host ('  Ending PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
  ping -n 2 127.0.0.1 >nul
)

echo Starting Desktop Activity Tracker (system tray)...
set "TRACKER_NO_TRAY="
wscript.exe //B "%~dp0tracker_tray_launch.vbs" "%PY%"
if errorlevel 1 (
  call "%~dp0_log_tracker_launch.bat" tray "ERROR wscript failed"
  echo ERROR: wscript failed to launch tracker.
  exit /b 1
)
call "%~dp0_log_tracker_launch.bat" tray "wscript ok — see data\logs\desktop_tracker.log"
echo Tracker started - check system tray (green dot). Hidden icons: ^^ near the clock.
echo Logs: data\logs\desktop_tracker.log  and  data\logs\tracker_launcher.log
echo Login: http://localhost:5173/login  (default admin / admin123)
echo Stop ^(PIN^): scripts\admin_only\stop_desktop_tracker.bat
endlocal
