@echo off
REM CALT Productivity uninstall gate (option B).
REM If protect_uninstall is on, require Focus unlock password/phrase before Inno unins.
setlocal EnableExtensions
set "APP=%~dp0"
set "REPO="
if exist "%APP%repo_root.txt" (
  set /p REPO=<"%APP%repo_root.txt"
)
if "%REPO%"=="" set "REPO=%APP%"
set "PY=%REPO%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

set "UNINS="
for %%F in ("%APP%unins*.exe") do (
  if not defined UNINS set "UNINS=%%~fF"
)
if not defined UNINS (
  echo No Inno uninstaller found in "%APP%".
  echo Use Settings → Apps if the entry is visible, or turn off Protect uninstall in Focus.
  pause
  exit /b 1
)

echo CALT Productivity uninstall
echo.
set /p UNLOCK="Unlock password/phrase (blank if protect is off): "
set "CALT_UNINSTALL_UNLOCK=%UNLOCK%"

pushd "%REPO%" >nul 2>&1
"%PY%" -c "import os,sys; from backend.behavior.uninstall_protect import cli_allow_uninstall; sys.exit(cli_allow_uninstall(os.environ.get('CALT_UNINSTALL_UNLOCK','')))"
set "RC=%ERRORLEVEL%"
popd >nul 2>&1

if not "%RC%"=="0" (
  echo.
  echo Blocked. Turn off Protect uninstall in Focus, or enter the correct password.
  pause
  exit /b 1
)

echo Starting uninstaller...
start "" "%UNINS%"
endlocal
exit /b 0
