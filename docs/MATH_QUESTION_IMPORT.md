# Math question import (draft format)

Import endpoints accept JSON while the canonical file format is finalized.

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| POST | `/api/math/questions/import/json` | Admin |
| POST | `/api/math/questions/import/file` | Admin (`.json` upload) |
| POST | `/api/math/questions/import/preview` | Admin (validate only) |
| GET | `/api/math/questions/export/json?topic=` | Admin |
| GET | `/api/math/questions` | User (list, no answers in list view) |

Practice still uses `/api/vocab/math/practice/next` — it picks from the **bank first**, then template generator.

## Draft envelope (`format_version: 1`)

```json
{
  "format_version": 1,
  "topic": "Algebra",
  "source": "gre-pack-2026",
  "questions": [
    {
      "external_id": "alg-001",
      "prompt": "Solve: 2x + 5 = 13",
      "expected_answer": "4",
      "explanation": "Subtract 5, divide by 2.",
      "latex": "",
      "difficulty": "easy",
      "tags": ["linear"],
      "answer_format": "plain",
      "metadata": {}
    }
  ]
}
```

## Shorthand (also supported)

- Root **array** of question objects (each must include `topic`).
- Aliases: `question` → `prompt`, `answer` → `expected_answer`.

## Upsert rules

- If `external_id` is set: upsert per `(topic, external_id)`.
- Otherwise: always insert a new row.
- Extra keys are stored in `metadata_json` when passed as `metadata` on the item.

## Randomizer

`backend/math/services/randomizer.py` — `pick_from_bank(db, topic)` is used by practice/next. Template generator runs only when the bank has no rows for that topic.

## Seed local sets (dev)

```bat
python -m backend.scripts.import_local_math_bank
```

Maps the same items as `LOCAL_QUESTION_SETS` in the frontend into SQLite.
