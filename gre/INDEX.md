# INDEX — GRE vocab + math practice + OCR

**Folder:** `gre/`  
**Purpose:** Architecture gist + HLD/LLD for designers working on GRE prep loops.

## Docs

| File | Description |
|------|-------------|
| [README.md](README.md) | Pack intro + scope |
| [GIST.md](GIST.md) | 2-minute mental model + failure cheat sheet |
| [HLD.md](HLD.md) | High-level — contexts, study loops, contracts |
| [LLD.md](LLD.md) | Low-level — endpoints, call graphs, modules |
| [FILE_MAP.md](FILE_MAP.md) | Routes, frontend, backend anchors |

## Suggested research order

1. GIST → HLD → LLD → FILE_MAP  
2. Vocab: `CycleManager.tsx` + `backend/vocab/routes.py`  
3. Math practice: `MathPracticePage.tsx` + `backend/math/router.py`  
4. OCR: `ocr_service.py` → `intervention_handler.py` → canvas export  
5. Smoke: login → vocab cycle → math practice Ask tutor → Train recognize digit

## Related live docs (not copied)

- `docs/GRE_VOCAB_PHASE1.md`
- `docs/MATH_TUTOR_VISION_PIPELINE.md`
- `docs/CANVAS_OCR_ROADMAP.md`
- `docs/HLD.md` / `docs/LLD.md`
- `AGENTS.md` — do not extend `UniversalReadMode.jsx`
