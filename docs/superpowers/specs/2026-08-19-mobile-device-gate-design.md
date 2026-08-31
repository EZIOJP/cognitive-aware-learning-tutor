# CALT Device Gate — low-tech design (2026-08-19)

Personal phone/tablet lock that matches the **PC distraction gate**:  
**no distraction until today’s productivity is done.** Not a second CALT study app.

**Status:** Design only. **NEXT PLAN:** Android Device Gate (Flutter + native). **THEN:** iOS/iPad. Do not start until the owner reopens this lane.  
**PC CALT** (study + tracker + Edge gate) stays the finished product. This is a **companion**.

---

## One-sentence product

Until the PC says the day is unlocked, distraction apps stay blocked; porn stays blocked even after unlock; everything else may get a short rest window.

---

## Who decides vs who enforces

| Role | Where | Job |
|------|--------|-----|
| Clock | PC FastAPI + desktop tracker | Bible / plan / productive minutes → **unlocked** |
| Face | Flutter app | Show minutes left, poll PC, 5‑min rest button |
| Hands | Native OS code | Actually cover/shield apps + optional DNS for porn |

Phones **do not** invent the daily goal. They read `day-status` and obey.

Existing signal (already on `GET /api/behavior/day-status` schema 3):

- `hard_block.unlocked` / `day_unlimited`
- `hard_block.productive_minutes` vs `daily_goal_minutes` / `remaining_minutes`
- `morning.bible_done` / `plan_confirmed`
- `browser_mode` (`bible` | `planning` | `study` | `free`)

Device Gate adds a **derived flag** (same endpoint, later): `device_gate.unlocked`  
= PC already treats the day as open for distraction (same meaning as gate unlock / free mode / goal met — **one definition, documented in code when implemented**).

---

## Stack (low-tech)

```text
PC CALT (:8000 or hub :8765)
        │  poll ~30s  JWT or wearable key
        ▼
Flutter UI  ── MethodChannel ──► Android Kotlin
                            └──► iOS Swift (later)
```

- **Flutter** = screens only. No blocking in Dart.
- **Android** = Accessibility overlay + optional local VPN/DNS. Sideload APK. Not Play Store.
- **iOS / iPad** = Family Controls / Screen Time shields + DNS profile. TestFlight. Weaker than Android.
- **Reach PC:** same Wi‑Fi **or** Tailscale. If unreachable → **fail closed** (keep last known lock; do not unlock).

Expo `packages/calt-android-tracker` stays a **checklist**. Device Gate is a **new** package (e.g. `packages/calt-device-gate`). Do not pretend Expo Go can overlay YouTube.

---

## Two lists

**Porn (hard)**  
Hosts + known apps. Never a 5‑min window. Never productive minutes. DNS/VPN is the backstop; overlay is the app backstop.

**Distraction (until unlock)**  
YouTube, Instagram, games, short-video, idle browsers — owner-editable package/bundle IDs.  
Until `device_gate.unlocked`: overlay/shield.  
After unlock: optional **one 5‑minute allow**, then block again (cooldown). Porn still hard.

Productive phone use (Maps, CALT itself, maybe Kindle) is **allow-listed** so the overlay does not trap the user.

---

## Flutter screens (keep tiny)

1. **Today** — unlocked? minutes remaining? last poll time?  
2. **Permissions** — Accessibility / Family Controls / DNS one-time setup  
3. **Lists** — porn vs distraction vs allow (local JSON + later sync from PC policy)  
4. **Rest** — “5 minutes” only when unlocked and not porn  

No lecture notes, no quiz, no Life Tracker on the phone.

---

## Native jobs

**Android**

- Foreground package via UsageStats  
- If porn package → overlay immediately, no timer  
- If distraction and not unlocked → overlay  
- If unlocked and user tapped 5‑min → allow that package until timer ends  
- Optional VpnService: sinkhole porn domains  

**iOS / iPad**

- ManagedSettings shield on distraction category/apps while locked  
- Web content / DNS for porn  
- Cannot overlay other apps like Android; accept Apple’s shield UX  
- 5‑min rest ≈ Apple “ask for more time” or a DeviceActivity interval — document which when building  

---

## Out of scope (do not fake)

- Same tightness as Edge + Windows hosts on iPad Safari  
- Play Store / App Store as a public product  
- Phone as source of productive minutes for v1 (PC clock only)  
- Killing apps from Flutter without plugins  
- Watch as enforcer (Zepp stays health dump + glance)

---

## Done when

**v1 (Android) — NEXT PLAN:** distraction apps cannot stay in front until PC unlocked; porn hard; 5‑min rest after unlock; works on owner’s phone on LAN or Tailscale.

**v2 (iOS/iPad) — NEXT PLAN after Android v1:** same *rule*, Apple-limited *force*.

**Not done:** “Flutter-only blocking.”

---

## Related

- PC gate: `docs/PRODUCTIVITY_SYSTEM.md`  
- Current phone glance: `docs/superpowers/specs/2026-08-04-amazfit-android-tracker-bridge-design.md`  
- Plan: `docs/superpowers/plans/2026-08-19-mobile-device-gate.md`
