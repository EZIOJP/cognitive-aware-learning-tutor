# Prod P5a — Native unlock accounting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move day-pass quota, reward-day credits, earned-minute rates/caps and incubation limits out of Python and into `calt_enforcer`, so unlocks work with `:8000` stopped — and fix the live bug where a day pass unlocks no website.

**Architecture:** New `productivity_*` SQLite tables owned by the enforcer, five new gateway ops on the existing named pipe, a one-time import of the current JSON history, and Python endpoints reduced to thin gateway callers. No scoring is moved in this phase — nothing here needs productive-minute maths.

**Tech Stack:** C++17 (`native/calt_enforcer`), bundled SQLite (`third_party/sqlite/sqlite3.c`), Win32 named pipes, Python 3 / FastAPI for the thin callers, pytest, PowerShell for pipe smoke.

**Spec:** [P5 design](../specs/2026-09-08-calt-productivity-p5-native-unlock-accounting-design.md) §5 "P5a"

## Global Constraints

- The enforcer is the **only** mutator of productivity state; UI and Python go through `\\.\pipe\calt_enforcer_cmd`. (`AGENTS.md`)
- Never require a live Python process for the enforcer to arm, kill, track, tick or answer a command.
- `softland_enabled` = sites/SoftLand only. `hard_block_armed` = native kill switch only. SoftLand never sets `hard_block_armed`.
- No Cold Turkey code. Pattern reference only.
- `HandleOp` contract: return `""` for success, or a short snake_case error token (`bad_payload`, `store_load_failed`, `policy_key_missing`, …). Extra response JSON goes through `extraOut`, always prefixed with a comma.
- Every state write goes through `SaveAndPublish(s, behaviorDir)` so the JSON mirrors and `gateway_seq` stay consistent.
- Confirm phrases are enforced **natively**, not by the caller: `PASS` for a day pass, `REWARD` for a reward claim (case-insensitive, trimmed).
- Quota numbers, copied verbatim from the code being replaced: `DAY_PASSES_PER_WEEK = 2` (`backend/bible/store.py:21`), `QUALIFYING_DAYS_PER_REWARD = 4` (`backend/behavior/reward_days.py:22`), earn rates Bible `15` / plan `10` / daily goal `30` minutes, `daily_earn_cap = 60` minutes (`backend/behavior/break_reward.py:33-42`), incubation `work_minutes = 45`, `break_minutes = 8`, `max_incubations_per_hour = 1`.
- Weeks run **Monday–Sunday**, local time. Days are local calendar dates (`YYYY-MM-DD`), never UTC.
- There is **no C++ unit-test harness** in this repo and this plan does not add one. The native test cycle is the pipe smoke script from Task 1, run against a live enforcer. Python changes are covered by pytest.

---

## File Structure

**Created:**
- `scripts/desktop_tracker/run/smoke_p5a.ps1` — repeatable pipe smoke for every op in this phase, with pass/fail output.

**Modified:**
- `native/calt_enforcer/src/productivity_store.h` / `.cpp` — three new tables, the reward-meta row, accessors, and the JSON history import.
- `native/calt_enforcer/src/cmd_gateway.cpp` — five new ops plus native enforcement of incubation limits.
- `backend/bible/store.py` — `request_day_pass` / `grant_day_pass` become gateway callers; quota code deleted.
- `backend/behavior/reward_days.py` — `claim_reward_day` / `status` become gateway callers; streak code deleted.
- `backend/behavior/enforcer_gateway.py` *(new file, created in Task 5)* — the single Python helper that talks to the pipe.
- `tests/test_bible_day_pass.py`, `tests/test_reward_days.py` — rewritten against the gateway helper.
- `docs/BLOCKING_RULES.md`, `docs/superpowers/specs/2026-09-08-calt-productivity-p5-native-unlock-accounting-design.md`, `AGENTS.md` — status and ownership.

**Not touched in P5a:** `softland_decide.cpp` (a pass grants `free_until`, which the ladder already honours), `session_db.cpp`, anything scoring-related.

---

### Task 1: Tables, reward meta, and the smoke harness

**Files:**
- Modify: `native/calt_enforcer/src/productivity_store.cpp:509-538` (the DDL string in `ProductivityStoreOpen`)
- Modify: `native/calt_enforcer/src/productivity_store.h`
- Create: `scripts/desktop_tracker/run/smoke_p5a.ps1`

**Interfaces:**
- Consumes: existing `Exec()`, `gDb`, `IsoWall()`, `JsonEscape()` in `productivity_store.cpp`.
- Produces, for Tasks 2–4:
  - `std::string ProductivityLocalDate();` → `"YYYY-MM-DD"` local
  - `std::string ProductivityWeekStart();` → local Monday of this week, `"YYYY-MM-DD"`
  - `int ProductivityPassesUsedThisWeek();`
  - `bool ProductivityPassGrantedToday();`
  - `bool ProductivityInsertPass(const std::string& localDate, const std::string& weekStart);`
  - `int ProductivityRewardCount(const char* kind);` — `kind` is `"qualified"` or `"used"`
  - `int ProductivityRewardGranted();`
  - `bool ProductivityRewardMark(const char* kind, const std::string& localDate);`
  - `bool ProductivityDayEventSeconds(const std::string& localDate, const std::string& event, int* outSeconds);` — `false` when the event has not fired today
  - `int ProductivityDayEarnedSecondsToday();`
  - `bool ProductivityInsertDayEvent(const std::string& localDate, const std::string& event, int earnedSeconds);`
  - `int ProductivityIncubationStartsSinceIso(const std::string& sinceIso);`

