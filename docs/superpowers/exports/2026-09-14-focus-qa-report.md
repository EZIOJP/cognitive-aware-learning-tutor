# Focus QA automation report

**When:** 2026-09-14T00:30:43+05:30 → 2026-09-14T00:31:44+05:30
**Result:** **115 PASS / 0 FAIL / 1 SKIP**
**Gateway:** ok
**Snapshot restored:** True
**Artifacts:** `C:\Users\Lenovo\Desktop\Cognitive-Aware Learning Tutor\docs\superpowers\exports\focus-qa-artifacts`

## Summary by suite

| Suite | Cases |
|-------|------:|
| arm | 26 |
| gateway | 12 |
| softland | 65 |
| sync | 6 |
| ui | 7 |

## Summary by category

| Category | Cases |
|----------|------:|
| edge | 17 |
| negative | 16 |
| positive | 83 |

## How to run

```bat
python scripts\desktop_tracker\run\focus_qa_suite.py
python scripts\desktop_tracker\run\focus_qa_suite.py --live --arm-kills --ui
```

## Failed cases

_None._

## All cases

| Status | Code | Suite | Cat | ID | Title |
|--------|------|-------|-----|----|-------|
| PASS | `OK` | softland | positive | `softland.fixture.study.https://youtube.com` | SoftLand study: https://youtube.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://www.youtube.com/watch?v=dQw4w9WgXcQ` | SoftLand study: https://www.youtube.com/watch?v=dQw4w9WgXcQ |
| PASS | `OK` | softland | positive | `softland.fixture.study.http://youtube.com` | SoftLand study: http://youtube.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://m.youtube.com` | SoftLand study: https://m.youtube.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://music.youtube.com` | SoftLand study: https://music.youtube.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://youtu.be/abc` | SoftLand study: https://youtu.be/abc |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://reddit.com` | SoftLand study: https://reddit.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://www.reddit.com/r/python` | SoftLand study: https://www.reddit.com/r/python |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://facebook.com` | SoftLand study: https://facebook.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://meet.google.com` | SoftLand study: https://meet.google.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://docs.meet.google.com` | SoftLand study: https://docs.meet.google.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://wikipedia.org` | SoftLand study: https://wikipedia.org |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://en.wikipedia.org/wiki/Test` | SoftLand study: https://en.wikipedia.org/wiki/Test |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://pornhub.com` | SoftLand study: https://pornhub.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://www.pornhub.com/video` | SoftLand study: https://www.pornhub.com/video |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://example.xxx` | SoftLand study: https://example.xxx |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://twitter.com` | SoftLand study: https://twitter.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://x.com/home` | SoftLand study: https://x.com/home |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://alwaysblock.example/path` | SoftLand study: https://alwaysblock.example/path |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://github.com` | SoftLand study: https://github.com |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://random-not-listed-9f3a.test` | SoftLand study: https://random-not-listed-9f3a.test |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://localhost:3000` | SoftLand study: https://localhost:3000 |
| PASS | `OK` | softland | positive | `softland.fixture.study.http://127.0.0.1/admin` | SoftLand study: http://127.0.0.1/admin |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://192.168.1.1` | SoftLand study: https://192.168.1.1 |
| PASS | `OK` | softland | positive | `softland.fixture.study.empty` | SoftLand study: empty |
| PASS | `OK` | softland | positive | `softland.fixture.study.not-a-url` | SoftLand study: not-a-url |
| PASS | `OK` | softland | positive | `softland.fixture.study.https://study.local.test` | SoftLand study: https://study.local.test |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://youtube.com` | SoftLand free: https://youtube.com |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://reddit.com` | SoftLand free: https://reddit.com |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://facebook.com` | SoftLand free: https://facebook.com |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://pornhub.com` | SoftLand free: https://pornhub.com |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://twitter.com` | SoftLand free: https://twitter.com |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://x.com` | SoftLand free: https://x.com |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://meet.google.com` | SoftLand free: https://meet.google.com |
| PASS | `OK` | softland | positive | `softland.fixture.free.https://github.com` | SoftLand free: https://github.com |
| PASS | `OK` | softland | positive | `softland.fixture.off.https://youtube.com` | SoftLand off: https://youtube.com |
| PASS | `OK` | softland | positive | `softland.fixture.off.https://pornhub.com` | SoftLand off: https://pornhub.com |
| PASS | `OK` | softland | positive | `softland.fixture.off.https://twitter.com` | SoftLand off: https://twitter.com |
| PASS | `OK` | softland | positive | `softland.fixture.off.https://alwaysblock.example` | SoftLand off: https://alwaysblock.example |
| PASS | `OK` | softland | positive | `softland.fixture.incubate.https://youtube.com` | SoftLand incubate: https://youtube.com |
| PASS | `OK` | softland | positive | `softland.fixture.incubate.https://pornhub.com` | SoftLand incubate: https://pornhub.com |
| PASS | `OK` | softland | positive | `softland.fixture.incubate.https://meet.google.com` | SoftLand incubate: https://meet.google.com |
| PASS | `OK` | softland | edge | `softland.fixture.study.HTTPS://YouTube.COM/Watch?V=1` | Case-insensitive YouTube host |
| PASS | `OK` | softland | edge | `softland.fixture.study.https://youtube.com.` | EDGE: trailing-dot host currently not_listed (not watch_list) |
| PASS | `OK` | softland | edge | `softland.fixture.study.https://youtube.com:443/watch` | Explicit :443 port |
| PASS | `OK` | softland | edge | `softland.fixture.study.https://user:pass@youtube.com/` | EDGE: userinfo URL currently not_listed (host parse) |
| PASS | `OK` | softland | edge | `softland.fixture.study.https://www.www.youtube.com` | Double-www subdomain |
| PASS | `OK` | softland | edge | `softland.fixture.study.https://notyoutube.com` | Suffix lookalike notyoutube.com |
| PASS | `OK` | softland | edge | `softland.fixture.study.https://youtube.com.evil.test` | Evil suffix after youtube.com |
| PASS | `OK` | softland | edge | `softland.fixture.study.javascript:alert(1)` | javascript: URL |
| PASS | `OK` | softland | edge | `softland.fixture.study.data:text/html,hi` | data: URL |
| PASS | `OK` | softland | edge | `softland.fixture.study.about:blank` | about:blank |
| PASS | `OK` | softland | edge | `softland.fixture.study.   ` | Whitespace-only URL |
| PASS | `OK` | softland | edge | `softland.fixture.study.https://xn--n3h.com` | Punycode host |
| PASS | `OK` | softland | negative | `softland.fixture.free.https://pornhub.com` | NEGATIVE: porn stays blocked in FREE |
| PASS | `OK` | softland | negative | `softland.fixture.free.https://twitter.com` | NEGATIVE: block_extra stays blocked in FREE |
| PASS | `OK` | softland | negative | `softland.fixture.off.https://pornhub.com` | NEGATIVE: SoftLand OFF must allow porn (no SoftLand block) |
| PASS | `OK` | softland | negative | `softland.fixture.incubate.https://youtube.com` | NEGATIVE: incubation overrides FREE watch |
| PASS | `OK` | arm | positive | `arm.unit.steam.exe->['steam.exe']` | Arm match: steam.exe vs ['steam.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.STEAM.EXE->['steam.exe']` | Arm match: STEAM.EXE vs ['steam.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.steam->['steam.exe']` | Arm match: steam vs ['steam.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.steam.exe->['steam']` | Arm match: steam.exe vs ['steam'] |
| PASS | `OK` | arm | positive | `arm.unit.steam.exe->['C:\\Games\\Steam\\steam.exe']` | Arm match: steam.exe vs ['C:\\Games\\Steam\\steam.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.notepad.exe->['steam.exe']` | Arm match: notepad.exe vs ['steam.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.calt_test_block_target.exe->['calt_test_block_target.exe']` | Arm match: calt_test_block_target.exe vs ['calt_test_block_target.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.calt_test_safe.exe->['calt_test_block_target.exe']` | Arm match: calt_test_safe.exe vs ['calt_test_block_target.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.explorer.exe->['explorer.exe']` | Arm match: explorer.exe vs ['explorer.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.python.exe->['python.exe']` | Arm match: python.exe vs ['python.exe'] |
| PASS | `OK` | arm | positive | `arm.unit.calt_enforcer.exe->['calt_enforcer.exe']` | Arm match: calt_enforcer.exe vs ['calt_enforcer.exe'] |
| PASS | `OK` | arm | edge | `arm.unit.extra.Mixed-case process name` | Mixed-case process name |
| PASS | `OK` | arm | edge | `arm.unit.extra.Mixed-case policy token` | Mixed-case policy token |
| PASS | `OK` | arm | negative | `arm.unit.extra.NEGATIVE: unlisted chrome must not match` | NEGATIVE: unlisted chrome must not match |
| PASS | `OK` | arm | negative | `arm.unit.extra.NEGATIVE: similar name must not fuzzy-match` | NEGATIVE: similar name must not fuzzy-match |
| PASS | `OK` | arm | edge | `arm.unit.extra.Empty process name` | Empty process name |
| PASS | `OK` | arm | negative | `arm.unit.extra.NEGATIVE: empty policy list never kills` | NEGATIVE: empty policy list never kills |
| PASS | `OK` | arm | edge | `arm.unit.extra.Empty policy token ignored` | Empty policy token ignored |
| PASS | `OK` | arm | negative | `arm.unit.extra.NEGATIVE: protected Focus never killed` | NEGATIVE: protected Focus never killed |
| PASS | `OK` | arm | edge | `arm.unit.extra.Full path process basename` | Full path process basename |
| PASS | `OK` | sync | positive | `sync.pre.status_vs_effective_arm` | Status armed matches effective Arm |
| PASS | `OK` | sync | positive | `sync.pre.sqlite_vs_json_arm` | SQLite Arm mirrors JSON |
| PASS | `OK` | sync | positive | `sync.pre.sqlite_vs_json_softland` | SQLite SoftLand enabled matches JSON |
| PASS | `OK` | gateway | positive | `gateway.read.status.snapshot` | Gateway status.snapshot |
| PASS | `OK` | gateway | positive | `gateway.read.day.status` | Gateway day.status |
| PASS | `OK` | gateway | positive | `gateway.read.reward.status` | Gateway reward.status |
| PASS | `OK` | gateway | positive | `gateway.read.day.loop_snapshot` | Gateway day.loop_snapshot |
| PASS | `OK` | gateway | positive | `gateway.read.ledger.snapshot` | Gateway ledger.snapshot |
| PASS | `OK` | gateway | positive | `gateway.read.device_block.status` | Gateway device_block.status |
| SKIP | `OK` | gateway | negative | `gateway.neg.arm.set.unlock` | NEGATIVE: arm.set with wrong unlock (may reject if password lock active) |
| PASS | `OK` | gateway | negative | `gateway.neg.softland.set_enabled.bad_payload` | NEGATIVE: softland.set_enabled missing enabled field |
| PASS | `OK` | gateway | negative | `gateway.neg.this.op.does.not.exist.unknown_op` | NEGATIVE: unknown gateway op |
| PASS | `OK` | gateway | negative | `gateway.neg.reward.claim.reward` | NEGATIVE: reward.claim when available may be 0 (reject or no-op fail) |
| PASS | `OK` | gateway | positive | `gateway.info.softland_ne_arm` | INFO: SoftLand and Arm are independent switches |
| PASS | `OK` | softland | positive | `softland.live.https://youtube.com` | Live SoftLand probe (watch) |
| PASS | `OK` | softland | positive | `softland.live.https://pornhub.com` | Live SoftLand probe (porn) |
| PASS | `OK` | softland | positive | `softland.live.https://meet.google.com` | Live SoftLand probe (allow) |
| PASS | `OK` | softland | positive | `softland.live.https://github.com` | Live SoftLand probe (other) |
| PASS | `OK` | softland | positive | `softland.live.https://twitter.com` | Live SoftLand probe (block_extra) |
| PASS | `OK` | softland | positive | `softland.live.empty` | Live SoftLand probe (empty) |
| PASS | `OK` | softland | positive | `softland.live.not-a-url` | Live SoftLand probe (garbage) |
| PASS | `OK` | arm | positive | `arm.live.set_fixture_list` | Arm live: set disposable kill list |
| PASS | `OK` | arm | negative | `arm.live.safe_not_killed` | NEGATIVE: unlisted safe EXE must survive Arm |
| PASS | `OK` | arm | positive | `arm.live.block_target_killed` | Arm ON kills listed fixture target |
| PASS | `OK` | arm | positive | `arm.live.disarm` | Arm live: disarm (clear lock_mode) |
| PASS | `OK` | arm | negative | `arm.live.disarmed_no_kill` | NEGATIVE: Arm OFF must not kill listed EXE |
| PASS | `OK` | arm | negative | `arm.live.wrong_password_no_disarm` | NEGATIVE: wrong unlock password must not disarm |
| PASS | `OK` | ui | positive | `ui.route._` | UI home (index.html) |
| PASS | `OK` | ui | positive | `ui.route._#_productivity_tab_home` | UI productivity home hash |
| PASS | `OK` | ui | positive | `ui.route._#_productivity_tab_settings` | UI settings hash |
| PASS | `OK` | ui | positive | `ui.route._#_productivity_tab_blocker` | UI blocker hash |
| PASS | `OK` | ui | positive | `ui.route._#_productivity_tab_focus` | UI focus hash |
| PASS | `OK` | ui | positive | `ui.route._#_journal` | UI journal hash |
| PASS | `OK` | ui | negative | `ui.neg.missing_asset_404` | NEGATIVE: missing static asset returns 404 |
| PASS | `OK` | gateway | positive | `restore.snapshot` | Restore SoftLand/Arm snapshot |
| PASS | `OK` | sync | positive | `sync.post.status_vs_effective_arm` | Status armed matches effective Arm |
| PASS | `OK` | sync | positive | `sync.post.sqlite_vs_json_arm` | SQLite Arm mirrors JSON |
| PASS | `OK` | sync | positive | `sync.post.sqlite_vs_json_softland` | SQLite SoftLand enabled matches JSON |

## Case details

### `softland.fixture.study.https://youtube.com` — SoftLand study: https://youtube.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | written | Y |
| 2 | msg_host get_mode('https://youtube.com') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://www.youtube.com/watch?v=dQw4w9WgXcQ` — SoftLand study: https://www.youtube.com/watch?v=dQw4w9WgXcQ

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://www.youtube.com/watch?v=dQw4w9WgXcQ') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.http://youtube.com` — SoftLand study: http://youtube.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('http://youtube.com') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://m.youtube.com` — SoftLand study: https://m.youtube.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://m.youtube.com') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://music.youtube.com` — SoftLand study: https://music.youtube.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://music.youtube.com') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://youtu.be/abc` — SoftLand study: https://youtu.be/abc

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://youtu.be/abc') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://reddit.com` — SoftLand study: https://reddit.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://reddit.com') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://www.reddit.com/r/python` — SoftLand study: https://www.reddit.com/r/python

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://www.reddit.com/r/python') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://facebook.com` — SoftLand study: https://facebook.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://facebook.com') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://meet.google.com` — SoftLand study: https://meet.google.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://meet.google.com') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.study.https://docs.meet.google.com` — SoftLand study: https://docs.meet.google.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://docs.meet.google.com') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.study.https://wikipedia.org` — SoftLand study: https://wikipedia.org

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://wikipedia.org') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.study.https://en.wikipedia.org/wiki/Test` — SoftLand study: https://en.wikipedia.org/wiki/Test

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://en.wikipedia.org/wiki/Test') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.study.https://pornhub.com` — SoftLand study: https://pornhub.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "porn"}`
- **Actual:** `{"action": "block", "reason": "porn", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://pornhub.com') | block | block/porn | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "porn"} | {"action": "block", "reason": "porn"} | Y |

### `softland.fixture.study.https://www.pornhub.com/video` — SoftLand study: https://www.pornhub.com/video

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "porn"}`
- **Actual:** `{"action": "block", "reason": "porn", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://www.pornhub.com/video') | block | block/porn | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "porn"} | {"action": "block", "reason": "porn"} | Y |

### `softland.fixture.study.https://example.xxx` — SoftLand study: https://example.xxx

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "porn"}`
- **Actual:** `{"action": "block", "reason": "porn", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://example.xxx') | block | block/porn | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "porn"} | {"action": "block", "reason": "porn"} | Y |

### `softland.fixture.study.https://twitter.com` — SoftLand study: https://twitter.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "block_extra"}`
- **Actual:** `{"action": "block", "reason": "block_extra", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://twitter.com') | block | block/block_extra | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "block_extra"} | {"action": "block", "reason": "block_extra"} | Y |

### `softland.fixture.study.https://x.com/home` — SoftLand study: https://x.com/home

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "block_extra"}`
- **Actual:** `{"action": "block", "reason": "block_extra", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://x.com/home') | block | block/block_extra | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "block_extra"} | {"action": "block", "reason": "block_extra"} | Y |

### `softland.fixture.study.https://alwaysblock.example/path` — SoftLand study: https://alwaysblock.example/path

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "block_extra"}`
- **Actual:** `{"action": "block", "reason": "block_extra", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://alwaysblock.example/path') | block | block/block_extra | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "block_extra"} | {"action": "block", "reason": "block_extra"} | Y |

### `softland.fixture.study.https://github.com` — SoftLand study: https://github.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://github.com') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.https://random-not-listed-9f3a.test` — SoftLand study: https://random-not-listed-9f3a.test

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://random-not-listed-9f3a.test') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.https://localhost:3000` — SoftLand study: https://localhost:3000

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://localhost:3000') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.study.http://127.0.0.1/admin` — SoftLand study: http://127.0.0.1/admin

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('http://127.0.0.1/admin') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.study.https://192.168.1.1` — SoftLand study: https://192.168.1.1

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://192.168.1.1') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.empty` — SoftLand study: empty

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "no_host"}`
- **Actual:** `{"action": "allow", "reason": "no_host", "mode": "study", "enforce": false}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('') | allow | allow/no_host | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "no_host"} | {"action": "allow", "reason": "no_host"} | Y |

### `softland.fixture.study.not-a-url` — SoftLand study: not-a-url

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('not-a-url') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.https://study.local.test` — SoftLand study: https://study.local.test

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://study.local.test') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.free.https://youtube.com` — SoftLand free: https://youtube.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]}`
- **Actual:** `{"action": "allow", "reason": "reward_day", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | written | Y |
| 2 | msg_host get_mode('https://youtube.com') | allow | allow/reward_day | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]} | {"action": "allow", "reason": "reward_day"} | Y |

### `softland.fixture.free.https://reddit.com` — SoftLand free: https://reddit.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]}`
- **Actual:** `{"action": "allow", "reason": "reward_day", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://reddit.com') | allow | allow/reward_day | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]} | {"action": "allow", "reason": "reward_day"} | Y |

### `softland.fixture.free.https://facebook.com` — SoftLand free: https://facebook.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]}`
- **Actual:** `{"action": "allow", "reason": "reward_day", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://facebook.com') | allow | allow/reward_day | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]} | {"action": "allow", "reason": "reward_day"} | Y |

### `softland.fixture.free.https://pornhub.com` — SoftLand free: https://pornhub.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "porn"}`
- **Actual:** `{"action": "block", "reason": "porn", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://pornhub.com') | block | block/porn | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "porn"} | {"action": "block", "reason": "porn"} | Y |

### `softland.fixture.free.https://twitter.com` — SoftLand free: https://twitter.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "block_extra"}`
- **Actual:** `{"action": "block", "reason": "block_extra", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://twitter.com') | block | block/block_extra | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "block_extra"} | {"action": "block", "reason": "block_extra"} | Y |

### `softland.fixture.free.https://x.com` — SoftLand free: https://x.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "block_extra"}`
- **Actual:** `{"action": "block", "reason": "block_extra", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://x.com') | block | block/block_extra | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "block_extra"} | {"action": "block", "reason": "block_extra"} | Y |

### `softland.fixture.free.https://meet.google.com` — SoftLand free: https://meet.google.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://meet.google.com') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.free.https://github.com` — SoftLand free: https://github.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]}`
- **Actual:** `{"action": "allow", "reason": "reward_day", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://github.com') | allow | allow/reward_day | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["reward_day", "free_window", "free_mode"]} | {"action": "allow", "reason": "reward_day"} | Y |

### `softland.fixture.off.https://youtube.com` — SoftLand off: https://youtube.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "softland_off"}`
- **Actual:** `{"action": "allow", "reason": "softland_off", "mode": "free", "enforce": false}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=off | policy written | written | Y |
| 2 | msg_host get_mode('https://youtube.com') | allow | allow/softland_off | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "softland_off"} | {"action": "allow", "reason": "softland_off"} | Y |

### `softland.fixture.off.https://pornhub.com` — SoftLand off: https://pornhub.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "softland_off"}`
- **Actual:** `{"action": "allow", "reason": "softland_off", "mode": "free", "enforce": false}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=off | policy written | reuse | Y |
| 2 | msg_host get_mode('https://pornhub.com') | allow | allow/softland_off | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "softland_off"} | {"action": "allow", "reason": "softland_off"} | Y |

### `softland.fixture.off.https://twitter.com` — SoftLand off: https://twitter.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "softland_off"}`
- **Actual:** `{"action": "allow", "reason": "softland_off", "mode": "free", "enforce": false}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=off | policy written | reuse | Y |
| 2 | msg_host get_mode('https://twitter.com') | allow | allow/softland_off | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "softland_off"} | {"action": "allow", "reason": "softland_off"} | Y |

### `softland.fixture.off.https://alwaysblock.example` — SoftLand off: https://alwaysblock.example

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "softland_off"}`
- **Actual:** `{"action": "allow", "reason": "softland_off", "mode": "free", "enforce": false}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=off | policy written | reuse | Y |
| 2 | msg_host get_mode('https://alwaysblock.example') | allow | allow/softland_off | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "softland_off"} | {"action": "allow", "reason": "softland_off"} | Y |

