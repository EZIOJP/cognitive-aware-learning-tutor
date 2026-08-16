# Admin-only tracker controls

These scripts **require** `TRACKER_EXIT_PIN` (or the default phrase `I AM DONE TRACKING`) before they stop or restart the desktop tracker. That stops casual bypass of game hard-block via `.bat` kill.

| Script | Purpose |
|--------|---------|
| `stop_desktop_tracker.bat` | Stop tracker (PIN) |
| `restart_desktop_tracker.bat` | Stop + start tray tracker (PIN) |

Legitimate full uninstall (also PIN-gated):

```bat
scripts\uninstall_tracker_persistence.bat
```

Set PIN in `.env`:

```bat
TRACKER_EXIT_PIN=your-secret
TRACKER_PERSIST_PROTECT=1
```

Tray **Confirm exit…** uses the same secret. Closing lock/rules windows does **not** quit the tracker.
