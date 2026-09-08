"""PlatformIO pre-script: create src/secrets.h from example if missing."""

Import("env")  # type: ignore  # noqa: F821 — PlatformIO injects Import
from pathlib import Path

src = Path(env["PROJECT_SRC_DIR"])  # type: ignore  # noqa: F821
dst = src / "secrets.h"
example = src / "secrets.h.example"
if not dst.exists():
    if not example.exists():
        # Fallback: repo-root example (older layout)
        root_ex = Path(env["PROJECT_DIR"]) / "secrets.h.example"  # type: ignore
        if root_ex.exists():
            example = root_ex
    if example.exists():
        dst.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[eeg] created {dst} from {example.name} — edit WiFi + UDP_TARGET_IP")
    else:
        print("[eeg] WARNING: no secrets.h.example found; build may fail")
