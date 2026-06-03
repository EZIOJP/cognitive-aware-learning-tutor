# Roadmap

## Philosophy

**Ship software first** on any PC (no GPU, no ESP32). Hardware and local AI are **plug-in upgrades** that motivate purchases — they are not blockers for GRE, math, life tracking, or the hub.

See **[HARDWARE_AND_AI_LATER.md](./HARDWARE_AND_AI_LATER.md)** for the buy-when-ready guide.

---

## Done (2026-06) — software path

- [x] Modular plugins + Feature Studio + hub export
- [x] Math Tutor plugin + **rule-based Ask tutor** (no Ollama required)
- [x] EEG + NutriNode optional plugins with **simulation / manual** defaults
- [x] Dashboard AI review, layout sync, browser stats
- [x] EEG WebSocket + UDP service (`EEG_ENABLED`) — waiting on your ESP32 firmware
- [x] Face calibration + Python mirror (webcam when laptop is back)
- [x] `OLLAMA_ENABLED=0` by default — opt-in local LLM later
- [x] Firmware placeholder docs (`docs/firmware/`)

---

## Phase 1 — GRE Vocabulary polish (no hardware) ✅

- [x] Audit read / cycle / low-mastery routes — API wired; see [GRE_VOCAB_PHASE1.md](./GRE_VOCAB_PHASE1.md)
- [x] Empty and error states (hub, read, cycle, admin)
- [x] Admin reset/export workflows (group JSON/CSV, fixed import/export bugs)
- [x] `POST /progress/{word_id}/read` for server-backed Read Mode

**You can use the app fully during this phase without boards or GPU.**

---

## Phase 2 — Real hardware (when you buy ESP32)

- [ ] Flash EEG firmware → UDP :5005 → `/ws/eeg` → hub `eeg_attention`
- [ ] Flash NutriNode firmware → ingest / live WS
- [ ] Face tracker reads calibration JSON from hub

App side: **ready**. See `docs/firmware/EEG_ESP32.md` and `NUTRI_ESP32.md`.

---

## Phase 3 — Math AI (optional, after laptop repair)

- [x] Rule-based tutor hints (default)
- [ ] Enable `OLLAMA_ENABLED=1` + vision model for whiteboard snapshots
- [ ] EEG + face triggers on practice page (data paths exist)

---

## Phase 4 — Platform (later)

- [ ] Community plugin
- [ ] User webhooks / sandbox ingest scripts
- [ ] Cloud API option for hints (no local GPU)
- [ ] PostgreSQL + production Docker
