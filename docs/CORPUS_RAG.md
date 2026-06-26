# Corpus / hybrid RAG (optional)
# pip install -r backend/requirements-corpus.txt

See [data/raw_library/README.md](../data/raw_library/README.md) for book layout and [CORPUS_STATUS.md](CORPUS_STATUS.md) for implementation status.

## One-command setup (writes `data/logs/corpus_setup_latest.log`)

```bat
scripts\run_corpus_mml_setup.bat
```

## Manual commands

```bat
python -m backend.corpus.cli ingest --source transcript --path data/transcripts/live_captions_20260623_204143.txt
python -m backend.corpus.cli ingest --source textbook --path data/raw_library/linear_algebra --chapter 1
python -m backend.corpus.cli ingest --source textbook --path data/raw_library/foundations
python -m backend.corpus.cli ingest-all-books
python -m backend.corpus.cli build-golden
python -m backend.corpus.cli ingest-lecture --transcript live_captions_20260623_204143.txt --note live_captions_20260623_204143_20260624_015452.md
python -m backend.corpus.cli query "What is an eigenvalue?" --subject linear_algebra
python -m backend.corpus.cli status
```