- [ ] **Step 1: Add the DDL**

In `productivity_store.cpp`, extend the `ddl` string (immediately before the closing `productivity_gateway_meta` entry) with:

```cpp
      "CREATE TABLE IF NOT EXISTS productivity_day_passes ("
      "  local_date TEXT PRIMARY KEY,"
      "  week_start TEXT NOT NULL,"
      "  granted_at TEXT NOT NULL,"
      "  source TEXT NOT NULL DEFAULT 'gateway'"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_reward_credits ("
      "  local_date TEXT NOT NULL,"
      "  kind TEXT NOT NULL,"          // 'qualified' | 'used'
      "  recorded_at TEXT NOT NULL,"
      "  PRIMARY KEY (local_date, kind)"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_reward_meta ("
      "  id INTEGER PRIMARY KEY CHECK (id = 1),"
      "  granted INTEGER NOT NULL DEFAULT 0"
      ");"
      "CREATE TABLE IF NOT EXISTS productivity_day_events ("
      "  local_date TEXT NOT NULL,"
      "  event TEXT NOT NULL,"
      "  at TEXT NOT NULL,"
      "  earned_seconds INTEGER NOT NULL DEFAULT 0,"
      "  PRIMARY KEY (local_date, event)"
      ");"
```

After the existing `productivity_gateway_meta` seed, add:

```cpp
  Exec("INSERT OR IGNORE INTO productivity_reward_meta (id, granted) VALUES (1, 0);");
```

- [ ] **Step 2: Add the local-date helpers**

In `productivity_store.cpp`, in the anonymous namespace next to `IsoWall()`:

```cpp
std::string LocalDateStr() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02u", st.wYear, st.wMonth, st.wDay);
  return buf;
}

// Monday-start week, local time.
std::string WeekStartStr() {
  SYSTEMTIME st;
  GetLocalTime(&st);
  // wDayOfWeek: 0=Sunday
  int back = (st.wDayOfWeek == 0) ? 6 : (st.wDayOfWeek - 1);
  FILETIME ft;
  SystemTimeToFileTime(&st, &ft);
  ULARGE_INTEGER uli;
  uli.LowPart = ft.dwLowDateTime;
  uli.HighPart = ft.dwHighDateTime;
  uli.QuadPart -= (ULONGLONG)back * 24ULL * 3600ULL * 10000000ULL;
  ft.dwLowDateTime = uli.LowPart;
  ft.dwHighDateTime = uli.HighPart;
  SYSTEMTIME out;
  FileTimeToSystemTime(&ft, &out);
  char buf[16];
  snprintf(buf, sizeof(buf), "%04u-%02u-%02u", out.wYear, out.wMonth, out.wDay);
  return buf;
}
```

`FileTimeToSystemTime` on a local-derived `FILETIME` keeps local wall clock, which is what we want here — the value is only ever compared against other local date strings.

- [ ] **Step 3: Add the accessors**

Append to `productivity_store.cpp` (and declare each in `productivity_store.h`):

