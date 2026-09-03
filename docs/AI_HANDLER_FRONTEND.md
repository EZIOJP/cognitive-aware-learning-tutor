# AI Handler — frontend

How the React app talks to the LLM gateway: prefs, UI entry points, API calls, and known gaps.

See also: [AI_HANDLER.md](AI_HANDLER.md) (overview), [AI_HANDLER_BACKEND.md](AI_HANDLER_BACKEND.md) (server flow).

---

## Core rule

**There is no `AIHandler` React component.** All FE LLM logic lives in `src/api/transcriptsClient.ts`.

- **Persist** user prefs in `localStorage`.
- **Fetch** health via `GET /api/transcripts/llm-config`.
- **Send** `llm_tier` (and optionally legacy overrides) on every study POST via `llmBodyFields()`.

API keys and provider chains stay on the server (`data/llm_tiers.json`, `.env`).

---

## File map

```text
src/api/
├── transcriptsClient.ts   ← Canonical: LlmConfig, loadLlmPrefs, getLlmConfig, llmBodyFields, study POSTs
├── corpusClient.ts        ← generateGroundedNotes (RAG) — passes llm_tier via llmBodyFields
├── hubClient.ts           ← Coach/agent chat — passes loadLlmPrefs()
└── behaviorClient.ts      ← Classification scan — passes loadLlmPrefs()

src/pages/settings/
├── SettingsHubPage.tsx    ← /settings hub
├── LlmGatewayCard.tsx     ← Tier buttons + chain health + heavy budget
└── NineRouterCard.tsx     ← Static 9Router setup links (external gateway)

src/pages/study/
├── LectureNotesPage.tsx   ← Study Library: tier UI, generate, regen, quiz
└── TopicStudyFlowPage.tsx ← /study-flow: reads loadLlmPrefs() only

src/components/study/
├── StudyLibraryCreateSheet.tsx   ← Create note; shows llmConfig.reachable
├── StudyLibraryViewer.tsx        ← "LLM online/offline" badge
├── useSectionBlockEdit.tsx         ← Block regen; gates on llmReachable
├── useSelectionRegenerate.tsx    ← Selection regen
└── SectionBlockToolbar.tsx       ← Fix-with-AI buttons
```

---

## Types and helpers (`transcriptsClient.ts`)

```typescript
// What the server returns from GET /api/transcripts/llm-config
export type LlmConfig = {
  enabled: boolean;
  reachable: boolean;
  default_tier?: string;
  selected_tier?: string;
  route_profile?: string;
  tiers?: Record<string, {
    chain: Array<{ provider: string; model: string; base_url?: string | null }>;
    reachable: boolean;
    budget?: { used: number; cap: number; exceeded: boolean };
  }>;
  last_call?: Record<string, unknown> | null;
  corpus_grounded_notes?: boolean;
  corpus_available?: boolean;
  // ...
};

// What the browser stores and sends on POSTs
export type LlmOverrides = {
  llm_tier?: string;
  llm_provider?: string;   // legacy — prefer tier only
  llm_base_url?: string;   // legacy
  llm_model?: string;      // legacy
  confirm_heavy_budget?: boolean;
};
```

Key functions:

| Function | Purpose |
|----------|---------|
| `loadLlmPrefs()` | Read `localStorage` key `lecture-notes:llm` |
| `saveLlmPrefs(prefs)` | Write merged prefs |
| `getLlmConfig(overrides?)` | `GET /api/transcripts/llm-config` |
| `llmBodyFields(llm?, confirm?)` | Spread into POST bodies |

---

## localStorage

| Key | Written by | Contents |
|-----|------------|----------|
| `lecture-notes:llm` | `saveLlmPrefs`, `LectureNotesPage`, `LlmGatewayCard` | `{ llm_tier, llm_provider?, llm_base_url?, llm_model?, confirm_heavy_budget? }` |
| `lecture-notes:llm-tier` | `LlmGatewayCard` only | Duplicate tier string — **prefer consolidating to `lecture-notes:llm` only** |
| `lecture-notes:llm-migration-v2` | `loadLlmPrefs` once | Migrates stored `gemini` provider → `lmstudio` |

No global React context or Zustand store — each page holds `useState` and re-fetches config on change.

---

## UI entry points

### Settings (`/settings` → `LlmGatewayCard`)

- Tier buttons: **Light / Medium / Heavy**
- Shows per-tier provider chain and reachability dots
- Heavy-tier daily usage and last-call metadata
- **Refresh** re-fetches `getLlmConfig()`
- Does **not** edit API keys or model chains (server-side only)

