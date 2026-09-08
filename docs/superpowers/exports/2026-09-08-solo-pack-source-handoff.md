# Solo-pack source handoff — Gate why/until + SoftLand JSON + reward day

**Date:** 2026-09-08  
**For:** External reviewer / Claude patching against *real* repo sources  
**Checklist:** `gate-why-until` first (verification)  
**Repo paths are authoritative** — excerpts below are copied from the tree, not invented C++.

Also see: [architecture note](./2026-09-08-productivity-settings-architecture-note.md) · [solo-pack design](../specs/2026-09-08-calt-productivity-solo-pack-design.md)

---

## 0. Reward day + Edge Gate (bug found / patched)

### How Gate learns “reward day” (HTTP path)

1. Settings / Bible API → `claim_reward_day()` in `backend/behavior/reward_days.py`
2. Sets Bible day `reward_day: true` + tray `set_free_override` until midnight
3. Gate polls `GET /api/behavior/distraction-gate` → caches `reward_day: true`
4. `gate_policy.js` `isFreeDay()` → YouTube/social softLand off (porn still blocked)

### How Gate SoftLand decides today (native preferred)

`background.js` / `service_worker.js` **call native `get_mode` first**. HTTP `shouldBlockUrl(gateCache)` only runs if native fails.

Native SoftLand (`softland_decide.cpp`) unlocks free only from `softland_policy.json`:

- `runtime.reward_day_active`
- and/or `runtime.free_until` / `free_after_hm`

### Gap (why “I used reward day” still felt blocked)

**Claim did not write `softland_policy.json`.** So with msg-host healthy, Gate never saw reward day on the native path.

**Patches (in-repo):**
1. `claim_reward_day` patches `runtime.reward_day_active` + `free_until` into `softland_policy.json`.
2. **Live verify (2026-09-08):** Bible already had `reward_day` but policy was still false — idempotent claim returned early without sync, and the sync helper imported missing `backend.core.timezone` (exception swallowed). Fixed: use `backend.planner.service.local_tz`; re-sync SoftLand on already-active claims. Confirmed: policy `reward_day_active: true`, native `get_mode` youtube → `allow`/`reward_day`/`until`.

Rebuild msg-host optional for reason labeling; **Python claim fix is the critical path**. Reload Gate after worker rebuild.
---

## 1. Native emit — `SoftlandModeResultToJson`

**File:** `native/calt_msg_host/src/softland_decide.cpp`  
**Header fields:** `native/calt_msg_host/src/softland_decide.h`

```cpp
struct SoftlandModeResult {
  bool ok = false;
  int schema_version = 1;
  std::string action;   // allow | block | none
  std::string mode;     // study | free | planning | bible
  std::string reason;
  bool softland_enabled = false;
  bool enforce = false;
  bool interstitial = false;
  std::string until;    // ISO or empty
  std::string matched;
  std::string redirect_url;
  std::string error;
};
```

```cpp
std::string SoftlandModeResultToJson(const SoftlandModeResult& r) {
  std::ostringstream o;
  o << "{"
    << "\"schema_version\":" << r.schema_version << ","
    << "\"ok\":" << (r.ok ? "true" : "false") << ","
    << "\"action\":\"" << JsonEscape(r.action) << "\","
    << "\"mode\":\"" << JsonEscape(r.mode) << "\","
    << "\"reason\":\"" << JsonEscape(r.reason) << "\","
    << "\"softland_enabled\":" << (r.softland_enabled ? "true" : "false") << ","
    << "\"enforce\":" << (r.enforce ? "true" : "false") << ","
    << "\"interstitial\":" << (r.interstitial ? "true" : "false") << ",";
  if (r.until.empty())
    o << "\"until\":null,";
  else
    o << "\"until\":\"" << JsonEscape(r.until) << "\",";
  if (r.matched.empty())
    o << "\"matched\":null,";
  else
    o << "\"matched\":\"" << JsonEscape(r.matched) << "\",";
  if (r.redirect_url.empty())
    o << "\"redirect_url\":null";
  else
    o << "\"redirect_url\":\"" << JsonEscape(r.redirect_url) << "\"";
  if (!r.error.empty()) o << ",\"error\":\"" << JsonEscape(r.error) << "\"";
  o << "}";
  return o.str();
}
```

Reward / free / incubation mode selection (same file, `SoftlandGetMode`):

