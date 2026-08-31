@echo off
REM After code changes: rebuild extensions, restart tracker, CALT stack, or everything.
REM Usage:
REM   scripts\update_and_restart.bat
REM   scripts\update_and_restart.bat tracker
REM   scripts\update_and_restart.bat stack
REM   scripts\update_and_restart.bat api
REM   scripts\update_and_restart.bat extensions
REM   scripts\update_and_restart.bat full
REM   scripts\update_and_restart.bat status
setlocal EnableDelayedExpansion
call "%~dp0_common.bat" env-only
if errorlevel 1 exit /b 1
cd /d "%ROOT%"

set "ARG=%~1"
if /i "%ARG%"=="tracker" goto TRACKER
if /i "%ARG%"=="stack" goto STACK
if /i "%ARG%"=="api" goto API
if /i "%ARG%"=="frontend" goto FRONTEND
if /i "%ARG%"=="fe" goto FRONTEND
if /i "%ARG%"=="extensions" goto EXTENSIONS
if /i "%ARG%"=="ext" goto EXTENSIONS
if /i "%ARG%"=="full" goto FULL
if /i "%ARG%"=="status" goto STATUS
if /i "%ARG%"=="/?" goto HELP
if /i "%ARG%"=="-h" goto HELP
if /i "%ARG%"=="help" goto HELP
if not "%ARG%"=="" (
  echo Unknown option: %ARG%
  echo.
  goto HELP
)

:MENU
cls
echo ============================================================
echo   CALT update / restart  (after tracker, API, or extension edits)
echo ============================================================
echo.
"%PY%" "%ROOT%\scripts\server_lifecycle.py" status
echo   1^) Tracker only          PIN — hub + tray pick up Python changes
echo   2^) CALT stack only       API :8000 + Vite :5173  ^(tracker stays^)
echo   3^) API only              FastAPI routes / day-status / comms
echo   4^) Frontend only         Vite UI
echo   5^) Rebuild extensions    SelfTracker + CALT Gate workers, open Edge
echo   6^) Full after code change  5 + stack + tracker
echo   S^) Status
echo   0^) Exit
echo.
set "CHOICE="
set /p "CHOICE=  Choose: "
if "%CHOICE%"=="0" goto END
if /i "%CHOICE%"=="q" goto END
if "%CHOICE%"=="1" goto TRACKER
if "%CHOICE%"=="2" goto STACK
if "%CHOICE%"=="3" goto API
if "%CHOICE%"=="4" goto FRONTEND
if "%CHOICE%"=="5" goto EXTENSIONS
if "%CHOICE%"=="6" goto FULL
if /i "%CHOICE%"=="S" goto STATUS
echo   Invalid choice.
pause
goto MENU

:HELP
echo.
echo   tracker       Restart desktop tracker ^(PIN required^)
echo   stack         Restart API + frontend, leave tracker running
echo   api           Restart API only
echo   frontend      Restart Vite only
echo   extensions    Rebuild MV3 service workers + open edge://extensions
echo   full          Extensions + stack + tracker
echo   status        Show API / frontend / tracker
echo.
goto END

:STATUS
echo.
"%PY%" "%ROOT%\scripts\server_lifecycle.py" status
if "%ARG%"=="" pause & goto MENU
goto END

:EXTENSIONS
echo.
echo === Rebuild Edge extension workers ===
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%\scripts\build_extension_workers.ps1"
if errorlevel 1 (
  echo Extension rebuild FAILED.
  if "%ARG%"=="" pause & goto MENU
  endlocal & exit /b 1
)
echo.
echo   Edge cannot hot-reload unpacked extensions from a script.
echo   Click Reload on BOTH:
echo     - CALT SelfTracker
echo     - CALT Gate
echo   Do not close Edge if those extensions are already active.
echo.
start "" "edge://extensions"
if /i "%ARG%"=="full" goto STACK
if "%ARG%"=="" pause & goto MENU
goto END

:API
echo.
echo === Restart CALT API (:8000) — tracker left running ===
"%PY%" "%ROOT%\scripts\server_lifecycle.py" restart-api --yes
if /i "%ARG%"=="full" goto FRONTEND
if "%ARG%"=="" pause & goto MENU
goto END

:FRONTEND
echo.
echo === Restart CALT frontend (:5173) — tracker left running ===
"%PY%" "%ROOT%\scripts\server_lifecycle.py" restart-frontend --yes
if /i "%ARG%"=="full" goto TRACKER
if "%ARG%"=="" pause & goto MENU
goto END

:STACK
echo.
echo === Restart CALT stack (API + frontend) — tracker left running ===
"%PY%" "%ROOT%\scripts\server_lifecycle.py" restart-api --yes
"%PY%" "%ROOT%\scripts\server_lifecycle.py" restart-frontend --yes
"%PY%" "%ROOT%\scripts\server_lifecycle.py" status
if /i "%ARG%"=="full" goto TRACKER
if "%ARG%"=="" pause & goto MENU
goto END

:TRACKER
echo.
echo === Restart desktop tracker (PIN) ===
call "%ROOT%\scripts\admin_only\restart_desktop_tracker.bat"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo Tracker restart aborted or failed. Exit %RC%
  if "%ARG%"=="" pause & goto MENU
  endlocal & exit /b %RC%
)
if "%ARG%"=="" pause & goto MENU
goto END

:FULL
echo.
echo === Full update after code changes ===
echo   1. Rebuild extension workers
echo   2. Restart API + frontend
echo   3. Restart tracker ^(PIN^)
echo.
set "ARG=full"
goto EXTENSIONS

:END
endlocal
exit /b 0
