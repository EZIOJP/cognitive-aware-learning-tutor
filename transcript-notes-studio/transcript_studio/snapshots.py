"""Slide screenshots during capture sessions — serial + timestamp, marker merge."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

SNAPSHOT_MARKER_RE = re.compile(r"^\[SNAPSHOT\s+(\d+)\]\s*$", re.MULTILINE)


@dataclass
class SlideCapture:
    index: int
    elapsed_sec: float
    path: Path
    captured_at: str


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class CaptureSession:
    """Screenshots linked to a lecture session (e.g. during Whisper)."""

    session_dir: Path
    captures: list[SlideCapture] = field(default_factory=list)
    _start_mono: float | None = None
    _stop_timer: threading.Event = field(default_factory=threading.Event)
    _timer_thread: threading.Thread | None = None

    @property
    def snapshots_dir(self) -> Path:
        d = self.session_dir / "snapshots"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @classmethod
    def create(cls, base_dir: Path, stem: str) -> CaptureSession:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in stem)[:40]
        session_dir = base_dir / f"{safe}_{stamp}"
        session_dir.mkdir(parents=True, exist_ok=True)
        (session_dir / "snapshots").mkdir(exist_ok=True)
        return cls(session_dir=session_dir)

    def start(self) -> None:
        self._start_mono = time.monotonic()

    def elapsed(self) -> float:
        if self._start_mono is None:
            return 0.0
        return time.monotonic() - self._start_mono

    def capture_now(self) -> SlideCapture:
        if self._start_mono is None:
            self.start()
        index = len(self.captures) + 1
        elapsed = self.elapsed()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"{index:03d}_{stamp}.png"
        path = self.snapshots_dir / filename
        _grab_screen(path)
        # Stable alias for markdown injection
        alias = self.snapshots_dir / f"{index}.png"
        if alias != path:
            alias.write_bytes(path.read_bytes())
        cap = SlideCapture(
            index=index,
            elapsed_sec=elapsed,
            path=path,
            captured_at=stamp,
        )
        self.captures.append(cap)
        return cap

    def start_auto_capture(self, interval_sec: float, on_capture: Callable[[SlideCapture], None] | None = None) -> None:
        if interval_sec <= 0:
            return
        self._stop_timer.clear()

        def loop() -> None:
            while not self._stop_timer.wait(interval_sec):
                try:
                    cap = self.capture_now()
                    if on_capture:
                        on_capture(cap)
                except Exception:
                    break

        self._timer_thread = threading.Thread(target=loop, daemon=True)
        self._timer_thread.start()

    def stop_auto_capture(self) -> None:
        self._stop_timer.set()

    def manifest_path(self) -> Path:
        return self.session_dir / "slides_manifest.txt"

    def write_manifest(self) -> None:
        lines = ["# slide_index elapsed_sec filename captured_at", ""]
        for c in self.captures:
            lines.append(f"{c.index}\t{c.elapsed_sec:.2f}\t{c.path.name}\t{c.captured_at}")
        self.manifest_path().write_text("\n".join(lines) + "\n", encoding="utf-8")


def _grab_screen(path: Path) -> None:
    try:
        from PIL import ImageGrab

        img = ImageGrab.grab()
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path, format="PNG")
        return
    except ImportError:
        pass
    try:
        import mss
        import mss.tools

        with mss.mss() as sct:
            monitor = sct.monitors[0]
            shot = sct.grab(monitor)
            mss.tools.to_png(shot.rgb, shot.size, output=str(path))
        return
    except ImportError as exc:
        raise RuntimeError(
            "Screenshot needs Pillow or mss: pip install Pillow"
        ) from exc


def merge_slides_into_transcript(
    text: str,
    segments: list[TranscriptSegment],
    captures: list[SlideCapture],
) -> str:
    """Insert [SNAPSHOT n] markers after the segment nearest each capture time."""
    if not captures:
        return text
    if not segments:
        lines = [text.rstrip(), ""]
        for c in captures:
            lines.append(f"[SNAPSHOT {c.index}]")
        return "\n".join(lines).strip() + "\n"

    # Build segment-ordered parts with markers after matching segments
    markers_after: dict[int, list[int]] = {}
    for cap in captures:
        best_i = 0
        best_dist = float("inf")
        for i, seg in enumerate(segments):
            mid = (seg.start + seg.end) / 2
            dist = abs(mid - cap.elapsed_sec)
            if dist < best_dist:
                best_dist = dist
                best_i = i
        markers_after.setdefault(best_i, []).append(cap.index)

    parts: list[str] = []
    for i, seg in enumerate(segments):
        parts.append(seg.text.strip())
        for n in sorted(markers_after.get(i, [])):
            parts.append(f"\n[SNAPSHOT {n}]\n")
    # Captures after last segment
    tail = markers_after.get(len(segments), [])
    for n in sorted(tail):
        parts.append(f"\n[SNAPSHOT {n}]\n")
    return " ".join(p for p in parts if p).strip() + "\n"


def inject_snapshot_images(
    raw: str,
    snapshots_dir: Path,
    *,
    note_path: Path,
) -> str:
    """Replace [SNAPSHOT N] with markdown images using paths relative to the note file."""

    def repl(match: re.Match[str]) -> str:
        n = int(match.group(1))
        img = snapshots_dir / f"{n}.png"
        if not img.is_file():
            matches = list(snapshots_dir.glob(f"{n:03d}_*.png"))
            img = matches[0] if matches else img
        if not img.is_file():
            return f"\n*[Slide {n} — image missing]*\n"
        try:
            rel = img.resolve().relative_to(note_path.parent.resolve()).as_posix()
        except ValueError:
            rel = img.as_posix()
        return f"\n![Slide {n}]({rel})\n"

    return SNAPSHOT_MARKER_RE.sub(repl, raw)
