# Bible study v2 — chapter-a-day + watch verses (no PDF required)

**Date:** 2026-07-23  
**Status:** Approved — implementing  
**You said you care about:**  
1. Use Bible **without PDF**  
2. Proper daily goal = **one chapter**  
3. After **study + Bible**, unlock games for the rest of the day (afternoon OK)  
4. **Watch** rotates verses from chapters you read **today**  
5. Structured data (JSON) for freedom — not PDF pages  

---

## Product north star

```text
Morning/anytime: Read & tick 1 chapter (JSON verses)
        +
Study hits daily productive goal
        ↓
Unlimited games until midnight (afternoon / evening fine)
        +
Watch shows a rotating verse from today's read chapter(s)
```

PDF is **not required**. Optional “open old GNB PDF” can stay as a buried link; credit and goals use structured text only.

---

## Steal sheet (compressed)

| Idea | From | Use in CALT |
|------|------|-------------|
| `GET /read/{version}/{book}/{chapter}` → verses[] | BibleApi | Our local FastAPI |
| Book → chapter → verse JSON | javascripture / WEB | `data/bible/structured/web.json` |
| Chapter-first UX | mdbible pattern | Book + chapter chips + verse list |
| Ref helpers later | pythonbible | Optional “jump to John 3:16” |
| Skip for v1 | Beblia dump, live Deno host, ESV/NVI packs | — |

---

## Goals & unlock rules (sensible redesign)

### Daily Bible goal
- **Complete 1 chapter today** (read in verse UI + tick, or auto-complete when you leave the chapter after spending a short dwell — see below).
- Shown as: `Bible today: 0/1 chapter` (not only minutes).

### Unlock modes

| Mode | Condition | Games |
|------|-----------|--------|
| **Locked** | Hard-block on, no pass, no chapter done (or no study+chapter for unlimited) | Kill games / TM when locked |
| **Chapter bank (optional keep)** | Each completed chapter beyond the first can still add bank *or* we simplify — **default: first chapter satisfies Bible side of unlimited; extra chapters optional** | See default below |
| **Day unlimited** | `productive ≥ study goal` **AND** `≥ 1 chapter completed today` | Unlimited until local midnight — **covers afternoon/evening** |
| **Day pass** | Weekly controlled skip (type `PASS`, 2/week) | Unlimited until midnight without reading |

**Default simplification (recommended):**  
Drop “30 min → 30 min bank” as the *primary* habit. Replace with:

1. **1 chapter / day** = Bible requirement for unlimited (with study goal).  
2. Keep a light **optional** bank later if you want midday games before study is done — **out of v1** unless you insist.

If you still want midday games *before* finishing study: say so; we can keep a small bank (e.g. 1 chapter → 30m bank) as a secondary rule.

### “Repeated afternoon”
No second Bible ritual required. Once **study goal + 1 chapter** are done, unlock lasts **until midnight**, so afternoon/evening gaming is already covered.

---

## Reading UX (JSON / API)

1. Book picker (OT / NT)  
2. Chapter chips with ✓ / ★ (click = tick done, long-press = bookmark)  
3. **Verse list** from local API (number + text)  
4. Prev / Next chapter  
5. Status: `Chapter goal 0/1` · study progress · unlock mode  

### Credit / “did I read?”
- **Manual tick** = chapter counts as complete (bookmark-style, trusted).  
- **Auto assist:** if you dwell on a chapter ≥ N minutes (e.g. 3) with focus, offer/auto tick (configurable).  
- Heartbeat: `{ book, chapter, focused }` while verse view is open.

### Position
Store `last_book`, `last_chapter`, `last_verse` (not PDF page).

---

## Watch: verse rotation

**Requirement:** Amazfit / CALT Sync shows verses from **chapters completed or actively read today**.

### Backend
- `GET /api/hub/bible-verse` (or wearables route already on tracker hub `:8765`)  
- Response:

