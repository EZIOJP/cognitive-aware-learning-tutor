# Working product guide

Use this checklist to run the app as a **complete local product** (not every future vision item).

## 1. Start

```bat
run.bat
```

Open http://localhost:5173 — login **admin** / **admin123**.

## 2. First-time setup (5 minutes)

1. **Settings → Plugin Manager** — enable: Math Tutor, GRE Vocab, Life Tracker (EEG / Focus Mirror / NutriNode optional).
2. **Settings → Feature Studio** — create a custom metric OR skip.
3. **Life Tracker** — log today’s sleep and study minutes (feeds Life Clock + AI review).
4. **Dashboard → Customize** — arrange widgets; layout saves when signed in.

## 3. Study loops

| Goal | Where |
|------|--------|
| GRE words | Sidebar → GRE Vocab → Start study cycle |
| Math practice | Math Tutor → topic → Practice → **Ask tutor** |
| Daily picture | Home → 24h Life Clock + AI Review |
| Browser time | Install `selftracker-extension`, reload extension, check Life Tracker widget |
| Nutrition | Enable NutriNode → Nutrition page (live WS optional) |
| Focus | Enable Focus Mirror → `scripts\run_face_tracker.bat` → calibrate at `/focus/calibrate` |

## 4. No laptop GPU? No ESP32? (your situation)

You do **not** need either for daily study:

- **Math Ask tutor** → built-in coach (`OLLAMA_ENABLED=0`, default).
- **EEG plugin** → turn on for **simulated** attention on the dashboard.
- **NutriNode** → log meals manually; skip live WebSocket.

When you repair the laptop and buy boards, read **[HARDWARE_AND_AI_LATER.md](./HARDWARE_AND_AI_LATER.md)**.

Optional later:

```env
EEG_ENABLED=1          # after ESP32 firmware → UDP :5005
OLLAMA_ENABLED=1       # only if Ollama installed
FACE_TRACKER_TOKEN=    # JWT for Python face mirror
```

## 5. Export data

Feature Studio → **Download JSON/CSV**, or Profile → account export.

## 6. Health check

- http://localhost:8000/health — `schema_ok: true`
- Build: `npm run build`

## Still planned (not required for daily use)

Community, user-uploaded ingest scripts, doctor review workflow, production PostgreSQL.
