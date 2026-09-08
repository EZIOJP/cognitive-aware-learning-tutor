@echo off
rem Thin Start Menu launcher installed by install_calt_desktop.iss (v2d skeleton).
rem Does NOT freeze Python — calls the repo's run_calt_desktop.bat.
rem Override: set CALT_REPO=C:\path\to\Cognitive-Aware Learning Tutor
setlocal EnableExtensions
set "APPDIR=%~dp0"
set "REPO="

if defined CALT_REPO set "REPO=%CALT_REPO%"
if not defined REPO if exist "%APPDIR%repo_root.txt" (
  set /p REPO=<"%APPDIR%repo_root.txt"
)
if defined REPO set "REPO=%REPO:"=%"
if defined REPO for %%I in ("%REPO%") do set "REPO=%%~fI"

if not defined REPO goto :MissingRepo
if exist "%REPO%\scripts\desktop_tracker\run\run_calt_desktop.bat" goto :Launch
if exist "%REPO%\scripts\desktop_tracker\run_calt_desktop.bat" goto :LaunchShim
goto :MissingLauncher

:Launch
cd /d "%REPO%"
call "%REPO%\scripts\desktop_tracker\run\run_calt_desktop.bat"
endlocal & exit /b %ERRORLEVEL%

:LaunchShim
cd /d "%REPO%"
call "%REPO%\scripts\desktop_tracker\run_calt_desktop.bat"
endlocal & exit /b %ERRORLEVEL%

:MissingRepo
echo ERROR: CALT repo path not set.
echo Edit "%APPDIR%repo_root.txt" ^(one line: full path to the repo^)
echo or set CALT_REPO before launching.
echo See INSTALLER.md in this folder.
pause
endlocal & exit /b 1

:MissingLauncher
echo ERROR: Expected launcher missing:
echo   %REPO%\scripts\desktop_tracker\run\run_calt_desktop.bat
echo Check repo_root.txt / CALT_REPO. Full clone + .venv still required for this skeleton.
pause
endlocal & exit /b 1