### `softland.fixture.incubate.https://youtube.com` — SoftLand incubate: https://youtube.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": "incubation"}`
- **Actual:** `{"action": "block", "reason": "incubation", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=incubate | policy written | written | Y |
| 2 | msg_host get_mode('https://youtube.com') | block | block/incubation | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "incubation"} | {"action": "block", "reason": "incubation"} | Y |

### `softland.fixture.incubate.https://pornhub.com` — SoftLand incubate: https://pornhub.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "block", "reason": ["incubation", "porn"]}`
- **Actual:** `{"action": "block", "reason": "incubation", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=incubate | policy written | reuse | Y |
| 2 | msg_host get_mode('https://pornhub.com') | block | block/incubation | Y |
| 3 | Compare action+reason | {"action": "block", "reason": ["incubation", "porn"]} | {"action": "block", "reason": "incubation"} | Y |

### `softland.fixture.incubate.https://meet.google.com` — SoftLand incubate: https://meet.google.com

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, positive
- **Expected:** `{"action": "allow", "reason": "allow_list"}`
- **Actual:** `{"action": "allow", "reason": "allow_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=incubate | policy written | reuse | Y |
| 2 | msg_host get_mode('https://meet.google.com') | allow | allow/allow_list | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "allow_list"} | {"action": "allow", "reason": "allow_list"} | Y |

### `softland.fixture.study.HTTPS://YouTube.COM/Watch?V=1` — Case-insensitive YouTube host

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | written | Y |
| 2 | msg_host get_mode('HTTPS://YouTube.COM/Watch?V=1') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://youtube.com.` — EDGE: trailing-dot host currently not_listed (not watch_list)

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://youtube.com.') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.https://youtube.com:443/watch` — Explicit :443 port

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://youtube.com:443/watch') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://user:pass@youtube.com/` — EDGE: userinfo URL currently not_listed (host parse)

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://user:pass@youtube.com/') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.https://www.www.youtube.com` — Double-www subdomain

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "block", "reason": "watch_list"}`
- **Actual:** `{"action": "block", "reason": "watch_list", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://www.www.youtube.com') | block | block/watch_list | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "watch_list"} | {"action": "block", "reason": "watch_list"} | Y |

### `softland.fixture.study.https://notyoutube.com` — Suffix lookalike notyoutube.com

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://notyoutube.com') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.https://youtube.com.evil.test` — Evil suffix after youtube.com

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://youtube.com.evil.test') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.javascript:alert(1)` — javascript: URL

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": ["no_host", "not_listed", "softland_off"]}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('javascript:alert(1)') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["no_host", "not_listed", "softland_off"]} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.data:text/html,hi` — data: URL

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": ["no_host", "not_listed"]}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('data:text/html,hi') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["no_host", "not_listed"]} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.about:blank` — about:blank

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": ["no_host", "not_listed"]}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('about:blank') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["no_host", "not_listed"]} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.   ` — Whitespace-only URL

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": ["no_host", "not_listed"]}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('   ') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": ["no_host", "not_listed"]} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.study.https://xn--n3h.com` — Punycode host

