# User features & plugins

## For users

### Enable a built-in module

1. Sign in (syncs preferences to the server).
2. **Settings → Plugin Manager** — toggle **Math Tutor**, **EEG**, **Focus Mirror**, Life Tracker, NutriNode, etc.
3. **Core Hub** only (dashboard + settings) stays on; everything else is optional.

### Add your own feature (no code)

1. **Settings → Feature Studio**
2. Name your feature, pick a URL slug (e.g. `water`).
3. Add one or more **metrics** (label + slug + unit).
4. Submit — you get a sidebar link and dashboard widget.
5. Open the feature page to **log readings**; data is stored in the hub (`readings` table with `recorded_at` timestamps).
6. **Feature Studio → Export central data** for JSON/CSV hub export.

Custom features sync per account via `user_features` and `user_plugins`.

### Developers: ship a coded plugin

1. `src/plugins/my_plugin/index.tsx` — `PluginDef` + `registerPlugin()`
2. `src/plugins/index.ts` — import the module
3. `backend/hub/services/catalog.py` — add catalog entry + default metrics
4. Users enable it in Plugin Manager

## API (authenticated)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/hub/features/catalog` | Built-in module catalog + metrics |
| GET | `/api/hub/plugins` | User plugin toggles + custom features |
| PUT | `/api/hub/plugins` | Enable/disable `{ plugin_id, enabled }` |
| GET | `/api/hub/features/custom` | List custom features |
| POST | `/api/hub/features/custom` | Create feature + metrics |
| DELETE | `/api/hub/features/custom/{id}` | Remove custom feature |
| GET | `/api/hub/metrics` | Metrics available for enabled modules |
| POST | `/api/hub/readings` | Log a value `{ readings: [{ slug, value_numeric }] }` |

## Database

- `user_plugins` — on/off per user (built-in + custom `feature_id`)
- `user_features` — custom feature metadata
- `reading_definitions` — system + per-user metric slugs (`u{userId}_{slug}`)

Run migrations: `alembic upgrade head`
