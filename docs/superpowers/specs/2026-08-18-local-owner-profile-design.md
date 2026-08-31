# Design: Local owner profile (drop login)

**Date:** 2026-08-18  
**Status:** Approved (slice 1)  
**Plan:** Cursor plan *Local owner profile*

## Goal

This machine has one owner. Opening `http://localhost:5173` loads the study app with no sign-in page. Profile is the place to set a display name and see where local data lives.

## Non-goals (parked)

- Deleting JWT or `POST /api/vocab/auth/login` (Android QR, admin word-import, face enroll still use tokens)
- Multi-account / register flow as onboarding
- Tailscale install in-app
- Rankings, DMs, community posts

## Architecture

Backend already runs `solo_local_user=True` ([`backend/config.py`](../../../backend/config.py)). `get_current_user()` returns the admin owner.

**Slice 1 wiring:**

1. `GET /api/vocab/auth/local-session` — mint a JWT for the solo owner when `solo_local_user` is on.
2. Frontend `AuthProvider` auto-binds on boot (empty `localStorage` included).
3. `/login` redirects to `/profile`.
4. `users.display_name` (nullable) via Alembic `0029_user_display_name`.
5. `GET`/`PATCH /api/vocab/auth/me` return/update display name.

## Later phases (no code in this slice)

**Phase 2 — Tailscale (slice 2):** Detect Tailscale CLI; show 100.x / MagicDNS URLs on Profile. Same APIs, same SQLite. Phone uses that URL off home Wi‑Fi.

**Phase 3 — Opt-in ranks (slice 2):** `publish_ranks` defaults **false**. Public card is display name + Pulse only. Peers are URLs the owner pastes (Tailscale CGNAT / LAN / `*.ts.net`). No CALT sign-in.

## Verification

- Empty `localStorage` → home loads after local-session
- `/login` → `/profile`
- pytest: `/auth/me` and `/auth/local-session` without password
- `npm run build`