- **Status:** PASS
- **Suite / category:** softland / edge
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, edge
- **Expected:** `{"action": "allow", "reason": "not_listed"}`
- **Actual:** `{"action": "allow", "reason": "not_listed", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=study | policy written | reuse | Y |
| 2 | msg_host get_mode('https://xn--n3h.com') | allow | allow/not_listed | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "not_listed"} | {"action": "allow", "reason": "not_listed"} | Y |

### `softland.fixture.free.https://pornhub.com` — NEGATIVE: porn stays blocked in FREE

- **Status:** PASS
- **Suite / category:** softland / negative
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, negative
- **Expected:** `{"action": "block", "reason": "porn"}`
- **Actual:** `{"action": "block", "reason": "porn", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | written | Y |
| 2 | msg_host get_mode('https://pornhub.com') | block | block/porn | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "porn"} | {"action": "block", "reason": "porn"} | Y |

### `softland.fixture.free.https://twitter.com` — NEGATIVE: block_extra stays blocked in FREE

- **Status:** PASS
- **Suite / category:** softland / negative
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, negative
- **Expected:** `{"action": "block", "reason": "block_extra"}`
- **Actual:** `{"action": "block", "reason": "block_extra", "mode": "free", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=free | policy written | reuse | Y |
| 2 | msg_host get_mode('https://twitter.com') | block | block/block_extra | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "block_extra"} | {"action": "block", "reason": "block_extra"} | Y |

### `softland.fixture.off.https://pornhub.com` — NEGATIVE: SoftLand OFF must allow porn (no SoftLand block)

