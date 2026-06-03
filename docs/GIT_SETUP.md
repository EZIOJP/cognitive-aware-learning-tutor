# Git & GitHub setup

This project uses **Alembic** for schema; after clone run `scripts\migrate.bat` or `scripts\run_all.bat`.

## First-time push (already committed locally)

1. Create an empty repository on GitHub (no README/license — we already have them).
2. In the project folder:

```bat
git remote add origin https://github.com/YOUR_USER/cognitive-aware-learning-tutor.git
git branch -M main
git push -u origin main
```

Replace the URL with your repository.

## Clone on another machine

```bat
git clone https://github.com/YOUR_USER/cognitive-aware-learning-tutor.git
cd cognitive-aware-learning-tutor
scripts\run_all.bat
```

## What is not in the repo

| Path | Reason |
|------|--------|
| `.venv/`, `node_modules/` | Reinstalled by `scripts\_common.bat` |
| `.env` | Secrets — copy from `.env.example` |
| `.browser-profiles/` | Local Chrome/Edge dev profiles |
| `refernces/` | Local reference UI copies |
| `data/logs/` | Generated CSV logs |

`data/vocab_app.db` is included if present so progress/demo data travels with the repo; omit it by uncommenting the line in `.gitignore`.

## GitHub CLI (optional)

```bat
winget install GitHub.cli
gh auth login
gh repo create cognitive-aware-learning-tutor --private --source=. --remote=origin --push
```
