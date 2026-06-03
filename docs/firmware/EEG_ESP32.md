# EEG ESP32 firmware (placeholder)

The **backend and frontend are ready** for real EEG. You only need to flash firmware that sends UDP JSON to the PC on port **5005** (default).

## Backend (already implemented)

- Set `EEG_ENABLED=1` in `.env`
- Service: `backend/eeg/service.py`
- WebSocket: `ws://localhost:8000/ws/eeg`
- Hub metric: `eeg_attention` (also posted from the study session when signed in)

## Expected packet shape (example)

Your firmware should send datagrams the service can parse (exact schema may match your BioAmp pipeline). Typical fields:

- `alpha`, `beta`, `gamma` (float power bands)
- optional `timestamp`

## Frontend

In `src/config.ts`, when hardware is live:

```ts
useSimulatedData: false,
```

Keep the **EEG plugin** enabled in Plugin Manager.

## When you buy boards

1. Wire ESP32-S3 + EXG per your lab design.
2. Flash firmware (add your `.ino` / ESP-IDF project in this folder or a sibling repo).
3. Same Wi‑Fi as PC; UDP target = laptop IP, port 5005.
4. Enable `EEG_ENABLED=1`, restart API, open dashboard EEG widget.

Until then, use **simulation** (default) — the dashboard and math load badge still work.