- **Status:** PASS
- **Suite / category:** softland / negative
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, negative
- **Expected:** `{"action": "allow", "reason": "softland_off"}`
- **Actual:** `{"action": "allow", "reason": "softland_off", "mode": "free", "enforce": false}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=off | policy written | written | Y |
| 2 | msg_host get_mode('https://pornhub.com') | allow | allow/softland_off | Y |
| 3 | Compare action+reason | {"action": "allow", "reason": "softland_off"} | {"action": "allow", "reason": "softland_off"} | Y |

### `softland.fixture.incubate.https://youtube.com` — NEGATIVE: incubation overrides FREE watch

- **Status:** PASS
- **Suite / category:** softland / negative
- **Error code:** `OK` — Pass
- **Tags:** fixture, softland, negative
- **Expected:** `{"action": "block", "reason": "incubation"}`
- **Actual:** `{"action": "block", "reason": "incubation", "mode": "study", "enforce": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Set fixture SoftLand cell=incubate | policy written | written | Y |
| 2 | msg_host get_mode('https://youtube.com') | block | block/incubation | Y |
| 3 | Compare action+reason | {"action": "block", "reason": "incubation"} | {"action": "block", "reason": "incubation"} | Y |

### `arm.unit.steam.exe->['steam.exe']` — Arm match: steam.exe vs ['steam.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'steam.exe' | token | steam.exe | Y |
| 2 | Match against ['steam.exe'] | True | True | Y |

### `arm.unit.STEAM.EXE->['steam.exe']` — Arm match: STEAM.EXE vs ['steam.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'STEAM.EXE' | token | steam.exe | Y |
| 2 | Match against ['steam.exe'] | True | True | Y |

### `arm.unit.steam->['steam.exe']` — Arm match: steam vs ['steam.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'steam' | token | steam | Y |
| 2 | Match against ['steam.exe'] | True | True | Y |

### `arm.unit.steam.exe->['steam']` — Arm match: steam.exe vs ['steam']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'steam.exe' | token | steam.exe | Y |
| 2 | Match against ['steam'] | True | True | Y |

### `arm.unit.steam.exe->['C:\\Games\\Steam\\steam.exe']` — Arm match: steam.exe vs ['C:\\Games\\Steam\\steam.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'steam.exe' | token | steam.exe | Y |
| 2 | Match against ['C:\\Games\\Steam\\steam.exe'] | True | True | Y |

### `arm.unit.notepad.exe->['steam.exe']` — Arm match: notepad.exe vs ['steam.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'notepad.exe' | token | notepad.exe | Y |
| 2 | Match against ['steam.exe'] | False | False | Y |

### `arm.unit.calt_test_block_target.exe->['calt_test_block_target.exe']` — Arm match: calt_test_block_target.exe vs ['calt_test_block_target.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'calt_test_block_target.exe' | token | calt_test_block_target.exe | Y |
| 2 | Match against ['calt_test_block_target.exe'] | True | True | Y |

### `arm.unit.calt_test_safe.exe->['calt_test_block_target.exe']` — Arm match: calt_test_safe.exe vs ['calt_test_block_target.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'calt_test_safe.exe' | token | calt_test_safe.exe | Y |
| 2 | Match against ['calt_test_block_target.exe'] | False | False | Y |

### `arm.unit.explorer.exe->['explorer.exe']` — Arm match: explorer.exe vs ['explorer.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'explorer.exe' | token | explorer.exe | Y |
| 2 | Match against ['explorer.exe'] | False | False | Y |

### `arm.unit.python.exe->['python.exe']` — Arm match: python.exe vs ['python.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'python.exe' | token | python.exe | Y |
| 2 | Match against ['python.exe'] | False | False | Y |

### `arm.unit.calt_enforcer.exe->['calt_enforcer.exe']` — Arm match: calt_enforcer.exe vs ['calt_enforcer.exe']

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, unit
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize process 'calt_enforcer.exe' | token | calt_enforcer.exe | Y |
| 2 | Match against ['calt_enforcer.exe'] | False | False | Y |

### `arm.unit.extra.Mixed-case process name` — Mixed-case process name

- **Status:** PASS
- **Suite / category:** arm / edge
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, edge
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'Steam.exe' | token | steam.exe | Y |
| 2 | Match vs ['steam.exe'] | True | True | Y |

### `arm.unit.extra.Mixed-case policy token` — Mixed-case policy token

- **Status:** PASS
- **Suite / category:** arm / edge
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, edge
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'steam.exe' | token | steam.exe | Y |
| 2 | Match vs ['STEAM.EXE'] | True | True | Y |

### `arm.unit.extra.NEGATIVE: unlisted chrome must not match` — NEGATIVE: unlisted chrome must not match

- **Status:** PASS
- **Suite / category:** arm / negative
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, negative
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'chrome.exe' | token | chrome.exe | Y |
| 2 | Match vs ['steam.exe'] | False | False | Y |

### `arm.unit.extra.NEGATIVE: similar name must not fuzzy-match` — NEGATIVE: similar name must not fuzzy-match

- **Status:** PASS
- **Suite / category:** arm / negative
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, negative
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'steamwebhelper.exe' | token | steamwebhelper.exe | Y |
| 2 | Match vs ['steam.exe'] | False | False | Y |

### `arm.unit.extra.Empty process name` — Empty process name

- **Status:** PASS
- **Suite / category:** arm / edge
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, edge
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize '' | token |  | Y |
| 2 | Match vs ['steam.exe'] | False | False | Y |

### `arm.unit.extra.NEGATIVE: empty policy list never kills` — NEGATIVE: empty policy list never kills

- **Status:** PASS
- **Suite / category:** arm / negative
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, negative
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'steam.exe' | token | steam.exe | Y |
| 2 | Match vs [] | False | False | Y |

### `arm.unit.extra.Empty policy token ignored` — Empty policy token ignored

- **Status:** PASS
- **Suite / category:** arm / edge
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, edge
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'steam.exe' | token | steam.exe | Y |
| 2 | Match vs [''] | False | False | Y |

### `arm.unit.extra.NEGATIVE: protected Focus never killed` — NEGATIVE: protected Focus never killed

- **Status:** PASS
- **Suite / category:** arm / negative
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, negative
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'calt_focus.exe' | token | calt_focus.exe | Y |
| 2 | Match vs ['calt_focus.exe'] | False | False | Y |

### `arm.unit.extra.Full path process basename` — Full path process basename

- **Status:** PASS
- **Suite / category:** arm / edge
- **Error code:** `OK` — Pass
- **Tags:** arm, unit, edge
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Normalize 'C:\\Games\\steam.exe' | token | steam.exe | Y |
| 2 | Match vs ['steam.exe'] | True | True | Y |

### `sync.pre.status_vs_effective_arm` — Status armed matches effective Arm

- **Status:** PASS
- **Suite / category:** sync / positive
- **Error code:** `OK` — Pass
- **Tags:** sync
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read enforcer_status.json armed | False | False | Y |

### `sync.pre.sqlite_vs_json_arm` — SQLite Arm mirrors JSON

- **Status:** PASS
- **Suite / category:** sync / positive
- **Error code:** `OK` — Pass
- **Tags:** sync
- **Expected:** `{"json_armed": false, "json_exes": []}`
- **Actual:** `{"sql_armed": false, "sql_exes": []}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Compare enforcer_runtime vs policy JSON | match | match | Y |

