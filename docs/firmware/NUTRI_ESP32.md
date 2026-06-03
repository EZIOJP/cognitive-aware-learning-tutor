# NutriNode ESP32 (placeholder)

Nutrition works **today** without hardware:

- Log meals on the Nutrition page (manual)
- `GET /api/nutrition/today` for totals
- Live WebSocket is **off by default** (no reconnect spam)

## When you buy a scale / sensor board

1. Enable **NutriNode** in Plugin Manager.
2. Point device firmware at your backend (same host as API, port 8000).
3. Optionally turn on live feed in the Nutrition UI (stores `nutrinode:live_ws`).

## Backend hooks (already in repo)

- Plugin: `backend/plugins/nutrinode_plugin.py`
- Pipeline: `backend/plugins/pipeline_nutrition.py`

Add your firmware project here when ready; document the JSON payload your ESP32 sends so we can align ingest routes.