```cpp
  JsonBoolNear(runtime, "reward_day_active", &reward_day);
  // ...
  if (reward_day || free_win) mode = "free";
  if (incubating) mode = "study";
  // ...
  if (incubating) { r.until = incubation_until; r.reason = "incubation"; }
  else if (reward_day) { r.reason = "reward_day"; r.until = ...; }
  else if (free_win) { r.reason = "free_window"; r.until = ...; }
  // later: if mode=="free" → action allow (keeps reward_day reason when set)
```

**Verdict:** Native JSON **does** emit `mode`, `reason`, `until` (not mode-only).

---

## 2. Gate interstitial — native → URL → locked page

### 2a. Prefer native, map `reason` / `until`

**File:** `calt-gate-extension/background.js` (mirrored in generated `service_worker.js`)

```javascript
  var native = await softlandNativeGetMode(url);
  if (native && native.ok !== false && native.action) {
    if (native.action === "allow" || native.action === "none") return false;
    if (native.action === "block" && native.enforce !== false) {
      var kindN = native.reason || "blocked";
      reportGateAlert(kindN, url.slice(0, 120));
      var spaN = lockedPageUrlForBlocked(url, kindN, native.until || "");
      return softLandBlockedTab(tabId, spaN, {
        fromUrl: url,
        kind: kindN,
        host: host || native.matched || "",
        until: native.until || "",
      });
    }
    return false;
  }
  // else HTTP fallback → shouldBlockUrl(gateCache) …
```

### 2b. Query string builder

```javascript
function lockedPageUrlForBlocked(blockedUrl, reason, untilIso) {
  // ...
  if (reason) {
    q += (q ? "&" : "") + "why=" + encodeURIComponent(String(reason).slice(0, 80));
  }
  if (untilIso) {
    q += (q ? "&" : "") + "until=" + encodeURIComponent(String(untilIso).slice(0, 40));
  }
  return q ? base + "?" + q : base;
}
```

### 2c. Locked page UI copy

**File:** `calt-gate-extension/locked.js`

```javascript
function parseBlockedHost() {
  const params = new URLSearchParams(window.location.search || "");
  // ...
  const why = (params.get("why") || "").trim();
  const until = (params.get("until") || "").trim();
  return { host, from, why, until };
}

function showRedirectDialog(parsed) {
  const whyLabel = why ? "Reason: " + why + ". " : "";
  const untilLabel = until ? " Until: " + until + "." : "";
  detailEl.textContent =
    whyLabel +
    "CALT SoftLand blocked this webpage. …" +
    untilLabel + …;
}
```

**Verdict (`gate-why-until`):** End-to-end path exists: native `reason`→`why` query, native `until`→`until` query → dialog. Focus Now “why” is a **separate** Python `focus-dashboard` path (stale when API down).

**Follow-ups closed (2026-09-08):**
- Every `action="block"` in `SoftlandGetMode` now sets `r.enforce = true` on the same return path (porn / block_extra / watch_list / missing / corrupt).
- HTTP `blockKindForUrl` emits the same short tokens as native (`porn`, `watch_list`, `morning_bible`, `incubation`, …) so locked-page `why=` is deterministic on fallback.
- Missing **or** corrupt policy (no parseable `softland_enabled`) → fail-closed block.

---

## 3. protect-focus — real sources (paste for review)

### `kill.cpp` — `IsProtected`

```cpp
bool IsProtected(const std::wstring& base) {
  static const wchar_t* kProtExact[] = {
      L"explorer.exe", L"csrss.exe",     L"winlogon.exe", L"services.exe",
      L"lsass.exe",    L"svchost.exe",   L"smss.exe",     L"fontdrvhost.exe",
      L"dwm.exe",      L"calt_enforcer.exe", L"calt_focus.exe", L"calt_msg_host.exe",
      nullptr};
  for (int i = 0; kProtExact[i]; ++i) {
    if (base == kProtExact[i]) return true;
  }
  if (base == L"python.exe" || base == L"pythonw.exe") return true;
  return false;
}
```

### `win_service.cpp` — status + tick (real order)

Within one loop iteration, **watchdog runs first**, then status publish (throttled to ~2.5s):

```cpp
    TickKills(dbPath, snap);
    sessions.Tick();

    bool softland = false;
    ReadSoftlandEnabled(dbPath, &softland);
    TickFocusWatchdog(snap.armed, softland, gFocusWatch);  // mutates gFocusWatch

    DWORD now = GetTickCount();
    // …
    if (lastStatus == 0 || now - lastStatus >= kStatusMs) {
      PublishStatus(dbPath, lockPath, snap);  // copies gFocusWatch.* into JSON
      lastStatus = now;
    }
```

