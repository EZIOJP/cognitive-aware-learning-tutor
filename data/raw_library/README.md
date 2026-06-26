# Raw reference library

Copy books here (gitignored binaries). Each subject folder needs `metadata.json` (copy from `metadata.json.example`).

## Layout

```
linear_algebra/     Mathematics for Machine Learning (PDF) — ingest chapters 1–2 first
statistics/         Practical Statistics (PDF) — full-book ingest
foundations/        Data Science from Scratch (PDF)
ml_systems/         Designing ML Systems (PDF)
ai_context/         AI: A Guide for Thinking Humans (PDF)
```

## One-command setup (logs to `data/logs/corpus_setup_latest.log`)

**GUI:** Knowledge Base → **Build Knowledge Base** (MML ch 1–2, transcripts, and any new full PDFs on disk).

```bat
scripts\run_corpus_mml_setup.bat
```

**All PDFs (MML chapters + whole books):**

```bat
python scripts\ingest_all_library_pdfs.py
```

or:

```bat
python -m backend.corpus.cli ingest-all-books
```

PowerShell (copy MML PDF from Downloads):

```powershell
Copy-Item "$env:USERPROFILE\Downloads\Mathematics For Machine Learning*.pdf" `
  "data\raw_library\linear_algebra\Mathematics_for_ML.pdf"
```

Per-book CLI examples:

```
python -m backend.corpus.cli ingest --source textbook --path data/raw_library/linear_algebra --chapter 1
python -m backend.corpus.cli ingest --source textbook --path data/raw_library/foundations
python -m backend.corpus.cli query "What is an eigenvalue?" --subject linear_algebra
```