```cpp
std::string ProductivityLocalDate() { return LocalDateStr(); }
std::string ProductivityWeekStart() { return WeekStartStr(); }

int ProductivityPassesUsedThisWeek() {
  if (!gDb) return 0;
  sqlite3_stmt* st = nullptr;
  int n = 0;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT COUNT(*) FROM productivity_day_passes WHERE week_start = ?;", -1,
                         &st, nullptr) == SQLITE_OK) {
    std::string wk = WeekStartStr();
    sqlite3_bind_text(st, 1, wk.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int(st, 0);
  }
  sqlite3_finalize(st);
  return n;
}

bool ProductivityPassGrantedToday() {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  bool found = false;
  if (sqlite3_prepare_v2(gDb, "SELECT 1 FROM productivity_day_passes WHERE local_date = ?;", -1,
                         &st, nullptr) == SQLITE_OK) {
    std::string d = LocalDateStr();
    sqlite3_bind_text(st, 1, d.c_str(), -1, SQLITE_TRANSIENT);
    found = sqlite3_step(st) == SQLITE_ROW;
  }
  sqlite3_finalize(st);
  return found;
}

bool ProductivityInsertPass(const std::string& localDate, const std::string& weekStart) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT OR IGNORE INTO productivity_day_passes "
                         "(local_date, week_start, granted_at, source) VALUES (?, ?, ?, 'gateway');",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  std::string now = IsoWall();
  sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, weekStart.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, now.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

int ProductivityRewardCount(const char* kind) {
  if (!gDb) return 0;
  sqlite3_stmt* st = nullptr;
  int n = 0;
  if (sqlite3_prepare_v2(gDb, "SELECT COUNT(*) FROM productivity_reward_credits WHERE kind = ?;",
                         -1, &st, nullptr) == SQLITE_OK) {
    sqlite3_bind_text(st, 1, kind, -1, SQLITE_STATIC);
    if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int(st, 0);
  }
  sqlite3_finalize(st);
  return n;
}

int ProductivityRewardGranted() {
  if (!gDb) return 0;
  sqlite3_stmt* st = nullptr;
  int n = 0;
  if (sqlite3_prepare_v2(gDb, "SELECT granted FROM productivity_reward_meta WHERE id = 1;", -1, &st,
                         nullptr) == SQLITE_OK) {
    if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int(st, 0);
  }
  sqlite3_finalize(st);
  return n;
}

bool ProductivityRewardMark(const char* kind, const std::string& localDate) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT OR IGNORE INTO productivity_reward_credits "
                         "(local_date, kind, recorded_at) VALUES (?, ?, ?);",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  std::string now = IsoWall();
  sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, kind, -1, SQLITE_STATIC);
  sqlite3_bind_text(st, 3, now.c_str(), -1, SQLITE_TRANSIENT);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

bool ProductivityDayEventSeconds(const std::string& localDate, const std::string& event,
                                 int* outSeconds) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  bool found = false;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT earned_seconds FROM productivity_day_events "
                         "WHERE local_date = ? AND event = ?;",
                         -1, &st, nullptr) == SQLITE_OK) {
    sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
    sqlite3_bind_text(st, 2, event.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(st) == SQLITE_ROW) {
      found = true;
      if (outSeconds) *outSeconds = sqlite3_column_int(st, 0);
    }
  }
  sqlite3_finalize(st);
  return found;
}

int ProductivityDayEarnedSecondsToday() {
  if (!gDb) return 0;
  sqlite3_stmt* st = nullptr;
  int n = 0;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT COALESCE(SUM(earned_seconds), 0) FROM productivity_day_events "
                         "WHERE local_date = ?;",
                         -1, &st, nullptr) == SQLITE_OK) {
    std::string d = LocalDateStr();
    sqlite3_bind_text(st, 1, d.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int(st, 0);
  }
  sqlite3_finalize(st);
  return n;
}

bool ProductivityInsertDayEvent(const std::string& localDate, const std::string& event,
                                int earnedSeconds) {
  if (!gDb) return false;
  sqlite3_stmt* st = nullptr;
  if (sqlite3_prepare_v2(gDb,
                         "INSERT OR IGNORE INTO productivity_day_events "
                         "(local_date, event, at, earned_seconds) VALUES (?, ?, ?, ?);",
                         -1, &st, nullptr) != SQLITE_OK)
    return false;
  std::string now = IsoWall();
  sqlite3_bind_text(st, 1, localDate.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 2, event.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_text(st, 3, now.c_str(), -1, SQLITE_TRANSIENT);
  sqlite3_bind_int(st, 4, earnedSeconds);
  bool ok = sqlite3_step(st) == SQLITE_DONE;
  sqlite3_finalize(st);
  return ok;
}

// Rate limit source for incubation: ledger rows written by set_incubation.
int ProductivityIncubationStartsSinceIso(const std::string& sinceIso) {
  if (!gDb) return 0;
  sqlite3_stmt* st = nullptr;
  int n = 0;
  if (sqlite3_prepare_v2(gDb,
                         "SELECT COUNT(*) FROM productivity_ledger "
                         "WHERE kind = 'incubation' AND ts >= ?;",
                         -1, &st, nullptr) == SQLITE_OK) {
    sqlite3_bind_text(st, 1, sinceIso.c_str(), -1, SQLITE_TRANSIENT);
    if (sqlite3_step(st) == SQLITE_ROW) n = sqlite3_column_int(st, 0);
  }
  sqlite3_finalize(st);
  return n;
}
```

- [ ] **Step 4: Write the smoke harness**

Create `scripts/desktop_tracker/run/smoke_p5a.ps1`:

```powershell
<#
  P5a pipe smoke. Requires calt_enforcer running. Read-only ops are safe;
  mutating ops are gated behind -Mutate so this can be run on a live day.
#>
param([switch]$Mutate)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$gw = Join-Path $PSScriptRoot "gateway_cmd.ps1"
$fail = 0

function Check($label, $json, $pattern) {
  if ($json -match $pattern) { "PASS  $label" }
  else { "FAIL  $label`n      got: $json"; $script:fail++ }
}

$s = & $gw -Op "day.status"
Check "day.status returns pass quota" $s '"passes_limit":\s*2'
Check "day.status returns credits"    $s '"reward_available":'

if ($Mutate) {
  $r = & $gw -Op "day.grant_pass" -Payload '{"confirm":"nope"}'
  Check "grant_pass rejects wrong phrase" $r '"error":\s*"confirm_required"'

  $r = & $gw -Op "reward.claim" -Payload '{"confirm":"nope"}'
  Check "reward.claim rejects wrong phrase" $r '"error":\s*"confirm_required"'

  $r = & $gw -Op "day.mark_event" -Payload '{"event":"bogus"}'
  Check "mark_event rejects unknown event" $r '"error":\s*"bad_payload"'
}

