@echo off
setlocal
title 9Router public tunnel (for Cursor Agent)

echo.
echo This exposes local 9Router (port 20128) on a temporary PUBLIC HTTPS URL.
echo Cursor Agent needs a public URL — localhost is blocked by Cursor cloud.
echo.
echo Prereqs:
echo   1) 9Router already running: scripts\9router\start_9router.bat
echo   2) cloudflared installed (Cloudflare Tunnel free client)
echo      Download: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
echo.

call "%~dp0verify_9router.bat"
if errorlevel 1 (
  echo.
  echo Start 9Router first, then re-run this script.
  exit /b 1
)

where cloudflared >nul 2>&1
if errorlevel 1 (
  echo.
  echo ERROR: cloudflared not found on PATH.
  echo Install cloudflared, reopen this terminal, then run again.
  echo Alternative: use ngrok  -^>  ngrok http 20128
  echo Then set Cursor Base URL to https://YOUR-NGROK-HOST/v1
  exit /b 1
)

echo.
echo Starting Cloudflare quick tunnel to http://127.0.0.1:20128 ...
echo When it prints a https://....trycloudflare.com URL:
echo   Cursor Override Base URL = that URL + /v1
echo   Example: https://xxxx.trycloudflare.com/v1
echo   API key = 9Router dashboard key
echo.
echo Keep this window open while using Cursor Agent.
echo.

cloudflared tunnel --url http://127.0.0.1:20128

endlocal
