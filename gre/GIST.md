# Gist — GRE vocab + math practice + OCR

## One sentence

**GRE vocab** is a signed-in mastery cycle (read → adaptive quiz → report → weak words again). **Math practice** is whiteboard + question bank + tutor hints. **Math OCR** turns canvas ink into LaTeX and (when stuck) triggers a Socratic intervention.

## Three lanes (do not mix)

| Lane | Job | Primary API | Primary UI |
|------|-----|-------------|------------|
| **A. Vocab cycle** | Learn word groups; persist mastery | `/api/vocab` | `/gre-vocab`, `/gre-vocab/cycle` |
| **B. Math practice** | Drill topics; ask for hints | `/api/math/tutor/*`, questions | `/math-tutor/practice/:topicId` |
| **C. Math OCR / intervention** | Ink → LaTeX → hint when stuck | `/api/math/ocr`, `/intervention` | Practice + `/math-tutor/train` |

Shared: one FastAPI app (`backend/main.py`), one SQLite (`data/vocab_app.db`), optional Ollama / NIM.

**Not this pack:** lecture RAG notes, global `/api/quiz` SRS (different quiz path from vocab adaptive quiz).

---

## Happy path A — GRE vocabulary

```text
Login (JWT)
  → GRE hub (/gre-vocab) loads groups + progress
  → Cycle: pick group
      → Read words (markWordRead → POST progress)
      → Adaptive quiz (/api/vocab/quiz/adaptive/*)
      → Report
      → Low-mastery prompt → read weak words → quiz again (max ~5)
```

Guest (not signed in): `words.json` + `localStorage` via `vocabStore` — **no merge** with server progress.

---

## Happy path B — Math practice

```text
Math hub → topic → practice page
  → load / generate question from bank
  → draw on whiteboard (MathSplitWhiteboard / MathGridCanvas)
  → Ask tutor → POST /api/math/tutor/hint
       (rule_tutor default; ollama_tutor if OLLAMA_ENABLED=1)
  → attempt logged → hub math_attempt reading (when wired)
```

---

## Happy path C — OCR + stuckness intervention

```text
Practice / Train canvas
  → idle + eraser + EEG-sim score → stuckness > 0.5
  → exportPng + paths_json
  → POST /api/math/intervention
       → OpenCV crop / mask
       → TexTeller ONNX (± Ollama vision / NIM)
       → SymPy / hallucination guards
       → Socratic hint (rule or Ollama)
       → DSC CSV + snapshot PNG under data_logs/
```

Manual OCR only: `POST /api/math/ocr` (Train / Recognize pages).

---

## Order of systems (designer checklist)

```text
1. Auth JWT          → vocab progress + admin
2. Word groups       → read criteria APIs
3. Adaptive quiz     → cycle UI only (not /api/quiz)
4. Math question DB  → practice page
5. Rule tutor        → always-on fallback
6. OCR stack         → TexTeller → vision fallbacks
7. Intervention      → stuckness gate → OCR → hint → log
8. Hub readings      → optional telemetry (vocab_quiz_complete, math_attempt)
```

---

## Configure in 60 seconds

```env
# Vocab / shared DB (defaults OK for local)
# DATABASE_URL=sqlite:///.../data/vocab_app.db

# Math tutor LLM (optional)
OLLAMA_ENABLED=0          # 0 = rule-based hints only
OLLAMA_VISION_MODEL=...   # OCR incomplete-step fallback

# OCR extras
# NIM_API_KEY=...         # optional teacher labels
# scripts\install_ocr.bat # ONNX / OpenCV deps
```

Frontend: `src/config.ts` — `intervention.enabled`, `intervention.autoTrigger`, `dev.useSimulatedData`.

---

## Failure cheat sheet

| Symptom | Likely cause |
|---------|----------------|
| Hub empty / retry banner | Backend down or not logged in |
| Cycle quiz 404 | Bad/expired adaptive session id |
| Progress not saving | Guest mode (localStorage only) or missing JWT |
| Hint is generic rules | `OLLAMA_ENABLED=0` (expected) |
| OCR = `\begin{array}` garbage | Grid noise / hallucination guard; use ink-only export + Train cells |
| Intervention never fires | Stuckness thresholds / cooldown / `autoTrigger=false` |
| OCR import fails | Missing TexTeller ONNX / run `install_ocr.bat` |

---

## Dual quiz warning (easy footgun)

| Path | Use for |
|------|---------|
| `/api/vocab/quiz/adaptive/*` | GRE **cycle** only |
| `/api/quiz/*` | Lecture / global SRS / study-flow |

Do not wire CycleManager to global quiz.
