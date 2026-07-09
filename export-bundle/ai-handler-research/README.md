# AI Handler Research Export

Portable snapshot of **49 files** for offline research (Google Drive, notebooks, etc.).

Every file in this folder is an **exact copy** of the live monorepo at the same relative path.  
**Index:** see [`INDEX.md`](INDEX.md) for the full numbered map and reading order.

## Start here

1. [`INDEX.md`](INDEX.md) — complete file list with descriptions  
2. [`docs/AI_HANDLER.md`](docs/AI_HANDLER.md) — subsystem overview  
3. [`docs/AI_HANDLER_BACKEND.md`](docs/AI_HANDLER_BACKEND.md) or [`docs/AI_HANDLER_FRONTEND.md`](docs/AI_HANDLER_FRONTEND.md)

## Zip for upload

From repo root:

```powershell
Compress-Archive -Path "export-bundle\ai-handler-research\*" -DestinationPath "export-bundle\ai-handler-research.zip" -Force
```

Upload `ai-handler-research.zip` to Google Drive.

## Do not commit secrets

This bundle includes `.env.example` only. Never copy your real `.env` (API keys) into Drive.