if ($fail -eq 0) { "`nP5a smoke: all checks passed" } else { "`nP5a smoke: $fail failure(s)"; exit 1 }
```

- [ ] **Step 5: Build**

Run: `scripts\desktop_tracker\build\build_native_enforcer.bat`
Expected: `Built: …\calt_enforcer.exe`, exit code 0. If the link fails with `Permission denied`, stop the running enforcer first (`Stop-Process -Name calt_enforcer -Force`) and rebuild.

- [ ] **Step 6: Verify the tables exist**

Run:
```powershell
python -c "import sqlite3;d=sqlite3.connect(r'data/vocab_app.db');print([r[0] for r in d.execute(\"select name from sqlite_master where type='table' and name like 'productivity_%'\")])"
```
Expected: the list includes `productivity_day_passes`, `productivity_reward_credits`, `productivity_reward_meta`, `productivity_day_events`.

- [ ] **Step 7: Commit**

```bash
git add native/calt_enforcer/src/productivity_store.h native/calt_enforcer/src/productivity_store.cpp scripts/desktop_tracker/run/smoke_p5a.ps1
git commit -m "feat(enforcer): day-pass/reward/day-event tables + P5a smoke harness"
```

---

### Task 2: `day.grant_pass` — the quota and the fix

**Files:**
- Modify: `native/calt_enforcer/src/cmd_gateway.cpp` (inside `HandleOp`, after the `softland.set_day_pass` block)

**Interfaces:**
- Consumes: Task 1's `ProductivityLocalDate`, `ProductivityWeekStart`, `ProductivityPassesUsedThisWeek`, `ProductivityPassGrantedToday`, `ProductivityInsertPass`; existing `EndOfLocalDayIso`, `SaveAndPublish`, `ProductivityLedgerAdd`, `ProductivityReplaceJsonValue`, `JsonGetString`.
- Produces: op `day.grant_pass`, error tokens `confirm_required`, `pass_quota_exhausted`.

- [ ] **Step 1: Add a confirm-phrase helper**

In the anonymous namespace of `cmd_gateway.cpp`:

```cpp
bool ConfirmMatches(const std::string& payload, const char* expected) {
  std::string got;
  if (!JsonGetString(payload, "confirm", &got)) return false;
  size_t a = got.find_first_not_of(" \t\r\n");
  size_t b = got.find_last_not_of(" \t\r\n");
  if (a == std::string::npos) return false;
  std::string trimmed = got.substr(a, b - a + 1);
  for (auto& c : trimmed) c = (char)toupper((unsigned char)c);
  return trimmed == expected;
}
```

- [ ] **Step 2: Add the op**

```cpp
  if (op == "day.grant_pass") {
    if (!ConfirmMatches(payload, "PASS")) return "confirm_required";
    const std::string today = ProductivityLocalDate();
    const bool already = ProductivityPassGrantedToday();
    if (!already && ProductivityPassesUsedThisWeek() >= 2) return "pass_quota_exhausted";
    if (!already && !ProductivityInsertPass(today, ProductivityWeekStart()))
      return "store_save_failed";

    // One free-window mechanism: the ladder already honours free_until. The
    // day_pass object stays as audit so day.status can report it.
    s.free_until = EndOfLocalDayIso();
    std::string obj = "{\"date\": \"" + today + "\", \"spent\": true, \"remaining_seconds\": 0}";
    if (!ProductivityReplaceJsonValue(s.document_json, "day_pass", obj)) return "policy_key_missing";
    std::string err = SaveAndPublish(s, behaviorDir);
    if (!err.empty()) return err;
    if (!already) ProductivityLedgerAdd("day_pass", 0, "day pass granted " + today, "gateway");
    return "";
  }
```

Granting twice in one day is idempotent — it re-arms `free_until` without burning a second pass, matching Python's "Already unlocked today" behaviour.

- [ ] **Step 3: Build and restart the enforcer**

Run: `scripts\desktop_tracker\build\build_native_enforcer.bat`
Then restart the service so the new binary is live:
`powershell -File scripts\desktop_tracker\install\install_native_enforcer.ps1`
Expected: build exit code 0; `gateway_cmd.ps1 -Op status.snapshot` answers.

- [ ] **Step 4: Test the reject path**

Run: `powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op day.grant_pass -Payload '{"confirm":"nope"}'`
Expected: `"ok":false` with `"error":"confirm_required"`.

- [ ] **Step 5: Test the grant path end to end**

Record the current state first so it can be restored:
```powershell
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op status.snapshot
```
Grant, then ask the real Gate path whether a watch site is allowed:
```powershell
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op day.grant_pass -Payload '{"confirm":"PASS"}'
powershell -File scripts\desktop_tracker\run\msg_host_cmd.ps1 -Json '{"type":"get_mode","url":"https://youtube.com"}'
```
Expected: grant returns `"ok":true`; `get_mode` returns `"action":"allow"` with `"mode":"free"` and a `"until"` of tonight 23:59:59. **This is the bug fix — before P5a this returned `"action":"block"`.**

- [ ] **Step 6: Test the quota**

With two passes already recorded this week, a third must fail:
```powershell
python -c "import sqlite3;d=sqlite3.connect(r'data/vocab_app.db');print(list(d.execute('select * from productivity_day_passes')))"
```
Expected: rows for the granted dates. Insert a synthetic second date for this week, then attempt a grant on a third date and expect `"error":"pass_quota_exhausted"`. Delete the synthetic row afterwards.

- [ ] **Step 7: Restore state and commit**

Clear the test pass if this was not a real pass day:
```powershell
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op softland.set_day_pass -Payload '{"date":null,"spent":false,"remaining_seconds":0}'
python -c "import sqlite3;d=sqlite3.connect(r'data/vocab_app.db');d.execute(\"delete from productivity_day_passes where local_date=date('now','localtime')\");d.commit()"
```

```bash
git add native/calt_enforcer/src/cmd_gateway.cpp
git commit -m "feat(enforcer): day.grant_pass enforces PASS + 2/week quota and opens the free window"
```

---

### Task 3: `day.mark_event` — earn rates and the daily cap

**Files:**
- Modify: `native/calt_enforcer/src/cmd_gateway.cpp` (after `day.grant_pass`)

**Interfaces:**
- Consumes: Task 1's `ProductivityDayEventSeconds`, `ProductivityDayEarnedSecondsToday`, `ProductivityInsertDayEvent`, `ProductivityLocalDate`.
- Produces: op `day.mark_event`; accepted events `chapter_done`, `plan_confirmed`, `daily_goal`, `bite_done`; error token `event_already_recorded`.

- [ ] **Step 1: Add the rate table and the op**

```cpp
  if (op == "day.mark_event") {
    std::string event;
    if (!JsonGetString(payload, "event", &event) || event.empty()) return "bad_payload";
    // Rates copied from backend/behavior/break_reward.py DEFAULT_CONFIG.
    int minutes = 0;
    if (event == "chapter_done") minutes = 15;
    else if (event == "plan_confirmed") minutes = 10;
    else if (event == "daily_goal") minutes = 30;
    else if (event == "bite_done") minutes = 0;
    else return "bad_payload";

    const std::string today = ProductivityLocalDate();
    if (ProductivityDayEventSeconds(today, event, nullptr)) return "event_already_recorded";

    // Daily cap 60 min: credit only the remainder, never negative.
    const int capSeconds = 60 * 60;
    int used = ProductivityDayEarnedSecondsToday();
    int want = minutes * 60;
    int credit = want;
    if (used + credit > capSeconds) credit = capSeconds - used;
    if (credit < 0) credit = 0;

    if (!ProductivityInsertDayEvent(today, event, credit)) return "store_save_failed";
    if (credit > 0) {
      s.earned_ledger_seconds += credit;
      std::string err = SaveAndPublish(s, behaviorDir);
      if (!err.empty()) return err;
      ProductivityLedgerAdd("earn", credit, event, "gateway");
    }
    if (extraOut)
      *extraOut = ",\"credited_seconds\":" + std::to_string(credit) +
                  ",\"balance_seconds\":" + std::to_string(s.earned_ledger_seconds);
    return "";
  }
