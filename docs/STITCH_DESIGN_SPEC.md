# Stitch design specification — Cognitive-Aware Learning Tutor

**Purpose:** Hand this document to [Stitch](https://stitch.withgoogle.com) (or v0 / Figma AI) to generate UI.  
**Do not invent new features** — match routes, API fields, and plugin structure below.  
**Backend is source of truth** — UI displays data from OpenAPI (`http://localhost:8000/openapi.json`). See `docs/API_CONTRACT.md`.

**Product name (UI):** Study Hub / Study Companion  
**Tagline:** A cognitive-aware learning OS — vocab, math, life habits, and focus in one place.

---

## 1. Design direction

### 1.1 Mood & references

- **Style:** Premium study companion — calm, focused, slightly futuristic (not playful kids’ app).
- **Surface language:** **Glossy glass** panels — frosted blur, soft borders, subtle inset highlights (Apple-adjacent, not Material heavy shadows).
- **Reference feel:** ChronoFocus-style **24-hour ring** for life/time; clean shadcn component density; dashboard widget grid like Notion/Linear cards.
- **Avoid:** Neon gamer UI, heavy gradients on every surface, cluttered charts, comic sans, pure Material purple.

### 1.2 Layout principles

- **Desktop-first** (1280px+); responsive down to 390px width.
- **Persistent shell:** Collapsible left sidebar (56px collapsed / 224px expanded) + top bar + optional right “dock” chips (Pomodoro, brain activity, cognitive load).
- **Content:** Max width ~1200px centered in main area; cards on `--background`.
- **Motion:** Subtle (150–300ms); ring segments and progress bars animate on load; no bounce.

---

## 2. Design tokens

### 2.1 Color — semantic (light mode default)

| Token | Hex | Usage |
|-------|-----|--------|
| `background` | `#FAFBFC` | Page canvas |
| `foreground` | `#0A0A0B` | Primary text |
| `card` | `#FFFFFF` | Card fill |
| `card-foreground` | `#0A0A0B` | Card text |
| `primary` | `#1A1A2E` | Buttons, links, focus rings (user can override — see accents) |
| `primary-foreground` | `#FFFFFF` | Text on primary |
| `secondary` | `#F0F2F5` | Secondary buttons, chips |
| `muted` | `#EEF0F4` | Subtle fills |
| `muted-foreground` | `#5C5F6B` | Labels, captions |
| `accent` | `#F4F6F9` | Hover rows, sidebar hover |
| `destructive` | `#D4183D` | Errors, wrong quiz answers |
| `border` | `rgba(0,0,0,0.1)` | Dividers |
| `input-background` | `#F3F3F5` | Input fields |

### 2.2 Color — semantic (dark mode)

| Token | Hex | Usage |
|-------|-----|--------|
| `background` | `#050505` | Page (intensity slider can lighten to ~`hsl(240 10% 30%)`) |
| `foreground` | `#F5F5F7` | Primary text |
| `card` | `#0C0C0C` | Cards |
| `primary` | `#F5F5F7` | Inverted primary |
| `primary-foreground` | `#0A0A0A` | On primary buttons |
| `muted-foreground` | `#A1A1AA` | Captions |
| `destructive` | `oklch(0.396 0.141 25.723)` | Errors |

### 2.3 Accent presets (user-selectable in Settings)

| Name | Hex | Use for primary CTA |
|------|-----|---------------------|
| Default (light) | `#1A1A2E` | Navy ink |
| Default (dark) | `#F5F5F7` | Near white |
| Emerald | `#10B981` | Success / health |
| Violet | `#8B5CF6` | Vocab / creative |
| Rose | `#F43F5E` | Alerts / social |
| Amber | `#F59E0B` | Study / math energy |

Custom hex allowed (color picker in Theme Settings).

### 2.4 Life Clock segment colors (fixed — from API `segments[].color`)

| Activity type | Hex | Label examples |
|---------------|-----|----------------|
| `sleep` | `#6366F1` | Sleep (indigo) |
| `study` | `#3B82F6` | Study (blue) |
| `math` | `#10B981` | Math (emerald) |
| `break` / `relaxation` | `#8B5CF6` | Break (violet) |
| `productive` | `#14B8A6` | Productive (teal) |
| `untracked` | `#64748B` | Other (slate) |

### 2.5 Widget card gradient accents (home dashboard)

Use as **subtle card header wash** (`from-X/20 to-Y/10`):

| Widget | Gradient |
|--------|----------|
| 24-hour life clock | `indigo-500/20` → `violet-500/10` |
| Study time | `amber-500/20` → `orange-500/10` |
| AI Review | `blue-500/20` → `cyan-500/10` |
| Community | `rose-500/20` → `pink-500/10` |
| GRE Vocab | `violet-500/20` → `purple-500/10` |
| Math Tutor | `emerald-500/20` → `teal-500/10` |
| Life Tracker | `rose-500/20` → `red-500/10` |
| Browser activity | `slate-500/20` → `gray-500/10` |

### 2.6 Chart / data viz

Use CSS vars `chart-1` … `chart-5` (oklch in theme). Life score rings:

| Pillar | Ring stroke color |
|--------|-------------------|
| Health | `#10B981` |
| Productivity | `#3B82F6` |
| Digital wellbeing | `#8B5CF6` |
| Mental | `#F59E0B` |
| Composite Life Score | `#6366F1` |

### 2.7 Gloss overlay tokens

| Token | Light | Dark |
|-------|-------|------|
| `gloss-surface` | `rgba(255,255,255,0.92)` | `rgba(12,12,12,0.94)` |
| `gloss-border` | `rgba(0,0,0,0.06)` | `rgba(255,255,255,0.08)` |
| `gloss-shadow` | `0 4px 24px rgba(0,0,0,0.06)` | `0 4px 32px rgba(0,0,0,0.5)` |

Apply class pattern: **gloss-panel** on cards, **gloss-sidebar** on nav, **gloss-topbar** on header.

### 2.8 Typography

| Role | Font | Size | Weight | Notes |
|------|------|------|--------|-------|
| Display / page title | System UI stack or **Inter** | 24–28px | 600 | Top bar title |
| Section heading | Inter | 18–20px | 600 | Card titles |
| Body | Inter | 14–16px (`--font-size: 16px`) | 400 | Default |
| Caption / label | Inter | 12px | 400–500 | `muted-foreground` |
| Mono (clock, timers) | **JetBrains Mono** or ui-monospace | 24px | 700 | Life clock center time |
| Button | Inter | 14px | 500 | |

Line height: 1.4 body, 1.2 headings.

### 2.9 Spacing & radius

| Token | Value |
|-------|--------|
| Base unit | 4px |
| Card padding | 16–24px (`p-4` / `p-6`) |
| Section gap | 24px |
| Grid gap (dashboard) | 16px |
| `--radius` default | `10px` (`0.625rem`) |
| Radius presets | sm `6px`, md `10px`, lg `16px`, xl `24px` |
| Sidebar width | 56px collapsed / 224px expanded |
| Top bar height | 56px |

### 2.9 Icons

**Lucide React** style — 16px inline, 20px nav, 24px widget headers.  
Stroke 1.5–2px; round caps.

---

## 3. Component library (build with shadcn/ui patterns)

Specify these components for Stitch; states required for each:

### 3.1 Primitives

| Component | Variants | States |
|-----------|----------|--------|
| **Button** | default, outline, ghost, destructive, link | default, hover, focus, disabled, loading (spinner) |
| **Input** | text, password, number | empty, filled, error, disabled |
| **Textarea** | — | same as Input |
| **Label** | — | — |
| **Badge** | default, secondary, outline, destructive | — |
| **Card** | default, gloss-panel | — |
| **Separator** | horizontal / vertical | — |
| **Switch** | — | on/off, disabled |
| **Slider** | — | Life tracker inputs |
| **Progress** | linear | determinate |
| **Tabs** | underline / pills | active tab |
| **Dialog / Sheet** | — | open/close |
| **Dropdown menu** | — | user menu in top bar |
| **Toast** | success, error, info | — |
| **Skeleton** | text, card, circle | loading |
| **Tooltip** | — | — |

### 3.2 App-specific components

| Component | Description |
|-----------|-------------|
| **AppSidebar** | Collapsible nav; icon + label; active item: `bg-accent` + `font-medium` |
| **AppTopBar** | Title left; center optional connection dot; right: theme toggle, docks, user menu |
| **DashboardWidget** | Drag handle (grip), title row, optional 1×1 or 2×2 grid span, hide toggle in customize mode |
| **DayTimeTracker** | 280×280 ring (compact 200px); see §4.2 |
| **ScoreRing** | 64×64 circular progress + center number |
| **CheckpointRoadmap** | Horizontal topic checkpoints (math) |
| **WordCard** | Vocab read mode: word, pronunciation, meaning, examples |
| **QuizOptionButton** | 4 options; correct=green border, wrong=red |
| **MathSplitWhiteboard** | Left: problem + answer input; right: canvas area |
| **ConnectionStatus** | Green/amber/red dot + “Connected” / “Offline” |
| **PomodoroDock** | Compact chip in top bar — timer |
| **BrainActivityDock** | EEG/brain placeholder chip |
| **CognitiveLoadDock** | Load meter chip |
| **CustomizerDrawer** | Right sheet: widget visibility, col/row span |

---

## 4. Screens (page-by-page)

### 4.1 App shell (wraps all routes)

**Structure:**

```
┌──────────┬────────────────────────────────────────────────────┐
│ Sidebar  │ TopBar: [Page title]     [docks] [theme] [user ▼]   │
│          ├────────────────────────────────────────────────────┤
│ Home     │                                                    │
│ Math     │              MAIN CONTENT (scroll)                 │
│ Vocab    │                                                    │
│ Life ❤   │                                                    │
│ Nutri    │                                                    │
│ Settings │                                                    │
│ Admin*   │                                                    │
└──────────┴────────────────────────────────────────────────────┘
* Admin only if `is_admin`
```

**Sidebar labels (exact):**

- Home
- Math Tutor
- GRE Vocab
- Life Tracker (heart icon)
- NutriNode (if plugin on)
- Settings
- Admin

**Top bar titles by route:**

| Path | Title |
|------|-------|
| `/` | Study Hub |
| `/math-tutor` | Math Dashboard |
| `/math-tutor/reports` | Math Reports |
| `/gre-vocab` | GRE Vocabulary |
| `/life-tracker` | Life Tracker |
| `/settings` | Settings |
| `/login` | (no shell or minimal) |

---

### 4.2 Home — Study Hub (`/`)

**Purpose:** Draggable widget dashboard.

**Header row:**

- Title: **“Good {morning|afternoon|evening}, {username}”** (fallback: “Learner”)
- Subtitle: **“Your cognitive-aware command center”**
- Buttons: **Customize layout** (icon LayoutGrid), **Focus mode** (optional)

**Widget grid:** 4-column CSS grid; widgets span 1×1, 2×1, 1×2, 2×2.

**Core widgets (always):**

1. **24-hour life clock** (2×2)  
   - Title: **24-hour life clock**  
   - Subtitle: **Track how your day is unfolding**  
   - Data: `GET /api/hub/daily/today` → `segments`, `time_left_hours`, `percent_elapsed`  
   - Center: live clock `HH:MM` + seconds small  
   - Footer stats: **Productive** `{hours}m`, **Sleep** `{hours}m`, **Day progress** bar  
   - Empty: “Log your day in Life Tracker to fill the ring”

2. **Study Time & Focus** (1×1)  
   - Title: **Study Time & Focus**  
   - Body metric: **{minutes}m today** (from hub or session)  
   - Subtext: **“Your focus is up 15% compared to yesterday”** (placeholder until insights API)

3. **AI Review** (1×1)  
   - Title: **AI Review**  
   - Badge: **Excellent Retention** / **Good** / **Needs improvement** (`GET /api/insights/daily`)  
   - Subtext: **“You completed {n} vocabulary questions”**

4. **Community** (1×1) — optional / future  
   - Title: **Community**  
   - Subtext: **“3 friends are currently studying”**  
   - CTA: **Join Room** (disabled state: “Coming soon”)

**Plugin widgets (when enabled):** GRE progress, Math mastery summary, Life score mini, Browser activity, Nutrition today.

**Customizer drawer (right sheet):**

- Title: **Customize dashboard**
- Per widget: name, toggle **Show/Hide**, **Width** (1|2 cols), **Height** (1|2 rows)

---

### 4.3 Login (`/login`)

**Card centered, max-width 384px, gloss-panel.**

- Heading: **Vocab Login**
- Subtext: **Sign in to sync progress across devices.**  
  Helper (small): **Demo: any username works without token; admin uses admin / admin123**
- Fields: **Username**, **Password**
- Buttons: **Login** (primary), **Register** (outline)
- Error: red text under fields
- Link: **Continue without account** → home (demo mode)

---

### 4.4 GRE Vocabulary — Hub (`/gre-vocab`)

**Hero:**

- Title: **GRE Vocabulary**
- Subtext: **Read, quiz, and master 30-word groups with spaced repetition.**

**Primary actions (cards or large buttons):**

| CTA | Subtext | Route |
|-----|---------|-------|
| **Start study cycle** | Read → Quiz → Report | `/gre-vocab/cycle` |
| **Browse & read** | All groups | `/gre-vocab/read` |
| **Add words** | Import JSON/CSV (admin) | `/gre-vocab/add-words` |

**Progress summary row (from `/api/vocab/progress/summary`):**

- **Studied:** `{studied_words}`
- **Mastered:** `{mastered_words}`
- **Due review:** `{due_reviews.count}`
- **Accuracy:** `{avg_accuracy}%`

**Group grid:** Cards per `group_number` from `/api/vocab/groups/detailed/`:

- Title: **Group {n}**
- Progress bar: completion %
- Chips: **Mastered**, **Need practice**, **Due**, **Not started**

---

### 4.5 Vocab — Read (`/gre-vocab/read`)

- Top: progress **Word {i} of {total}**
- **WordCard:** large word, IPA pronunciation, meaning, mnemonic, etymology, examples list
- Nav: **Previous** | **Next** | **Mark known**
- Sidebar optional: group filter

---

### 4.6 Vocab — Study cycle (`/gre-vocab/cycle`)

**Steps indicator:** Read → Quiz → Report → Low mastery (conditional)

**Quiz step:**

- Progress: **Question {n} of {total}**
- Word display (no meaning)
- **4 option buttons** (large, full width stack on mobile)
- Feedback overlay: **Correct!** / **Incorrect — {correct_answer}**
- Keyboard hint: **Press 1–4 to answer**

**Report step:**

- Title: **Session complete**
- Stats: **Accuracy {pct}%**, **{correct}/{total} correct**, **Words improved {n}**
- CTA: **Review low mastery** | **Back to dashboard**

---

### 4.7 Math — Dashboard (`/math-tutor`)

**Header:**

- Title: **Math Tutor**
- Subtext: **Pick a topic — practice with whiteboard and instant feedback.**

**Topic cards** (Arithmetic, Algebra, Geometry, Calculus, Trigonometry):

Each card:

- Title: topic label
- Description: one line from curriculum
- **{n} drills** badge
- CTA: **Open topic** → `/math-tutor/topic/{id}`

**Secondary:** **View reports** → `/math-tutor/reports`

---

### 4.8 Math — Topic (`/math-tutor/topic/:topicId`)

- Breadcrumb: **Math Tutor / {Topic}**
- **Read sections** (accordion): theory bullets
- **Formulas** strip with LaTeX-style monospace
- **Checkpoint roadmap** — horizontal steps
- Primary CTA: **Start practice** → `/math-tutor/practice/{topicId}`

---

### 4.9 Math — Practice (`/math-tutor/practice/:topicId`)

**Layout:** Split view

**Left column:**

- Timer: **{MM:SS}**
- Progress bar: question index
- **Prompt** (large): problem text
- **Your answer** input
- Buttons: **Check answer** | **Next problem**
- Feedback banner: success/destructive

**Right column:**

- **Whiteboard** toolbar: pen, eraser, clear
- Canvas area (light grid)

**End state:** **Post-session diagnostics** modal — duration, accuracy, performance label

---

### 4.10 Math — Reports (`/math-tutor/reports`)

- Title: **Math Reports**
- Table/list of attempts from `/api/vocab/math/sessions`
- Columns: **Topic**, **Prompt** (truncated), **Result** ✓/✗, **Date**
- **Mastery by topic** cards from `/api/vocab/math/mastery`

---

### 4.11 Life Tracker (`/life-tracker`)

**Two columns on desktop:**

**Left (upper):**

- **DayTimeTracker** full size (same as home widget)
- **Life Score** giant number: **{life_score}/100** with label **Today’s balance**

**Right — form sections (collapsible):**

| Section | Fields (labels exact) |
|---------|----------------------|
| **Health** | Sleep hours (0–12), Sleep quality (1–5), Exercise minutes, Water glasses (0–12), Healthy meals (0–3) |
| **Productivity** | Study minutes, Tasks completed, Deep work blocks |
| **Digital wellbeing** | Screen time hours, Social media minutes, Outdoor minutes |
| **Mental** | Mood (1–5), Stress (1–5), Meditation minutes |

**Pillar score rings:** Health, Productivity, Digital, Mental — values 0–100.

**CTA:** **Save today** → triggers `PUT /api/life/daily/today`  
**Success toast:** **“Day saved · Life score {n}”**

---

### 4.12 Settings hub (`/settings`)

List rows:

| Row | Chevron | Route |
|-----|---------|-------|
| **Appearance** | → | `/settings/theme` |
| **Plugins** | → | `/settings/plugins` |
| **Profile** | → | `/profile` |

---

### 4.13 Theme settings (`/settings/theme`)

- Title: **Appearance**
- **Theme:** Light / Dark toggle
- **Accent color:** swatches Default, Emerald, Violet, Rose, Amber + **Custom hex** input
- **Corner radius:** sm | md | lg | xl (preview card)
- **Contrast intensity:** slider 0–100 with labels **Softer** ↔ **Punchier**
- Live preview card with sample Button + Input

---

### 4.14 Plugin settings (`/settings/plugins`)

- Title: **Plugins**
- List: **Core Features** (locked on), **GRE Vocabulary**, **Math Tutor**, **Life Tracker**, **NutriNode**
- Each row: name, description, toggle (Switch)

---

### 4.15 Admin (`/admin`) — admin only

- Title: **Admin Panel**
- Table **Users:** username, progress rows, mastered, password hint field
- Actions: **Reset progress**, **Reset password**
- Danger zone: **Reset all progress**

---

### 4.16 Profile (`/profile`)

- Username display
- **Logout** button
- Link **Login** if guest

---

## 5. Copy & microcopy glossary

| Context | Text |
|---------|------|
| Loading | **Loading…** / **Loading modules…** |
| Empty vocab | **No words in this group yet.** |
| Empty hub clock | **Log your day in Life Tracker to fill the ring.** |
| API error | **Couldn’t reach the server. Check that the API is running on port 8000.** |
| Auth error | **Invalid credentials** |
| Quiz correct | **Correct!** |
| Quiz wrong | **Not quite — the answer is {answer}** |
| Math correct | **Correct (+{points} mastery)** |
| Connected | **Live** (green dot) |
| Disconnected | **Offline** |
| Save life | **Save today** |
| Customize | **Customize layout** |

**Tone:** Encouraging, concise, no exclamation overload. Second person (“you/your”).

---

## 6. Data binding (for realistic mocks in Stitch)

| UI area | Endpoint | Key fields |
|---------|----------|------------|
| Life clock | `GET /api/hub/daily/today` | `segments[]`, `life_score`, `productive_minutes`, `sleep_minutes` |
| Life form | `PUT /api/life/daily/today` | all life_daily_log fields → returns `life_score` |
| AI widget | `GET /api/insights/daily` | `overall_performance`, `life_score`, `vocab_events` |
| Vocab groups | `GET /api/vocab/groups/detailed/` | `groups[].stats`, `completion_percentage` |
| Quiz | `POST /api/vocab/quiz/adaptive/...` | session flow |
| Math problem | `GET /api/vocab/math/practice/next?topic=` | `problem.prompt`, `expected_answer` |
| Behavior widget | `GET /api/behavior/stats` | `events_today`, `domains[]` |

---

## 7. Responsive rules

| Breakpoint | Behavior |
|------------|----------|
| `<768px` | Sidebar collapsed by default; single column widgets; math practice stacks (problem above whiteboard) |
| `768–1024px` | 2-column widget grid |
| `≥1280px` | 4-column widget grid; full split practice |

---

## 8. Accessibility

- Min contrast WCAG AA for text on backgrounds
- Focus rings: `ring-2 ring-ring`
- All icon buttons: `aria-label`
- Quiz options: keyboard 1–4 called out in helper text
- Reduced motion: respect `prefers-reduced-motion` (disable ring animation)

---

## 9. Deliverables to request from Stitch

Ask Stitch to produce **high-fidelity mockups** (light + dark) for:

1. Study Hub dashboard (widgets visible)
2. Life Tracker full page
3. GRE Vocab hub + Quiz step
4. Math practice split view
5. Theme settings
6. Component sheet: buttons, inputs, cards, badges (all states)

**Export:** Figma-compatible or PNG @2x; include token table page.

---

## 10. Out of scope for this design pass

- Community rooms (placeholder only)
- Mobile native apps
- New navigation items not listed above
- Brand logo illustration (use text “Study Hub” until logo exists)

---

## Appendix: Paste-ready Stitch prompt (short)

```
Design a premium "Study Hub" web app (desktop 1440px) for GRE vocab, math practice, and daily life tracking. Style: glossy glass cards, Inter font, navy primary #1A1A2E, dark mode #050505 background. Include: collapsible sidebar, top bar with timer docks, draggable dashboard with a large 24-hour circular life clock (indigo sleep #6366F1, study blue #3B82F6, math green #10B981), widget cards with subtle gradient headers. Screens: Home dashboard, Life Tracker form with score rings, GRE quiz with 4 options, Math practice split (problem left, whiteboard right). Use shadcn/ui patterns. Light and dark variants. No gamification clutter.
```
