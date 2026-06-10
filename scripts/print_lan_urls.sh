#!/usr/bin/env bash
# Prints LAN URLs for phone/tablet on the same WiFi

ip=""
if command -v ip >/dev/null 2>&1; then
  ip=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}')
elif command -v hostname >/dev/null 2>&1; then
  ip=$(hostname -I 2>/dev/null | awk '{print $1}')
fi

echo ""
echo "  WiFi access (same network):"
if [[ -n "$ip" ]]; then
  echo "    Frontend:     http://${ip}:5173"
  echo "    API health:   http://${ip}:8000/health"
  echo "    Vocab API:    http://${ip}:8000/api/vocab"
  echo "    OpenAPI:      http://${ip}:8000/openapi.json"
  echo "    EEG WS:       ws://${ip}:8000/ws/eeg"
  echo "    Nutrition WS: ws://${ip}:8000/ws/nutrition/live"
else
  echo "    (Could not detect LAN IP — use: ip route get 1.1.1.1)"
fi
echo "    Backend binds 0.0.0.0:8000 — frontend auto-uses this machine IP when opened from LAN."
echo ""