### Study Library (`/lecture-notes` → `LectureNotesPage`)

- Header: tier dropdown only (provider/model controls removed)
- Status: `llmConfig.reachable` → "LLM online/offline" in viewer
- Actions that call the gateway:
  - Generate notes (create sheet)
  - Regenerate block / selection
  - Repair all blocks
  - Gap analysis, quiz, drills
  - Folder summarize
- `runWithBudgetConfirm()` — if heavy cap exceeded, `window.confirm` then retry with `confirm_heavy_budget: true`

### Topic study flow (`/study-flow` → `TopicStudyFlowPage`)

- No tier UI on the page
- Calls `loadLlmPrefs()` and passes to `startTopicStudyFlow({ llm })`

---

## API calls from the frontend

All study functions in `transcriptsClient.ts` accept optional `llm?: LlmOverrides` and spread `llmBodyFields(llm)` into the body.

| User action | Function | Endpoint |
|-------------|----------|----------|
| Check health | `getLlmConfig()` | `GET /api/transcripts/llm-config` |
| Generate notes | `generateNotes()` | `POST /api/transcripts/notes/generate` |
| Topic study flow | `startTopicStudyFlow()` | `POST /api/transcripts/study-flow/start` |
| Generate quiz | `generateLibraryQuiz()` | `POST /api/transcripts/library/generate-quiz` |
| Fix mermaid block | `regenerateNoteBlock()` | `POST /api/transcripts/library/regenerate-block` |
| Grounded RAG button | `generateGroundedNotes()` | `POST /api/corpus/generate-notes-grounded` |

Math tutor uses gateway on the backend with no tier UI (defaults to `math_hint` / light). Classification scan passes `loadLlmPrefs()` via `behaviorClient`.

---

## User action → backend (sequence)

```text
1. User sets tier in Settings or Study Library header
      → saveLlmPrefs({ llm_tier: "medium", ... })

2. Page calls getLlmConfig({ llm_tier })
      → GET /api/transcripts/llm-config?llm_tier=medium
      → UI shows chain health

3. User clicks "Generate notes"
      → generateNotes({ ..., llm: llmOverrides })
      → POST body includes llm_tier, confirm_heavy_budget

4. Backend runs note_generation → ollama_generate → llm_gateway

5. On success, fallbackNotice() may re-fetch getLlmConfig()
      → toast if last_call.fallback === true
```

---

## Target architecture (Phase 1 complete)

| Item | Status |
|------|--------|
| Tier-only Study Library header | Done |
| Single `lecture-notes:llm` localStorage | Done |
| `generateGroundedNotes` passes tier | Done |
| Coach/agent/classification pass tier | Done |

Chains and API keys remain in `data/llm_tiers.json` and `.env` — never in the browser.

---

## Adding a new frontend AI action

1. Add a function in `transcriptsClient.ts` (or extend an existing one).
2. Accept `llm?: LlmOverrides` and spread `...llmBodyFields(llm)`.
3. Gate buttons on `llmConfig?.reachable !== false` where appropriate.
4. Wrap in `runWithBudgetConfirm` pattern if the action may hit heavy tier.
5. Add backend endpoint that accepts `llm_tier` (see [AI_HANDLER_BACKEND.md](AI_HANDLER_BACKEND.md)).

Example:

```typescript
export async function myNewAiAction(args: { topic: string; llm?: LlmOverrides }) {
  const res = await fetch(`${BASE}/api/transcripts/my-action`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({
      topic: args.topic,
      ...llmBodyFields(args.llm),
    }),
  });
  // ...
}
```

---

## Known gaps (for contributors fixing the subsystem)

| Issue | Files involved |
|-------|----------------|
| Duplicate tier storage | `LlmGatewayCard.tsx`, `transcriptsClient.ts` |
| Legacy provider UI bypasses chains | `LectureNotesPage.tsx` header controls |
| RAG generate ignores tier | `corpusClient.ts`, `LectureNotesPage` `handleGenerateGrounded` |
| Settings vs Study Library tier can desync | Both write prefs differently |
| Gemini option shown but auto-migrated away | `loadLlmPrefs()` migration vs header dropdown |

---

## Quick manual test

1. Log in, open **Settings → AI / LLM gateway** — confirm at least one tier is reachable.
2. Open **Study Library** — tier dropdown matches Settings.
3. Generate notes from a transcript — succeeds or shows clear offline message.
4. Click **Fix with AI** on a mermaid block — regen works when LLM online.
5. DevTools → Application → Local Storage → verify `lecture-notes:llm` has `llm_tier`.
