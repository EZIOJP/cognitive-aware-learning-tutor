# Transcript Notes Studio

Standalone desktop tool for **live-caption transcript cleanup** and **LLM summarization** into markdown lecture notes.

Extracted from the Cognitive-Aware Learning Tutor project — no FastAPI, database, or React required.

## Features

- **Summarize & combine** — `.txt` transcript + `.pdf` / `.ipynb` / `.md` references; 3-pass pipeline (sections → refine → Colab enrich)
- **Live Captions** — built-in Windows 11 scraper tab (Win+Ctrl+L); no separate batch file needed
- **Transcribe audio** — separate Whisper tab (optional slide capture); send result to Summarize when done
- **Parse** — dedupe lines, remove fillers/stutters, optional aggressive mode for Windows Live Captions snapshots
- **2nd-pass refine** — stitch chunk summaries into one flowing document; merge duplicate topics
- **Context folder** — load `.md`, `.txt`, `.pdf`, `.ipynb`, `.py` prereqs/notebooks into summaries
- **Slide capture** — screenshots during Whisper ASR; embedded in notes via `[SNAPSHOT N]` markers
- **GUI** — two-mode tabbed app (Summarize | Transcribe)
- **CLI** — scriptable batch generation

## Quick start (Windows)

```bat
cd transcript-notes-studio
run.bat
```

1. Put `.txt` transcripts in `data/transcripts/` (or transcribe on the **Transcribe audio** tab)
2. Start **LM Studio** or **Ollama** with your model loaded
3. **Summarize & combine** tab → Add file(s) (`.txt`, `.md`, `.pdf`) or double-click from library → **Generate notes**
4. Notes appear in `data/notes/` (or your chosen output folder)

## Manual setup

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env
python run_gui.py
```

`run.bat` ensures `requirements.txt` (including `sentence-transformers`) is installed on every launch.

## CLI

```bat
.venv\Scripts\python -m transcript_studio.cli --latest --title "EDA recap"
.venv\Scripts\python -m transcript_studio.cli -i slides.pdf --title "Lecture PDF"
.venv\Scripts\python -m transcript_studio.cli -i my_lecture.txt --aggressive
.venv\Scripts\python -m transcript_studio.cli -i lecture.txt --context ./prereqs --no-refine
.venv\Scripts\python -m transcript_studio.cli --parse-only live_captions.txt
```

## Whisper (audio → transcript)

Install once (GPU recommended):

```bat
install_whisper.bat
```

In the GUI **Whisper ASR** section:

1. Pick model preset (`openai/whisper-large-v3-turbo` recommended)
2. **From audio file:** browse `.mp3`/`.wav` → **Transcribe → .txt**
3. **Live microphone:** set chunk size → **Start live mic** → **Stop & save** when done
4. Then switch to **Summarize & combine**

| Mode | How it works |
|------|----------------|
| **Audio file** | Full-file batch transcribe (transformers or faster-whisper) |
| **Live Whisper** | Chunks (~10s) via faster-whisper; **System audio** = what you hear (WASAPI) |
| **Live Captions tab** | Instant Windows captions (Win+Ctrl+L) — best for live lectures on screen |

Live Whisper is **not** instant word-by-word captions; it batches speech every N seconds.

| Setting | Options |
|---------|---------|
| Engine | `transformers` (Hugging Face) or `faster-whisper` (lighter) |
| Model | HF presets or custom ID |
| Device | `auto`, `cpu`, `cuda:0` |
| Task | `transcribe` or `translate` (to English) |

**Note:** `xkeyC/whisper-large-v3-turbo-gguf` is a GGUF quant — this app uses the equivalent
[`openai/whisper-large-v3-turbo`](https://huggingface.co/openai/whisper-large-v3-turbo) weights via Transformers.
Paste the xkeyC ID in **Model ID** and it will auto-map.

### Slide capture + context (new)

1. Enable **Capture screenshots while transcribing** before **Transcribe → .txt**
2. Set **Auto every (sec)** (e.g. `120`) or use **Snap now** during transcription
3. Screenshots land in `data/sessions/<lecture>_<timestamp>/snapshots/` as `001_…png`, `002_…png`
4. Transcript gets `[SNAPSHOT N]` markers aligned to Whisper segment times
5. Set **Context folder** to a folder with prereq `.md`, `.ipynb`, etc.
6. Enable **2nd pass — stitch topics & refine flow** (on by default)
7. **Generate notes** embeds slide images and weaves context into the final `.md`

Requires `Pillow` (`pip install Pillow`) for screenshots on Windows.

## Windows Live Captions (GUI)

First-time setup:

```bat
install_captions.bat
```

In the GUI **Live Captions** tab:

1. Press **Win+Ctrl+L** to turn on Windows Live Captions during your lecture
2. Click **Start capture** — lines appear in the log as they are read
3. Click **Stop & save** when the lecture ends
4. Transcript saves to `data/transcripts/live_captions_<timestamp>.txt`
5. Click **Send last transcript → Summarize** (aggressive dedup is turned on automatically)

| Setting | Meaning |
|---------|---------|
| Method `uia` | Read caption text directly (recommended) |
| Method `ocr` | Screenshot fallback (needs Tesseract) |
| Poll (sec) | How often to read the caption panel |
| Max duration | Auto-stop after N seconds (0 = until you press Stop) |

## Configuration

Settings are stored in `config.json` (created when you click **Save settings** in the GUI).

Optional `.env` overrides:

| Variable | Default |
|----------|---------|
| `LLM_ENABLED` | `1` |
| `LLM_PROVIDER` | `lmstudio` |
| `LLM_BASE_URL` | `http://127.0.0.1:1234` |
| `LLM_MODEL` | `google/gemma-4-e4b` |

Providers: `lmstudio`, `ollama`, `openai` (OpenAI-compatible `/v1/chat/completions`).

## Project layout

```
transcript-notes-studio/
  run.bat              # Windows launcher (venv + GUI)
  run_gui.py
  requirements.txt
  data/
    transcripts/       # input .txt files
    notes/             # output .md files
    sessions/          # ASR sessions + snapshots
  transcript_studio/
    cleanup.py         # parser / dedup / markdown repair
    notes_generator.py # summarization + 2nd-pass refine
    snapshots.py       # slide capture + marker merge
    source_loader.py   # .txt / .md / .pdf text extraction
    context_loader.py  # prereq / ipynb / pdf folder loader
    llm_client.py      # LM Studio / Ollama / OpenAI
    whisper_client.py  # Whisper ASR with segment timestamps
    gui.py             # tkinter UI
    cli.py
    config.py
  tests/
```

## Export as its own repo

Copy the entire `transcript-notes-studio/` folder to a new repository. It has no imports from the parent project.

```bat
xcopy /E /I transcript-notes-studio C:\path\to\new-repo
```

Or zip and share:

```bat
tar -acf transcript-notes-studio.zip transcript-notes-studio
```

## Tests

```bat
.venv\Scripts\python -m pytest tests/ -q
```

## Relationship to main app

| Main app (`backend/transcripts/`) | This project |
|-----------------------------------|--------------|
| FastAPI routes + SQLite KB | Files only |
| Study Library UI | Standalone GUI |
| Same `cleanup.py` logic | Vendored copy |
| Same summarization prompts | Vendored copy |

When you improve cleanup or prompts here, you can sync changes back to `backend/transcripts/cleanup.py` and `notes_generator.py` manually.
