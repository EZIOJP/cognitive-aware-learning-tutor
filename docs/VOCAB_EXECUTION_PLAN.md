# Vocab Execution Plan (FastAPI-first)

This plan focuses on finishing a stable vocab MVP quickly, then layering browser extension tracking and stronger auth.

## Phase 1 - Finalize Vocab MVP (Now)

1. Keep FastAPI backend as source of truth for user progress.
2. Use JWT login/register for account-based progress.
3. Persist per-user progress in SQLite (`vocab_app.db`).
4. Ship stable cycle flow: dashboard -> read -> quiz -> report.
5. Support vocab content maintenance via CRUD + CSV import/export.

## Phase 2 - Frontend Integration Hardening (Next)

1. Replace localStorage-only progress reads with backend API calls.
2. Add auth UI:
   - register/login screens
   - token storage and auto-attach `Authorization: Bearer <token>`
   - logout and session-expired handling
3. Add loading, empty, and retry states for all vocab endpoints.
4. Add migration helper to copy old local progress into backend once per user.

## Phase 3 - Browser Extension (Self-monitoring)

Feasible now as an isolated project:

1. Manifest V3 extension with:
   - active tab URL + domain capture
   - focus/blur duration tracking
   - optional manual "study mode" toggle
2. Send daily summary events to FastAPI endpoint:
   - focused minutes
   - distraction switches
   - domain categories
3. Show extension metrics in vocab dashboard as contextual signals.

## Security & Quality Checklist

1. Move JWT secret to environment variable.
2. Add password policy and username validation.
3. Add endpoint rate limiting for auth routes.
4. Add unit tests for:
   - auth flow
   - quiz mastery updates
   - import dedupe and malformed row handling
5. Add backup script for `vocab_app.db`.

## Immediate Next Sprint (Recommended)

1. Wire frontend to backend auth and progress APIs.
2. Keep old localStorage path as fallback for one release.
3. Add "suspend word" action in UI.
4. Add dashboard trend cards (7-day activity, avg quiz accuracy).