`PublishStatus` reads `gFocusWatch` after the tick — not previous-iteration-only. Caveat: status write is every ~2500ms while the poll is ~1500ms, so the JSON can still be up to one status interval stale relative to the latest watchdog mutation, but it is not systematically writing *pre-tick* state.

### `focus_watchdog.cpp` — relaunch + backoff (full prune/suppress logic)

**Behavior:** suppression **auto-clears** when the rolling 60s window rolls, **unconditionally every tick** (not only on SoftLand/Arm off). Pruning is a wall-clock window reset, not a timestamp list:

```cpp
void TickFocusWatchdog(bool armed, bool softland_enabled, FocusWatchState& state) {
  state.softland_enabled = softland_enabled;
  state.softland_or_armed = softland_enabled || armed;
  state.focus_running = ProcessBasenameRunning(L"calt_focus.exe");

  static DWORD window_start_ms = 0;
  static unsigned launches_in_window = 0;
  static unsigned lifetime_relaunches = 0;
  static std::string last_relaunch_iso;
  static bool suppressed = false;

  const DWORD now = GetTickCount();
  // Runs every tick, even while suppressed / Focus missing:
  if (window_start_ms == 0 || now - window_start_ms > 60000) {
    window_start_ms = now;
    launches_in_window = 0;
    suppressed = false;   // auto-clear after ~60s wall time
  }

  state.focus_relaunch_count = lifetime_relaunches;
  state.focus_last_relaunch_at = last_relaunch_iso;
  state.focus_relaunch_suppressed = suppressed;

  if (!state.softland_or_armed) {
    suppressed = false;
    state.focus_relaunch_suppressed = false;
    return;
  }
  if (state.focus_running) return;
  if (launches_in_window >= 3) {
    suppressed = true;
    state.focus_relaunch_suppressed = true;
    return;
  }

  const std::wstring exe = ResolveFocusExePath();
  if (exe.empty()) {
    suppressed = true;
    state.focus_relaunch_suppressed = true;
    return;
  }

  // CreateProcessW(...); on success: ++launches_in_window, suppressed=false
}
```

So after a crash burst: suppress for the remainder of the current 60s window, then `launches_in_window` resets and relaunch resumes automatically — no SoftLand-off/Arm-off cycle required. SoftLand-off/Arm-off also clears suppression immediately as a second path.

**Tradeoff (documented, accepted):** this is a **fixed** 60s window, not a sliding count of individual launch ages. A crash burst that straddles a window boundary can produce up to ~6 relaunches across ~60s (3 near end of window + 3 after reset) before settling. Low-stakes for accidental crash-loops; not worth sliding-window complexity for Phase 1.

Empty `ResolveFocusExePath()` also sets suppressed; that also clears on the next window roll (and will fail-open to suppressed again if path still empty).

### `IsProtected` — unchanged (clean)

```cpp
bool IsProtected(const std::wstring& base) {
  static const wchar_t* kProtExact[] = {
      L"explorer.exe", L"csrss.exe",     L"winlogon.exe", L"services.exe",
      L"lsass.exe",    L"svchost.exe",   L"smss.exe",     L"fontdrvhost.exe",
      L"dwm.exe",      L"calt_enforcer.exe", L"calt_focus.exe", L"calt_msg_host.exe",
      nullptr};
  // …
}
```

Other paths for continued review:

| Topic | Path |
|-------|------|
| Status fields | `native/calt_enforcer/src/status_writer.cpp` |
| track_tab | `native/calt_msg_host/src/main.cpp`, `track_tab.cpp` |
| Reward claim | `backend/behavior/reward_days.py` |
| SoftLand SoT | `data/behavior/softland_policy.json` |

Do **not** invent parallel C++ SoftLand — patch these files.

---

## 4. Quick owner check after reward-day fix

1. Start API briefly, claim reward day (type `REWARD`).  
2. Open `data/behavior/softland_policy.json` → expect `"reward_day_active": true` and a `free_until` tonight.  
3. Stop API; browse YouTube → native `get_mode` should `action":"allow"`, `reason":"reward_day"` (or `free_mode`).  
4. Reload Gate if it still redirects from a stale DNR rule (`syncDeclarativeWatchBlock` may need a gate poll once while API is up after claim).
5. Force a SoftLand block URL → confirm JSON has `"enforce":true` alongside `"action":"block"`.
6. SoftLand off + Disarm → Focus tray Quit stays quit.