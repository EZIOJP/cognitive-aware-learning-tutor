@echo off
setlocal
cd /d "%~dp0.."
echo Corpus ingest helper — see docs\CORPUS_RAG.md
echo.
echo Examples:
echo   python -m backend.corpus.cli status
echo   python -m backend.corpus.cli ingest --source transcript --path data\transcripts\YOUR_FILE.txt
echo   python -m backend.corpus.cli ingest --source textbook --path data\raw_library\linear_algebra --chapter 1
echo.
if "%~1"=="" (
  python -m backend.corpus.cli status
) else (
  python -m backend.corpus.cli %*
)
