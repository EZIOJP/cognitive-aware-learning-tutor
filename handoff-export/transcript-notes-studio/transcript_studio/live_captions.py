"""Live Captions capture — backend engine with Studio GUI conveniences."""

from __future__ import annotations

import platform
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.transcripts.live_captions import (
    LiveCaptionsScraper as _BackendLiveCaptionsScraper,
    extract_caption_delta,
    ensure_windows as _backend_ensure_windows,
)

from transcript_studio.paths import transcripts_dir

__all__ = [
    "LiveCaptionsScraper",
    "check_captions_deps",
    "ensure_windows",
    "extract_caption_delta",
]


def ensure_windows() -> None:
    if platform.system() != "Windows":
        raise OSError("Live Captions scraping only works on Windows 11.")


def check_captions_deps() -> tuple[bool, str]:
    if platform.system() != "Windows":
        return False, "Windows 11 required for Live Captions."
    try:
        import pywinauto  # noqa: F401

        return True, "pywinauto installed — enable captions with Win+Ctrl+L"
    except ImportError:
        return False, "Install captions extras: pip install -r backend/requirements-captions.txt"


class LiveCaptionsScraper(_BackendLiveCaptionsScraper):
    """Backend scraper with stop-event and configurable output directory."""

    def run(
        self,
        *,
        max_seconds: float | None = None,
        stop_event: threading.Event | None = None,
    ) -> list[str]:
        if stop_event is None:
            return super().run(max_seconds=max_seconds)

        text_block = self._connect_uia()
        deadline = time.monotonic() + max_seconds if max_seconds else None

        while True:
            if stop_event.is_set():
                break
            if deadline is not None and time.monotonic() >= deadline:
                break
            try:
                self.poll_once(text_block)
            except Exception:
                break
            time.sleep(self.poll_interval)

        return self.segments

    def save(self, path: Path | None = None, *, output_dir: Path | None = None) -> Path:
        root = output_dir or transcripts_dir()
        root.mkdir(parents=True, exist_ok=True)
        if path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = root / f"live_captions_{stamp}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.segments), encoding="utf-8")
        return path
