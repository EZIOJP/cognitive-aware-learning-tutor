# Learn folders + Shorts cards (2026-09-04)

## Goal

Hierarchical Learn tree driven by real `data/notes/` folders, with Math Core first, and read cards presented as a full-bleed one-at-a-time stack (YouTube Shorts feel).

## Folder order (top-level)

| Folder | Contents |
|--------|----------|
| `math-core/` | MT1 aptitude / fluency notes (`MT1-T01`, `T16`–`T24`) |
| `math/` | Other math modules (`MT2+`) |
| `numpy/` | L02–L03 lecture notes |
| `pandas/` | L04–L05 lecture notes |
| `lecture/` | Other lecture notes (`L*`) |
| `vocab/` | Placeholder (vocab tags remain virtual) |

`rules/` stays out of the Learn tree.

## Hierarchy

```
Folder → Tags (MT*/L*/vocab.group.*) → Read cards (Shorts stack)
```

Tag ids unchanged. `note_paths` and card ids (`path::TAG`) update when files move. Legacy path remaps keep old URLs/DB refs working.

## Shorts reader

- Full-bleed card in Learn/Notes pane
- One card at a time; Next / Prev / keyboard / vertical swipe
- Last card → **Mark read & practice**
- Edit/save still via existing Approach A write-back

## Non-goals

- Second SRS, new quiz engine, or hard-block UX
- Splitting MT1 into one-file-per-tag (tags stay sections inside one file)
