@echo off
setlocal
echo.
echo [9Router] Installing global 9router package...
echo   Dashboard will be at http://localhost:20128
echo   API endpoint:            http://localhost:20128/v1
echo.

where npm >nul 2>&1
if errorlevel 1 (
  echo ERROR: npm not found. Install Node.js 18+ from https://nodejs.org
  exit /b 1
)

call npm install -g 9router
if errorlevel 1 (
  echo ERROR: npm install -g 9router failed.
  exit /b 1
)

echo.
echo [9Router] Installed. Next steps:
echo   1. Run: scripts\9router\start_9router.bat  (or start_9router_tray.bat for background)
echo   2. Dashboard: connect Kiro AI and/or OpenCode Free (free tiers in 2026)
echo   3. Create a combo (e.g. free-forever) in Dashboard -^> Combos
echo   4. Copy API key from dashboard; point Cursor at http://localhost:20128/v1
echo.
echo See docs\9ROUTER_SETUP.md (aligned with github.com/decolua/9router README v0.5.20).
endlocal
