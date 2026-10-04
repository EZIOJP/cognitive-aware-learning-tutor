# Bible devotion: adjustable chapters, editable prayers, per-slot journals

**Date:** 2026-09-15  
**Status:** Owner-approved — implement  
**Product:** CALT Focus (C++ life content + Bible UI)

## Success

1. **Morning / Afternoon / Evening** each have a progress cursor; mark-done advances that cursor for the next day.
2. All three slots are **changeable** (prev/next/pick). Afternoon defaults Proverbs; evening defaults Psalms; any book allowed.
3. **Prayers** on all three slots are **editable + savable** (defaults: full Lord’s Prayer morning; stock aft/eve texts; reset-to-default).
4. **Journals** per slot (morning/afternoon/evening), persisted with the day and linked into Focus Journal.
5. SoftLand `bible_done` still only from **morning** mark-done.

## Architecture

- SoT: `productivity_bible_day.document_json` + user-level `productivity_bible_reader` (or fields in a reader doc) for cursors.
- New gateway ops:
  - `bible.devotion.assign` `{ slot, book, chapter }`
  - `bible.devotion.prayer` `{ slot, text }` (+ optional `reset: true`)
  - Extend notes / journal: `bible.devotion.journal` `{ slot, text }` (or reuse notes as journal body + `journal.upsert` mirror)
- FE: `BibleReaderPage` — Change reading, editable PrayerBlock, Journal field per tab.

## Out of scope

- SoftLand rule changes beyond morning unlock
- Study Python `plan_cursor` as SoT
