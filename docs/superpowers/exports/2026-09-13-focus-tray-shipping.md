# Focus shipping — tray + control door (2026-09-13)

## Problem
No visible tray menu on Win11 → no Reload UI / Quit / Settings from the system tray.

## Root cause
Tray was bound to an `HWND_MESSAGE` window. Win11 often fails `Shell_NotifyIcon` there, so `added_` stayed false and balloons/menus never appeared. Icons may also sit in the overflow (^).

## Fixes shipped
1. **Tray on main window HWND** + retry add + `TaskbarCreated` re-add + VERSION_4 select/context handlers
2. **Startup balloon** explaining Win11 ^ overflow
3. **In-app Focus menu** (top bar •••): Reload UI, Settings, Show tray menu, Find tray icon, Quit — works even if the tray icon is hidden
4. Rebuilt `calt_focus.exe` → installer payload + `dist-focus`

## What you should see
1. Teal CALT Focus icon near the clock (or under ^ — pin it)
2. Right-click tray → Open Focus / Settings / Reload UI / Quit
3. Top bar **Focus** menu as backup

## SoftLand ≠ Arm (unchanged)
SoftLand = sites. Arm = OS kills. SoftLand ON ≠ Armed.

## Smoke
- Enforcer running; Focus relaunched from rebuilt binary
- `npm run build:focus` green
- Native focus build green
