@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo.
echo  CALT PORN BLOCK — desktop tracker list (theporndude.com + defaults)
echo  Does NOT block YouTube. Requires Administrator once.
echo.

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting admin...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b 0
)

cd /d "%ROOT%"
echo Refreshing porn site list from theporndude.com (index pages only)...
"%PY%" -c "from backend.behavior.porn_blocklist import refresh_if_stale; print(refresh_if_stale(force=True))"

echo Enabling porn-only device block...
"%PY%" -c "from backend.behavior.device_block import save_settings, load_settings; save_settings({**load_settings(), 'enabled': True, 'block_porn': True, 'block_watch': False, 'block_social': False})"

"%PY%" -m backend.behavior.device_block_cli apply --enable
set RC=%ERRORLEVEL%
if %RC% GEQ 1 (
  echo FAILED — could not write hosts.
  pause
  exit /b 1
)

echo.
echo Done. Desktop tracker will keep this list updated weekly.
echo YouTube is NOT blocked. Close/reopen browser tabs if a site still loads.
pause
endlocal
