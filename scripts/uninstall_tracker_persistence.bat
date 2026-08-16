@echo off
REM Legitimate uninstall of tracker persistence (does not require admin for user tasks).
REM Requires TRACKER_EXIT_PIN / exit phrase — same as tray Confirm exit.

setlocal
echo === CALT Tracker — remove persistence ===
echo.

call "%~dp0desktop_tracker\_require_exit_pin.bat" "uninstall tracker persistence"
if errorlevel 1 (
  echo Uninstall aborted.
  endlocal & exit /b 1
)

echo TIP: set TRACKER_PERSIST_PROTECT=0 in .env if Protect kept rewriting Run while Armed.
echo.

set "CALT_TRACKER_SKIP_STOP_PIN=1"
call "%~dp0desktop_tracker\stop_desktop_tracker.bat"
call "%~dp0desktop_tracker\uninstall_tracker_startup.bat"
set "CALT_TRACKER_SKIP_STOP_PIN="

echo Removing HKCU Run key...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name 'CALT Desktop Tracker' -ErrorAction SilentlyContinue; Write-Host 'HKCU Run cleared (if present)'"

echo.
echo Done. Also:
echo   - Clear TRACKER_EXIT_PIN from .env if set
echo   - Set TRACKER_PERSIST_PROTECT=0 before uninstall if Protect kept rewriting Run
echo   - Unload SelfTracker extensions from edge://extensions / about:addons
endlocal
