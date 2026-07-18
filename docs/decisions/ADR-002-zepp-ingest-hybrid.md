# ADR-002: Zepp Mini Program → custom CALT endpoint + phone plan notifications

## Status

Accepted (user direction 2026-07-18)

## Date

2026-07-18

## Context

User wants Amazfit health data and plan reminders without Google Calendar. Prefer watch Mini Program dumping to a custom CALT endpoint over Wi‑Fi, and notifications for tasks/plans via CALT on the phone (watch agenda optional).

## Decision

1. **Ingest + plans:** Zepp OS Mini Program sync cycle → `POST` health dump **and** `GET` active plans → update watch agenda whenever CALT is reachable.  
2. **No Google Calendar** in this feature.  
3. **Notifications:** CALT phone app schedules local notifications from planner blocks.  
4. **Watch:** health dump + **required** active-plan refresh on sync; not Amazfit system calendar writer.  
5. Optional cloud sidecar later → same health ingest only.

## Consequences

### Positive
- Matches “our endpoint” mental model; no Google dependency  
- Official OS 5 sensors + processed sleep summaries  
- Plan alerts stay under CALT control  

### Negative
- HTTP hop is phone Side Service (watch alone isn’t the HTTP client) — must document  
- Phone CALT app must implement notification scheduling  
- Side Service sync weak if Zepp is force-stopped  

### Neutral
- Gap-fill busy = CALT routines/blocks only until another busy source is chosen (not Google)
