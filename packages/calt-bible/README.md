# CALT Bible — offline WEB reader (watch)

Separate Zepp app (`appId` 1088804). Full World English Bible on the watch. No PC sync required to read.

## What it does

- **Today:** current chapter + Read (full chapter, scrollable)
- **Browse:** all 66 books / 1189 chapters (paged lists)
- **Settings:** set current chapter (source of truth for the daily plan)
- **Daily:** at local midnight the current chapter advances Genesis → Revelation, then stops
- **Notify:** hourly verse 08:00–21:00 via **Zepp OS 6 alarm** (wakes once an hour, then sleeps). Settings → **Send verse now** tests a notification.

Phone: Developer Mode → + → Scan the QR. **Uninstall** the old CALT Bible first, then install so the watch gets **1.0.8**. Allow **alarm** + **notification**.

## Troubleshooting history (important constraints)

**Black screen (fixed 1.0.1):** Zepp `readFileSync` only reads **`/data`**. Bible JSON is packaged under **`/assets`**, so reads must use `openAssetsSync` + `readSync`.

**Watch crash / reboot (fixed 1.0.3):** whole-book JSON reached **250 KB**; reading and parsing that exhausted watch RAM. Assets are now **one file per chapter** (largest ≈ 15 KB, index ≈ 4 KB) and only one chapter is cached at a time.

**Stack OOM while flipping verses (fixed 1.0.4):** Prev/Next and list paging used `push`, so each tap stacked another page until the watch ran out of memory. Those navigations now use `replace`.

**Full chapter scroll (1.0.5):** Read shows the whole chapter in a scrollable list (batched TEXT widgets). Do not create one widget per verse for long chapters.

> Never reintroduce whole-book files or a 1189-entry plan array. The daily plan is computed on device from each book's chapter count.

If Browse says “Bible files not found”:

1. Re-pack assets: `python scripts\pack_watch_bible.py`
2. Re-sideload: `packages\calt-bible\sideload.bat`
3. Confirm version **1.0.8** on the watch

## Pack the Bible

```bat
python scripts\pack_watch_bible.py
```

Writes `index.json` plus `{book}/{chapter}.json` into:

- `assets/480x480-t-rex-3/bible/` (device target)
- `assets/raw/bible/` (shared `/assets/raw/bible` after build)

## Install

```bat
packages\calt-bible\sideload.bat
```

Phone: Developer Mode → + → Scan the QR. **Uninstall** the old CALT Bible first, then install so the watch gets **1.0.8**.

## Usage

1. Open **CALT Bible**
2. **Read** → full chapter on one scrollable screen (including Psalm 119’s 176 verses)
3. **Browse** → book → chapter → same full-chapter reader
4. Settings → **Set current chapter** for the daily plan + hourly notify

> Verses are batched into a few TEXT widgets (not one per verse) so long chapters stay within watch RAM.
