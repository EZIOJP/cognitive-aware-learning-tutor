"""Capture Windows Live Captions text via UI Automation (pywinauto)."""

from __future__ import annotations

import platform
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from backend.paths import TRANSCRIPTS_DIR
from backend.transcripts.cleanup import normalize_segment
CAPTIONS_EXE = "LiveCaptions.exe"
CAPTIONS_AUTO_ID = "CaptionsTextBlock"


def _split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _longest_line_overlap(prev_lines: list[str], curr_lines: list[str]) -> int:
    best = 0
    for i in range(1, min(len(prev_lines), len(curr_lines)) + 1):
        if prev_lines[-i:] == curr_lines[:i]:
            best = i
    return best


def extract_caption_delta(previous: str, current: str) -> str | None:
    """Return newly spoken text when Live Captions updates its text block."""
    previous = previous.strip()
    current = current.strip()
    if not current:
        return None
    if current == previous:
        return None
    if previous and current.startswith(previous):
        delta = current[len(previous) :].strip()
        return delta or None

    prev_lines = _split_lines(previous)
    curr_lines = _split_lines(current)
    if not prev_lines:
        return current
    if not curr_lines:
        return None

    overlap = _longest_line_overlap(prev_lines, curr_lines)
    if overlap > 0:
        new_lines = curr_lines[overlap:]
        return "\n".join(new_lines) if new_lines else None

    last_prev, first_curr = prev_lines[-1], curr_lines[0]
    if first_curr.startswith(last_prev) and len(first_curr) > len(last_prev):
        remainder = first_curr[len(last_prev) :].strip()
        parts = ([remainder] if remainder else []) + curr_lines[1:]
        return "\n".join(parts) if parts else None

    prev_set = set(prev_lines)
    new_only = [ln for ln in curr_lines if ln not in prev_set]
    return "\n".join(new_only) if new_only else None


@dataclass
class LiveCaptionsScraper:
    """Poll Windows Live Captions and accumulate transcript lines."""

    poll_interval: float = 0.5
    method: Literal["uia", "ocr"] = "uia"
    on_segment: Callable[[str], None] | None = None
    segments: list[str] = field(default_factory=list)
    _last_block: str = ""

    def _connect_uia(self):
        if platform.system() != "Windows":
            raise OSError("Live Captions scraping requires Windows.")

        try:
            from pywinauto.application import Application
        except ImportError as exc:
            raise ImportError(
                "pywinauto is required. Install with: pip install -r backend/requirements-captions.txt"
            ) from exc

        app = Application(backend="uia").connect(path=CAPTIONS_EXE)
        window = app.top_window()
        try:
            return window.child_window(auto_id=CAPTIONS_AUTO_ID, control_type="Text")
        except Exception:
            texts = window.descendants(control_type="Text")
            if not texts:
                raise RuntimeError(
                    "Could not find CaptionsTextBlock. Start Live Captions with Win+Ctrl+L."
                )
            return texts[0]

    def _read_uia(self, text_block) -> str:
        return (text_block.window_text() or "").strip()

    def _read_ocr(self, text_block) -> str:
        try:
            import pytesseract
            from PIL import ImageGrab
        except ImportError as exc:
            raise ImportError(
                "OCR fallback needs pytesseract and Pillow. "
                "Install Tesseract OCR and: pip install pytesseract"
            ) from exc

        rect = text_block.rectangle()
        image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
        return (pytesseract.image_to_string(image) or "").strip()

    def _record(self, segment: str) -> None:
        segment = normalize_segment(segment)
        if not segment:
            return
        self.segments.append(segment)
        if self.on_segment:
            self.on_segment(segment)

    def poll_once(self, text_block) -> bool:
        """Read current caption block; append delta if changed. Returns True if new text."""
        reader = self._read_ocr if self.method == "ocr" else self._read_uia
        current = reader(text_block)
        delta = extract_caption_delta(self._last_block, current)
        if delta is None:
            return False
        self._last_block = current
        self._record(delta)
        return True

    def run(self, *, max_seconds: float | None = None) -> list[str]:
        """Block until KeyboardInterrupt, max_seconds, or repeated connection loss."""
        text_block = self._connect_uia()
        deadline = time.monotonic() + max_seconds if max_seconds else None
        last_heartbeat = time.monotonic()
        failures = 0

        while True:
            if deadline is not None and time.monotonic() >= deadline:
                break
            try:
                if self.poll_once(text_block):
                    failures = 0
            except Exception as exc:
                failures += 1
                if failures >= 3:
                    print(f"\nReconnecting to Live Captions ({exc})…", file=sys.stderr, flush=True)
                    try:
                        text_block = self._connect_uia()
                        failures = 0
                        print("Reconnected.", flush=True)
                        continue
                    except Exception as reconnect_exc:
                        print(f"Reconnect failed: {reconnect_exc}", file=sys.stderr)
                        break
                time.sleep(min(2.0, self.poll_interval * 4))
                continue

            now = time.monotonic()
            if now - last_heartbeat >= 60.0:
                print(
                    f"… still listening ({len(self.segments)} segments) — Ctrl+C to stop",
                    flush=True,
                )
                last_heartbeat = now

            time.sleep(self.poll_interval)

        return self.segments

    def save(self, path: Path | None = None) -> Path:
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        if path is None:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = TRANSCRIPTS_DIR / f"live_captions_{stamp}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self.segments), encoding="utf-8")
        return path


def ensure_windows() -> None:
    if platform.system() != "Windows":
        print("Live Captions scraping only works on Windows 11.", file=sys.stderr)
        sys.exit(1)
