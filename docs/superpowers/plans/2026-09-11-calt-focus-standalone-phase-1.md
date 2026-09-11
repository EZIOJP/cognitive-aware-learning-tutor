# Phase 1 — Live Settings hub + enforcer-unreachable gate

> **For agentic workers:** Follow checkbox steps. Spec: [2026-09-11 standalone design](../specs/2026-09-11-calt-focus-standalone-productivity-design.md) Phase 1.

**Goal:** SoftLand ON/OFF, Arm, site rules, schedules write via enforcer gateway; Settings is the live hub (not Make); hard-block if pipe down.

**Done in this landing:**
- [x] Restore `ProductivitySettingsHub` + `ProductivitySettingsTab` from last live commit (decision 6C)
- [x] `EnforcerWriteGate` probes `status.snapshot`; locks writes when down/unknown/no bridge (decision 3A)
- [x] `spend_free` / day-pass remain deferred to Phase 2 (changelog #1)

**Remaining smoke (owner):**
- [ ] Toggle SoftLand/Arm/rules/schedules in Focus with Study `:8000` killed
- [ ] Confirm Network tab has no SoftLand HTTP mutators
- [ ] Kill enforcer → Settings shows banner and controls are non-interactive
- [ ] Rebuild `calt_focus` so `open_external` Study link uses ShellExecute

**Not in Phase 1 exit:** spend_free, day-pass opening sites.