```

- [ ] **Step 2: Build and restart**

Run: `scripts\desktop_tracker\build\build_native_enforcer.bat` then the install script.
Expected: exit code 0, gateway answers.

- [ ] **Step 3: Test rate, idempotence and cap**

```powershell
$gw = "scripts\desktop_tracker\run\gateway_cmd.ps1"
powershell -File $gw -Op day.mark_event -Payload '{"event":"chapter_done"}'
powershell -File $gw -Op day.mark_event -Payload '{"event":"chapter_done"}'
powershell -File $gw -Op day.mark_event -Payload '{"event":"plan_confirmed"}'
powershell -File $gw -Op day.mark_event -Payload '{"event":"daily_goal"}'
powershell -File $gw -Op day.mark_event -Payload '{"event":"bogus"}'
```
Expected in order: `credited_seconds:900`; `"error":"event_already_recorded"`; `credited_seconds:600`; `credited_seconds:1800`; `"error":"bad_payload"`. Total credited 3300s — under the 3600s cap, so nothing is clipped. To exercise the clip, add a synthetic 2400s event row for today first and confirm `daily_goal` then credits only the remainder.

- [ ] **Step 4: Restore and commit**

```powershell
python -c "import sqlite3;d=sqlite3.connect(r'data/vocab_app.db');d.execute(\"delete from productivity_day_events where local_date=date('now','localtime')\");d.execute(\"delete from productivity_ledger where source='gateway' and kind='earn' and ts>=datetime('now','-1 hour')\");d.commit()"
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op ledger.add -Payload '{"kind":"adjust","seconds":0,"note":"p5a smoke reset"}'
```
Then set `earned_ledger_seconds` back to its pre-test value recorded in Task 2 Step 5.

```bash
git add native/calt_enforcer/src/cmd_gateway.cpp
git commit -m "feat(enforcer): day.mark_event credits earn rates once per day under the 60m cap"
```

---

### Task 4: `reward.claim`, `reward.status`, `day.status`, and native incubation limits

**Files:**
- Modify: `native/calt_enforcer/src/cmd_gateway.cpp` (after `day.mark_event`, and inside the existing `softland.set_incubation` block)

**Interfaces:**
- Consumes: Task 1's `ProductivityRewardCount`, `ProductivityRewardGranted`, `ProductivityRewardMark`, `ProductivityIncubationStartsSinceIso`, `ProductivityPassesUsedThisWeek`; existing `EndOfLocalDayIso`, `AddMinutesLocalIso`.
- Produces: ops `reward.claim`, `reward.status`, `day.status`; error tokens `no_reward_available`, `already_unlocked`, `incubation_rate_limited`.

- [ ] **Step 1: Add reward status and claim**

```cpp
  if (op == "reward.status" || op == "day.status") {
    const int qualified = ProductivityRewardCount("qualified");
    const int used = ProductivityRewardCount("used");
    const int granted = ProductivityRewardGranted();
    const int earned = qualified / 4;  // QUALIFYING_DAYS_PER_REWARD
    int available = earned + granted - used;
    if (available < 0) available = 0;
    const int toNext = 4 - (qualified % 4);
    std::string extra = ",\"qualified_days\":" + std::to_string(qualified) +
                        ",\"reward_earned\":" + std::to_string(earned) +
                        ",\"reward_granted\":" + std::to_string(granted) +
                        ",\"reward_spent\":" + std::to_string(used) +
                        ",\"reward_available\":" + std::to_string(available) +
                        ",\"days_to_next_reward\":" + std::to_string(toNext);
    if (op == "day.status") {
      extra += ",\"passes_limit\":2,\"passes_used\":" +
               std::to_string(ProductivityPassesUsedThisWeek()) +
               ",\"pass_today\":" + (ProductivityPassGrantedToday() ? "true" : "false") +
               ",\"earned_today_seconds\":" + std::to_string(ProductivityDayEarnedSecondsToday()) +
               ",\"balance_seconds\":" + std::to_string(s.earned_ledger_seconds) +
               ",\"free_until\":" + (s.free_until.empty() ? "null" : "\"" + s.free_until + "\"") +
               ",\"reward_day_active\":" + (s.reward_day_active ? "true" : "false");
    }
    if (extraOut) *extraOut = extra;
    return "";
  }
  if (op == "reward.claim") {
    if (!ConfirmMatches(payload, "REWARD")) return "confirm_required";
    const int qualified = ProductivityRewardCount("qualified");
    const int used = ProductivityRewardCount("used");
    const int available = qualified / 4 + ProductivityRewardGranted() - used;
    if (available <= 0) return "no_reward_available";
    if (s.reward_day_active) return "already_unlocked";
    const std::string today = ProductivityLocalDate();
    if (!ProductivityRewardMark("used", today)) return "store_save_failed";
    s.reward_day_active = true;
    s.free_until = EndOfLocalDayIso();
    std::string err = SaveAndPublish(s, behaviorDir);
    if (!err.empty()) return err;
    ProductivityLedgerAdd("reward_day", 0, "reward day claimed " + today, "gateway");
    return "";
  }