### `sync.pre.sqlite_vs_json_softland` — SQLite SoftLand enabled matches JSON

- **Status:** PASS
- **Suite / category:** sync / positive
- **Error code:** `OK` — Pass
- **Tags:** sync
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Compare SoftLand enabled | False | False | Y |

### `gateway.read.status.snapshot` — Gateway status.snapshot

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Tags:** gateway, read
- **Expected:** `"ok:true"`
- **Actual:** `{"ok": true, "id": "4bc44bcb-dfd2-485b-89fa-a4e3136284fa", "gateway_seq": 3688, "as_of": "2026-09-14T00:30:46", "softland_enabled": false, "free_until": null, "incubation_until": null, "reward_day_active": false, "earned_ledger_seconds": 6000}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call status.snapshot | ok:true JSON | {"ok":true,"id":"4bc44bcb-dfd2-485b-89fa-a4e3136284fa","gateway_seq":3688,"as_of":"2026-09-14T00:30:46","softland_enabled":false,"free_until":null,"incubation_until":null,"reward_d | Y |

### `gateway.read.day.status` — Gateway day.status

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Tags:** gateway, read
- **Expected:** `"ok:true"`
- **Actual:** `{"ok": true, "id": "2171376c-c572-4e53-8f27-d939cde67f0f", "gateway_seq": 3688, "as_of": "2026-09-14T00:30:49", "softland_enabled": false, "free_until": null, "incubation_until": null, "reward_day_active": false, "earned_ledger_seconds": 6000, "qualified_days": 10, "reward_earned": 2, "reward_granted": 3, "reward_spent": 5, "reward_available": 0, "days_to_next_reward": 2, "passes_limit": 2, "passes_used": 0, "pass_today": false, "earned_today_seconds": 0, "balance_seconds": 6000}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call day.status | ok:true JSON | {"ok":true,"id":"2171376c-c572-4e53-8f27-d939cde67f0f","gateway_seq":3688,"as_of":"2026-09-14T00:30:49","softland_enabled":false,"free_until":null,"incubation_until":null,"reward_d | Y |

### `gateway.read.reward.status` — Gateway reward.status

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Tags:** gateway, read
- **Expected:** `"ok:true"`
- **Actual:** `{"ok": true, "id": "0100d0e4-6012-46e9-813e-89d3ca74bd7d", "gateway_seq": 3688, "as_of": "2026-09-14T00:30:52", "softland_enabled": false, "free_until": null, "incubation_until": null, "reward_day_active": false, "earned_ledger_seconds": 6000, "qualified_days": 10, "reward_earned": 2, "reward_granted": 3, "reward_spent": 5, "reward_available": 0, "days_to_next_reward": 2}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call reward.status | ok:true JSON | {"ok":true,"id":"0100d0e4-6012-46e9-813e-89d3ca74bd7d","gateway_seq":3688,"as_of":"2026-09-14T00:30:52","softland_enabled":false,"free_until":null,"incubation_until":null,"reward_d | Y |

### `gateway.read.day.loop_snapshot` — Gateway day.loop_snapshot

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Tags:** gateway, read
- **Expected:** `"ok:true"`
- **Actual:** `{"ok": true, "id": "c77c67dc-7d5c-427a-8391-498446c3453e", "gateway_seq": 3688, "as_of": "2026-09-14T00:30:55", "softland_enabled": false, "free_until": null, "incubation_until": null, "reward_day_active": false, "earned_ledger_seconds": 6000, "loop": {"date": "2026-09-14", "planned_minutes": 0, "tracked_productive_minutes": 0, "threshold_minutes": 0, "tasks_total": 0, "tasks_done": 0, "checkboxes_ok": true, "time_ok": false, "dual_gate_ok": false, "closeout_free_granted": false, "free_until": n`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call day.loop_snapshot | ok:true JSON | {"ok":true,"id":"c77c67dc-7d5c-427a-8391-498446c3453e","gateway_seq":3688,"as_of":"2026-09-14T00:30:55","softland_enabled":false,"free_until":null,"incubation_until":null,"reward_d | Y |

### `gateway.read.ledger.snapshot` — Gateway ledger.snapshot

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Tags:** gateway, read
- **Expected:** `"ok:true"`
- **Actual:** `{"ok": true, "id": "ac8d9a50-4126-4947-8403-5eff801a8d1c", "gateway_seq": 3688, "as_of": "2026-09-14T00:30:58", "softland_enabled": false, "free_until": null, "incubation_until": null, "reward_day_active": false, "earned_ledger_seconds": 6000, "ledger": [{"ts": "2026-09-13T15:28:24", "kind": "earn", "seconds": 1800, "note": "daily_goal", "source": "gateway"}, {"ts": "2026-09-13T15:28:22", "kind": "earn", "seconds": 900, "note": "chapter_done", "source": "gateway"}, {"ts": "2026-09-11T22:03:38", `

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call ledger.snapshot | ok:true JSON | {"ok":true,"id":"ac8d9a50-4126-4947-8403-5eff801a8d1c","gateway_seq":3688,"as_of":"2026-09-14T00:30:58","softland_enabled":false,"free_until":null,"incubation_until":null,"reward_d | Y |

### `gateway.read.device_block.status` — Gateway device_block.status

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Tags:** gateway, read
- **Expected:** `"ok:true"`
- **Actual:** `{"ok": true, "id": "87a5e9b9-8060-49de-b054-df5c729a3bc3", "gateway_seq": 3688, "as_of": "2026-09-14T00:31:01", "softland_enabled": false, "free_until": null, "incubation_until": null, "reward_day_active": false, "earned_ledger_seconds": 6000, "device_block": {"settings": {"enabled": true, "block_porn": true, "block_watch": false, "block_social": true, "source": "theporndude.com"}, "active": true, "configured_domain_count": 106, "managed_host_entries": 72, "needs_sync": true, "refresh": "idle", `

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call device_block.status | ok:true JSON | {"ok":true,"id":"87a5e9b9-8060-49de-b054-df5c729a3bc3","gateway_seq":3688,"as_of":"2026-09-14T00:31:01","softland_enabled":false,"free_until":null,"incubation_until":null,"reward_d | Y |

### `gateway.neg.arm.set.unlock` — NEGATIVE: arm.set with wrong unlock (may reject if password lock active)

- **Status:** SKIP
- **Suite / category:** gateway / negative
- **Error code:** `OK` — Pass
- **Tags:** gateway, negative, unlock
- **Detail:** lock_mode may be none — wrong unlock not enforced; skipped strict assert
- **Expected:** `"reject when password lock active"`
- **Actual:** `{"ok": true, "id": "a2ebc937-b0f0-4e19-a940-2dda769bb809", "gateway_seq": 3689, "as_of": "2026-09-14T00:31:04", "softland_enabled": false, "free_until": null, "incubation_until": null, "reward_day_active": false, "earned_ledger_seconds": 6000}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call arm.set (negative) | reject / ok:false / error |  | Y |

### `gateway.neg.softland.set_enabled.bad_payload` — NEGATIVE: softland.set_enabled missing enabled field

- **Status:** PASS
- **Suite / category:** gateway / negative
- **Error code:** `OK` — Pass
- **Tags:** gateway, negative, bad_payload
- **Expected:** `"reject / ok:false"`
- **Actual:** `{"ok": false, "id": "807c20ce-08e6-4492-a967-353417494234", "error": "bad_payload"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call softland.set_enabled (negative) | reject / ok:false / error | {"ok":false,"id":"807c20ce-08e6-4492-a967-353417494234","error":"bad_payload"} | Y |

### `gateway.neg.this.op.does.not.exist.unknown_op` — NEGATIVE: unknown gateway op

- **Status:** PASS
- **Suite / category:** gateway / negative
- **Error code:** `OK` — Pass
- **Tags:** gateway, negative, unknown_op
- **Expected:** `"reject / ok:false"`
- **Actual:** `{"ok": false, "id": "2d2caf40-7bca-45fa-9760-14a6fe5d3269", "error": "unknown_op"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call this.op.does.not.exist (negative) | reject / ok:false / error | {"ok":false,"id":"2d2caf40-7bca-45fa-9760-14a6fe5d3269","error":"unknown_op"} | Y |

### `gateway.neg.reward.claim.reward` — NEGATIVE: reward.claim when available may be 0 (reject or no-op fail)

- **Status:** PASS
- **Suite / category:** gateway / negative
- **Error code:** `OK` — Pass
- **Tags:** gateway, negative, reward
- **Expected:** `"reject / ok:false"`
- **Actual:** `{"ok": false, "id": "f4255038-c4a6-4d68-852e-25746d90454d", "error": "confirm_required"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Call reward.claim (negative) | reject / ok:false / error | {"ok":false,"id":"f4255038-c4a6-4d68-852e-25746d90454d","error":"confirm_required"} | Y |

### `gateway.info.softland_ne_arm` — INFO: SoftLand and Arm are independent switches

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Tags:** gateway, info
- **Expected:** `"independent"`
- **Actual:** `{"softland_enabled": false, "hard_block_armed": false}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read mirrors | both readable | ok | Y |

### `softland.live.https://youtube.com` — Live SoftLand probe (watch)

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** live, watch
- **Expected:** `"allow/softland_off"`
- **Actual:** `{"action": "allow", "reason": "softland_off"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read live softland_enabled | False | False | Y |
| 2 | Live get_mode('https://youtube.com') | softland_off allow | allow/softland_off | Y |

### `softland.live.https://pornhub.com` — Live SoftLand probe (porn)

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** live, porn
- **Expected:** `"allow/softland_off"`
- **Actual:** `{"action": "allow", "reason": "softland_off"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read live softland_enabled | False | False | Y |
| 2 | Live get_mode('https://pornhub.com') | softland_off allow | allow/softland_off | Y |

### `softland.live.https://meet.google.com` — Live SoftLand probe (allow)

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** live, allow
- **Expected:** `"allow/softland_off"`
- **Actual:** `{"action": "allow", "reason": "softland_off"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read live softland_enabled | False | False | Y |
| 2 | Live get_mode('https://meet.google.com') | softland_off allow | allow/softland_off | Y |

### `softland.live.https://github.com` — Live SoftLand probe (other)

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** live, other
- **Expected:** `"allow/softland_off"`
- **Actual:** `{"action": "allow", "reason": "softland_off"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read live softland_enabled | False | False | Y |
| 2 | Live get_mode('https://github.com') | softland_off allow | allow/softland_off | Y |

### `softland.live.https://twitter.com` — Live SoftLand probe (block_extra)

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** live, block_extra
- **Expected:** `"allow/softland_off"`
- **Actual:** `{"action": "allow", "reason": "softland_off"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read live softland_enabled | False | False | Y |
| 2 | Live get_mode('https://twitter.com') | softland_off allow | allow/softland_off | Y |

### `softland.live.empty` — Live SoftLand probe (empty)

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** live, empty
- **Expected:** `"allow/softland_off"`
- **Actual:** `{"action": "allow", "reason": "softland_off"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read live softland_enabled | False | False | Y |
| 2 | Live get_mode('') | softland_off allow | allow/softland_off | Y |

### `softland.live.not-a-url` — Live SoftLand probe (garbage)

- **Status:** PASS
- **Suite / category:** softland / positive
- **Error code:** `OK` — Pass
- **Tags:** live, garbage
- **Expected:** `"allow/softland_off"`
- **Actual:** `{"action": "allow", "reason": "softland_off"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read live softland_enabled | False | False | Y |
| 2 | Live get_mode('not-a-url') | softland_off allow | allow/softland_off | Y |

### `arm.live.set_fixture_list` — Arm live: set disposable kill list

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, live
- **Expected:** `"arm.set ok"`
- **Actual:** `"{\"ok\":true,\"id\":\"83ba57fc-10ad-4348-a4df-e10dd75adff1\",\"gateway_seq\":3690,\"as_of\":\"2026-09-14T00:31:18\",\"softland_enabled\":false,\"free_until\":null,\"incubation_until\":null,\"reward_day_active\":false,\"earned_ledger_seconds\":6000}"`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | gateway arm.set fixture list + Arm ON | ok | {"ok":true,"id":"83ba57fc-10ad-4348-a4df-e10dd75adff1","gateway_seq":3690,"as_of":"2026-09-14T00:31:18","softland_enabled":false,"free_until":null,"incubation_until":null,"reward_day_active":false,"ea | Y |

### `arm.live.safe_not_killed` — NEGATIVE: unlisted safe EXE must survive Arm

- **Status:** PASS
- **Suite / category:** arm / negative
- **Error code:** `OK` — Pass
- **Tags:** arm, live, negative
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Launch calt_test_safe.exe | alive | True | Y |
| 2 | Wait enforcer tick | not killed | alive | Y |

### `arm.live.block_target_killed` — Arm ON kills listed fixture target

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, live
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Launch calt_test_block_target.exe | listed | launched | Y |
| 2 | Wait enforcer tick | killed | killed | Y |

### `arm.live.disarm` — Arm live: disarm (clear lock_mode)

- **Status:** PASS
- **Suite / category:** arm / positive
- **Error code:** `OK` — Pass
- **Tags:** arm, live
- **Expected:** `"ok"`
- **Actual:** `"{\"ok\":true,\"id\":\"4299445b-a90b-4bf9-aeda-ebbf98a14db0\",\"gateway_seq\":3691,\"as_of\":\"2026-09-14T00:31:26\",\"softland_enabled\":false,\"free_until\":null,\"incubation_until\":null,\"reward_day_active\":false,\"ea"`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | arm.set hard_block_armed=false lock_mode=none | ok | {"ok":true,"id":"4299445b-a90b-4bf9-aeda-ebbf98a14db0","gateway_seq":3691,"as_of":"2026-09-14T00:31:26","softland_enable | Y |

### `arm.live.disarmed_no_kill` — NEGATIVE: Arm OFF must not kill listed EXE

- **Status:** PASS
- **Suite / category:** arm / negative
- **Error code:** `OK` — Pass
- **Tags:** arm, live, negative
- **Expected:** `true`
- **Actual:** `true`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Disarm | disarmed | ok | Y |
| 2 | Respawn listed target | stays alive | True | Y |

### `arm.live.wrong_password_no_disarm` — NEGATIVE: wrong unlock password must not disarm

- **Status:** PASS
- **Suite / category:** arm / negative
- **Error code:** `OK` — Pass
- **Tags:** arm, live, negative, unlock
- **Expected:** `"reject or stay armed"`
- **Actual:** `{"gateway_ok": true, "out": "{\"ok\":false,\"id\":\"9c779846-7c14-463c-9b4f-5333d60e6e91\",\"error\":\"unlock_failed\"}", "hard_block_armed": true}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Arm ON with lock_mode=password | armed | armed | Y |
| 2 | arm.set disarm with wrong provided_unlock | reject/stay armed | ok=True armed=True | Y |

### `ui.route._` — UI home (index.html)

- **Status:** PASS
- **Suite / category:** ui / positive
- **Error code:** `OK` — Pass
- **Tags:** ui, smoke
- **Expected:** `"200 html shell"`
- **Actual:** `{"status": 200, "sample": "\n  <!DOCTYPE html>\n  <html lang=\"en\">\n    <head>\n      <meta charset=\"UTF-8\" />\n      <meta name=\"viewport\" content=\"wid"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | HTTP GET http://127.0.0.1:4177/ | 200 + html | status=200 bytes~532 | Y |
| 2 | Note target hash route / | reachable via SPA | / | Y |

**Screenshots:**
- `C:\Users\Lenovo\Desktop\Cognitive-Aware Learning Tutor\docs\superpowers\exports\focus-qa-artifacts\screenshots\ui.route.__pass.png`

![ui.route._](focus-qa-artifacts/screenshots/ui.route.__pass.png)

### `ui.route._#_productivity_tab_home` — UI productivity home hash

- **Status:** PASS
- **Suite / category:** ui / positive
- **Error code:** `OK` — Pass
- **Tags:** ui, smoke
- **Expected:** `"200 html shell"`
- **Actual:** `{"status": 200, "sample": "\n  <!DOCTYPE html>\n  <html lang=\"en\">\n    <head>\n      <meta charset=\"UTF-8\" />\n      <meta name=\"viewport\" content=\"wid"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | HTTP GET http://127.0.0.1:4177/ | 200 + html | status=200 bytes~532 | Y |
| 2 | Note target hash route /#/productivity?tab=home | reachable via SPA | /#/productivity?tab=home | Y |

### `ui.route._#_productivity_tab_settings` — UI settings hash

- **Status:** PASS
- **Suite / category:** ui / positive
- **Error code:** `OK` — Pass
- **Tags:** ui, smoke
- **Expected:** `"200 html shell"`
- **Actual:** `{"status": 200, "sample": "\n  <!DOCTYPE html>\n  <html lang=\"en\">\n    <head>\n      <meta charset=\"UTF-8\" />\n      <meta name=\"viewport\" content=\"wid"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | HTTP GET http://127.0.0.1:4177/ | 200 + html | status=200 bytes~532 | Y |
| 2 | Note target hash route /#/productivity?tab=settings | reachable via SPA | /#/productivity?tab=settings | Y |

**Screenshots:**
- `C:\Users\Lenovo\Desktop\Cognitive-Aware Learning Tutor\docs\superpowers\exports\focus-qa-artifacts\screenshots\ui.route.___productivity_tab_settings_pass.png`

![ui.route._#_productivity_tab_settings](focus-qa-artifacts/screenshots/ui.route.___productivity_tab_settings_pass.png)

### `ui.route._#_productivity_tab_blocker` — UI blocker hash

- **Status:** PASS
- **Suite / category:** ui / positive
- **Error code:** `OK` — Pass
- **Tags:** ui, smoke
- **Expected:** `"200 html shell"`
- **Actual:** `{"status": 200, "sample": "\n  <!DOCTYPE html>\n  <html lang=\"en\">\n    <head>\n      <meta charset=\"UTF-8\" />\n      <meta name=\"viewport\" content=\"wid"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | HTTP GET http://127.0.0.1:4177/ | 200 + html | status=200 bytes~532 | Y |
| 2 | Note target hash route /#/productivity?tab=blocker | reachable via SPA | /#/productivity?tab=blocker | Y |

**Screenshots:**
- `C:\Users\Lenovo\Desktop\Cognitive-Aware Learning Tutor\docs\superpowers\exports\focus-qa-artifacts\screenshots\ui.route.___productivity_tab_blocker_pass.png`

![ui.route._#_productivity_tab_blocker](focus-qa-artifacts/screenshots/ui.route.___productivity_tab_blocker_pass.png)

### `ui.route._#_productivity_tab_focus` — UI focus hash

- **Status:** PASS
- **Suite / category:** ui / positive
- **Error code:** `OK` — Pass
- **Tags:** ui, smoke
- **Expected:** `"200 html shell"`
- **Actual:** `{"status": 200, "sample": "\n  <!DOCTYPE html>\n  <html lang=\"en\">\n    <head>\n      <meta charset=\"UTF-8\" />\n      <meta name=\"viewport\" content=\"wid"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | HTTP GET http://127.0.0.1:4177/ | 200 + html | status=200 bytes~532 | Y |
| 2 | Note target hash route /#/productivity?tab=focus | reachable via SPA | /#/productivity?tab=focus | Y |

### `ui.route._#_journal` — UI journal hash

- **Status:** PASS
- **Suite / category:** ui / positive
- **Error code:** `OK` — Pass
- **Tags:** ui, smoke
- **Expected:** `"200 html shell"`
- **Actual:** `{"status": 200, "sample": "\n  <!DOCTYPE html>\n  <html lang=\"en\">\n    <head>\n      <meta charset=\"UTF-8\" />\n      <meta name=\"viewport\" content=\"wid"}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | HTTP GET http://127.0.0.1:4177/ | 200 + html | status=200 bytes~532 | Y |
| 2 | Note target hash route /#/journal | reachable via SPA | /#/journal | Y |

### `ui.neg.missing_asset_404` — NEGATIVE: missing static asset returns 404

- **Status:** PASS
- **Suite / category:** ui / negative
- **Error code:** `OK` — Pass
- **Tags:** ui, negative
- **Expected:** `"404"`
- **Actual:** `"404"`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | GET http://127.0.0.1:4177/this-asset-should-not-exist-focus-qa.js | 404 | 404 | Y |

### `restore.snapshot` — Restore SoftLand/Arm snapshot

- **Status:** PASS
- **Suite / category:** gateway / positive
- **Error code:** `OK` — Pass
- **Detail:** SoftLand/Arm snapshot restored
- **Expected:** `"restored"`
- **Actual:** `"ok"`

### `sync.post.status_vs_effective_arm` — Status armed matches effective Arm

- **Status:** PASS
- **Suite / category:** sync / positive
- **Error code:** `OK` — Pass
- **Tags:** sync
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Read enforcer_status.json armed | False | False | Y |

### `sync.post.sqlite_vs_json_arm` — SQLite Arm mirrors JSON

- **Status:** PASS
- **Suite / category:** sync / positive
- **Error code:** `OK` — Pass
- **Tags:** sync
- **Expected:** `{"json_armed": false, "json_exes": []}`
- **Actual:** `{"sql_armed": false, "sql_exes": []}`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Compare enforcer_runtime vs policy JSON | match | match | Y |

### `sync.post.sqlite_vs_json_softland` — SQLite SoftLand enabled matches JSON

- **Status:** PASS
- **Suite / category:** sync / positive
- **Error code:** `OK` — Pass
- **Tags:** sync
- **Expected:** `false`
- **Actual:** `false`

| # | Step | Expected | Actual | OK |
|---|------|----------|--------|----|
| 1 | Compare SoftLand enabled | False | False | Y |

