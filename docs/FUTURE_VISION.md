# Future Vision

Long-term **Smart Pomodoro / cognitive-aware math tutor**. Detailed math+vision engineering spec: [MATH_TUTOR_VISION_PIPELINE.md](./MATH_TUTOR_VISION_PIPELINE.md).

## Product thesis

```text
An AI study companion that notices when the learner is stuck and gives the right
hint at the right moment.
```

Biometrics (EEG, face, gaze) are **optional signals**. Core value = timely Socratic help on the whiteboard.

## North star loop

```text
student writes math
  → stroke + pause + (optional) EEG/face/gaze
  → stuckness score
  → cropped canvas snapshot
  → OCR/LaTeX or vision fallback
  → local Socratic hint (JSON, no full answer)
  → session logs (DSC_*) for better future hints
```

## Phase map (aligned with ROADMAP)

| Roadmap | Vision | Hardware |
|---------|--------|----------|
| Phase 1 GRE | Done | None |
| Phase 2 | Real EEG, Nutri ESP32, face calibration file | ESP32, webcam |
| **Phase 3 Math AI** | Stuckness + OCR + structured Ollama | Laptop + GPU optional |
| Phase 4 | Community, webhooks, production DB | Server |

### Phase 3 sub-phases (software-first)

See [MATH_TUTOR_VISION_PIPELINE.md](./MATH_TUTOR_VISION_PIPELINE.md):

- **3a** — Stuckness heuristic, debounced snapshots, intervention UI, CSV logging (**no GPU**)
- **3b** — Ollama structured Socratic JSON + `keep_alive` VRAM policy
- **3c** — OpenCV + Pix2Text/pix2tex + SymPy incomplete-step detection
- **3d** — WebGazer + real EEG/face in stuckness weights

**Today:** rule-based Ask tutor + manual hint; 3a is the next coding slice.

## Vision stack choices (RTX 5060 / 8 GB)

- **Canvas:** keep `react-sketch-canvas`; add `exportPaths`, coalesced pointer kinematics, bbox crop on export.
- **Recognize:** Pix2Text or pix2tex → LaTeX → text LLM; LLaVA only when OCR marks incomplete or low confidence.
- **Tutor:** Ollama with Pydantic `format=` schema; never send full history of base64 images—text hints + LaTeX only.
- **VRAM:** one model resident during study; flush after Pomodoro break.

## Stuckness score (v1 weights)

Combine (tunable):

- Gamma / cognitive load vs baseline
- Canvas idle after last stroke
- Eraser burst count
- Wrong answer streak (math practice)
- Face attention drop (Python mirror)
- Later: gaze fixation on equation bbox (WebGazer)

Do **not** trigger on gamma alone.

## Data flywheel (Phase 4)

Append-only CSVs (not SQLite blobs):

```text
DSC_Kinematics.csv      stroke velocity, paths, pauses
DSC_Biometrics.csv      EEG bands, face_attention
DSC_Interventions.csv   hint JSON, snapshot path, learner_recovered
```

Snapshots on disk: `data_logs/interventions/{session_id}/`.

Example record:

```json
{
  "session_id": "hub-42",
  "topic": "linear_equations",
  "canvas_snapshot": "data_logs/interventions/hub-42/step3.png",
  "eeg_window": { "gamma": 78.4 },
  "behavior": { "canvas_inactive_seconds": 47, "eraser_events": 3 },
  "stuckness_score": 0.86,
  "hint_given": "What operation undoes the constant on the left?",
  "learner_recovered": true
}
```

## Consumer ladder

1. **Software-only** stuckness-aware tutor (no ESP32, no Ollama required for rules)
2. **Prosumer lab** — Ollama + optional EEG/face
3. **Wearable ecosystem** — ESP32 EXG + polished hardware path

Finish (1) before buying hardware. See [HARDWARE_AND_AI_LATER.md](./HARDWARE_AND_AI_LATER.md).

## Out of scope for near term

- Cloud APIs (privacy-first local default)
- Nougat full-document OCR (wrong tool for whiteboard crops)
- Character-by-character CNN OCR (fails on connected handwriting; use LaTeX OCR or VLM fallback)
- Continuous LLaVA on every frame