```json
{
  "ok": true,
  "schema": 1,
  "ref": "Genesis 1:3",
  "text": "And God said, Let there be light...",
  "book": "Genesis",
  "chapter": 1,
  "verse": 3,
  "rotation_index": 2,
  "source_chapters": ["Genesis|1"]
}
```

### Rotation rules
1. Collect today’s completed chapter keys (+ optional “currently reading”).  
2. Build verse pool from those chapters (local WEB JSON).  
3. Rotate on each watch poll (or every K minutes server-side by time bucket) so the face changes through the day.  
4. If no chapter today → fallback short line: “Read one chapter to feed the watch.”

### Watch app
- Existing CALT Sync / hub client: poll verse endpoint on an interval (e.g. 5–15 min) or on each complication refresh.  
- No PDF on watch — text only (fits JSON freedom).

---

## Data (local)

```text
data/bible/structured/web.json     # public-domain World English Bible
data/bible/day_{user}_{date}.json # bible_seconds optional; chapters_completed[]; day_pass
data/bible/reader_{user}.json      # last_book, last_chapter, ticks, bookmarks
data/bible/day_passes_{user}.json  # weekly PASS quota
```

GNB PDF: optional file only; **not** on the critical path.

---

## API sketch

```
GET  /api/bible/v2/meta
GET  /api/bible/v2/read/{version}/{book}/{chapter}
POST /api/bible/v2/heartbeat     { book, chapter, focused }
POST /api/bible/v2/chapters/tick { book, chapter, done: true }
GET  /api/bible/state            # includes chapter_goal: { done, target: 1 }, unlock hints
POST /api/bible/day-pass         # confirm PASS
GET  /api/hub/bible-verse        # watch rotation (wearable key)
```

Shape of `read` mirrors BibleApi (familiar, simple):

```json
{
  "version": "web",
  "name": "Genesis",
  "num_chapters": 50,
  "chapter": 1,
  "verses": [{ "number": 1, "text": "..." }]
}
```

---

## Surfaces

| Surface | Role |
|---------|------|
| `/bible` | Primary verse reader + chapter goal |
| Lock popup | “Read today’s chapter” → opens `/bible` (same UI) |
| Policy panel | Study goal, hard-block, day-pass |
| Watch via hub | Rotating verse from today’s chapters |

---

## Out of scope (v1)

- Depending on live `bible-api.deno.dev`  
- Beblia multilingual dump  
- Shipping NVI/ESV/GNB as JSON without license  
- PDF chapter scanning / PyMuPDF primary reader  
- Full concordance / Strong’s  

---

## Success criteria

- [ ] Read any chapter offline as verses (no PDF)  
- [ ] Daily goal UI: **1 chapter**  
- [ ] Study goal + 1 chapter → `day_unlimited` until midnight (afternoon OK)  
- [ ] Watch/hub returns rotating verses from today’s chapter(s)  
- [ ] Day-pass still works with `PASS` + weekly limit  
- [ ] No external Bible HTTP in the study loop  

---

## Phases

1. Import WEB JSON + `v2/read` + meta  
2. `/bible` verse UI + chapter tick goal  
3. Gate: unlimited = study + ≥1 chapter (afternoon covered)  
4. Hub `bible-verse` rotation + Sync/watch poll  
5. Retire PDF-primary path; optional PDF link only  

---

## Defaults if you approve as-is

| Choice | Default |
|--------|---------|
| Text | World English Bible (WEB), public domain |
| Daily Bible goal | **1 chapter** (not 30 minutes) |
| Midday bank without study | **Off** in v1 (unlimited only after study+chapter, or day-pass) |
| Watch pool | Verses from chapters ticked/completed today |
| PDF | Optional only |

---

## One confirmation

If you need **games time at lunch before study is done**, say so — we’ll add “1 chapter → 30m bank” back as a secondary rule. Otherwise v1 stays: **chapter + study → free until midnight**.
