@echo off
setlocal
cd /d "%~dp0..\..\.."
set "REPO=%CD%"
set "CALT_DB=%REPO%\data\vocab_app.db"
set "CALT_ENFORCER_LOCK=%REPO%\data\behavior\enforcer_owner.lock"
set "EXE="
if exist "%REPO%\calt-focus\backend\calt_enforcer\build\Release\calt_enforcer.exe" set "EXE=%REPO%\calt-focus\backend\calt_enforcer\build\Release\calt_enforcer.exe"
if exist "%REPO%\calt-focus\backend\calt_enforcer\build\calt_enforcer.exe" set "EXE=%REPO%\calt-focus\backend\calt_enforcer\build\calt_enforcer.exe"
if not defined EXE (
  echo Missing calt_enforcer.exe — run scripts\desktop_tracker\build\build_native_enforcer.bat
  exit /b 1
)
echo Console enforcer. DB=%CALT_DB%
echo Ctrl+C to stop. For boot stay-alive use install\install_native_enforcer.ps1 as Admin.
"%EXE%"
endlocal
