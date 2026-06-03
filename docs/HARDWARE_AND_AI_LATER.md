# Hardware & local AI — when you are ready

You can use the app **fully today** on any laptop (even while yours is in repair — borrow a machine or use a school PC). No GPU, no ESP32 boards, no Ollama required.

This doc is the **motivation map**: software is already wired; buying hardware or fixing your laptop only **unlocks richer data**, not basic study flows.

---

## What works right now (zero extra purchases)

| Area | Today | Needs hardware / GPU? |
|------|--------|------------------------|
| GRE vocab, math practice, Life Tracker | Yes | No |
| Dashboard, plugins, Feature Studio, export | Yes | No |
| **Ask tutor** on math | Rule-based coach (topic + stress aware) | No |
| **AI Review** on home | Hub stats + templates | No |
| **EEG plugin** | Frontend **simulation** + hub metric when enabled | No (simulation) |
| **NutriNode** | Manual meals + REST; live WS off by default | No (manual log) |
| **Focus Mirror** | Optional: any PC webcam + `run_face_tracker.bat` | Webcam only (no ESP32) |
| Browser extension → Life Tracker | Yes | No |

Default config: `EEG_ENABLED=0`, `OLLAMA_ENABLED=0` in `.env` (see `.env.example`).

---

## When your laptop is back (optional — local AI)

Only if you want **smarter** math hints or vision on the whiteboard:

1. Install [Ollama](https://ollama.ai) on a machine with enough RAM (GPU helps but small models can run on CPU).
2. In `.env`:
   ```env
   OLLAMA_ENABLED=1
   OLLAMA_URL=http://127.0.0.1:11434
   OLLAMA_MODEL=llama3.2
   ```
3. Math **Ask tutor** will try Ollama once; if it fails, you still get rule-based hints.

**If repair means no GPU:** leave `OLLAMA_ENABLED=0` forever — the product is designed for that.

Future (not built yet): cloud API key for hints without local GPU — see [ROADMAP.md](./ROADMAP.md).

---

## Shopping list (when you want real sensors)

### EEG (Focus / cognitive load plugin)

| Item | Role |
|------|------|
| ESP32-S3 (or similar) | Send UDP packets to PC port **5005** |
| BioAmp EXG Pill + electrodes | Signal (project-specific firmware) |

**Software already done:**

- Backend: `EEG_ENABLED=1` → UDP ingest → WebSocket `/ws/eeg` → hub `eeg_attention`
- Frontend: set `config.dev.useSimulatedData = false` when using real stream

**After purchase:** flash firmware (see [firmware/EEG_ESP32.md](./firmware/EEG_ESP32.md)), enable EEG plugin, set `.env`:

```env
EEG_ENABLED=1
```

### NutriNode (nutrition plugin)

| Item | Role |
|------|------|
| ESP32 + scale / sensor board | Auto log meals (your hardware design) |

**Software already done:**

- Manual logging + daily totals today
- Live WebSocket optional (`nutrinode:live_ws` in browser storage)

**After purchase:** device posts to your ingest API / WS — see [firmware/NUTRI_ESP32.md](./firmware/NUTRI_ESP32.md).

### Focus Mirror (no ESP32)

Uses **Python + OpenCV** on the laptop (`backend/face_tracker.py`). Any USB webcam works once the laptop is back.

---

## Suggested order (motivating path)

1. **Now** — Run `run.bat`, sign in, enable Math + Vocab + Life, use dashboard + Feature Studio (borrow laptop if needed).
2. **Laptop repaired** — Chrome extension + optional face tracker + manual NutriNode.
3. **First board** — EEG ESP32 (biggest “wow” on dashboard widget).
4. **Second board** — NutriNode automation.
5. **Optional** — Ollama on a capable machine for LLM hints.

---

## Roadmap alignment

- **Phase 1** (GRE polish) — no hardware.
- **Phase 2** (hardware loops) — firmware + your boards; app side ready.
- **Phase 3** (math AI) — Ollama/vision optional; rule tutor shipped.

See [ROADMAP.md](./ROADMAP.md) and [WORKING_PRODUCT.md](./WORKING_PRODUCT.md).
