# FILE_MAP — GRE vocab + math practice + OCR

Quick anchors for the GRE lane. Prefer this pack’s [LLD.md](LLD.md) for call graphs.

---

## 1. Frontend routes

### GRE vocab (`src/plugins` / core plugins)

| URL | Page / component |
|-----|------------------|
| `/gre-vocab` | `src/pages/GreVocabPage.tsx` |
| `/gre-vocab/read` | `src/pages/vocab/VocabReadPage.tsx` |
| `/gre-vocab/read/:mode` | same + `ReadMode.tsx` filters |
| `/gre-vocab/cycle` | `src/pages/vocab/VocabCyclePage.tsx` → `CycleManager.tsx` |
| `/gre-vocab/add-words` | Add words UI |
| `/login` | `src/pages/auth/LoginPage.tsx` |
| `/admin` | `src/pages/admin/AdminPanelPage.tsx` |

### Math tutor

| URL | Page |
|-----|------|
| `/math-tutor` | Math hub (plugin) |
| `/math-tutor/topic/:topicId` | `src/pages/math/MathTopicPage.tsx` |
| `/math-tutor/practice/:topicId` | `src/pages/math/MathPracticePage.tsx` |
| `/math-tutor/train` | `src/pages/math/TrainPlaygroundPage.tsx` |
| `/math-tutor/recognize-test` | `src/pages/math/MathRecognizeTestPage.tsx` |
| `/math-tutor/reports` | `src/pages/math/MathReportsPage.tsx` |

---

## 2. Vocab frontend

| Role | Path |
|------|------|
| Hub | `src/pages/GreVocabPage.tsx` |
| Read UI | `src/features/vocab/components/read/ReadMode.tsx` |
| Word card | `src/features/vocab/components/read/WordCard.tsx` |
| Cycle orchestrator | `src/features/vocab/cycle/components/CycleManager.tsx` |
| Cycle dashboard | `src/features/vocab/cycle/components/CycleDashboard.tsx` |
| Cycle read | `src/features/vocab/cycle/components/CycleReadStep.tsx` |
| Cycle quiz | `src/features/vocab/cycle/components/CycleQuizStep.tsx` |
| Cycle report | `src/features/vocab/cycle/components/CycleReportStep.tsx` |
| Low-mastery prompt | `src/features/vocab/cycle/components/LowMasteryPrompt.tsx` |
| Guest store | `src/features/vocab/store/vocabStore.ts` |
| Cycle local logic | `src/features/vocab/cycle/cycleService.ts` |
| Auth client | `src/features/vocab/api/authClient.ts` |
| Read helpers | `src/features/vocab/api/readModeAPI.ts` |
| Types | `src/features/vocab/types.ts`, `cycle/types.ts` |
| Word JSON | `public/data/words.json` |

**Legacy — do not extend:** `src/features/vocab/components/UniversalReadMode.jsx`

---

## 3. Math frontend

| Role | Path |
|------|------|
| Practice | `src/pages/math/MathPracticePage.tsx` |
| Topic | `src/pages/math/MathTopicPage.tsx` |
| Train | `src/pages/math/TrainPlaygroundPage.tsx` |
| Recognize test | `src/pages/math/MathRecognizeTestPage.tsx` |
| Reports | `src/pages/math/MathReportsPage.tsx` |
| Split whiteboard | `src/app/components/MathSplitWhiteboard.tsx` |
| Intervention UI | `AITutorIntervention` (mounted on practice) |
| Session / stuckness | `src/context/StudySessionContext.tsx` |
| App config | `src/config.ts` |

---

## 4. Backend

| Role | Path |
|------|------|
| App entry | `backend/main.py` |
| Vocab routes | `backend/vocab/routes.py` |
| Vocab quiz store | `backend/vocab/quiz_store.py` |
| Math router | `backend/math/router.py` |
| Rule tutor | `backend/math/rule_tutor.py` |
| Ollama tutor | `backend/math/ollama_tutor.py` |
| OCR service | `backend/math/ocr_service.py` |
| TexTeller | `backend/math/texteller_onnx.py` |
| Intervention | `backend/math/intervention_handler.py` |
| Intervention log | `backend/math/intervention_log.py` |
| Train service | `backend/math/training_service.py` |
| SQLite | `data/vocab_app.db` |
| OCR install | `scripts/install_ocr.bat` / `.sh` |
| TexTeller download | `scripts/download_texteller.bat` |

**Legacy shim:** `backend/vocab_backend.py` — do not add features there.

---

## 5. Auth / token

| Item | Value |
|------|-------|
| Token key | `vocab:auth-token` |
| API base | `VITE_VOCAB_API_BASE` or `http://localhost:8000/api/vocab` |
| Group size | `GROUP_SIZE = 30` |

---

## 6. Dual data / dual quiz

| Concern | Path A | Path B |
|---------|--------|--------|
| Vocab progress | JWT + SQLite | Guest `vocabStore` + localStorage |
| Quiz | `/api/vocab/quiz/adaptive/*` (cycle) | `/api/quiz/*` (lecture / global SRS) |

---

## 7. Tests (when changing OCR / vocab)

| Area | Tests |
|------|-------|
| Math OCR | `tests/test_math_ocr.py` |
| Stroke metrics | `tests/test_stroke_metrics.py` |
| Vocab / broader | see `tests/` + Sprint 4 regression in `docs/COMPLETION_SPRINT.md` |