```

`already_unlocked` here means "a reward day is already running", which is the narrow, useful version of Python's over-broad `already_unlocked` check (spec §1 sharp edge 8). Refusing a claim because the day was earned organically is a P5c decision, once the enforcer knows the day's unlock state.

- [ ] **Step 2: Enforce the incubation rate limit natively**

Replace the body of the existing `softland.set_incubation` block with:

```cpp
  if (op == "softland.set_incubation") {
    // max_incubations_per_hour = 1 (break_reward.py DEFAULT_CONFIG)
    if (ProductivityIncubationStartsSinceIso(AddMinutesLocalIso(-60)) >= 1)
      return "incubation_rate_limited";
    std::string until;
    int minutes = 0;
    if (JsonGetString(payload, "until_iso", &until) && !until.empty()) {
      s.incubation_until = until;
    } else if (JsonGetInt(payload, "minutes", &minutes) && minutes > 0) {
      s.incubation_until = AddMinutesLocalIso(minutes);
    } else {
      s.incubation_until = AddMinutesLocalIso(8);  // break_minutes default
    }
    std::string err = SaveAndPublish(s, behaviorDir);
    if (!err.empty()) return err;
    ProductivityLedgerAdd("incubation", 0, "incubation start", "gateway");
    return "";
  }
```

`AddMinutesLocalIso` must accept a negative argument for this to work — confirm it does; if it clamps at zero, add `AddMinutesLocalIso(int minutes)` support for negatives before using it here.

- [ ] **Step 3: Build, restart, and run the smoke harness**

Run: `scripts\desktop_tracker\build\build_native_enforcer.bat`, then the install script, then:
`powershell -File scripts\desktop_tracker\run\smoke_p5a.ps1 -Mutate`
Expected: `P5a smoke: all checks passed`.

- [ ] **Step 4: Test claim and rate limit by hand**

```powershell
$gw = "scripts\desktop_tracker\run\gateway_cmd.ps1"
powershell -File $gw -Op reward.status
powershell -File $gw -Op reward.claim -Payload '{"confirm":"REWARD"}'
powershell -File $gw -Op softland.set_incubation -Payload '{"minutes":8}'
powershell -File $gw -Op softland.set_incubation -Payload '{"minutes":8}'
```
Expected: status reports counts; claim fails with `no_reward_available` on a fresh DB (or succeeds if credits were imported); first incubation succeeds; **second returns `incubation_rate_limited`**. Clear with `softland.clear_incubation`.

- [ ] **Step 5: Commit**

```bash
git add native/calt_enforcer/src/cmd_gateway.cpp
git commit -m "feat(enforcer): reward.claim/status, day.status, native incubation rate limit"
```

---

### Task 5: Import the existing JSON history

**Files:**
- Modify: `native/calt_enforcer/src/productivity_store.cpp` (new `ProductivityImportLegacyUnlockHistory`, called once from `ProductivityMigrateAndImport`)
- Modify: `native/calt_enforcer/src/productivity_store.h`

**Interfaces:**
- Consumes: `data/bible/reward_days_*.json` (`qualified_dates`, `used_dates`, `granted`) and `data/bible/day_passes_*.json` (`week`, `dates`).
- Produces: `void ProductivityImportLegacyUnlockHistory(const std::wstring& dataDir);` — idempotent, `INSERT OR IGNORE` only, never deletes the source files.

- [ ] **Step 1: Write the import**

The files are small and flat, so reuse the existing string-scanning helpers rather than adding a JSON library. For each `reward_days_*.json`: pull the `qualified_dates` and `used_dates` arrays with `ParseStringArrayNear`-style scanning, insert each with `ProductivityRewardMark("qualified"|"used", date)`, and write `granted` into `productivity_reward_meta`. For each `day_passes_*.json`: insert each date in `dates` with `ProductivityInsertPass(date, week)` — the stored `week` field is already the Monday key.

Guard the whole thing with a marker so it runs once:

```cpp
  // Import only while the tables are empty — re-running must not resurrect
  // rows the owner deleted on purpose.
  if (ProductivityRewardCount("qualified") > 0 || ProductivityRewardCount("used") > 0) return;
