# Data directory

| Path | Purpose |
|------|---------|
| `vocab_app.db` | SQLite — per-user vocab progress (local dev) |
| `plate_images/` | NutriNode upload images (created at runtime) |
| `pipeline_output/` | NutriNode pipeline CSV/JSON output |

Do not commit production secrets. `vocab_app.db` is local prototype state.
