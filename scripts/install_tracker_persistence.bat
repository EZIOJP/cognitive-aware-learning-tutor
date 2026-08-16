@echo off
REM Install full tracker persistence: Startup shortcut + scheduled tasks + HKCU Run.
REM Alias preferred by docs; delegates to desktop_tracker install + Run key.

setlocal
call "%~dp0desktop_tracker\install_tracker_startup.bat" %*
if errorlevel 1 exit /b 1

echo.
echo [3/3] HKCU Run key (survives Startup-folder deletes)...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$root = (Resolve-Path '%~dp0..').Path; ^
   $pyw = Join-Path $root '.venv\Scripts\pythonw.exe'; ^
   if (-not (Test-Path $pyw)) { $pyw = Join-Path $root '.venv\Scripts\python.exe' }; ^
   $vbs = Join-Path $root 'scripts\desktop_tracker\tracker_tray_launch.vbs'; ^
   $cmd = 'wscript.exe //B \"' + $vbs + '\" \"' + $pyw + '\"'; ^
   Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'CALT Desktop Tracker' -Value $cmd -Force; ^
   Write-Host 'OK HKCU Run: CALT Desktop Tracker'"
if errorlevel 1 (
  echo       WARN — HKCU Run failed; Startup tasks still installed.
) else (
  echo       OK
)

echo.
echo Persistence installed.
echo   Exit PIN: set TRACKER_EXIT_PIN in .env  ^(default phrase: I AM DONE TRACKING^)
echo   Protect: TRACKER_PERSIST_PROTECT=1 re-adds Run key while Armed
echo   Stop/restart ^(PIN^): scripts\admin_only\
echo   Uninstall ^(PIN^): scripts\uninstall_tracker_persistence.bat
endlocal
