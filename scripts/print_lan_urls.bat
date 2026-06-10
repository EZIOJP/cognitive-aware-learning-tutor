@echo off
rem Prints LAN URLs for phone/tablet on the same WiFi
echo.
echo   WiFi access (same network — allow ports 5173 and 8000 in Windows Firewall):
for /f "usebackq tokens=*" %%i in (`powershell -NoProfile -Command "$ip = (Get-NetIPAddress -AddressFamily IPv4 ^| Where-Object { $_.IPAddress -notmatch '^127\.' -and $_.PrefixOrigin -ne 'WellKnown' } ^| Select-Object -First 1 -ExpandProperty IPAddress); if ($ip) { Write-Output $ip }"`) do (
  echo     Frontend:     http://%%i:5173
  echo     API health:   http://%%i:8000/health
  echo     Vocab API:    http://%%i:8000/api/vocab
  echo     OpenAPI:      http://%%i:8000/openapi.json
  echo     EEG WS:       ws://%%i:8000/ws/eeg
  echo     Nutrition WS: ws://%%i:8000/ws/nutrition/live
)
echo     Backend binds 0.0.0.0:8000 — frontend auto-uses this PC IP when opened from LAN.
echo.
