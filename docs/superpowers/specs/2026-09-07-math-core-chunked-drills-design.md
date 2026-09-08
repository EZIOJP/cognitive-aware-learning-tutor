# Math Core chunked drills (Keep going / End)

**Status:** approved 2026-09-07  
**Scope:** Math Core worksheet drills only (`MT0-T01`…`T09`)

## Behavior

1. Start a short **chunk** (~12 questions), coverage-biased (~70% unpracticed facts), with combination diversity where applicable (e.g. tables).
2. At chunk end, UI offers **Keep going** (append another chunk) and **End** (close session).
3. **Proficiency** updates only on **correct** answers: per fact key + topic coverage % (`practiced / universe`).
4. GRE / notes / non-MT0 quiz flows unchanged.

## API

- Start practice uses chunk size (not fixed 20).
- `POST /quiz/{session_id}/answer` — on last item: `complete`, `can_keep_going`, `coverage`.
- `POST /quiz/{session_id}/keep-going` — append chunk, return `next_question`.
- `POST /quiz/{session_id}/complete` — End; include `coverage` when Math Core drill.
