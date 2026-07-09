# Workflow Quick Reference

## Start

```bat
transcript-notes-studio\run.bat
```

Entry: `run_gui.py` → `transcript_studio.gui.main()` → `gui.py`

---

## Four steps (GUI)

### 1 — Capture

- **Live Captions:** enable Windows Live Captions (Win+Ctrl+L), Start → Stop → auto-opens Tune if `auto_open_summarize=true`.
- **Whisper:** file or live system audio → `data/transcripts/live_captions_*.txt`.
- **Lecture Auto:** Capture tab → Start Lecture Auto → idle stop (600s default) → parse → RAG → save → quit.

### 2 — Tune

- Add transcript from library or file list.
- **Parse & preview** — aggressive dedup for `live_captions_*` files.
- Review **Cleanup audit** and **Notes audit** tabs after a generate.
- Save cleaned transcript optional (`test_!.txt` etc.).

### 3 — Generate

**Prerequisites:**

- LLM: LM Studio at `http://127.0.0.1:1234`, model loaded (e.g. `google/gemma-4-e4b`).
- RAG: **Quick init (textbooks + MML)** — indexes textbooks only for notes retrieval.

**Button:** `Generate notes (RAG)` when corpus + LLM ready.

**Options:**

| Setting | Effect |
|---------|--------|
| Quality preset `quality` | Semantic chunking, narrative style, ASR restore, refine pass |
| Coherence mode | `compact` (default), `sequential` (overnight), `cloud_heavy` (heavy LLM tier) |
| Note style | `bullets` (fast/balanced) or `narrative` (quality) |
| Restore punctuation | ASR restore for live captions (`recasepunc` default) |
| Fast mode | Fewer passes, no enrich/refine |
| Auto fast (≥10k words) | Enabled automatically on large tuned text |
| Include diagrams | `enrich_visuals` — mermaid/code pass |
| Legacy pipeline | Forces non-RAG `llm_client` path |

**Output:** `data/notes/<title>_YYYYMMDD_HHMMSS.md`

### 4 — Done

- Open notes folder, Study Library in browser, export insights JSON.

---

## CLI (same engine)

```bat
cd transcript-notes-studio

python -m transcript_studio.cli parse live_captions_20260627_054240.txt --aggressive
python -m transcript_studio.cli generate -i live_captions_20260627_054240.txt -t numpy_lecture --aggressive --fast
python -m transcript_studio.cli lecture-auto --idle 600 --fast
```

---

## Corpus / RAG counts

- **Textbooks** (~5): used during notes RAG.
- **Transcripts + notes** in registry: from old full builds + **corpus handoff** after save — for web quiz, not notes RAG.

UI shows: `N chunks · 5 textbooks (+9 transcripts/notes for quiz)`.

If status shows **SQLite vectors (Qdrant locked)**, close extra Python processes and restart Studio. Use `scripts\run_backend_no_reload.bat` instead of `run_backend.bat` when Studio and API run together.

---

## Qdrant / multi-process

Embedded Qdrant (`data/corpus/qdrant`) allows **one process** at a time.

| Symptom | Fix |
|---------|-----|
| Generate hangs mid-chunk | Kill zombie `python` / stop duplicate Studio or backend |
| `SQLite vectors` in RAG line | Same — another process holds Qdrant; retrieval quality drops |
| `uvicorn --reload` + Studio | Reload spawns two workers — use `scripts\run_backend_no_reload.bat` for corpus work |

---

## Notes health

- Status bar shows **LINT_FAILED** warning if broken mermaid/code blocks were saved with markers.
- Status bar shows **NARRATIVE_LOW** if heuristic narrative score is below 3 (try quality preset or sequential coherence).
- Grep: `findstr /s /m LINT_FAILED data\notes\*.md`
- Grep: `findstr /s /m NARRATIVE_LOW data\notes\*.md`

---

## Log files

| File | Content |
|------|---------|
| `data/logs/transcript_studio.log` | GUI actions, parse word counts |
| `data/logs/notes_generation.log` | Chunk summarize, RAG, enrich |
| `data/logs/lecture_auto_*.json` | Lecture Auto run summary |

**Healthy generate log line:** `RAG mode: retrieving corpus chunks per segment…` then `Hybrid RAG notes: N words`.

---

## File trace for “Generate” click

1. `gui.py` → `_run_summarize`
2. `notes_generator.py` → `generate_notes_from_file`
3. `backend_note_generation.py` → `generate_notes_unified`
4. `backend_hybrid_notes.py` OR `backend_grounded_notes.py`
5. `backend_retrieve.py` + `backend_llm_gateway.py`
6. `backend_note_enrich.py` (if enrich on)
7. Write `data/notes/*.md` + optional handoff
