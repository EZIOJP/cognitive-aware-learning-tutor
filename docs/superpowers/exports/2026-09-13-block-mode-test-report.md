# SoftLand / Arm block test report

> **Superseded for full matrix:** see
> [`2026-09-13-block-mode-suite-report.md`](2026-09-13-block-mode-suite-report.md)
> (73/73 PASS after disarm sticky + SQLite sync fixes). This file is the earlier
> one-shot probe kept for history.

**When:** 2026-09-13 ~13:35 IST  
**Method:** Live mirrors + SQLite SoT + `calt_msg_host` `get_mode` (fixture via `CALT_DATA_DIR`). Did **not** open browsers/games interactively (gateway pipe was timing out; decide path still testable offline).

Scripts used:
- `scripts/desktop_tracker/run/_arm_state_dump.py`
- `scripts/desktop_tracker/run/_block_mode_report.py`
- Prefer: `scripts/desktop_tracker/run/block_mode_suite.py`

---

## Live machine (your current day)

| Switch | Live value | Source |
|--------|------------|--------|
| SoftLand | **OFF** (`softland_enabled: false`) | `softland_policy.json` + SQLite `productivity_softland` |
| Arm (kills) | **ON** in SoT (`hard_block_armed=1`) | SQLite `enforcer_runtime` |
| Arm (JSON mirror) | **OFF** + `exes: []` | `enforcer_policy.json` — **stale / out of sync** |
| Status chip | `armed: true`, `last_kill: ""` | `enforcer_status.json` |
| Focus | running | status |
| Enforcer gateway pipe | **timeout** (`status.snapshot` failed) | `gateway_cmd.ps1` |

### Live SoftLand URL probe (real policy)

All sampled URLs → **`allow` / `reason=softland_off` / `enforce=false`**  
Including youtube, meet, porn, reddit, wikipedia, twitter.

**Meaning:** with SoftLand off, **no site is blocked** by Gate SoftLand (including porn heuristics — they only run when SoftLand is on).

### Live Arm / apps

SQLite kill list (armed):

`steam.exe`, `steamwebhelper.exe`, `epicgameslauncher.exe`, `epicwebhelper.exe`, `galaxyclient.exe`, `battle.net.exe`, `riotclientservices.exe`, `leagueclient.exe`, `leagueclientux.exe`, `valorant.exe`, `fortniteclient-win64-shipping.exe`, `minecraft.exe`, `robloxplayerbeta.exe`, `mhur.exe`

- Status: armed, but **`last_kill` empty** → no recent kill recorded in the mirror.
- JSON policy mirror claims disarmed + empty `exes` → **UI/Settings reading only the JSON mirror can lie**; SoT is SQLite.
- Did not force-launch Steam/etc. in this pass (pipe stuck; don’t want to thrash while gateway is unhealthy).

---

## Fixture SoftLand matrix (decide engine)

Fixture lists used when SoftLand **ON**:

- Allow: `meet.google.com`, `wikipedia.org`
- Watch: `youtube.com`, `reddit.com`
- Block-extra: `twitter.com`, `x.com`
- Schedule: study 00:00–23:59 every day  
- FREE case: `free_until=2099-12-31` + `reward_day_active`

### STUDY (SoftLand ON)

| URL | Action | Reason |
|-----|--------|--------|
| youtube.com | **block** | `watch_list` |
| meet.google.com | allow | `allow_list` |
| pornhub.com | **block** | `porn` |
| reddit.com | **block** | `watch_list` |
| wikipedia.org | allow | `allow_list` |
| twitter.com | **block** | `block_extra` |
| github.com | allow | `not_listed` |
| facebook.com | **block** | `watch_list` (social / heuristic — not in your watch_extra) |

### FREE / reward window (SoftLand ON)

| URL | Action | Reason |
|-----|--------|--------|
| youtube.com | allow | `reward_day` |
| meet.google.com | allow | `allow_list` |
| pornhub.com | **block** | `porn` (stays blocked in FREE) |
| reddit.com | allow | `reward_day` |
| wikipedia.org | allow | `allow_list` |
| twitter.com | **block** | `block_extra` (always-block list) |
| github.com | allow | `reward_day` |
| facebook.com | allow | `reward_day` |

### SoftLand OFF (fixture)

youtube / porn / twitter → all **allow** `softland_off`.

---

## Mode cheat-sheet (what actually blocks what)

| Mode | Sites (SoftLand) | Apps (Arm) |
|------|------------------|------------|
| SoftLand **OFF** | Nothing blocked by SoftLand | Independent — Arm may still kill exes |
| SoftLand **ON** + **STUDY** | Watch + block_extra + porn + social heuristics; allow list open | Arm independent |
| SoftLand **ON** + **FREE** | Watch/social often open; **porn** + **block_extra** still blocked | Arm independent |
| Arm **ON** | — | Processes named in `exes` killed |
| Arm **OFF** | — | No kills |

SoftLand ON ≠ Arm. Your live day currently has SoftLand off + Arm on (per SQLite/status).

---

## Issues found

1. **`enforcer_policy.json` out of sync with SQLite** — mirror says disarmed/empty; SoT says armed + full game list. Risk: Settings UI shows wrong Arm state if it trusts the mirror only.
2. **Gateway named pipe timeout** — enforcer process is alive but `gateway_cmd.ps1 status.snapshot` failed; Focus writes may be stuck until restart.
3. **Live SoftLand off** — opening “blocked” sites in the browser will **not** trip SoftLand until you turn SoftLand on in Settings.
4. **github.com `allow`/`not_listed` in STUDY** — worth a follow-up if you expect strict allowlist to block unlisted sites; result may depend on `mode_flags.study.block_other` / ladder order (observed as allow in this fixture).
5. **msg_host PowerShell helper** — fragile quoting on this shell; Python framing works. Prefer the Python probe scripts above.

---

## How to re-run

```bat
python scripts\desktop_tracker\run\_arm_state_dump.py
python scripts\desktop_tracker\run\_block_mode_report.py
```

To live-test sites after turning SoftLand **ON** in Focus Settings:

```bat
python -c "import struct,subprocess,json; exe=r'calt-focus\\backend\\calt_msg_host\\build\\calt_msg_host.exe'; u='https://youtube.com'; raw=json.dumps({'type':'get_mode','url':u}).encode(); p=subprocess.Popen([exe],stdin=subprocess.PIPE,stdout=subprocess.PIPE); p.stdin.write(struct.pack('<I',len(raw))+raw); p.stdin.close(); n=struct.unpack('<I',p.stdout.read(4))[0]; print(p.stdout.read(n).decode())"
```

For apps: confirm Arm in UI matches SQLite, then launch a listed `.exe` and check `enforcer_status.json` → `last_kill` / `last_kill_exe`.
