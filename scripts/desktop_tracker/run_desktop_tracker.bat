@echo off
setlocal
call "%~dp0..\_common.bat" env-only
if errorlevel 1 exit /b 1

cd /d "%ROOT%"
call "%~dp0_log_tracker_launch.bat" tray "launch requested"

rem Tray mode requires a single instance — stop headless/other copy first.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -match 'desktop_tracker' }; if ($p) { Write-Host 'NOTE: Stopping existing tracker so tray mode can start...'; $p | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue } }"

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
echo Stop: scripts\desktop_tracker\stop_desktop_tracker.bat
endlocal
