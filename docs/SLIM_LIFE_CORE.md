# slim/life-core — frontend-only surface cut

This branch keeps the **UI** focused on daily life tools. Backend code for GRE/math/EEG still exists (not deleted) so `main` can stay full-featured.

## Kept in nav

- Home
- Journal
- Lecture Notes
- App Logs
- AI Coach
- Productivity
- Life Tracker
- Settings / Admin

## Hidden (routes redirect / plugins forced off)

- GRE Vocab, Math Tutor, EEG, Study Room, Nutrition, Focus Mirror
- Study Flow, Knowledge Base, Review Hub, Cortex Hub, Project Agent

## Toggle

- Default: slim ON (`src/plugins/slimLifeCore.ts`)
- Restore full UI on this branch: set `VITE_SLIM_LIFE_CORE=0` in `.env` and restart Vite
