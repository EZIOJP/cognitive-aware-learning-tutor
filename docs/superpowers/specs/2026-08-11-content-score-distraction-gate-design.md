# Content-score distraction gate (soft warn → escalate)

**Date:** 2026-08-11  
**Status:** Approved for implementation  
**Related:** `2026-07-17-distraction-hard-block-design.md`, CALT Gate + SelfTracker, `backend/behavior/browser_gate_policy.py`  
**Plan:** `docs/superpowers/plans/2026-08-11-content-score-distraction-gate.md`

## Problem

Domain blocklists cannot cover every adult site or mirror. Clean-looking hosts still load pages whose **visible text and link labels** are clearly NSFW. Today the gate only matches keywords on **URL + tab title**, so body content can slip through on pages that are allowed to load (Free mode, or Study allowlist).

## Goal

On pages that actually render (not already DNR-hard-blocked), score page text with **weighted keywords**. Soft-warn when the score is medium; hard-lock when it stays high or keeps rising. If the score is **low and not rising**, stop sampling for that navigation — no endless re-checks.

## Non-goals (v1)

- Image / video NSFW ML models
- Sending full page HTML to the backend for scoring
- Crawling live adult sites from the agent/CI to train lists
- Replacing host DNR hard-blocks (those stay first line of defense)

## Placement in the stack

| Layer | Role |
|-------|------|
| DNR + `FORCE_PORN_HOSTS` | Instant hard redirect for known distraction hosts (every mode) |
| URL/title keywords | Fast pre-load / softLand path (existing) |
| **Content sampler (new)** | After load on allowed pages; weighted score + escalate |

Study mode already blocks unknown hosts via allowlist / `block_other`. This feature targets **pages that were allowed to open**, especially Study allowlist and Free browsing.

## Components

### 1. Weighted keyword lexicon

- Extend `DEFAULT_BLOCK_KEYWORDS` (Python) and the matching offline seed in `gate_policy.js`.
- Prefer multi-word / explicit phrases; avoid bare short tokens (`ass`, `sex`) that false-trip medical/news pages.
- Each term has a **weight** (e.g. 1–5). Strong explicit terms weigh more than milder ones (`nsfw`, `erotic`).
- Hostnames already on the porn list do not need content scoring (DNR wins).

### 2. Content sampler (extension content script)

Runs only when:

- Gate redirects are enabled
- URL is not extension/internal, not `locked.html`, not CALT SPA
- Host is **not** a force-porn / force-watch host already handled by DNR

On each sample tick:

1. Collect `document.title` + truncated visible text (`innerText` of `body`, cap ~6k chars) + up to N link texts (`a` labels, cap ~2k chars combined).
2. Decode lightly (same spirit as existing keyword haystack).
3. Compute score = sum of weights for distinct matched terms in the sample, with a soft per-term frequency cap (e.g. same term counts at most 2–3×) so one repeated word alone cannot max the score — **clusters of different adult terms** matter more.
4. Compare to previous sample on this tab navigation: `delta = score - prevScore`.

### 3. Stop-early scheduler

Per tab navigation (`tabId` + URL key):

| Condition | Action |
|-----------|--------|
| After 1–2 samples, score &lt; `WARN_THRESHOLD` and `delta ≈ 0` | **Arm off** — no further samples until full reload, history URL change, or large DOM mutation burst |
| Score in `[WARN, LOCK)` | Soft warn once; keep sampling a few more ticks (Study: fewer ticks / lower bars) |
| Score ≥ `LOCK_THRESHOLD`, or score ≥ WARN and still rising after warn | Hard lock → `locked.html` (same path as other blocks); report gate alert kind `distraction` / `keyword` |

Default tick spacing: ~2.5s while armed; not a tight loop. MutationObserver may **re-arm** only if previously stopped and churn exceeds ~800 added text characters (or ~40 added nodes) within a 1s window — ignores tiny UI noise.

### 4. Soft warn UI

- Lightweight in-page banner (content script): short copy that this page looks like a distraction; no scary overlay stack.
- One show per navigation unless score climbs again after dismiss (optional dismiss does **not** disable hard lock if score later crosses LOCK).
- User-facing language: “distraction” / study focus — not graphic wording.

### 5. Mode thresholds (option B for Study allowlist)

| Mode context | WARN | LOCK | Max samples while armed |
|--------------|------|------|-------------------------|
| Free | 8 | 16 | 5 |
| Study + allowlisted host | 5 | 10 | 3 |

Starter weights: mild phrase = 1–2, strong explicit = 3–5. Constants live in one block in `gate_policy.js` (mirror weights in Python for unit tests). Tunable without redesign.

### 6. Temp allow / exclusions

- Force-porn / category porn hosts remain **not** temp-allowable (existing rule).
- Soft warn does not grant access; hard lock uses existing locked page.
- Allowlist hosts (Scaler, Colab, GitHub, etc.) **are** sampled — that is the point — but lexicon weights must stay explicit enough to avoid locking docs that mention “adult learning” etc. Prefer phrase matches.

## Data flow

```text
Page loads (allowed)
  → content script arms sampler
  → sample text+links → weighted score
  → low & flat → disarm (done)
  → medium → soft warn; continue briefly
  → high / rising → message SW → softLand / tabs.update locked.html
```

Service worker keeps policy (`block_porn`, `block_keywords`, mode). Sampler respects `redirectsEnabled` and does not double-hit DNR hosts (same softLand skip pattern as watch/porn hosts).

## Failure / privacy

- Scoring stays **on-device** in the extension; no page body POST to FastAPI in v1.
- Optional: alert kind + host only to existing gate alert endpoint (same as today), not raw text.
- If content script cannot inject (PDF viewer, restricted page), fall back to URL/title keywords only.

## Testing

- Unit: weighted score + frequency cap (JS and/or Python mirror of weights).
- Unit: stop-early when low and flat; escalate when rising.
- Policy regression: known hosts still block in Free/Study; `erome.com` etc. unchanged.
- Manual: allowlisted-looking page with planted adult link labels → warn then lock; normal docs page → 1–2 samples then quiet.

## Success criteria

1. Unknown adult pages with explicit body/link text get soft warn then hard lock without being on the host list.
2. Normal Study allowlist pages with low flat scores are not re-scanned forever.
3. Known distraction hosts still hard-block instantly via DNR.
4. No full-page text leaves the machine for scoring in v1.
