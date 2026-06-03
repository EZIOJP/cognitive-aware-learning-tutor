# Project Status

Last updated: 2026-06-02

## Current Focus

Finalize the GRE Vocabulary MVP before expanding the biometric Smart Pomodoro
system.

## Current Product Shape

The project is a local-first study dashboard with:

- GRE vocabulary read and cycle flows
- Admin panel for users and word management
- Math whiteboard prototype
- Pomodoro dock
- Simulated cognitive load / EEG indicators
- FastAPI vocab backend
- FastAPI EEG backend reference

## Working Now

- Frontend builds with `npm.cmd run build`
- App routes are wired through React Router
- Vocab words load from `public/data/words.json`
- Vocab progress can persist locally and through backend paths
- Admin user exists for prototype use
- Admin panel can view users, reset progress, import/export words, and edit words
- Prototype admin password visibility/reset flow exists

## Known Prototype Credentials

```text
username: admin
password: admin123
```

## Important Prototype Warning

Admin password visibility is intentionally prototype-only. It exists because this
is a local study project and passwords are easy to forget during development.
Remove the plain-password field before any real deployment.

## Documentation map

- Repo layout (all folders): `docs/PROJECT_LAYOUT.md`
- Vocab components + API: `docs/FILE_MAP.md`
- Session checklist: `docs/SESSION_LOG.md`
- Doc index: `docs/README.md`

## Next Engineering Target

Make vocab feel complete end to end:

1. Validate Read Mode
2. Validate Cycle Mode
3. Validate quiz/report/low-mastery loop
4. Validate backend auth and progress sync
5. Clean UI states and empty states

