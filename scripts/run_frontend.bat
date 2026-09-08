@echo off
setlocal
call "%~dp0_common.bat"
if errorlevel 1 exit /b 1

echo Frontend: http://localhost:5173
call "%~dp0print_lan_urls.bat"

REM Vite dev can hang on first HTTP on some Windows + Node 24 setups (TCP accepts, no response).
REM Default: serve pre-built dist via preview. Set CALT_FRONTEND_MODE=dev to force HMR dev server.
if /I "%CALT_FRONTEND_MODE%"=="dev" (
  npm.cmd run dev
  endlocal
  exit /b %ERRORLEVEL%
)

if not exist "%~dp0..\dist\index.html" (
  echo [frontend] No dist/ — running one-time build for preview...
  call npm.cmd run build
  if errorlevel 1 (
    endlocal
    exit /b 1
  )
) else (
  REM Rebuild when source is newer than dist (preview does not hot-reload)
  powershell -NoProfile -Command "$dist=(Get-Item '%~dp0..\dist\index.html').LastWriteTimeUtc; $src=(Get-ChildItem '%~dp0..\src' -Recurse -File | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc; if ($src -gt $dist) { exit 1 } else { exit 0 }"
  if errorlevel 1 (
    echo [frontend] Source newer than dist — rebuilding...
    call npm.cmd run build
    if errorlevel 1 (
      endlocal
      exit /b 1
    )
  )
)

npm.cmd run preview
endlocal
exit /b %ERRORLEVEL%