```

- [ ] **Step 2: Call it from the migrator**

In `ProductivityMigrateAndImport`, after the softland import, add
`ProductivityImportLegacyUnlockHistory(dataDir);`.

- [ ] **Step 3: Verify counts match the JSON**

Before building, record the truth:
```powershell
Get-ChildItem data\bible\reward_days_*.json | ForEach-Object { $j = Get-Content $_ -Raw | ConvertFrom-Json; "$($_.Name): qualified=$($j.qualified_dates.Count) used=$($j.used_dates.Count) granted=$($j.granted)" }
Get-ChildItem data\bible\day_passes_*.json | ForEach-Object { $j = Get-Content $_ -Raw | ConvertFrom-Json; "$($_.Name): week=$($j.week) dates=$($j.dates.Count)" }
```
Build, restart, then compare:
```powershell
python -c "import sqlite3;d=sqlite3.connect(r'data/vocab_app.db');print('qualified',list(d.execute(\"select count(*) from productivity_reward_credits where kind='qualified'\"))[0][0]);print('used',list(d.execute(\"select count(*) from productivity_reward_credits where kind='used'\"))[0][0]);print('passes',list(d.execute('select count(*) from productivity_day_passes'))[0][0]);print('granted',list(d.execute('select granted from productivity_reward_meta'))[0][0])"
```
Expected: counts equal the JSON totals. `reward.status` must now report the same `available` as the Python `/api/bible/day` response did before the change.

- [ ] **Step 4: Confirm idempotence**

Restart the enforcer once more and re-run the count query.
Expected: identical numbers, no duplicates.

- [ ] **Step 5: Commit**

```bash
git add native/calt_enforcer/src/productivity_store.h native/calt_enforcer/src/productivity_store.cpp
git commit -m "feat(enforcer): one-time import of day-pass and reward-credit history"
```

---

### Task 6: Python becomes a thin caller

**Files:**
- Create: `backend/behavior/enforcer_gateway.py`
- Modify: `backend/bible/store.py:571-652` (`grant_day_pass`, `day_pass_status`, `request_day_pass`)
- Modify: `backend/behavior/reward_days.py` (`status`, `claim_reward_day`, `record_qualifying_day`)
- Test: `tests/test_bible_day_pass.py`, `tests/test_reward_days.py`

**Interfaces:**
- Produces: `gateway_call(op: str, payload: dict | None = None, *, timeout: float = 3.0) -> dict` — returns the parsed reply, raises `GatewayUnavailable` when the pipe is absent.

- [ ] **Step 1: Write the failing test**

In `tests/test_bible_day_pass.py`:

```python
def test_request_day_pass_goes_through_gateway(monkeypatch):
    calls = []

    def fake_call(op, payload=None, **kw):
        calls.append((op, payload))
        return {"ok": True}

    monkeypatch.setattr("backend.behavior.enforcer_gateway.gateway_call", fake_call)
    out = store.request_day_pass(1, confirm="PASS")
    assert out["ok"] is True
    assert calls == [("day.grant_pass", {"confirm": "PASS"})]
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python -m pytest tests/test_bible_day_pass.py::test_request_day_pass_goes_through_gateway -v`
Expected: FAIL — `ModuleNotFoundError: backend.behavior.enforcer_gateway`.

- [ ] **Step 3: Write the gateway helper**

```python
"""Single Python door to the calt_enforcer command gateway (Phase 2 / P5)."""

from __future__ import annotations

import json
import logging

PIPE = r"\\.\pipe\calt_enforcer_cmd"
logger = logging.getLogger(__name__)


class GatewayUnavailable(RuntimeError):
    """calt_enforcer is not running, or the pipe refused the connection."""


def gateway_call(op: str, payload: dict | None = None, *, timeout: float = 3.0) -> dict:
    req = json.dumps({"op": op, "payload": payload or {}}, separators=(",", ":"))
    try:
        with open(PIPE, "r+b", buffering=0) as pipe:
            pipe.write(req.encode("utf-8"))
            raw = pipe.read(64 * 1024)
    except OSError as exc:
        raise GatewayUnavailable(str(exc)) from exc
    try:
        return json.loads(raw.decode("utf-8", "replace") or "{}")
    except ValueError as exc:
        raise GatewayUnavailable(f"bad reply: {raw!r}") from exc
```

Match the framing `scripts/desktop_tracker/run/gateway_cmd.ps1` uses — read that script first and mirror it exactly, including any length prefix. If it retries on a broken pipe, retry here too (3 attempts, 120ms apart), because the server recycles the pipe between clients.

- [ ] **Step 4: Rewrite the Python entry points**

`backend/bible/store.py` — delete `_passes_path`, the weekly-quota arithmetic in `day_pass_status`, and the `dates` bookkeeping in `request_day_pass`. Keep `day["day_pass"]` as the study-side display flag, set from the gateway's answer:

```python
def request_day_pass(user_id: int, *, confirm: str) -> dict[str, Any]:
    """Spend one weekly pass. Quota + confirm phrase are enforced by calt_enforcer."""
    from backend.behavior.enforcer_gateway import gateway_call

    reply = gateway_call("day.grant_pass", {"confirm": confirm})
    if not reply.get("ok"):
        err = str(reply.get("error") or "gateway_refused")
        if err == "confirm_required":
            raise ValueError("Type PASS to confirm a day pass")
        if err == "pass_quota_exhausted":
            raise ValueError("No day passes left this week")
        raise ValueError(err)

    day = load_day(user_id)
    day["day_pass"] = True
    day["game_consumed_seconds"] = 0
    save_day(user_id, day)
    status = gateway_call("day.status")
    return {
        **summary(user_id),
        "day_pass_status": {
            "limit": status.get("passes_limit", 2),
            "used": status.get("passes_used", 0),
            "already": bool(status.get("pass_today")),
        },
        "ok": True,
        "message": "Day pass granted — games and sites unlocked until midnight",
    }
