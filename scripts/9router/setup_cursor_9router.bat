@echo off
setlocal EnableExtensions
title Cursor + 9Router setup

echo.
echo ============================================================
echo  Cursor + 9Router setup (Windows)
echo ============================================================
echo.
echo IMPORTANT about Cursor Agent:
echo   Cursor Agent runs in the CLOUD. It CANNOT call http://localhost.
echo   That causes: "Access to private networks is forbidden".
echo.
echo You have TWO modes:
echo   A) Local Chat / custom OpenAI models in Cursor IDE
echo      - can use localhost:20128 IF Cursor calls models locally
echo   B) Cursor Agent (plan/execute cloud path)
echo      - MUST use a PUBLIC HTTPS URL (tunnel / VPS), not localhost
echo.
echo ------------------------------------------------------------
echo  STEP 0 — Start 9Router
echo ------------------------------------------------------------
echo   scripts\9router\start_9router.bat
echo   Dashboard: http://localhost:20128/dashboard
echo.
call "%~dp0verify_9router.bat"
echo.

echo ------------------------------------------------------------
echo  STEP 1 — In 9Router dashboard
echo ------------------------------------------------------------
echo   1. Providers -^> ensure Cursor OAuth (cu/*) is Active
echo   2. Settings  -^> copy API Key
echo   3. Optional Combos:
echo        free-forever:
echo          1. cu/claude-4.6-sonnet-medium-thinking
echo          2. cu/claude-4.5-haiku
echo          3. cu/gpt-5.3-codex
echo.

set /p NINE_KEY=Paste your 9Router API key here (or press Enter to skip): 

echo.
echo ------------------------------------------------------------
echo  STEP 2A — Cursor settings for LOCAL model calls
echo ------------------------------------------------------------
echo   Cursor Settings -^> Models -^> API Keys
echo.
echo   OpenAI API Key            = ON
echo   Paste key                 = your 9Router API key
echo   Override OpenAI Base URL  = ON
echo   Base URL                  = http://127.0.0.1:20128/v1
echo.
echo   Then Add models and toggle them ON:
echo     cu/claude-4.6-sonnet-medium-thinking
echo     cu/claude-4.5-haiku
echo     cu/gpt-5.3-codex
echo.
echo   Pick one of those models in the chat model dropdown.
echo   Restart Cursor after saving.
echo.

echo ------------------------------------------------------------
echo  STEP 2B — Cursor AGENT / cloud path (required for Agent)
echo ------------------------------------------------------------
echo   If you use Agent and see private-network errors, do ONE of:
echo.
echo   Option 1 (simplest): turn Override Base URL OFF and use Cursor defaults.
echo.
echo   Option 2 (keep 9Router for Agent):
echo     run: scripts\9router\start_9router_public_tunnel.bat
echo     then set Cursor Base URL to the printed HTTPS URL + /v1
echo     example: https://xxxx.trycloudflare.com/v1
echo.

if not "%NINE_KEY%"=="" (
  echo ------------------------------------------------------------
  echo  Optional: launch Cursor from this shell with env hints
  echo ------------------------------------------------------------
  set "OPENAI_API_BASE=http://127.0.0.1:20128/v1"
  set "OPENAI_BASE_URL=http://127.0.0.1:20128/v1"
  set "OPENAI_API_KEY=%NINE_KEY%"
  echo   Env set for this window:
  echo     OPENAI_API_BASE=%OPENAI_API_BASE%
  echo     OPENAI_API_KEY=(hidden)
  echo.
  where cursor >nul 2>&1
  if not errorlevel 1 (
    set /p LAUNCH=Launch Cursor now from this window? [y/N]: 
    if /i "%LAUNCH%"=="y" (
      start "" cursor
      echo Cursor launched. Still confirm Settings -^> Models match the values above.
    )
  ) else (
    echo   Note: 'cursor' CLI not on PATH. Open Cursor manually and paste settings.
  )
)

echo.
echo Done. Full guide: docs\9ROUTER_SETUP.md  (section: Cursor config)
echo Also: scripts\9router\CURSOR_SETTINGS.txt
endlocal
