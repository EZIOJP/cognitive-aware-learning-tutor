@echo off
setlocal
set "ROOT=%~dp0..\.."
cd /d "%ROOT%"

if not exist "%ROOT%\node_modules\@google\stitch-sdk" (
  echo [stitch] Installing @google/stitch-sdk...
  call npm install @google/stitch-sdk --save-dev --no-fund --no-audit
  if errorlevel 1 exit /b 1
)

set "JOB=%~1"
if "%JOB%"=="" set "JOB=verify"

if /i "%JOB%"=="verify" (
  node "%ROOT%\scripts\stitch\verify.mjs"
  exit /b %ERRORLEVEL%
)

if /i "%JOB%"=="download" (
  node "%ROOT%\scripts\stitch\download_screens.mjs"
  exit /b %ERRORLEVEL%
)

node "%ROOT%\scripts\stitch\generate.mjs" %JOB%
exit /b %ERRORLEVEL%