```

Apply the same treatment to `reward_days.claim_reward_day` (call `reward.claim`, map `no_reward_available` and `already_unlocked` to the existing user-facing messages) and `reward_days.status` (call `reward.status`). Delete `_sync_reward_day_to_softland_policy`, `QUALIFYING_DAYS_PER_REWARD`, and the JSON load/save helpers — the enforcer owns all of it now. `record_qualifying_day` becomes `gateway_call("day.mark_event", {"event": "chapter_done"})` plus, when the goal is met, `{"event": "daily_goal"}`; the qualifying-day *decision* stays in `distraction_gate` until P5c moves it.

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/test_bible_day_pass.py tests/test_reward_days.py tests/test_break_reward.py tests/test_morning_rewards.py -v`
Expected: PASS. Tests that asserted on the deleted JSON files must be rewritten to assert on the gateway calls, not deleted outright — the behaviour they cover still exists, it just lives elsewhere.

- [ ] **Step 6: Verify the API path with the enforcer live**

Start `:8000`, then:
```powershell
curl.exe -s -X POST http://127.0.0.1:8000/api/bible/day-pass -H "Content-Type: application/json" -d '{\"confirm\":\"PASS\"}'
```
Expected: `ok: true`, and `msg_host_cmd.ps1 -Json '{"type":"get_mode","url":"https://youtube.com"}'` now allows. Then confirm the reverse dependency is gone: stop `:8000`, run `gateway_cmd.ps1 -Op day.grant_pass -Payload '{"confirm":"PASS"}'`, and confirm it still works.

- [ ] **Step 7: Commit**

```bash
git add backend/behavior/enforcer_gateway.py backend/bible/store.py backend/behavior/reward_days.py tests/test_bible_day_pass.py tests/test_reward_days.py
git commit -m "refactor(behavior): day pass + reward claim go through the enforcer gateway"
```

---

### Task 7: Documentation and status

**Files:**
- Modify: `docs/BLOCKING_RULES.md` (the "Goals, earning and unlocks" section and sharp edges 9 and 12)
- Modify: `docs/superpowers/specs/2026-09-08-calt-productivity-p5-native-unlock-accounting-design.md` (mark P5a done, record what was verified)
- Modify: `AGENTS.md` (current-focus table: add the P5a row as Done)

- [ ] **Step 1: Rewrite the ownership claims**

In `BLOCKING_RULES.md`, replace "Everything here is Python-owned, which means it needs `:8000` running" with the P5a truth: day passes, reward credits, earned minutes and incubation limits are enforced by `calt_enforcer` and work with the API stopped; only qualification maths (productive minutes) still needs Python until P5b/P5c. Delete sharp edge 12's claim that passes and credits freeze without the API, and update sharp edge 5 if the day-pass wording changed.

- [ ] **Step 2: Fix the day-pass description**

The section currently says a pass "unlocks the day" — after Task 2 it also opens the free window, so say so plainly, and remove the note that `runtime.day_pass` is dead-on-read.

- [ ] **Step 3: Record verification evidence**

In the spec, under P5a, list the exact commands run and their answers (the `get_mode` allow after a grant, the quota refusal, the cap clip, the rate limit, the import counts) — the same evidence style Phase 2 used.

- [ ] **Step 4: Commit**

```bash
git add docs/BLOCKING_RULES.md docs/superpowers/specs/2026-09-08-calt-productivity-p5-native-unlock-accounting-design.md AGENTS.md
git commit -m "docs: P5a closed — native unlock accounting, day-pass bug fixed"
```

---

## Self-Review

**Spec coverage.** P5a's spec bullets map to tasks as follows: tables and import → Tasks 1 and 5; `day.grant_pass` with quota and phrase → Task 2; `day.mark_event` with rates and cap → Task 3; `reward.claim` / `day.status` → Task 4; incubation duration and 1-per-hour → Task 4 Step 2; "grant writes `free_until` plus `day_pass` audit" → Task 2 Step 2; "Python becomes a thin caller, quota code deleted" → Task 6; exit criteria evidence → Task 7 Step 3. No P5a bullet is unclaimed. P5b and P5c are deliberately out of scope and get their own plans.

**Placeholder scan.** One soft spot is called out rather than hidden: Task 6 Step 3 tells the implementer to read `gateway_cmd.ps1` and mirror its exact wire framing, because the pipe's length-prefix convention is defined there and must not be guessed. Task 4 Step 2 likewise flags that `AddMinutesLocalIso` must tolerate a negative argument, with the fix if it does not.

**Type consistency.** Accessor names are used identically in Tasks 1–5 (`ProductivityRewardCount`, `ProductivityRewardMark`, `ProductivityInsertPass`, `ProductivityDayEventSeconds`, `ProductivityDayEarnedSecondsToday`, `ProductivityInsertDayEvent`, `ProductivityIncubationStartsSinceIso`, `ProductivityPassesUsedThisWeek`, `ProductivityPassGrantedToday`, `ProductivityLocalDate`, `ProductivityWeekStart`). Op names are consistent between the ops, the smoke script and the Python callers (`day.grant_pass`, `day.mark_event`, `day.status`, `reward.claim`, `reward.status`). Error tokens are snake_case throughout and each is asserted in at least one test step.
