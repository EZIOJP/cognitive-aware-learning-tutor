# How blocking actually works

Written from the code, not from intent. If this file and the code disagree, the
code wins and this file is a bug. Last checked against source **2026-09-08**.

Read [The 60-second version](#the-60-second-version) if you just need to explain
it to someone. Everything after that is the exact rule, with the file that
decides it.

---

## The 60-second version

You have **two separate weapons** and they share nothing except your intent:

| | SoftLand | Arm |
|---|---|---|
| Blocks | **websites**, in the browser | **apps**, at the OS level |
| Decided by | `calt_msg_host.exe` asked by the Gate extension | `calt_enforcer.exe` kill loop |
| Switch | `softland_enabled` | `hard_block_armed` |
| Reads | `data/behavior/softland_policy.json` | `data/behavior/enforcer_policy.json` |
| Can it kill Steam? | Never | Yes |
| Can it block YouTube? | Yes | Never |

**SoftLand ON is not Armed.** Turning SoftLand on does not arm anything, and
SoftLand code is structurally forbidden from setting `hard_block_armed`.

SoftLand is **stateful**: the same URL is allowed or blocked depending on what
*mode* the day is in right now. Mode comes from your schedule, then gets
overridden by a reward day or free window (→ `free`), and incubation overrides
everything back to `study`.

SoftLand is a **blocklist, not an allowlist**. A site nobody has ever listed is
allowed, in every mode. Only the porn filter, your block/watch lists and the
built-in distractor list block anything.

**The day gets unlocked three ways, and only three:** hit your daily minutes
*and* tick a Bible chapter; spend a reward day (4 qualifying days buys one); or
spend a day pass (2 a week). Separately, small chores pay out **earned minutes**
(15 for Bible, 10 for the plan, 30 for the goal, 60/day cap) that you spend in
15-minute chunks. Reward days and passes are Python-owned, so they need `:8000`
up; the blocking itself never does.

---

## SoftLand: the exact decision ladder

One file decides: `native/calt_msg_host/src/softland_decide.cpp`
(`SoftlandGetMode`). The Gate extension asks it per navigation and blocks only
when the answer is `action: "block"` **and** `enforce` is not `false`.

### Step 0 — can the policy be read at all?

| Situation | Result | `reason` |
|-----------|--------|----------|
| `softland_policy.json` missing | **Block everything** | `softland_policy_missing` |
| File there but `softland_enabled` unreadable | **Block everything** | `softland_policy_corrupt` |
| `softland_enabled: false` | Allow everything, `enforce: false` | `softland_off` |

Missing or corrupt policy **fails closed** — a broken file must not open the
whole web. This is deliberate.

### Step 1 — what mode is it right now?

In this order, each line able to overwrite the one above:

1. **Schedule window.** If `schedules.enabled`, the **first** window whose
   `days` include today (Mon=0 … Sun=6) and whose `start`–`end` contains now
   supplies the mode. Windows may cross midnight (`22:00`–`06:00` works).
   No match, or schedules off → `study`.
2. **Reward day or free window** → `free`.
   A free window means `runtime.free_until` is in the future, **or** the clock
   has passed `runtime.free_after_hm`.
3. **Incubation** (`runtime.incubation_until` in the future) → back to `study`.
   Incubation always wins; it is the "you just tried to relapse, sit still"
   state.

The banner text picks its reason in the same priority: incubation, then reward
day, then free window — so during a cooldown you always see *why* you are stuck,
not the nicer reason underneath it.

### Step 2 — the host ladder, first match wins

Host is lowercased with scheme, port and a leading `www.` stripped. Matching is
exact host **or** any subdomain (`docs.google.com` matches `*.docs.google.com`).

| # | Rule | Verdict | `reason` |
|---|------|---------|----------|
| 1 | `site_rules.allow_extra`, or `localhost` / `127.0.0.1` | **Allow** | `allow_list` |
| 2 | Looks like porn, and the mode's `block_porn` is on | **Block** | `porn` |
| 3 | `site_rules.block_extra` | **Block** | `block_extra` |
| 4 | Mode is `free` and not incubating | **Allow** | `reward_day` / `free_window` / `free_mode` |
| 5 | Mode's `block_watch_sites` is on, and host is in `watch_extra` **or** the built-in list | **Block** | `watch_list` |
| 6 | Anything else | **Allow** | `not_listed` / `default_allow` |

Consequences worth saying out loud, because they surprise people:

- **Porn and `block_extra` beat free mode.** Rules 2 and 3 come before rule 4,
  so a reward day does not open them. That is the intended asymmetry.
- **`watch_extra` is study-only.** A reward day, a free window or a `free`
  schedule window lets everything on the watch list through (rule 4 fires
  first). If you want a site blocked *even on a reward day*, it belongs in
  `block_extra`, not `watch_extra`.
- **`allow_extra` beats the porn filter.** Rule 1 is above rule 2, so
  allow-listing a host disables porn blocking for it. See
  [Sharp edges](#sharp-edges).
- **While incubating, every block reads `incubation`**, even if what technically
  matched was the watch list — the urgent reason is not overwritten by a
  lesser one.

### The built-in watch list

Hardcoded in `softland_decide.cpp`, always in effect when
`block_watch_sites` is on, and **not editable from Settings**:

`youtube.com`, `youtu.be`, `netflix.com`, `primevideo.com`, `hotstar.com`,
`disneyplus.com`, `hulu.com`, `twitch.tv`, `reddit.com`, `twitter.com`, `x.com`,
`instagram.com`, `facebook.com`, `tiktok.com`, `discord.com`

The only way to unblock one of these in study mode is to put it in
`allow_extra`.

### The porn filter

Heuristic, not a list: host ends in `.xxx` / `.porn` / `.sex`, or contains
`porn`, `xvideos` or `pornhub`. It is on by default in **both** study and free
mode. It is not the same thing as the hosts-file porn block (see
[Hosts porn block](#hosts-porn-block)).

### Mode flags

`mode_flags.<mode>` overrides the defaults per mode. Unknown modes
(`planning`, `bible`) fall back to the `study` block.

| Flag | Study default | Free default | Actually used? |
|------|---------------|--------------|----------------|
| `block_porn` | on | on | **Yes** — rule 2 |
| `block_watch_sites` | on | off | **Yes** — rule 5 |
| `block_social` | on | off | No — social sites are covered by the built-in watch list |
| `block_keywords` | on | on | No — no keyword rule exists in the decide path |
| `block_other` | on | off | No real effect |
| `strict_allowlist` | on | off | No real effect — see below |

`strict_allowlist` does **not** create allowlist-only browsing. Unknown sites
are allowed regardless (rule 6). If you want allowlist-only study mode, that is
a feature to build, not a checkbox to flip.

---

## Arm: the exact kill rules

`calt_enforcer.exe` owns this end to end and needs **no Python running**.

- Reads `data/behavior/enforcer_policy.json` every tick (~1.5s). The JSON is
  authoritative; the SQLite row is a fallback when the file is missing.
- While `hard_block_armed` is true, it enumerates processes and terminates any
  whose executable base name matches your `exes` list, then appends to
  `data/behavior/enforcer_kills.log`.
- **Protected, never killed:** core Windows processes (`explorer.exe`,
  `csrss.exe`, `winlogon.exe`, `services.exe`, `lsass.exe`, `svchost.exe`,
  `smss.exe`, `fontdrvhost.exe`, …) plus `calt_focus.exe` and
  `calt_msg_host.exe`. Browsers are *not* blanket-protected — list a browser and
  it dies.
- **Lock modes** (`lock_mode`): `none`, `timer` (until `lock_until_unix`),
  `password`, `phrase`. A disarm that does not satisfy the lock is refused and
  the enforcer forces `armed + locked` back on, so editing the JSON by hand does
  not get you out.
- **Focus watchdog:** while SoftLand is on *or* Arm is on, `calt_focus.exe` and
  `calt_msg_host.exe` are relaunched if they die — at most 3 times in a rolling
  60s window, after which relaunching is suppressed (visible as
  `focus_relaunch_suppressed` in status) so a crash loop cannot spin forever.
- **Focus refuses to quit** from the tray while SoftLand is on or Arm is armed.
  Turn SoftLand off and disarm first.

---

## Hosts porn block

A third, independent thing, easy to confuse with the SoftLand porn filter.
`backend/behavior/device_block.py` writes a `# BEGIN CALT-DEVICE-BLOCK` section
into `C:\Windows\System32\drivers\etc\hosts`, pointing porn domains at
`0.0.0.0`. It needs **admin rights**, it applies to **every app** on the machine
(not just the browser), and it does not care whether SoftLand is on, what mode
you are in, or whether it is a reward day. Defaults: porn on, watch off, social
off.

So a porn domain can be blocked by up to three separate things at once: the
hosts file, the SoftLand porn heuristic, and the extension's own rules. Turning
one off does not turn the others off.

---

## Goals, earning and unlocks

This is the part with real numbers. Everything here is Python-owned, which means
**it needs `:8000` running** — unlike SoftLand and Arm, which do not.

> **This is a known deviation, not the design.** `AGENTS.md` locks day-pass, free
> and incubation accounting to the C++ product; it simply has not moved yet.
> Prod P5 does the move — see the
> [P5 design](superpowers/specs/2026-09-08-calt-productivity-p5-native-unlock-accounting-design.md)
> and the [P5a plan](superpowers/plans/2026-09-08-calt-productivity-p5a-native-unlock-accounting.md).
> Until then, read this section as "how it works today".

### What unlocks the day

One line decides it (`backend/behavior/distraction_gate.py:784`):

```python
day_unlimited = bool(reward_day or day_pass or (productive >= goal and chapter_met))
```

Three independent doors, any one of which opens the day:

| Door | Requirement |
|------|-------------|
| **Earn it** | productive minutes ≥ daily goal **and** ≥ 1 Bible chapter ticked |
| **Spend a reward day** | a credit from a 4-day streak (below) |
| **Spend a day pass** | 2 per Mon–Sun week, deliberate skip |

- **Daily goal** default **240 min** (`daily_goal_minutes`, editable 15–960).
- **Productive minutes** = wall-clock time in sessions whose score ≥ `threshold`
  (default **60**), with overlapping sessions merged so nothing double-counts and
  sleep windows subtracted.
- **Chapter** = 1 chapter, and it only counts when you tick it by hand — dwell
  time and PDF page turns deliberately do not count.

### Reward days — the 4-day streak

- A day **qualifies** when you hit both halves: productive ≥ goal *and* the
  chapter. Recorded once per day.
- **A day spent on a reward day never qualifies**, so you cannot farm streaks
  out of your days off.
- **4 qualifying days = 1 reward day** (`QUALIFYING_DAYS_PER_REWARD = 4`).
  `available = earned + granted − spent`.
- **Claiming** takes the typed phrase **`REWARD`**, and is refused if today is
  already unlocked some other way — "save the reward day for another day".
- Claiming writes four things at once: today into `used_dates`, `reward_day` on
  the Bible day, `runtime.reward_day_active` + `free_until` (today 23:59:59
  local) into the SoftLand policy, and a free override until midnight.
- **It ends at local midnight**, by the day file rolling over. There is no
  "end reward day" button.

### Day pass — the deliberate skip

Two per Mon–Sun week, confirmed by typing **`PASS`**. Unlike a reward day it does
**not** excuse you from the morning Bible and plan redirects. That asymmetry is
intentional: a pass buys the day, not the morning.

> **Broken today (fixed by P5a):** a day pass does not unlock a single website.
> `request_day_pass` writes only the Bible day file, and the SoftLand ladder never
> reads `runtime.day_pass` — so the pass flips the Python `day_unlimited` flag,
> which since Prod P4 no longer reaches the browser. Reward days work only because
> their claim explicitly writes `free_until`; nobody wired the pass. If you burn a
> pass right now, YouTube stays blocked.

### Earned minutes — the small change

A separate, much smaller currency than reward days
(`backend/behavior/break_reward.py`):

| Action | Earns | How often |
|--------|-------|-----------|
| Bible done | **15 min** | once a day |
| Plan confirmed | **10 min** | once a day |
| Daily goal hit | **30 min** | once a day |

Capped at **60 min earned per day**. Spending (default 15 min at a time) debits
the ledger and opens a free window; it is **refused while incubating**; and it
asks for a PIN only if `TRACKER_EXIT_PIN` is set in the environment. On the
native side, `softland.spend_free` always **extends** the current free window —
spending 15 minutes during a reward day can never shorten it.

### Incubation — the cooldown

- Starts either when a **study block ends** or after a **productive streak** of
  `work_minutes` (**45 min**).
- Lasts `break_minutes` (**8 min**, 480s fallback).
- **At most 1 per rolling hour.**
- While it runs: mode is forced to `study`, and spending earned minutes is
  refused.
- **It cannot be cancelled early.** There is no endpoint for it, and the
  `allow_snooze` config flag is stored but never read.

### Evening free and the study-loop gate

- **Evening free:** after `BROWSER_FREE_AFTER` (default **21:00**) the Python
  browser gate reports mode `free`. Native reads the same idea from
  `runtime.free_after_hm`.
- **Study-loop gate** is **off by default**. When on, and the plan is confirmed
  and the daily bite is unfinished, the morning step becomes `study` — only
  `/bible`, `/productivity`, `/profile` and `/review` stay reachable, redirecting
  to `/review?tab=loop`. It never writes the SoftLand policy itself.

---

## Where the state lives, and who may change it

```text
SoT (the truth)      → SQLite productivity_* tables in data/vocab_app.db
Only mutator         → calt_enforcer gateway, named pipe \\.\pipe\calt_enforcer_cmd
SoftLand hot read    → data/behavior/softland_policy.json   (mirror, published by enforcer)
Kill hot read        → data/behavior/enforcer_policy.json   (mirror, published by enforcer)
Health               → data/behavior/enforcer_status.json   (written by enforcer)
Kill history         → data/behavior/enforcer_kills.log
```

The UI never writes policy files directly. `calt_focus` posts a command into the
pipe, the enforcer applies it to SQLite and republishes the mirrors. Python may
still write `softland_policy.json`; the enforcer imports it whenever the file's
`updated_at` is newer than its own row, so nothing is lost in either direction.

The enforcer also runs a **clock tick**: expired incubation and free windows
clear themselves, and delayed edits (`productivity_pending_changes`) apply when
their `apply_after` passes — with no window open and no Python running.

---

## Settings, control by control

| Control | What it really does |
|---------|---------------------|
| SoftLand on/off | Master switch for **site** blocking only. Off = every site allowed (`softland_off`) |
| Allow extra | Rule 1 — wins over everything, including porn |
| Watch extra | Rule 5 — study mode only |
| Block extra | Rule 3 — every mode, including reward days |
| Gate schedules | Supplies the mode by day + time; first matching window wins |
| Mode flags | Only `block_porn` and `block_watch_sites` change behaviour today |
| Arm / Disarm + kill list | The OS killer and its target list |
| Lock mode / anti-tamper / protect uninstall | How hard it is to undo an Arm |
| Daily goal (min) and Plan's "daily focus h" | The **same** unlock target under two names — default 240 min |
| Category scores / productive threshold / app overrides | Feed the productive-time maths, i.e. whether the day counts. Python-owned — needs the API |
| Reward days / day pass / earned minutes | The three unlock currencies — see [Goals, earning and unlocks](#goals-earning-and-unlocks). Python-owned |
| Study-loop gate | Off by default; when on it forces the morning into the daily bite |
| Device porn block (hosts) | Separate OS-level filter, all apps, needs admin, unrelated to SoftLand rules |
| Demo mode (fake clock) | Testing aid; moves the clock the rules read |

Anything in the "needs the API" row stops working when `:8000` is down.
Everything above it — SoftLand, lists, schedules, Arm, the ledger — keeps
working, because it goes through the enforcer gateway.

---

## Sharp edges

Real behaviours that a reasonable person would guess wrong. None of these are
speculation; each was read out of the code.

1. **`allow_extra` disables the porn filter for that host.** The allow list is
   checked first so it can rescue a false positive (the filter is a substring
   heuristic), but it also means the allow list is a self-sabotage hatch. If you
   want porn blocking to be unconditional, rule 2 has to move above rule 1 —
   an intentional decision, not a bug fix, so it is left to you.
2. **`watch_extra` does nothing on a reward day.** Use `block_extra` for
   "always blocked".
3. **`strict_allowlist`, `block_other`, `block_social`, `block_keywords` are
   inert.** They are stored and shown but no rule consults them (social is
   handled by the built-in list). Do not tune them expecting an effect.
4. **The built-in watch list cannot be edited**, only overridden per host via
   `allow_extra`.
5. **Two names, one number:** Plan's "daily focus h" and Settings' "Daily goal
   (min)" are the same unlock target.
6. **Arm has a fail-open window:** if the enforcer process is not running,
   nothing kills anything. That is why it holds an ownership lock, gets
   relaunched, and should be installed as a service for stay-alive.
7. **"Goal met" and "day unlocked" are computed by two different functions and
   can disagree.** The unlock path (`distraction_gate`) uses your policy
   `threshold`, merges overlapping sessions, subtracts sleep, counts every
   source, **and requires a Bible chapter**. The `goal_met` chip
   (`goals_alerts`) uses a hardcoded threshold of 60, sums buckets, counts only
   three sources, and **ignores the Bible entirely**. So the chip can read "goal
   met" while the day is still locked.
8. **Claiming a reward day is refused on a day you already unlocked by working.**
   That is deliberate — it stops you burning a hard-won credit on a day you had
   already earned — but the message ("Today is already unlocked") reads like an
   error rather than a save.
9. **Incubation cannot be cancelled, by anyone.** No endpoint, no UI, and
   `allow_snooze` does nothing. Once it starts you wait the 8 minutes.
10. **The legacy Bible "game bank" is dead.** 30-minute chunks are still tracked
    and stored, but `has_bank` is hardcoded `False`, so banked time unlocks
    nothing. Chapter + study minutes is the only earn path.
11. **`softland_policy.goals.goal_met` is never written by Python.** It exists in
    the schema and normalises to `False` on read. Do not build UI on it.
12. **Everything in this section stops at `:8000`.** Goals, reward days, day
    passes, earned minutes and incubation are Python-owned, so with the API down
    they freeze — while SoftLand, the lists, schedules, Arm and the ledger keep
    working through the enforcer gateway. A day where the API was down is a day
    that earns no streak credit.

### Fixed on 2026-09-08 while writing this

Two rules did not match any reasonable description of them, and both are now
corrected in `softland_decide.cpp`:

- **Only the first schedule window was ever evaluated.** The window scan started
  on the `schedules` object itself, so window 1's fields were read and the loop
  then ran off the end. A "weekday focus + evening free" pair silently never
  entered evening free. Now the `windows` array is iterated properly, and `days`
  is parsed as numbers instead of searching the raw text for a digit.
- **`until` stamps were read as UTC.** Both free windows and incubation ran for
  the whole UTC offset longer than the UI promised — 5h30m here, so a reward day
  labelled "until 23:59" actually kept the web open until 05:29. Bare stamps are
  now read as local time and `+05:30` / `Z` suffixes are honoured. (The enforcer
  tick, which compares local time correctly, had been masking this whenever it
  was running.)

---

## Verify any of this yourself

No browser and no `:8000` needed:

```bat
:: what SoftLand thinks about one URL, through the real Gate path
powershell -File scripts\desktop_tracker\run\msg_host_cmd.ps1 -Json "{\"type\":\"get_mode\",\"url\":\"https://youtube.com\"}"

:: current SoftLand state straight from the SoT
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op status.snapshot

:: earned-minute ledger
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op ledger.snapshot -Payload "{\"limit\":10}"
```

To try rule changes without touching your live day, point the host at a fixture:

```powershell
$env:CALT_DATA_DIR = "$env:TEMP\calt_try\"   # needs behavior\softland_policy.json inside
powershell -File scripts\desktop_tracker\run\msg_host_cmd.ps1 -Json '{"type":"get_mode","url":"https://youtube.com"}'
Remove-Item Env:CALT_DATA_DIR
```

The reply's `reason` tells you which ladder rung fired, and `mode` tells you
which mode the clock and schedule put you in.

---

## Files that decide things

| Question | File |
|----------|------|
| Is this URL blocked? | `native/calt_msg_host/src/softland_decide.cpp` |
| Does the browser obey? | `calt-gate-extension/background.js`, `gate_policy.js`, `locked.js` |
| Is this app killed? | `native/calt_enforcer/src/kill.cpp`, `policy_db.cpp` |
| Who may change policy? | `native/calt_enforcer/src/cmd_gateway.cpp` |
| When do timers expire? | `native/calt_enforcer/src/softland_tick.cpp` |
| Policy shape + defaults | `backend/behavior/softland_policy.py` |
| Is the day unlocked? | `backend/behavior/distraction_gate.py` (line 784 is the whole answer) |
| Reward-day streak maths | `backend/behavior/reward_days.py` |
| Earned minutes + incubation | `backend/behavior/break_reward.py`, `break_reward_hooks.py` |
| Day pass + chapter goal | `backend/bible/store.py` |
| Scoring / what counts as productive | `backend/behavior/productivity_policy.py`, `category_scores.py` |
| Hosts-file porn block | `backend/behavior/device_block.py` |
| Product rules of ownership | [AGENTS.md](../AGENTS.md), [Phase 2 gateway spec](superpowers/specs/2026-09-08-calt-productivity-phase2-gateway-design.md) |
