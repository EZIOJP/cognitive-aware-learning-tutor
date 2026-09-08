@echo off
setlocal EnableExtensions
REM Flash CALT EEG firmware (ESP32-S3 + BioAmp EXG Pill)
REM Requires: USB cable to the board + 2.4 GHz WiFi credentials in secrets.h

set "ROOT=%~dp0.."
set "EEG_DIR=%ROOT%\hardware\eeg"
cd /d "%EEG_DIR%" || exit /b 1

if not exist "src\secrets.h.example" (
  if exist "secrets.h.example" (
    copy /Y "secrets.h.example" "src\secrets.h.example" >nul
  )
)

if not exist "src\secrets.h" (
  echo [eeg] Creating src\secrets.h from example — EDIT WiFi + laptop IP then re-run.
  copy /Y "src\secrets.h.example" "src\secrets.h" >nul
  echo.
  echo    Edit: %EEG_DIR%\src\secrets.h
  echo    Set WIFI_SSID, WIFI_PASSWORD, UDP_TARGET_IP (your PC LAN IP)
  echo.
  notepad "src\secrets.h"
  echo After saving secrets.h, run this script again.
  exit /b 2
)

where pio >nul 2>&1
if errorlevel 1 (
  if exist "%APPDATA%\Python\Python314\Scripts\pio.exe" (
    set "PATH=%APPDATA%\Python\Python314\Scripts;%PATH%"
  ) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\Scripts\pio.exe" (
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%PATH%"
  )
)
where pio >nul 2>&1
if errorlevel 1 (
  echo [eeg] PlatformIO CLI not found.
  echo.
  echo Option A — Cursor/VS Code extension:
  echo   Extensions → search "PlatformIO IDE" → Install → open hardware/eeg → Upload
  echo.
  echo Option B — install CLI:
  echo   pip install platformio
  echo   then re-run this script
  echo.
  echo Board must show as a COM port (Device Manager) when USB is plugged in.
  exit /b 3
)

echo [eeg] Building (SELF_TEST snaps by default — see src\secrets.h)...
pio run
if errorlevel 1 exit /b 1

echo [eeg] Uploading (USB COM port required)...
pio run -t upload
if errorlevel 1 (
  echo.
  echo Upload failed. Check:
  echo   1. USB cable data-capable, board powered
  echo   2. Correct COM port: pio device list
  echo   3. Hold BOOT if needed, then reset
  exit /b 1
)

echo.
echo [eeg] Flash OK. In another terminal run:
echo   .venv\Scripts\python.exe scripts\eeg_udp_listen.py
echo You should see SNAP #1, #2, ... every ~2 seconds.
echo.
echo [eeg] Opening serial monitor (Ctrl+C to stop)...
pio device monitor
endlocal
