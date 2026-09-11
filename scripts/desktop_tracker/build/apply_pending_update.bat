@echo off
REM Apply staged *.exe.new binaries after Focus/enforcer have exited.
setlocal EnableExtensions
cd /d "%~dp0..\..\.."
set "REPO=%CD%"
set "FOCUS_NEW=%REPO%\native\calt_focus\build\calt_focus.exe.new"
set "FOCUS_EXE=%REPO%\native\calt_focus\build\calt_focus.exe"
set "ENF_NEW=%REPO%\native\calt_enforcer\build\calt_enforcer.exe.new"
set "ENF_EXE=%REPO%\native\calt_enforcer\build\calt_enforcer.exe"
set "PAYLOAD=%REPO%\scripts\desktop_tracker\installer\installer_payload\bin"
set "NEED_FOCUS=0"
set "NEED_ENF=0"
if exist "%FOCUS_NEW%" set "NEED_FOCUS=1"
if exist "%ENF_NEW%" set "NEED_ENF=1"
if "%NEED_FOCUS%"=="0" if "%NEED_ENF%"=="0" (
  echo No *.exe.new found — nothing to apply.
  goto :start_focus
)

echo Waiting for processes to exit (max ~90s)...
set /A LOOPS=0
:wait
set /A LOOPS+=1
if %LOOPS% GTR 90 (
  echo Timed out waiting for exit. Close Focus/enforcer manually, then re-run this bat.
  pause
  exit /b 1
)
if "%NEED_FOCUS%"=="1" (
  tasklist /FI "IMAGENAME eq calt_focus.exe" 2>nul | find /I "calt_focus.exe" >nul && (timeout /t 1 /nobreak >nul & goto wait)
)
if "%NEED_ENF%"=="1" (
  tasklist /FI "IMAGENAME eq calt_enforcer.exe" 2>nul | find /I "calt_enforcer.exe" >nul && (timeout /t 1 /nobreak >nul & goto wait)
)

if exist "%FOCUS_NEW%" (
  echo Applying Focus update...
  copy /Y "%FOCUS_NEW%" "%FOCUS_EXE%" >nul
  if exist "%PAYLOAD%\calt_focus.exe" copy /Y "%FOCUS_NEW%" "%PAYLOAD%\calt_focus.exe" >nul
  del /F /Q "%FOCUS_NEW%" >nul 2>&1
)
if exist "%ENF_NEW%" (
  echo Applying Enforcer update...
  copy /Y "%ENF_NEW%" "%ENF_EXE%" >nul
  if exist "%PAYLOAD%\calt_enforcer.exe" copy /Y "%ENF_NEW%" "%PAYLOAD%\calt_enforcer.exe" >nul
  del /F /Q "%ENF_NEW%" >nul 2>&1
)

if exist "%REPO%\data\behavior\pending_update.json" del /F /Q "%REPO%\data\behavior\pending_update.json" >nul 2>&1

:start_focus
echo Starting CALT Focus...
if exist "%REPO%\scripts\desktop_tracker\run\run_calt_desktop.bat" (
  start "" "%REPO%\scripts\desktop_tracker\run\run_calt_desktop.bat"
) else if exist "%REPO%\scripts\desktop_tracker\run_calt_desktop.bat" (
  start "" "%REPO%\scripts\desktop_tracker\run_calt_desktop.bat"
) else (
  start "" "%FOCUS_EXE%"
)
endlocal
