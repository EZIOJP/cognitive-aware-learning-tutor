# Documentation Index

All project docs live here. Use with the file kernel at repo root.

## Cursor / AI kernel

| Doc | Use |
|-----|-----|
| [../AGENTS.md](../AGENTS.md) | Agent role — **cape time**: verify then polish |
| [PROJECT_LAYOUT.md](PROJECT_LAYOUT.md) | **Full repo** folders and where to add files |
| [FILE_MAP.md](FILE_MAP.md) | GRE vocab components and API endpoints |
| [SESSION_LOG.md](SESSION_LOG.md) | Session checklist (check off as you go) |

## Product & engineering

| Doc | Use |
|-----|-----|
| [ROADMAP.md](ROADMAP.md) | Phases 0–5 |
| [PROJECT_STATUS.md](PROJECT_STATUS.md) | What works now (cape-time / daily-use snapshot) |
| [TASKS.md](TASKS.md) | Kanban-style tasks |
| [CURRENT_ARCHITECTURE.md](CURRENT_ARCHITECTURE.md) | Short architecture summary (today) |
| [HLD.md](HLD.md) | **High-level design** — system context, study loops, gaps (code-grounded) |
| [LLD.md](LLD.md) | **Low-level design** — algorithms, schemas, config, file map |
| [COMPLETION_SPRINT.md](COMPLETION_SPRINT.md) | **Cape-time board** — Sprints 1–3 done; verify (4) then polish (5) |
| [TASK_COMPLETION.md](TASK_COMPLETION.md) | **Master checklist** — loop closure, connections, polish, final build |
| [decisions/ADR-001-quiz-practice-orchestration.md](decisions/ADR-001-quiz-practice-orchestration.md) | **Quiz / practice loop** — backlog `next_step`, math multi-Q, Layer 0 |
| [MATH_TUTOR_VISION_PIPELINE.md](MATH_TUTOR_VISION_PIPELINE.md) | Math canvas, OCR, Ollama Socratic pipeline |
| [HARDWARE_AND_AI_LATER.md](HARDWARE_AND_AI_LATER.md) | No GPU / no ESP32 path |
| [WORKING_PRODUCT.md](WORKING_PRODUCT.md) | Daily-use checklist |
| [GRE_VOCAB_PHASE1.md](GRE_VOCAB_PHASE1.md) | GRE Phase 1 complete |
| [../gre/INDEX.md](../gre/INDEX.md) | **GRE lane design pack** — GIST / HLD / LLD for vocab + math practice + OCR |
| [DEPENDENCIES.md](DEPENDENCIES.md) | **Fresh-machine install** (Windows/Linux/macOS) |
| [SETUP_AND_COMMANDS.md](SETUP_AND_COMMANDS.md) | Quick commands and scripts |
| [GOOGLE_CALENDAR_AMAZFIT.md](GOOGLE_CALENDAR_AMAZFIT.md) | Push planner → Google Calendar → Amazfit watch |
| [CALT_SYNC_MANUAL_DUMP.md](CALT_SYNC_MANUAL_DUMP.md) | **CALT Sync 4.0** — manual health dump + replay-safe ingest |
| [superpowers/specs/2026-08-19-mobile-device-gate-design.md](superpowers/specs/2026-08-19-mobile-device-gate-design.md) | **Deferred:** Flutter UI + native phone lock until PC productivity done |
| [superpowers/plans/2026-08-19-mobile-device-gate.md](superpowers/plans/2026-08-19-mobile-device-gate.md) | Device Gate phases (Android first, iOS later) |
| [exports/CALT_PROJECT_TRACKERS_DEVICE_GATE_REVIEW.md](exports/CALT_PROJECT_TRACKERS_DEVICE_GATE_REVIEW.md) | **Review export** — whole project + trackers + Device Gate |
| [exports/CALT_TRACKING_BLOCKS_REWARDS.md](exports/CALT_TRACKING_BLOCKS_REWARDS.md) | **Review export** — tracking, blocking, rewards; Android/iOS marked next |
| [exports/math-ocr/MATH_OCR_BUILD_AND_CHANGES.md](exports/math-ocr/MATH_OCR_BUILD_AND_CHANGES.md) | **Math OCR** — changes, build, run, retrain (2026-08-30) |
| [exports/math-ocr/OCR_CLOSEOUT_2026-08-30.md](exports/math-ocr/OCR_CLOSEOUT_2026-08-30.md) | Math OCR close-out summary |
| [exports/math-ocr/README.md](exports/math-ocr/README.md) | **Math OCR export folder** — canvas, OCR, SymPy, tutor architecture |
| [DATABASE.md](DATABASE.md) | Schema and env vars |
| [MIGRATIONS.md](MIGRATIONS.md) | Alembic revisions |
| [API_CONTRACT.md](API_CONTRACT.md) | HTTP API reference |
| [DOCKER.md](DOCKER.md) | Container deployment |
| [STITCH_MCP_SETUP.md](STITCH_MCP_SETUP.md) | Stitch MCP + generate scripts |
| [CENTRAL_HUB.md](CENTRAL_HUB.md) | Hub metrics and ingest |
| [STITCH_DESIGN_SPEC.md](STITCH_DESIGN_SPEC.md) | UI tokens, components, screens for Stitch/v0 |
| [STITCH_PROMPT.txt](STITCH_PROMPT.txt) | Short paste prompt for Stitch |
| [MERMAID_RENDER_AND_REGEN_HANDOFF.md](MERMAID_RENDER_AND_REGEN_HANDOFF.md) | **Study Library:** Mermaid render, Fix syntax, LM Studio regen |
| [MERMAID_CODE_REFERENCE.md](MERMAID_CODE_REFERENCE.md) | Mermaid pipeline code excerpts |
| [STUDY_LIBRARY_MERMAID_FILE_MAP.md](STUDY_LIBRARY_MERMAID_FILE_MAP.md) | One-line file index for Mermaid fix stack |
| [TRANSCRIPT_STUDIO_WORKFLOW.md](TRANSCRIPT_STUDIO_WORKFLOW.md) | Studio Capture → Tune → Generate workflow |
| [TRANSCRIPT_STUDIO_HANDOFF.md](TRANSCRIPT_STUDIO_HANDOFF.md) | **Handoff:** file map, pipelines, export bundle, backlog |
| [LOCAL_LLM_NOTES_GUIDE.md](LOCAL_LLM_NOTES_GUIDE.md) | Local models, CPU/GPU, quality presets |
| [AI_HANDLER.md](AI_HANDLER.md) | **AI handler overview** — how FE + BE LLM routing fits together |
| [AI_HANDLER_BACKEND.md](AI_HANDLER_BACKEND.md) | Backend gateway modules, call flow, tasks, endpoints |
| [AI_HANDLER_FRONTEND.md](AI_HANDLER_FRONTEND.md) | Frontend prefs, UI entry points, API calls, known gaps |
| [LLM_GATEWAY.md](LLM_GATEWAY.md) | Tier chains + route profiles + `/api/llm/complete` for CALT and scripts |
| [../export-bundle/notes-gen-render/README.md](../export-bundle/notes-gen-render/README.md) | **Notes gen + render export** — GIST / HLD / LLD / CONFIG + sources |
| [../export-bundle/notes-gen-render-docs/README.md](../export-bundle/notes-gen-render-docs/README.md) | **Notes docs pack for planning** — all related docs + PLANNING_BRIEF |
| [../export-bundle/ai-handler-research/INDEX.md](../export-bundle/ai-handler-research/INDEX.md) | **Research export** — 49-file snapshot + index for Drive upload |
| [../export-bundle/productivity-system/README.md](../export-bundle/productivity-system/README.md) | **Productivity full export** — architecture + FE/BE + extension + tracker + schemas (folder only, no zip) |
| [PRODUCTIVITY_SYSTEM.md](PRODUCTIVITY_SYSTEM.md) | How productivity / gate / sleep / plan-vs-actual works |
| [9ROUTER_SETUP.md](9ROUTER_SETUP.md) | **9Router** — Cursor + free-provider routing at localhost:20128 |
| [VOCAB_EXECUTION_PLAN.md](VOCAB_EXECUTION_PLAN.md) | Vocab MVP steps |
| [FUTURE_VISION.md](FUTURE_VISION.md) | Long-term vision + Phase 3 map |
| [FUTURE_TAGGED_DAILY_PRACTICE.md](FUTURE_TAGGED_DAILY_PRACTICE.md) | **Deferred:** tagged Daily Practice engine (Option 3) |
| [superpowers/specs/2026-08-18-local-owner-profile-design.md](superpowers/specs/2026-08-18-local-owner-profile-design.md) | Local owner — drop login, Profile, parked Tailscale/community |
| [superpowers/plans/](superpowers/plans/) | **Archive** — shipped design plans (cape time: don’t reopen unless asked) |

## Repo root guides

- [../README.md](../README.md) — overview and quick start
- [../INTEGRATION_GUIDE.md](../INTEGRATION_GUIDE.md)
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Common errors and fixes |
